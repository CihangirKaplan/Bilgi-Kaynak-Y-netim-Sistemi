"""Yönetici parola güvenliği: yönetici hesabı uygulamadan sıfırlanamaz, geçici parola süresi, yönetici taleplerinin ele alınışı.

Gerçek veritabanı kullanılmaz; sahte imleçle sunucu işlevleri doğrudan çağrılır.
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Response
from fastapi.testclient import TestClient

import server.guvenlik as guvenlik
import server.sunucu as sunucu
from server.guvenlik import parola_hashle
from server.modeller import ParolaSifirlamaTalebiModeli

GECICI = "Gecici-Parola-123"
GECICI_HASH = parola_hashle(GECICI)


def sahte_vt(*sonuclar):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = list(sonuclar)
    return conn, cursor


def sifirla(conn, hedef_id=20, yonetici_id=10):
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        return sunucu.kullanici_parola_sifirla(kullanici_id=hedef_id, response=Response(), islem_yapan_id=yonetici_id)


# ------------------------------------------------------------------ yönetici hesabı uygulamadan sıfırlanamaz
def test_yonetici_baska_yoneticinin_parolasini_sifirlayamaz_hicbir_sey_yazilmaz():
    conn, cursor = sahte_vt(("ADMIN",), (True, "ADMIN"))
    with pytest.raises(HTTPException) as hata:
        sifirla(conn)
    assert hata.value.status_code == 403
    assert "kurtarma aracı" in hata.value.detail and "admin_parola_kurtar" in hata.value.detail
    assert not any(c.args[0].lstrip().upper().startswith(("UPDATE", "INSERT")) for c in cursor.execute.call_args_list)
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()


def test_pasif_yonetici_icin_de_ayni_engel_uygulanir():
    conn, _ = sahte_vt(("ADMIN",), (False, "ADMIN"))
    with pytest.raises(HTTPException) as hata:
        sifirla(conn)
    assert hata.value.status_code == 403                                     # 409 (pasif) değil: önce yönetici engeli


def test_yonetici_olmayan_hedefin_parolasi_sifirlanir_ve_gecerlilik_suresi_yazilir():
    conn, cursor = sahte_vt(("ADMIN",), (True, "MEMUR"))
    with patch("server.sunucu.gecici_parola_uret", return_value="GECICI"), patch("server.sunucu.parola_hashle", return_value="HASH"):
        sonuc = sifirla(conn)
    assert sonuc["durum"] == "basarili" and sonuc["gecici_parola_gecerlilik_saat"] == guvenlik.GECICI_PAROLA_GECERLILIK_SAAT
    guncelleme = next(c for c in cursor.execute.call_args_list if " ".join(c.args[0].split()).startswith("UPDATE kullanicilar"))
    sql = " ".join(guncelleme.args[0].split())
    assert f"gecici_parola_bitis = {guvenlik.GECICI_PAROLA_BITIS_SQL}" in sql and "ilk_giris_mi = TRUE" in sql
    assert guncelleme.args[1] == ("HASH", 20)
    conn.commit.assert_called_once()


def test_hedef_sorgusu_rolu_da_okur_ve_satiri_kilitler():
    conn, cursor = sahte_vt(("ADMIN",), (True, "MEMUR"))
    sifirla(conn)
    sorgu = " ".join(cursor.execute.call_args_list[1].args[0].split())
    assert "r.rol_adi" in sorgu and "FOR UPDATE OF k" in sorgu


# ------------------------------------------------------------------ yönetici hesabı için talep açılamaz / listelenmez
def talep(kullanici):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = [kullanici, None, (0,), (77,)]
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.denetim.denetim_kaydi_olustur"):
        try:
            return sunucu.parola_sifirlama_talebi_olustur(ParolaSifirlamaTalebiModeli(kullanici_adi="admin")), cursor
        except HTTPException as hata:
            return hata, cursor


def test_yonetici_hesabi_icin_talep_403_ve_kod_ile_reddedilir_talep_kaydedilmez():
    hata, cursor = talep((1, True, "ADMIN"))
    assert isinstance(hata, HTTPException) and hata.status_code == 403
    assert hata.detail["kod"] == "HESAP_YONETICI" and "sunucu" in hata.detail["mesaj"].lower()
    assert not any("INSERT INTO parola_sifirlama_talepleri" in " ".join(c.args[0].split()) for c in cursor.execute.call_args_list)


def test_yonetici_olmayan_hesap_icin_talep_eskisi_gibi_alinir():
    sonuc, _ = talep((2, True, "MEMUR"))
    assert sonuc["durum"] == "alindi"


def test_talep_listesi_yonetici_hesaplarini_gostermez():
    conn = MagicMock()
    conn.cursor.return_value.fetchall.return_value = []
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        sunucu.parola_sifirlama_taleplerini_listele(response=Response(), kullanici_id=10)
    sorgu = " ".join(conn.cursor.return_value.execute.call_args.args[0].split())
    assert "r.rol_adi IS DISTINCT FROM 'ADMIN'" in sorgu


# ------------------------------------------------------------------ geçici parola süresi: giriş
def giris(kullanici, parola=GECICI):
    conn = MagicMock()
    conn.cursor.return_value.fetchone.side_effect = [kullanici, (7,)]
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.sunucu.denetim_kaydi_olustur") as denetim:
        yanit = TestClient(sunucu.app).post("/api/login", json={"kullanici_adi": "ayse", "parola": parola})
    return yanit, denetim


def kullanici(ilk_giris=True, bitis=None, hash_=GECICI_HASH):
    return (11, "ayse", hash_, 3, True, 0, None, ilk_giris, "MEMUR", bitis)


def test_suresi_dolmus_gecici_parolayla_giris_reddedilir_ve_denetime_yazilir():
    yanit, denetim = giris(kullanici(bitis=datetime.now() - timedelta(minutes=1)))
    assert yanit.status_code == 403 and "süresi doldu" in yanit.json()["detail"] and "access_token" not in yanit.text
    assert denetim.call_args.kwargs["olay_turu"] == "LOGIN_FAILED"


def test_suresi_dolmamis_gecici_parola_girise_izin_verir():
    yanit, _ = giris(kullanici(bitis=datetime.now() + timedelta(hours=1)))
    assert yanit.status_code == 200 and yanit.json()["sifre_degistirme_gerekli"] is True


def test_suresiz_eski_kayit_ve_normal_parola_etkilenmez():
    assert giris(kullanici(bitis=None))[0].status_code == 200                                   # eski geçici parola: süresiz
    assert giris(kullanici(ilk_giris=False, bitis=datetime.now() - timedelta(days=30)))[0].status_code == 200   # normal parola: süre yok sayılır


def test_yanlis_parolada_sure_bilgisi_sizdirilmaz():
    yanit, _ = giris(kullanici(bitis=datetime.now() - timedelta(days=3)), parola="Yanlis-Parola-1")
    assert yanit.status_code == 401 and "süresi" not in yanit.text


def test_eski_sema_satiri_dokuz_sutunlu_olsa_da_giris_calisir():
    eski = (11, "ayse", GECICI_HASH, 3, True, 0, None, True, "MEMUR")                             # süre sütunu yok (geriye uyum)
    assert giris(eski)[0].status_code == 200


# ------------------------------------------------------------------ süre bilgisi nerede yazılır / temizlenir
def test_parola_degistirilince_sure_bilgisi_temizlenir():
    kaynak = open(sunucu.__file__, encoding="utf-8").read()
    assert "ilk_giris_mi = FALSE, gecici_parola_bitis = NULL" in kaynak


def test_yeni_kullanici_gecici_parolasi_da_sureli_ve_yanitta_sure_vardir():
    kaynak = open(sunucu.__file__, encoding="utf-8").read()
    assert "(kullanici_adi, parola_hash, rol_id, aktif_mi, ilk_giris_mi, gecici_parola_bitis)" in kaynak
    assert '"gecici_parola_gecerlilik_saat": GECICI_PAROLA_GECERLILIK_SAAT' in kaynak


def test_gecerlilik_suresi_varsayilan_48_saat_ve_sql_guvenli_tamsayi():
    assert guvenlik.GECICI_PAROLA_GECERLILIK_SAAT >= 1
    assert guvenlik.GECICI_PAROLA_BITIS_SQL == f"CURRENT_TIMESTAMP + INTERVAL '{guvenlik.GECICI_PAROLA_GECERLILIK_SAAT} hours'"
    assert str(guvenlik.GECICI_PAROLA_GECERLILIK_SAAT).isdigit()                                  # SQL'e gömülen değer yalnızca rakam


# ------------------------------------------------------------------ pencerelerde süre bilgisi
def test_gecici_parola_penceresi_gecerlilik_suresini_gosterir(tkys_qapplication):
    from client.gecici_parola_dialog import GeciciParolaDialog
    d = GeciciParolaDialog("ayse", "Pw-123456", gecerlilik_saat=48)
    assert "48 saat geçerlidir" in d.lbl_not.text()
    d.close()
    d2 = GeciciParolaDialog("ayse", "Pw-123456")                                                  # eski çağrı biçimi bozulmaz
    assert "saat geçerlidir" not in d2.lbl_not.text()
    d2.close()


def test_talep_penceresi_yonetici_hesabi_mesajini_gosterir():
    from client.parola_talebi_dialog import ParolaTalebiDialog
    assert "HESAP_YONETICI" in ParolaTalebiDialog.BILINEN_HATA_KODLARI
    yanit = MagicMock()
    yanit.json.return_value = {"detail": {"kod": "HESAP_YONETICI", "mesaj": "Bu bir yönetici hesabı."}}
    assert ParolaTalebiDialog._bilinen_hata_mesaji(yanit) == "Bu bir yönetici hesabı."
