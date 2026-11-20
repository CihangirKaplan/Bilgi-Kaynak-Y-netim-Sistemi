"""TKYS - Yönetici için sistem durumu: sürüm, şema, yedek, son girişler.

Yalnızca özet bilgi döner: kişisel veri, parola, dosya yolu ya da bağlantı bilgisi içermez. Yedek bilgisi yedek klasöründeki
dosya adlarından ve zamanlarından okunur (scripts/backup/veritabani_yedekle.py: <veritabani>_<YYYYMMDD>_<HHMMSS>_<mikrosaniye>.dump).
"""
import os
import re
from datetime import datetime
from pathlib import Path

from server.surum import SURUM, UYGULAMA_ADI

OTURUM_SURESI_DK = int(os.getenv("JWT_EXPIRE_MINUTES") or 45)
YEDEK_ESKI_SAAT = 36        # bundan eski son yedek "eski" sayılır (günlük yedek + pay)


def yedek_klasoru():
    return Path(os.getenv("TKYS_BACKUP_DIR") or (Path(__file__).resolve().parents[1] / "backups")).resolve()


def son_yedek_bilgisi(klasor, veritabani, simdi=None):
    """Klasördeki en yeni yedeği özetler. Klasör ya da yedek yoksa var=False döner (hata fırlatmaz)."""
    simdi = simdi or datetime.now()
    desen = re.compile(rf"^{re.escape(veritabani)}_(\d{{8}})_(\d{{6}})_\d{{6}}\.dump$")
    bos = {"var": False, "tarih": None, "gecen_saat": None, "eski": True, "adet": 0, "boyut_mb": None}
    try:
        dosyalar = [d for d in Path(klasor).iterdir() if d.is_file() and desen.match(d.name)]
    except OSError:
        return bos
    kayitlar = []
    for dosya in dosyalar:
        eslesme = desen.match(dosya.name)
        try:
            zaman = datetime.strptime(eslesme.group(1) + eslesme.group(2), "%Y%m%d%H%M%S")
            boyut = dosya.stat().st_size
        except (ValueError, OSError):
            continue
        kayitlar.append((zaman, boyut))
    if not kayitlar:
        return bos
    zaman, boyut = max(kayitlar)
    gecen = max((simdi - zaman).total_seconds() / 3600, 0)
    return {
        "var": True, "tarih": zaman.isoformat(), "gecen_saat": round(gecen, 1), "eski": gecen > YEDEK_ESKI_SAAT,
        "adet": len(kayitlar), "boyut_mb": round(boyut / 1024 / 1024, 2),
    }


def sema_surumu(cursor):
    try:
        cursor.execute("SELECT version_num FROM alembic_version;")
        satir = cursor.fetchone()
        return satir[0] if satir else None
    except Exception:
        cursor.connection.rollback()
        return None


def sistem_durumu(cursor, veritabani, klasor=None, simdi=None):
    cursor.execute("SELECT pg_database_size(current_database());")
    boyut_mb = round((cursor.fetchone()[0] or 0) / 1024 / 1024, 1)

    cursor.execute(
        """
        SELECT k.kullanici_adi, COALESCE(r.gorunen_ad, r.rol_adi), MAX(d.olusturulma_tarihi)
        FROM denetim_kayitlari d
        JOIN kullanicilar k ON k.kullanici_id = d.kullanici_id
        JOIN roller r ON r.rol_id = k.rol_id
        WHERE d.olay_turu::text = 'LOGIN' AND d.olusturulma_tarihi >= NOW() - make_interval(mins => %s)
        GROUP BY k.kullanici_adi, COALESCE(r.gorunen_ad, r.rol_adi)
        ORDER BY MAX(d.olusturulma_tarihi) DESC;
        """, (OTURUM_SURESI_DK,),
    )
    son_girisler = [{"kullanici_adi": s[0], "rol": s[1], "zaman": s[2].isoformat() if s[2] else None} for s in cursor.fetchall()]

    cursor.execute(
        "SELECT COUNT(*) FROM denetim_kayitlari WHERE olay_turu::text = 'LOGIN_FAILED' AND olusturulma_tarihi >= NOW() - INTERVAL '24 hours';"
    )
    basarisiz_24s = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM kullanicilar WHERE aktif_mi = TRUE;")
    aktif_kullanici = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM randevular;")
    randevu = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM danisan_kodlari;")
    danisan = cursor.fetchone()[0]

    return {
        "uygulama": UYGULAMA_ADI, "surum": SURUM, "sema_surumu": sema_surumu(cursor),
        "veritabani_boyutu_mb": boyut_mb,
        "yedek": son_yedek_bilgisi(klasor or yedek_klasoru(), veritabani, simdi),
        "oturum_suresi_dk": OTURUM_SURESI_DK, "son_girisler": son_girisler,
        "basarisiz_giris_24s": basarisiz_24s,
        "sayilar": {"aktif_kullanici": aktif_kullanici, "randevu": randevu, "danisan_kodu": danisan},
    }
