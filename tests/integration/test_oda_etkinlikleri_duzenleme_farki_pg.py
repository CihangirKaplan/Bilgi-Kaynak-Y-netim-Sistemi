"""Oda etkinliği düzenleme, gerçek PostgreSQL üzerinde (test kendi verisini üretir, sonda geri alınır).

- Denetim kaydına ve veritabanına yalnızca gerçekten değişen alanlar yazılır (istemci tüm alanları gönderse de).
- Hiçbir şey değişmediyse günlere dokunulmaz, denetim kaydı yazılmaz.
- Listede düzenleyen adı sunucudan gelir (Admin rollü düzenleyen de görünür).
"""
import os
import uuid
from unittest.mock import patch

import psycopg2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.oda_etkinlikleri_api import router_olustur
from server.sunucu import VT_AYARLARI


class SahteBaglanti:
    """Uç noktanın commit'ini engeller; her şey testin işleminde kalır ve sonda geri alınır."""

    def __init__(self, gercek):
        self.gercek = gercek

    def cursor(self, *args, **kwargs):
        return self.gercek.cursor(*args, **kwargs)

    def commit(self):
        pass

    def rollback(self):
        with self.gercek.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT test_verisi_hazir")

    def close(self):
        pass


def _kullanici_ve_personel(cur, etiket, rol, kod):
    cur.execute(
        "INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id) "
        "VALUES (%s, 'x', (SELECT rol_id FROM roller WHERE rol_adi = %s)) RETURNING kullanici_id",
        (f"qa_oda_{kod}_{etiket}", rol),
    )
    kullanici_id = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO personel (kullanici_id, personel_kodu, aktif_mi) VALUES (%s, %s, TRUE) RETURNING personel_id",
        (kullanici_id, f"QA{kod}{etiket}"[:20]),
    )
    return kullanici_id, cur.fetchone()[0]


@pytest.fixture
def ortam():
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    baglanti = psycopg2.connect(**VT_AYARLARI)
    etiket = uuid.uuid4().hex[:8]
    try:
        with baglanti.cursor() as cur:
            yonetici_id, memur_personel = _kullanici_ve_personel(cur, etiket, "MEMUR", "M")
            _, ikinci_personel = _kullanici_ve_personel(cur, etiket, "MEMUR", "N")
            _, admin_personel = _kullanici_ve_personel(cur, etiket, "ADMIN", "A")
            cur.execute(
                "INSERT INTO odalar (oda_adi, kapasite) VALUES (%s, 4), (%s, 4) RETURNING oda_id",
                (f"QA Oda 1 {etiket}", f"QA Oda 2 {etiket}"),
            )
            oda1, oda2 = [r[0] for r in cur.fetchall()]
            cur.execute("SAVEPOINT test_verisi_hazir")

        uygulama = FastAPI()
        uygulama.include_router(router_olustur(lambda izin: lambda: yonetici_id, VT_AYARLARI))
        with patch("psycopg2.connect", return_value=SahteBaglanti(baglanti)):
            with TestClient(uygulama) as istemci:
                yield {
                    "istemci": istemci, "conn": baglanti, "yonetici_id": yonetici_id, "personel": memur_personel,
                    "ikinci_personel": ikinci_personel, "admin_personel": admin_personel, "oda1": oda1, "oda2": oda2,
                    "etiket": etiket,
                }
    finally:
        baglanti.rollback()
        baglanti.close()


def _gunler(*gunler):
    return [{"baslangic_zamani": f"2049-06-{g:02d}T13:00:00", "bitis_zamani": f"2049-06-{g:02d}T14:00:00"} for g in gunler]


def _olustur(ortam, ad="Seminer", gunler=(15, 16), **ek):
    yanit = ortam["istemci"].post("/api/oda-etkinlikleri", json={
        "oda_id": ortam["oda1"], "organize_eden_personel_id": ortam["personel"], "etkinlik_adi": ad,
        "katilimci_sayisi": 10, "gunler": _gunler(*gunler), **ek,
    })
    assert yanit.status_code == 201, yanit.text
    return yanit.json()["etkinlik_id"]


def _son_denetim(ortam, etkinlik_id):
    with ortam["conn"].cursor() as cur:
        cur.execute(
            "SELECT olay_turu::text, ayrinti FROM denetim_kayitlari WHERE hedef_tablo = 'oda_etkinlikleri' "
            "AND hedef_kayit_id = %s ORDER BY denetim_id DESC LIMIT 1", (etkinlik_id,))
        return cur.fetchone()


def _denetim_sayisi(ortam, etkinlik_id):
    with ortam["conn"].cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM denetim_kayitlari WHERE hedef_tablo = 'oda_etkinlikleri' AND hedef_kayit_id = %s",
            (etkinlik_id,))
        return cur.fetchone()[0]


def _gun_kimlikleri(ortam, etkinlik_id):
    with ortam["conn"].cursor() as cur:
        cur.execute("SELECT gun_id FROM oda_etkinlik_gunleri WHERE etkinlik_id = %s ORDER BY baslangic_zamani", (etkinlik_id,))
        return [r[0] for r in cur.fetchall()]


def _tam_govde(ortam, **degisen):
    """İstemcinin gönderdiği gibi: düzenlenmeyen alanlar da dahil tüm alanlar."""
    govde = {
        "oda_id": ortam["oda1"], "organize_eden_personel_id": ortam["personel"], "etkinlik_adi": "Seminer",
        "katilimci_sayisi": 10, "gunler": _gunler(15, 16),
    }
    govde.update(degisen)
    return govde


def test_yalniz_ad_degisince_denetim_yalniz_adi_yazar_ve_gunlere_dokunulmaz(ortam):
    etkinlik_id = _olustur(ortam)
    onceki_gunler = _gun_kimlikleri(ortam, etkinlik_id)

    yanit = ortam["istemci"].patch(f"/api/oda-etkinlikleri/{etkinlik_id}", json=_tam_govde(ortam, etkinlik_adi="  Yeni ad  "))
    assert yanit.status_code == 200 and yanit.json()["durum"] == "basarili"

    olay, ayrinti = _son_denetim(ortam, etkinlik_id)
    assert olay == "UPDATE" and ayrinti["degisen_alanlar"] == ["etkinlik_adi"]
    assert _gun_kimlikleri(ortam, etkinlik_id) == onceki_gunler                     # günler silinip yeniden yazılmadı


def test_gunler_degisince_gunler_ve_zamanlar_degisen_alan_olarak_yazilir(ortam):
    etkinlik_id = _olustur(ortam)
    onceki_gunler = _gun_kimlikleri(ortam, etkinlik_id)

    yanit = ortam["istemci"].patch(f"/api/oda-etkinlikleri/{etkinlik_id}", json=_tam_govde(ortam, gunler=_gunler(15, 17)))
    assert yanit.status_code == 200

    _, ayrinti = _son_denetim(ortam, etkinlik_id)
    assert ayrinti["degisen_alanlar"] == ["bitis_zamani", "gunler"] and ayrinti["gun_sayisi"] == 2
    assert _gun_kimlikleri(ortam, etkinlik_id) != onceki_gunler


def test_hicbir_sey_degismediyse_denetim_yazilmaz_ve_veri_ayni_kalir(ortam):
    etkinlik_id = _olustur(ortam)
    onceki_gunler = _gun_kimlikleri(ortam, etkinlik_id)
    onceki_sayi = _denetim_sayisi(ortam, etkinlik_id)

    yanit = ortam["istemci"].patch(f"/api/oda-etkinlikleri/{etkinlik_id}", json=_tam_govde(ortam))
    assert yanit.status_code == 200 and yanit.json()["durum"] == "degisiklik_yok"
    assert _denetim_sayisi(ortam, etkinlik_id) == onceki_sayi
    assert _gun_kimlikleri(ortam, etkinlik_id) == onceki_gunler


def test_oda_ve_personel_degisimi_denetimde_gorunur(ortam):
    etkinlik_id = _olustur(ortam)
    yanit = ortam["istemci"].patch(
        f"/api/oda-etkinlikleri/{etkinlik_id}",
        json=_tam_govde(ortam, oda_id=ortam["oda2"], organize_eden_personel_id=ortam["ikinci_personel"], katilimci_sayisi=None))
    assert yanit.status_code == 200, yanit.text
    _, ayrinti = _son_denetim(ortam, etkinlik_id)
    assert ayrinti["degisen_alanlar"] == ["katilimci_sayisi", "oda_id", "organize_eden_personel_id"]
    assert ayrinti["onceki"]["oda_id"] == ortam["oda1"] and ayrinti["yeni"]["oda_id"] == ortam["oda2"]


def test_liste_duzenleyen_adini_admin_dahil_sunucudan_getirir(ortam):
    # Admin rollü düzenleyen seçeneklerde çıkmaz; ancak mevcut atama korunur ve listede adı görünmelidir.
    etkinlik_id = _olustur(ortam)
    with ortam["conn"].cursor() as cur:
        cur.execute("UPDATE oda_etkinlikleri SET organize_eden_personel_id = %s WHERE etkinlik_id = %s",
                    (ortam["admin_personel"], etkinlik_id))

    yanit = ortam["istemci"].get("/api/oda-etkinlikleri", params={"baslangic": "2049-06-01", "bitis": "2049-06-30"})
    assert yanit.status_code == 200
    kayit = next(e for e in yanit.json()["etkinlikler"] if e["etkinlik_id"] == etkinlik_id)
    assert kayit["duzenleyen_adi"] == f"qa_oda_A_{ortam['etiket']}"

    # Düzenleme formu Admin düzenleyenle açılıp kaydedildiğinde (kimlik değişmediği için) reddedilmez.
    yanit = ortam["istemci"].patch(
        f"/api/oda-etkinlikleri/{etkinlik_id}",
        json=_tam_govde(ortam, organize_eden_personel_id=ortam["admin_personel"], etkinlik_adi="Admin düzenleyenli"))
    assert yanit.status_code == 200, yanit.text
