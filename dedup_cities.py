import psycopg2
import os
import sys
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=os.getenv('PGDATABASE'),
            user=os.getenv('PGUSER'),
            password=os.getenv('PGPASSWORD'),
            host=os.getenv('PGHOST'),
            port=int(os.getenv('PGPORT', '5432'))
        )
        return conn
    except Exception as e:
        print(f'Error connecting to database: {e}', file=sys.stderr)
        sys.exit(1)


def dedup_cities(conn, dry_run=True):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT name FROM cities
            GROUP BY name
            HAVING COUNT(*) > 1
            ORDER BY name
        """)
        dup_names = [row[0] for row in cur.fetchall()]

        if not dup_names:
            print('No duplicate cities found.')
            return

        print(f'Found {len(dup_names)} city names with duplicates.\n')

        cities_deleted = 0
        streets_reassigned = 0
        addresses_reassigned = 0
        addresses_deleted = 0

        for name in dup_names:
            cur.execute("""
                SELECT id, name, province_code, istat_code
                FROM cities
                WHERE name = %s
                ORDER BY id
            """, (name,))
            rows = cur.fetchall()

            ranked = sorted(rows, key=lambda r: (
                0 if r[2] is not None else 1,
                0 if r[3] is not None else 1,
                r[0]
            ))

            best = ranked[0]
            to_delete = [r[0] for r in ranked[1:]]

            if dry_run:
                for bad_id in to_delete:
                    cur.execute("SELECT COUNT(*) FROM streets WHERE city_id = %s", (bad_id,))
                    street_count = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM addresses WHERE city_id = %s", (bad_id,))
                    addr_count = cur.fetchone()[0]

                    print(f'  [{name}] city_id={bad_id} -> keep city_id={best[0]} '
                          f'({street_count} streets, {addr_count} addresses to repoint)')
                continue

            for bad_id in to_delete:
                # Step 1: Handle conflicting streets (same name exists in target city)
                cur.execute("""
                    SELECT s.id, s.name FROM streets s
                    WHERE s.city_id = %s
                    AND EXISTS (
                        SELECT 1 FROM streets s2
                        WHERE s2.name = s.name AND s2.city_id = %s
                    )
                """, (bad_id, best[0]))
                for s_id, s_name in cur.fetchall():
                    cur.execute("SELECT id FROM streets WHERE name = %s AND city_id = %s",
                                (s_name, best[0]))
                    target_street_id = cur.fetchone()[0]

                    cur.execute("""
                        UPDATE addresses SET street_id = %s, city_id = %s
                        WHERE street_id = %s AND city_id = %s
                        AND NOT EXISTS (
                            SELECT 1 FROM addresses a2
                            WHERE a2.street_id = %s
                              AND a2.house_number = addresses.house_number
                              AND a2.city_id = %s
                        )
                    """, (target_street_id, best[0], s_id, bad_id, target_street_id, best[0]))
                    addresses_reassigned += cur.rowcount

                    cur.execute("SELECT COUNT(*) FROM addresses WHERE street_id = %s", (s_id,))
                    remaining = cur.fetchone()[0]
                    if remaining:
                        cur.execute("DELETE FROM addresses WHERE street_id = %s", (s_id,))
                        addresses_deleted += cur.rowcount

                    cur.execute("DELETE FROM streets WHERE id = %s", (s_id,))
                    streets_reassigned += 1

                # Step 2: Repoint non-conflicting streets to the target city
                cur.execute("""
                    UPDATE streets SET city_id = %s
                    WHERE city_id = %s
                    AND NOT EXISTS (
                        SELECT 1 FROM streets s2
                        WHERE s2.name = streets.name AND s2.city_id = %s
                    )
                """, (best[0], bad_id, best[0]))
                streets_reassigned += cur.rowcount

                # Step 3: Repoint remaining addresses, delete conflicts
                cur.execute("""
                    UPDATE addresses SET city_id = %s
                    WHERE city_id = %s
                    AND NOT EXISTS (
                        SELECT 1 FROM addresses a2
                        WHERE a2.street_id = addresses.street_id
                          AND a2.house_number = addresses.house_number
                          AND a2.city_id = %s
                    )
                """, (best[0], bad_id, best[0]))
                addresses_reassigned += cur.rowcount

                cur.execute("SELECT COUNT(*) FROM addresses WHERE city_id = %s", (bad_id,))
                remaining = cur.fetchone()[0]
                if remaining:
                    cur.execute("DELETE FROM addresses WHERE city_id = %s", (bad_id,))
                    addresses_deleted += remaining

                # Step 4: Final sweep — delete leftover streets, then the city
                cur.execute("DELETE FROM streets WHERE city_id = %s", (bad_id,))
                cur.execute("DELETE FROM cities WHERE id = %s", (bad_id,))
                cities_deleted += 1

        conn.commit()

        if not dry_run:
            print(f'\nCleanup complete!')
            print(f'  Cities deleted: {cities_deleted}')
            print(f'  Streets reassigned: {streets_reassigned}')
            print(f'  Addresses reassigned: {addresses_reassigned}')
            if addresses_deleted:
                print(f'  Addresses deleted (duplicates in target): {addresses_deleted}')


def main():
    print('=== Cities Deduplication Tool ===\n')

    dry_run = '--dry-run' in sys.argv or '-d' in sys.argv

    if dry_run:
        print('DRY RUN: No changes will be made.\n')

    conn = get_db_connection()

    try:
        dedup_cities(conn, dry_run=dry_run)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
