"""FR-017 Oda tanımlama ve FR-018 Oda pasifleştirme: sunucu davranışı (POST/PATCH /api/odalar).

Gerçek PostgreSQL kullanılmaz; bağlantı taklit edilir. Yetki, doğrulama, yazılan SQL, denetim kaydı ve işlemin
geri alınması doğrudan doğrulanır.
"""
from unittest.mock import MagicMock, patch

import psycopg2
import pytest
from fastapi.testclient import TestClient

from sunucu import app, mevcut_kullanici_id

KULLANICI = 5


@pytest.fixture(autouse=True)
def giris_yapmis_kullanici():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: KULLANICI
    yield
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def baglanti(fetchone=(), cakisma_sorgusu=None):
    """cakisma_sorgusu: bu metni içeren SQL çalışınca UniqueViolation fırlatılır."""
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = list(fetchone)
    if cakisma_sorgusu:
        def calistir(sorgu, *args):
            if cakisma_sorgusu in sorgu:
                raise psycopg2.errors.UniqueViolation()
        cursor.execute.side_effect = calistir
    return conn, cursor


def istek(metot, yol, conn, **kwargs):
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with TestClient(app) as istemci:
            return getattr(istemci, metot)(yol, **kwargs)


def sorgular(cursor):
    return [(" ".join(c.args[0].split()), c.args[1] if len(c.args) > 1 else None) for c in cursor.execute.call_args_list]


def yazma_var_mi(cursor):
    return any(s.upper().startswith(("INSERT", "UPDATE", "DELETE")) for s, _ in sorgular(cursor))


def ekleme(cursor):
    return next(p for s, p in sorgular(cursor) if s.startswith("INSERT INTO odalar"))


def denetim(cursor):
    return [p for s, p in sorgular(cursor) if s.startswith("INSERT INTO denetim_kayitlari")]


# =============================================================== FR-017 oda ekleme
def test_oda_ekleme_izni_yoksa_403_ve_hicbir_sey_yazilmaz():
    conn, cursor = baglanti(fetchone=[(0,)])
    yanit = istek("post", "/api/odalar", conn, json={"oda_adi": "Oda 9"})
    assert yanit.status_code == 403 and not yazma_var_mi(cursor)
    conn.commit.assert_not_called()


def test_izin_kaydi_hic_yoksa_da_403():
    conn, cursor = baglanti(fetchone=[None])
    assert istek("post", "/api/odalar", conn, json={"oda_adi": "Oda 9"}).status_code == 403
    assert not yazma_var_mi(cursor)


def test_oda_eklenir_201_yanit_sorgu_parametreleri_ve_denetim_kaydi():
    conn, cursor = baglanti(fetchone=[(1,), (77,)])
    yanit = istek("post", "/api/odalar", conn, json={"oda_adi": "Oda 7", "kapasite": 4, "aktif_mi": False})
    assert yanit.status_code == 201
    assert yanit.json() == {"durum": "basarili", "mesaj": "Oda başarıyla oluşturuldu.", "oda_id": 77}
    assert ekleme(cursor) == ("Oda 7", 4, False)
    assert denetim(cursor) == [(KULLANICI, "CREATE", "odalar", 77)]       # kim, ne, hangi tablo, hangi kayıt
    conn.commit.assert_called_once()


def test_varsayilanlar_kapasite_1_ve_aktif():
    conn, cursor = baglanti(fetchone=[(1,), (78,)])
    assert istek("post", "/api/odalar", conn, json={"oda_adi": "Oda 8"}).status_code == 201
    assert ekleme(cursor) == ("Oda 8", 1, True)


def test_oda_adinin_basindaki_ve_sonundaki_bosluklar_kirpilir():
    conn, cursor = baglanti(fetchone=[(1,), (79,)])
    istek("post", "/api/odalar", conn, json={"oda_adi": "  Oda 10  "})
    assert ekleme(cursor)[0] == "Oda 10"


def test_oda_adi_sorguya_gomulmez_parametre_olarak_gider():
    kotu = "x'); DROP TABLE odalar;--"
    conn, cursor = baglanti(fetchone=[(1,), (80,)])
    istek("post", "/api/odalar", conn, json={"oda_adi": kotu})
    sorgu, parametre = next((s, p) for s, p in sorgular(cursor) if s.startswith("INSERT INTO odalar"))
    assert "DROP" not in sorgu and parametre[0] == kotu


def test_ayni_isimde_oda_409_islem_geri_alinir_denetim_yazilmaz():
    conn, cursor = baglanti(fetchone=[(1,)], cakisma_sorgusu="INSERT INTO odalar")
    yanit = istek("post", "/api/odalar", conn, json={"oda_adi": "Oda 1"})
    assert yanit.status_code == 409 and "zaten mevcut" in yanit.json()["detail"]
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    assert denetim(cursor) == []


@pytest.mark.parametrize("govde", [
    {},                                         # ad yok
    {"oda_adi": ""},                            # boş
    {"oda_adi": "x" * 51},                      # en fazla 50
    {"oda_adi": "Oda", "kapasite": 0},          # kapasite en az 1
    {"oda_adi": "Oda", "kapasite": -3},
    {"oda_adi": "Oda", "kapasite": "çok"},
    {"oda_adi": 123456},
])
def test_gecersiz_girdi_422_ve_veritabanina_hic_yazilmaz(govde):
    conn, cursor = baglanti(fetchone=[(1,)])
    yanit = istek("post", "/api/odalar", conn, json=govde)
    assert yanit.status_code == 422 and not yazma_var_mi(cursor)
    conn.commit.assert_not_called()


def test_oda_adi_tam_50_karakter_kabul_edilir():
    conn, cursor = baglanti(fetchone=[(1,), (81,)])
    assert istek("post", "/api/odalar", conn, json={"oda_adi": "x" * 50}).status_code == 201


# =============================================================== FR-018 oda pasifleştirme
def guncelle(govde, fetchone, fetchall=(), cakisma_sorgusu=None, oda_id=2):
    conn, cursor = baglanti(fetchone=fetchone, cakisma_sorgusu=cakisma_sorgusu)
    cursor.fetchall.side_effect = list(fetchall)
    return istek("patch", f"/api/odalar/{oda_id}", conn, json=govde), conn, cursor


def test_oda_duzenleme_izni_yoksa_403_ve_hicbir_sey_yazilmaz():
    yanit, conn, cursor = guncelle({"aktif_mi": False}, fetchone=[(0,)])
    assert yanit.status_code == 403 and not yazma_var_mi(cursor)
    conn.commit.assert_not_called()


def test_oda_pasife_alinir_kayit_silinmez_ve_denetim_yazilir():
    yanit, conn, cursor = guncelle({"aktif_mi": False}, fetchone=[(1,), (2,), (2, "Oda 2", 3, False)], fetchall=[[]])
    assert yanit.status_code == 200
    assert yanit.json()["oda"] == {"oda_id": 2, "oda_adi": "Oda 2", "kapasite": 3, "aktif_mi": False}
    guncelleme = next((s, p) for s, p in sorgular(cursor) if s.startswith("UPDATE odalar"))
    assert guncelleme[0].startswith("UPDATE odalar SET aktif_mi = %s WHERE oda_id = %s") and guncelleme[1] == (False, 2)
    assert not any(s.upper().startswith("DELETE") for s, _ in sorgular(cursor))       # pasifleştirme silme değildir
    assert denetim(cursor) == [(KULLANICI, "UPDATE", "odalar", 2)]
    conn.commit.assert_called_once()


def test_pasif_oda_yeniden_aktiflestirilebilir_ve_psikolog_kontrolu_yapilmaz():
    yanit, conn, cursor = guncelle({"aktif_mi": True}, fetchone=[(1,), (2,), (2, "Oda 2", 1, True)])
    assert yanit.status_code == 200 and yanit.json()["oda"]["aktif_mi"] is True
    assert not any("psikolog_odalar" in s for s, _ in sorgular(cursor))
    assert denetim(cursor) == [(KULLANICI, "UPDATE", "odalar", 2)]


def test_pasiflestirmede_satir_kilitlenir_yaris_durumunu_onler():
    _, _, cursor = guncelle({"aktif_mi": False}, fetchone=[(1,), (2,), (2, "Oda 2", 1, False)], fetchall=[[]])
    assert any(s.startswith("SELECT oda_id FROM odalar WHERE oda_id = %s FOR UPDATE") for s, _ in sorgular(cursor))


def test_olmayan_oda_404_ve_hicbir_sey_yazilmaz():
    yanit, conn, cursor = guncelle({"aktif_mi": False}, fetchone=[(1,), None], oda_id=999)
    assert yanit.status_code == 404 and "bulunamadı" in yanit.json()["detail"]
    assert not yazma_var_mi(cursor)
    conn.commit.assert_not_called()


@pytest.mark.parametrize("govde", [{}, {"aktif_mi": None}, {"oda_adi": None}, {"kapasite": None}])
def test_bos_ya_da_null_guncelleme_422_ve_veritabanina_gidilmez(govde):
    yanit, conn, cursor = guncelle(govde, fetchone=[(1,)])
    assert yanit.status_code == 422 and not yazma_var_mi(cursor)
    conn.commit.assert_not_called()


@pytest.mark.parametrize("govde", [{"oda_adi": ""}, {"oda_adi": "x" * 51}, {"kapasite": 0}, {"aktif_mi": "belki"}])
def test_gecersiz_guncelleme_degerleri_422(govde):
    yanit, _, cursor = guncelle(govde, fetchone=[(1,)])
    assert yanit.status_code == 422 and not yazma_var_mi(cursor)


def test_baska_odayla_ayni_isme_yeniden_adlandirma_409_geri_alinir():
    yanit, conn, cursor = guncelle({"oda_adi": "Oda 1"}, fetchone=[(1,), (2,)], cakisma_sorgusu="UPDATE odalar")
    assert yanit.status_code == 409 and "başka bir oda zaten mevcut" in yanit.json()["detail"]
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    assert denetim(cursor) == []


def test_ad_ve_kapasite_ayni_istekte_guncellenir_yalniz_gonderilen_alanlar_yazilir():
    yanit, _, cursor = guncelle({"oda_adi": "Yeni", "kapasite": 5}, fetchone=[(1,), (2,), (2, "Yeni", 5, True)])
    assert yanit.status_code == 200
    guncelleme = next((s, p) for s, p in sorgular(cursor) if s.startswith("UPDATE odalar"))
    set_kismi = guncelleme[0].split(" WHERE ")[0]                         # RETURNING listesi aktif_mi içerir; SET içermez
    assert set_kismi == "UPDATE odalar SET oda_adi = %s, kapasite = %s"
    assert guncelleme[1] == ("Yeni", 5, 2)


# =============================================================== yalnızca boşluktan oluşan oda adı
BOS_ADLAR = ["   ", "\t", "\n  \n", "\u00a0", " \u3000 "]          # boşluk, sekme, satır sonu, bölünmez boşluk, geniş boşluk


@pytest.mark.parametrize("ad", BOS_ADLAR)
def test_yalniz_bosluktan_olusan_ad_ekleme_422_ve_hicbir_sey_yazilmaz(ad):
    conn, cursor = baglanti(fetchone=[(1,)])
    yanit = istek("post", "/api/odalar", conn, json={"oda_adi": ad})
    assert yanit.status_code == 422 and not yazma_var_mi(cursor)
    assert "Oda adı boş olamaz" in yanit.text
    conn.commit.assert_not_called()


@pytest.mark.parametrize("ad", BOS_ADLAR)
def test_yalniz_bosluktan_olusan_ad_guncellemede_422(ad):
    yanit, conn, cursor = guncelle({"oda_adi": ad}, fetchone=[(1,)])
    assert yanit.status_code == 422 and not yazma_var_mi(cursor)
    conn.commit.assert_not_called()


def test_guncellemede_ad_da_kirpilarak_yazilir():
    yanit, _, cursor = guncelle({"oda_adi": "  Yeni Ad  "}, fetchone=[(1,), (2,), (2, "Yeni Ad", 1, True)])
    assert yanit.status_code == 200
    assert next(p for s, p in sorgular(cursor) if s.startswith("UPDATE odalar")) == ("Yeni Ad", 2)


def test_uzunluk_siniri_kirpilmis_ada_uygulanir_ic_bosluklar_korunur():
    conn, cursor = baglanti(fetchone=[(1,), (90,)])
    assert istek("post", "/api/odalar", conn, json={"oda_adi": "  " + "x" * 50 + "  "}).status_code == 201
    assert ekleme(cursor)[0] == "x" * 50
    conn2, _ = baglanti(fetchone=[(1,)])
    assert istek("post", "/api/odalar", conn2, json={"oda_adi": " " + "x" * 51}).status_code == 422
    conn3, cursor3 = baglanti(fetchone=[(1,), (91,)])
    istek("post", "/api/odalar", conn3, json={"oda_adi": "Görüşme  Odası 3"})
    assert ekleme(cursor3)[0] == "Görüşme  Odası 3"


def test_modeller_adi_dogrudan_kirpar_bos_adi_reddeder_none_ve_gonderilmeyen_degismedi():
    from pydantic import ValidationError
    from modeller import OdaGuncelleModeli, OdaOlusturModeli
    assert OdaOlusturModeli(oda_adi="  Oda 3 ").oda_adi == "Oda 3"
    assert OdaGuncelleModeli(oda_adi="  Oda 3 ").oda_adi == "Oda 3"
    for sinif in (OdaOlusturModeli, OdaGuncelleModeli):
        with pytest.raises(ValidationError, match="Oda adı boş olamaz"):
            sinif(oda_adi="    ")
    assert OdaGuncelleModeli(kapasite=3).model_dump(exclude_unset=True) == {"kapasite": 3}
    assert OdaGuncelleModeli(oda_adi=None).oda_adi is None          # None kabul edilir; "gönderilmeli" kuralı sunucuda 422 verir
