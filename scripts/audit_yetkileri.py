"""
TKYS - PostgreSQL uygulama rolü yetkilendirmesi.

Yalnızca açıkça belirtilen veritabanında çalıştırılmalıdır.
Veritabanı rolü önceden oluşturulmuş olmalıdır.
"""

import argparse
import os

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--role", default="tkys_app")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not args.apply:
        print("Önizleme modu: veritabanında değişiklik yapılmadı.")
        print(f"Hedef veritabanı: {args.database}")
        print(f"Uygulama rolü: {args.role}")
        print("Uygulamak için --apply parametresi gereklidir.")
        return

    if args.database != "crkys_alembic_test":
        raise SystemExit(
            "Bu script şimdilik yalnızca crkys_alembic_test üzerinde uygulanabilir."
        )

    conn = psycopg2.connect(
        dbname=args.database,
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s",
                (args.role,),
            )
            if cursor.fetchone() is None:
                raise ValueError("Uygulama rolü bulunamadı.")

            cursor.execute("""
                SELECT 1 FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename = 'denetim_kayitlari'
            """)
            if cursor.fetchone() is None:
                raise ValueError("Audit tablosu bulunamadı.")

            cursor.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(args.database),
                    sql.Identifier(args.role),
                )
            )
            cursor.execute(
                sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                    sql.Identifier(args.role)
                )
            )
            cursor.execute(
                sql.SQL("""
                    GRANT SELECT, INSERT, UPDATE, DELETE
                    ON ALL TABLES IN SCHEMA public TO {}
                """).format(sql.Identifier(args.role))
            )
            cursor.execute(
                sql.SQL("""
                    GRANT USAGE, SELECT
                    ON ALL SEQUENCES IN SCHEMA public TO {}
                """).format(sql.Identifier(args.role))
            )
            cursor.execute(
                sql.SQL("""
                    REVOKE UPDATE, DELETE
                    ON TABLE public.denetim_kayitlari FROM {}
                """).format(sql.Identifier(args.role))
            )

            cursor.execute(
                sql.SQL("""
                    REVOKE INSERT, UPDATE, DELETE
                    ON TABLE public.alembic_version FROM {}
                """).format(sql.Identifier(args.role))
            )

            cursor.execute("""
                SELECT
                    has_table_privilege(%s, 'public.denetim_kayitlari', 'INSERT'),
                    has_table_privilege(%s, 'public.denetim_kayitlari', 'UPDATE'),
                    has_table_privilege(%s, 'public.denetim_kayitlari', 'DELETE')
            """, (args.role, args.role, args.role))

            izinler = cursor.fetchone()

            if izinler != (True, False, False):
                raise RuntimeError(
                    f"Audit yetkileri güvenli değil: {izinler}"
                )

        conn.commit()
        print("Yetkilendirme tamamlandı.")
        print("Audit INSERT / UPDATE / DELETE:", izinler)

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
