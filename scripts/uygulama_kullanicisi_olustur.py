"""TKYS - Sunucunun veritabanına bağlanacağı KISITLI kullanıcıyı oluşturur.

Neden: Sunucu şimdiye kadar tam yetkili (süper kullanıcı) hesapla bağlanıyordu. Sunucuda bir açık çıksa, saldırgan
veritabanının tamamını silebilir ya da değiştirebilirdi. Bu betik, yalnızca veri okuyup yazabilen ayrı bir
kullanıcı (varsayılan adı tkys_uygulama) oluşturur:

  * tabloları oluşturamaz, silemez, değiştiremez (DDL yok); süper kullanıcı değildir
  * denetim_kayitlari tablosuna yalnızca satır ekleyebilir (UPDATE / DELETE / TRUNCATE yok)
  * alembic_version tablosuna yazamaz
  * ileride migration ile eklenen yeni tablolara otomatik olarak okuma/yazma yetkisi alır

Şema güncellemeleri (alembic upgrade) ve yedekten geri yükleme tam yetkili hesapla yapılmaya devam eder; o hesabın bilgisi
.env içinde DB_MIGRATION_USER / DB_MIGRATION_PASSWORD olarak verilir (bkz. docs/Sunucu_Kurulum_Kilavuzu.md).

Kullanım (sunucu bilgisayarında, proje klasöründe):
    python scripts/uygulama_kullanicisi_olustur.py                 # önizleme, hiçbir şey değiştirmez
    python scripts/uygulama_kullanicisi_olustur.py --uygula        # kullanıcıyı oluşturur, parolayı bir kez gösterir

Betik tekrar çalıştırılabilir: kullanıcı varsa yalnızca yetkileri yeniden uygular (parolasına dokunmaz;
parolayı yenilemek için --parolayi-yenile).
"""

import argparse
import os
import re
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql

from server.sema_kimligi import SemaKimligiHatasi, sema_kimligi

VARSAYILAN_ROL = "tkys_uygulama"
GECERLI_ROL = re.compile(r"[a-z_][a-z0-9_]{0,62}")
KORUNAN_ROLLER = {"postgres", "public", "pg_database_owner"}


class KullaniciOlusturmaHatasi(Exception):
    """Beklenen, kullanıcıya mesajla bildirilecek hata."""


def rol_adini_dogrula(rol):
    if not rol or not GECERLI_ROL.fullmatch(rol):
        raise KullaniciOlusturmaHatasi(
            "Rol adı küçük harf, rakam ve alt çizgiden oluşmalı, harf ya da alt çizgiyle başlamalı (en çok 63 karakter)."
        )
    if rol in KORUNAN_ROLLER or rol.startswith("pg_"):
        raise KullaniciOlusturmaHatasi(f"'{rol}' adı kullanılamaz.")


def yeni_parola_uret():
    return secrets.token_urlsafe(32)


def _rol_var_mi(imlec, rol):
    imlec.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (rol,))
    return imlec.fetchone() is not None


def yetkileri_uygula(imlec, veritabani, rol, yonetici):
    """Rolü kısıtlı yetkilerle donatır. 'yonetici': tabloları oluşturan (sahip) kullanıcı."""
    r = sql.Identifier(rol)
    imlec.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(veritabani), r))
    imlec.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(r))
    imlec.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(r))
    imlec.execute(sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(r))

    # Yönetici ileride migration ile yeni tablo/sıra oluşturunca aynı yetkiler otomatik verilsin.
    y = sql.Identifier(yonetici)
    imlec.execute(sql.SQL(
        "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
    ).format(y, r))
    imlec.execute(sql.SQL(
        "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {}"
    ).format(y, r))

    # Denetim kaydı yalnızca eklenir; alembic sürüm tablosuna uygulama hiç yazmaz.
    imlec.execute(sql.SQL("REVOKE UPDATE, DELETE, TRUNCATE ON TABLE public.denetim_kayitlari FROM {}").format(r))
    imlec.execute(sql.SQL("REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE public.alembic_version FROM {}").format(r))


def yetkileri_dogrula(imlec, rol):
    """Rolün gerçekten kısıtlı olduğunu kontrol eder; değilse hata verir. Dönüş: bulgu sözlüğü."""
    imlec.execute(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname = %s",
        (rol,),
    )
    super, dbyarat, rolyarat, kopya, rlsatla = imlec.fetchone()
    imlec.execute(
        """
        SELECT
            has_table_privilege(%(r)s, 'public.denetim_kayitlari', 'INSERT'),
            has_table_privilege(%(r)s, 'public.denetim_kayitlari', 'UPDATE'),
            has_table_privilege(%(r)s, 'public.denetim_kayitlari', 'DELETE'),
            has_table_privilege(%(r)s, 'public.denetim_kayitlari', 'TRUNCATE'),
            has_table_privilege(%(r)s, 'public.alembic_version', 'INSERT'),
            has_table_privilege(%(r)s, 'public.alembic_version', 'UPDATE'),
            has_table_privilege(%(r)s, 'public.kullanicilar', 'SELECT'),
            has_table_privilege(%(r)s, 'public.kullanicilar', 'INSERT'),
            has_table_privilege(%(r)s, 'public.kullanicilar', 'UPDATE'),
            has_schema_privilege(%(r)s, 'public', 'CREATE')
        """,
        {"r": rol},
    )
    (da_ins, da_upd, da_del, da_trn, av_ins, av_upd, k_sel, k_ins, k_upd, sema_olustur) = imlec.fetchone()

    bulgu = {
        "süper kullanıcı": super, "veritabanı oluşturabilir": dbyarat, "rol oluşturabilir": rolyarat,
        "replikasyon": kopya, "satır güvenliğini aşar": rlsatla,
        "denetim INSERT": da_ins, "denetim UPDATE": da_upd, "denetim DELETE": da_del, "denetim TRUNCATE": da_trn,
        "alembic_version INSERT": av_ins, "alembic_version UPDATE": av_upd,
        "kullanicilar SELECT": k_sel, "kullanicilar INSERT": k_ins, "kullanicilar UPDATE": k_upd,
        "şemada tablo oluşturabilir": sema_olustur,
    }
    beklenen = {
        "süper kullanıcı": False, "veritabanı oluşturabilir": False, "rol oluşturabilir": False,
        "replikasyon": False, "satır güvenliğini aşar": False,
        "denetim INSERT": True, "denetim UPDATE": False, "denetim DELETE": False, "denetim TRUNCATE": False,
        "alembic_version INSERT": False, "alembic_version UPDATE": False,
        "kullanicilar SELECT": True, "kullanicilar INSERT": True, "kullanicilar UPDATE": True,
        "şemada tablo oluşturabilir": False,
    }
    yanlis = [f"{ad} = {bulgu[ad]} (olması gereken {beklenen[ad]})" for ad in beklenen if bulgu[ad] != beklenen[ad]]
    if yanlis:
        raise KullaniciOlusturmaHatasi("Rolün yetkileri güvenli değil: " + "; ".join(yanlis))
    return bulgu


def kullaniciyi_olustur(baglanti, veritabani, rol, yonetici, parolayi_yenile=False):
    """Rolü oluşturur (yoksa) ve yetkilerini uygular. Yeni parola ürettiyse onu döndürür, yoksa None."""
    rol_adini_dogrula(rol)
    if rol == yonetici:
        raise KullaniciOlusturmaHatasi(
            "Kısıtlı kullanıcı, yönetici kullanıcıyla aynı olamaz. Farklı bir ad seçin (--rol)."
        )
    parola = None
    with baglanti.cursor() as imlec:
        if not _rol_var_mi(imlec, rol):
            parola = yeni_parola_uret()
            imlec.execute(
                sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %s").format(
                    sql.Identifier(rol)
                ),
                (parola,),
            )
        elif parolayi_yenile:
            parola = yeni_parola_uret()
            imlec.execute(sql.SQL("ALTER ROLE {} PASSWORD %s").format(sql.Identifier(rol)), (parola,))

        yetkileri_uygula(imlec, veritabani, rol, yonetici)
        yetkileri_dogrula(imlec, rol)
    baglanti.commit()
    return parola


def _argumanlar(argv=None):
    p = argparse.ArgumentParser(description="Sunucu için kısıtlı veritabanı kullanıcısı oluşturur.")
    p.add_argument("--rol", default=VARSAYILAN_ROL, help=f"Oluşturulacak kullanıcı adı (varsayılan: {VARSAYILAN_ROL})")
    p.add_argument("--uygula", action="store_true", help="Değişiklikleri gerçekten yapar (yoksa yalnızca önizleme).")
    p.add_argument("--parolayi-yenile", action="store_true", help="Kullanıcı varsa yeni parola üretir.")
    return p.parse_args(argv)


def main(argv=None):
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    args = _argumanlar(argv)
    try:
        rol_adini_dogrula(args.rol)
        yonetici, yonetici_parola = sema_kimligi()
        veritabani = os.environ["DB_NAME"]
        if not yonetici or not yonetici_parola:
            raise KullaniciOlusturmaHatasi(".env dosyasında DB_USER ve DB_PASSWORD (ya da DB_MIGRATION_*) tanımlı olmalı.")
        if args.rol == yonetici:
            raise KullaniciOlusturmaHatasi(f"'{args.rol}' zaten yönetici kullanıcının adı. Farklı bir ad seçin (--rol).")

        if not args.uygula:
            print("ÖNİZLEME: veritabanında hiçbir şey değiştirilmedi.")
            print(f"  Veritabanı            : {veritabani}")
            print(f"  Yönetici kullanıcı    : {yonetici}")
            print(f"  Oluşturulacak kullanıcı: {args.rol} (süper kullanıcı değil; tablo oluşturamaz/silemez)")
            print("Gerçekten oluşturmak için komuta --uygula ekleyin.")
            return 0

        baglanti = psycopg2.connect(
            dbname=veritabani, user=yonetici, password=yonetici_parola,
            host=os.environ["DB_HOST"], port=os.environ.get("DB_PORT", "5432"),
        )
        try:
            parola = kullaniciyi_olustur(baglanti, veritabani, args.rol, yonetici, args.parolayi_yenile)
        except Exception:
            baglanti.rollback()
            raise
        finally:
            baglanti.close()
    except (KullaniciOlusturmaHatasi, SemaKimligiHatasi) as hata:
        print(f"HATA: {hata}")
        return 1
    except psycopg2.Error as hata:
        print(f"HATA: Veritabanı işlemi başarısız: {str(hata).strip().splitlines()[0]}")
        return 1

    print(f"'{args.rol}' kullanıcısının yetkileri uygulandı ve doğrulandı.")
    if parola:
        print()
        print("Bu parola YALNIZCA BİR KEZ gösterilir; şimdi .env dosyasına yazın:")
        print(f"  DB_MIGRATION_USER={yonetici}")
        print("  DB_MIGRATION_PASSWORD=<şu an DB_PASSWORD olarak yazılı olan yönetici parolası>")
        print(f"  DB_USER={args.rol}")
        print(f"  DB_PASSWORD={parola}")
        print("Sonra sunucuyu yeniden başlatın. Ayrıntı: docs/Sunucu_Kurulum_Kilavuzu.md")
    else:
        print("Kullanıcı zaten vardı; parolası değiştirilmedi (yenilemek için --parolayi-yenile).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
