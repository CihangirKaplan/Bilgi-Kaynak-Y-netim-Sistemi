"""
Psikolog oda yetkileri (kural: her psikologun en az bir odası olmalı; odanın psikoloğu olmak zorunda değil).

- GET/PUT /api/kullanicilar/{id}/odalar            (ROL_ATAMA_DEGISTIRME)
- GET /api/oda-psikolog-atamalari                  (Oda Yönetimi ekranını görenler: ODA_EKLE + ODA_DUZENLE)
- Psikolog oluştururken en az bir aktif oda zorunlu; diğer rollere oda verilemez
- Bir psikologun tek aktif odası pasife alınamaz
- /api/personel ekranda görünen rol adını (gorunen_ad) da döndürür
- Cihaz rezervasyonu için kullanılan (süren ya da gelecekteki rezervasyonu olan) oda psikologa atanamaz (409 + uyarı metni)
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from server.modeller import KullaniciOlusturModeli, OdaGuncelleModeli
from server.sunucu import app, kullanici_olustur, mevcut_kullanici_id, oda_guncelle, personel_listele


@pytest.fixture(autouse=True)
def giris_yapmis_kullanici():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def baglanti(fetchone=(), fetchall=()):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = list(fetchone)
    cursor.fetchall.side_effect = list(fetchall)
    return conn, cursor


def istek(metot, yol, conn, **kwargs):
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with TestClient(app) as istemci:
            return getattr(istemci, metot)(yol, **kwargs)


def sorgular(cursor):
    return [c.args[0] for c in cursor.execute.call_args_list]


def yazma_sorgusu_var_mi(cursor):
    return any(s.strip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for s in sorgular(cursor))


# ------------------------------------------------------------------ GET /odalar
def test_oda_yetkilerini_getir_izin_yoksa_403():
    conn, _ = baglanti(fetchone=[(0,)])
    assert istek("get", "/api/kullanicilar/11/odalar", conn).status_code == 403


def test_oda_yetkilerini_getir_kullanici_yoksa_404():
    conn, _ = baglanti(fetchone=[(1,), None])
    assert istek("get", "/api/kullanicilar/99/odalar", conn).status_code == 404


def test_oda_yetkisi_psikolog_olmayana_tanimlanamaz():
    conn, _ = baglanti(fetchone=[(1,), ("MEMUR",)])
    yanit = istek("get", "/api/kullanicilar/14/odalar", conn)
    assert yanit.status_code == 422
    assert "psikolog" in yanit.json()["detail"]


@pytest.mark.parametrize("rol_adi", ["PSIKOLOG", "Psikolog"])
def test_oda_yetkilerini_getir(rol_adi):
    conn, _ = baglanti(fetchone=[(1,), (rol_adi,)], fetchall=[[(2,), (3,)]])
    yanit = istek("get", "/api/kullanicilar/11/odalar", conn)
    assert yanit.status_code == 200
    assert yanit.json() == {"kullanici_id": 11, "oda_idleri": [2, 3]}


# ------------------------------------------------------------------ PUT /odalar
@pytest.mark.parametrize("govde", [{"oda_idleri": []}, {"oda_idleri": "2"}, {}, {"oda_idleri": ["a"]}])
def test_oda_yetkisi_bos_ya_da_gecersiz_liste_422(govde):
    conn, cursor = baglanti(fetchone=[(1,)])
    assert istek("put", "/api/kullanicilar/11/odalar", conn, json=govde).status_code == 422
    assert not yazma_sorgusu_var_mi(cursor)


def test_oda_yetkisi_guncelleme_izin_yoksa_403():
    conn, cursor = baglanti(fetchone=[(0,)])
    assert istek("put", "/api/kullanicilar/11/odalar", conn, json={"oda_idleri": [2]}).status_code == 403
    assert not yazma_sorgusu_var_mi(cursor)


def test_oda_yetkisi_psikolog_olmayana_yazilamaz():
    conn, cursor = baglanti(fetchone=[(1,), ("ADMIN",)])
    assert istek("put", "/api/kullanicilar/13/odalar", conn, json={"oda_idleri": [2]}).status_code == 422
    assert not yazma_sorgusu_var_mi(cursor)
    conn.commit.assert_not_called()


def test_cihaz_rezervasyonlu_odaya_yetki_verilemez_ve_uyari_doner():
    conn, cursor = baglanti(fetchone=[(1,), ("PSIKOLOG",)], fetchall=[[(2,), (3,)], [("EEG Odası", 2)]])
    yanit = istek("put", "/api/kullanicilar/11/odalar", conn, json={"oda_idleri": [2, 3]})
    assert yanit.status_code == 409
    detay = yanit.json()["detail"]
    assert "EEG Odası (2 rezervasyon)" in detay and "psikologa atanamaz" in detay and "iptal edin" in detay
    assert not yazma_sorgusu_var_mi(cursor)                                                 # atama hiç yazılmaz
    conn.commit.assert_not_called()
    conn.rollback.assert_called()


def test_oda_yetkisi_guncellenirken_mevcut_atamalar_denetimden_muaf_tutulur():
    conn, cursor = baglanti(fetchone=[(1,), ("PSIKOLOG",)], fetchall=[[(2,), (3,)], [], [], [], [], [(2,), (3,)]])
    assert istek("put", "/api/kullanicilar/11/odalar", conn, json={"oda_idleri": [2, 3]}).status_code == 200
    sql, parametreler = next(c.args for c in cursor.execute.call_args_list if "FROM cihaz_rezervasyonlari cr" in c.args[0])
    assert parametreler == ([2, 3], 11)                                                      # 11 numaralı psikologa zaten atanmış odalar sayılmaz
    assert "NOT EXISTS (SELECT 1 FROM psikolog_odalar po" in sql and "po.kullanici_id = %s" in sql


def test_cihaz_rezervasyonu_denetimi_iptalleri_ve_biten_rezervasyonlari_saymaz():
    conn, cursor = baglanti(fetchone=[(1,), ("PSIKOLOG",)], fetchall=[[(2,)], [], [], [], [], [(2,)]])
    istek("put", "/api/kullanicilar/11/odalar", conn, json={"oda_idleri": [2]})
    sql = next(c.args[0] for c in cursor.execute.call_args_list if "FROM cihaz_rezervasyonlari cr" in c.args[0])
    assert "COALESCE(cr.iptal_edildi_mi, FALSE) = FALSE" in sql and "cr.bitis_zamani > NOW()" in sql
    assert "cr.kullanilacak_oda_id = ANY(%s)" in sql


def test_planli_randevusu_olan_odayi_kaldirmak_409_verir_ve_uyari_doner():
    conn, cursor = baglanti(fetchone=[(1,), ("PSIKOLOG",)], fetchall=[[(2,)], [], [], [("Görüşme Odası-1", 2)]])
    yanit = istek("put", "/api/kullanicilar/11/odalar", conn, json={"oda_idleri": [2]})
    assert yanit.status_code == 409
    detay = yanit.json()["detail"]
    assert "Görüşme Odası-1 (2 randevu)" in detay and "bugün ve sonrası için planlı randevu var" in detay and "Tamamlandı / Gelmedi" in detay
    assert not yazma_sorgusu_var_mi(cursor)                                                 # atama değişmez
    conn.commit.assert_not_called()
    conn.rollback.assert_called()


def test_planli_randevu_denetimi_yalnizca_kaldirilan_aktif_odalarin_bugun_ve_sonrasini_sayar():
    conn, cursor = baglanti(fetchone=[(1,), ("PSIKOLOG",)], fetchall=[[(2,), (3,)], [], [], [], [], [(2,), (3,)]])
    istek("put", "/api/kullanicilar/11/odalar", conn, json={"oda_idleri": [2, 3]})
    sql, parametreler = next(c.args for c in cursor.execute.call_args_list if "FROM randevular r" in c.args[0])
    assert parametreler == (11, [2, 3])                                                      # psikolog ve yeni oda kümesi
    assert "r.durum = 'PLANLANDI'" in sql and "r.baslangic_zamani >= CURRENT_DATE" in sql  # bugünkü randevu da engeller; dünden öncesi ve iptaller engellemez
    assert "r.oda_id <> ALL(%s)" in sql and "o.aktif_mi = TRUE" in sql                        # yalnızca kaldırılan aktif odalar
    assert "EXISTS (SELECT 1 FROM psikolog_odalar po WHERE po.kullanici_id = p.kullanici_id AND po.oda_id = r.oda_id)" in sql   # şu an atanmış odalar


def test_pasif_ya_da_olmayan_odaya_yetki_verilemez():
    conn, cursor = baglanti(fetchone=[(1,), ("PSIKOLOG",)], fetchall=[[(2,)]])  # 3 numaralı oda aktif değil
    yanit = istek("put", "/api/kullanicilar/11/odalar", conn, json={"oda_idleri": [2, 3]})
    assert yanit.status_code == 422
    assert "aktif" in yanit.json()["detail"]
    assert not yazma_sorgusu_var_mi(cursor)
    conn.commit.assert_not_called()
    conn.rollback.assert_called()


def test_oda_yetkileri_kumeye_esitlenir_ve_denetim_kaydi_dusulur():
    conn, cursor = baglanti(fetchone=[(1,), ("PSIKOLOG",)], fetchall=[[(2,), (3,)], [], [], [], [], [(2,), (3,)]])      # 2. liste: cihaz rezervasyonlu oda yok, 3. liste: kaldırılan odalarda planlı randevu yok
    yanit = istek("put", "/api/kullanicilar/11/odalar", conn, json={"oda_idleri": [3, 2, 3]})

    assert yanit.status_code == 200
    assert yanit.json() == {"durum": "basarili", "kullanici_id": 11, "oda_idleri": [2, 3]}

    tum = cursor.execute.call_args_list
    dogrulama = next(c for c in tum if "FROM odalar WHERE oda_id = ANY" in c.args[0])
    assert dogrulama.args[1] == ([2, 3],)  # tekrarlar atılmış, sıralı

    silme = next(c for c in tum if c.args[0].strip().upper().startswith("DELETE FROM PSIKOLOG_ODALAR"))
    assert "o.aktif_mi = TRUE" in silme.args[0]  # pasif odalardaki atamalara dokunulmaz
    assert silme.args[1] == (11, [2, 3])

    eklemeler = [c.args[1] for c in tum if c.args[0].strip().upper().startswith("INSERT INTO PSIKOLOG_ODALAR")]
    assert eklemeler == [(11, 2), (11, 3)]

    denetim = next(c for c in tum if "denetim_kayitlari" in c.args[0])
    assert denetim.args[1][:4] == (5, "UPDATE", "psikolog_odalar", 11)
    conn.commit.assert_called_once()


# ------------------------------------------------------------------ Oda Yönetimi: Psikologlar sütunu
def test_atamalar_ucu_iki_izin_de_gerekir():
    conn, cursor = baglanti(fetchone=[(1,)])  # 2 izinden yalnızca 1'i var
    assert istek("get", "/api/oda-psikolog-atamalari", conn).status_code == 403
    sorgu, parametreler = cursor.execute.call_args_list[0].args
    assert "izin_var = 1" in sorgu
    assert parametreler == (5, ["ODA_DUZENLE", "ODA_EKLE"])
    assert len(cursor.execute.call_args_list) == 1


def test_atamalar_ucu_odaya_gore_gruplar():
    conn, _ = baglanti(
        fetchone=[(2,)],
        fetchall=[[(2, "psikolog1"), (2, "psikolog2"), (3, "reyhan")]],
    )
    yanit = istek("get", "/api/oda-psikolog-atamalari", conn)
    assert yanit.status_code == 200
    assert yanit.json() == [
        {"oda_id": 2, "psikologlar": ["psikolog1", "psikolog2"]},
        {"oda_id": 3, "psikologlar": ["reyhan"]},
    ]


def test_atamalar_ucu_yalnizca_aktif_kullanicilari_listeler_psikologsuz_oda_yok_sayilir():
    conn, cursor = baglanti(fetchone=[(2,)], fetchall=[[]])
    yanit = istek("get", "/api/oda-psikolog-atamalari", conn)
    assert yanit.json() == []  # cihaz odaları listede olmayabilir; bu bir hata değildir
    assert "k.aktif_mi = TRUE" in sorgular(cursor)[-1]


def test_atamalar_ucu_yalnizca_su_an_psikolog_rolundeki_kullanicilari_listeler():
    """Psikolog olup sonradan başka role geçen kişinin (eski kayıt kalmış olsa bile) adı Oda Yönetimi'nde görünmez."""
    conn, cursor = baglanti(fetchone=[(2,)], fetchall=[[(2, "psikolog1")]])
    istek("get", "/api/oda-psikolog-atamalari", conn)
    sql = " ".join(sorgular(cursor)[-1].split())
    assert "JOIN roller r ON r.rol_id = k.rol_id" in sql and "UPPER(r.rol_adi) = 'PSIKOLOG'" in sql


# ------------------------------------------------------------------ Psikolog oluşturma kuralı
def sahte_olusturma_veritabani(rol, aktif_odalar=(1, 2, 3), rezervasyonlu=None):
    """kullanici_olustur için sahte veritabanı: istenen odalardan yalnızca aktif olanlar döner.

    rezervasyonlu: {oda_id: oda_adi}; istenen odalar arasında bunlar varsa cihaz rezervasyonu sorgusu o odaları döndürür."""
    rezervasyonlu = rezervasyonlu or {}
    conn = MagicMock()
    cursor = conn.cursor.return_value
    durum = {"sorgu": "", "parametreler": None}

    def execute(sorgu, parametreler=None):
        durum["sorgu"] = sorgu.upper()
        durum["parametreler"] = parametreler

    def fetchone():
        s = durum["sorgu"]
        if "FROM KULLANICILAR K JOIN ROLLER R" in s:
            return ("ADMIN",)
        if "ROL_IZINLERI" in s:
            return (1,)
        if "FROM ROLLER WHERE ROL_ID" in s:
            return (rol,)
        if "INSERT INTO KULLANICILAR" in s:
            return (25,)
        if "INSERT INTO PERSONEL" in s:
            return (15,)
        return None

    def fetchall():
        if "FROM ODALAR" in durum["sorgu"]:
            return [(o,) for o in durum["parametreler"][0] if o in aktif_odalar]
        if "FROM CIHAZ_REZERVASYONLARI" in durum["sorgu"]:
            return [(ad, 1) for oda, ad in rezervasyonlu.items() if oda in durum["parametreler"][0]]
        return []

    cursor.execute.side_effect = execute
    cursor.fetchone.side_effect = fetchone
    cursor.fetchall.side_effect = fetchall
    return conn, cursor


def olustur(rol, rol_id, oda_idleri, aktif_odalar=(1, 2, 3), **ekstra):
    conn, cursor = sahte_olusturma_veritabani(rol, aktif_odalar)
    yeni = KullaniciOlusturModeli(kullanici_adi="yeni_kisi", rol_id=rol_id, oda_idleri=oda_idleri, **ekstra)
    with patch("server.sunucu.psycopg2.connect", return_value=conn), \
            patch("server.sunucu.gecici_parola_uret", return_value="Gecici123!"), \
            patch("server.sunucu.parola_hashle", return_value="hash"):
        try:
            sonuc = kullanici_olustur(yeni_kullanici=yeni, kullanici_id=10)
            hata = None
        except HTTPException as h:
            sonuc, hata = None, h
    return conn, cursor, sonuc, hata


def kullanici_eklendi_mi(cursor):
    return any(s.strip().upper().startswith("INSERT INTO KULLANICILAR") for s in sorgular(cursor))


@pytest.mark.parametrize("oda_idleri", [[], None])
def test_psikolog_odasiz_olusturulamaz(oda_idleri):
    conn, cursor, _, hata = olustur("PSIKOLOG", 1, oda_idleri)
    assert hata.status_code == 422
    assert "en az bir" in hata.detail
    assert not kullanici_eklendi_mi(cursor)
    conn.commit.assert_not_called()


def test_psikolog_pasif_ya_da_olmayan_odayla_olusturulamaz():
    conn, cursor, _, hata = olustur("PSIKOLOG", 1, [2, 9], aktif_odalar=(2,))
    assert hata.status_code == 422
    assert "aktif" in hata.detail
    assert not kullanici_eklendi_mi(cursor)


@pytest.mark.parametrize("rol, rol_id, ekstra", [
    ("MEMUR", 2, {}),
    ("DANISMA_OGRENCISI", 4, {"ad_soyad": "Ali Veli", "ogrenci_numarasi": "2021001"}),
])
def test_psikolog_olmayana_oda_verilemez(rol, rol_id, ekstra):
    conn, cursor, _, hata = olustur(rol, rol_id, [2], **ekstra)
    assert hata.status_code == 422
    assert "psikolog" in hata.detail
    assert not kullanici_eklendi_mi(cursor)


def test_psikolog_cihaz_rezervasyonlu_odayla_olusturulamaz():
    conn, cursor = sahte_olusturma_veritabani("PSIKOLOG", (1, 2, 3), rezervasyonlu={2: "EEG Odası"})
    yeni = KullaniciOlusturModeli(kullanici_adi="yeni_kisi", rol_id=1, oda_idleri=[1, 2])
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.sunucu.gecici_parola_uret", return_value="Gecici123!"), \
            patch("server.sunucu.parola_hashle", return_value="hash"):
        with pytest.raises(HTTPException) as hata:
            kullanici_olustur(yeni_kullanici=yeni, kullanici_id=10)
    assert hata.value.status_code == 409 and "EEG Odası" in hata.value.detail and "psikologa atanamaz" in hata.value.detail
    assert not kullanici_eklendi_mi(cursor)
    conn.commit.assert_not_called()


def test_psikolog_odalariyla_olusturulur_ve_odalar_kaydedilir():
    conn, cursor, sonuc, hata = olustur("PSIKOLOG", 1, [3, 2, 3])
    assert hata is None and sonuc["durum"] == "basarili"
    eklemeler = [c.args[1] for c in cursor.execute.call_args_list
                 if c.args[0].strip().upper().startswith("INSERT INTO PSIKOLOG_ODALAR")]
    assert eklemeler == [(25, 2), (25, 3)]
    conn.commit.assert_called_once()


def test_odasiz_roller_eskisi_gibi_olusturulur():
    _, cursor, sonuc, hata = olustur("MEMUR", 2, None)
    assert hata is None and sonuc["durum"] == "basarili"
    assert not any("PSIKOLOG_ODALAR" in s.upper() for s in sorgular(cursor))


# ------------------------------------------------------------------ Odayı pasife alma
def oda_guncelle_dene(degisiklik, fetchall, fetchone=((2,), (2, "Oda", 1, False))):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    fetchone = list(fetchone)
    if degisiklik.get("aktif_mi") is False and len(fetchone) == 2:
        fetchone.insert(1, (0,))                         # pasife alırken odadaki planlı randevu sayısı (0)
    cursor.fetchone.side_effect = fetchone
    cursor.fetchall.side_effect = list(fetchall)
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        try:
            sonuc = oda_guncelle(oda_id=2, oda=OdaGuncelleModeli(**degisiklik), kullanici_id=1)
            hata = None
        except HTTPException as h:
            sonuc, hata = None, h
    return conn, cursor, sonuc, hata


def test_psikologun_tek_aktif_odasi_pasife_alinamaz():
    conn, cursor, _, hata = oda_guncelle_dene({"aktif_mi": False}, fetchall=[[("psikolog1",), ("psikolog2",)]])
    assert hata.status_code == 409
    assert "psikolog1, psikolog2" in hata.detail
    assert "tek aktif odası" in hata.detail
    assert not any(s.strip().upper().startswith("UPDATE ODALAR") for s in sorgular(cursor))
    conn.commit.assert_not_called()


def test_baska_aktif_odasi_olan_psikologlar_icin_pasife_alinabilir():
    conn, cursor, sonuc, hata = oda_guncelle_dene({"aktif_mi": False}, fetchall=[[]])
    assert hata is None and sonuc["durum"] == "basarili"
    kontrol = next(s for s in sorgular(cursor) if "FROM psikolog_odalar po" in s)
    assert "NOT EXISTS" in kontrol and "o2.aktif_mi = TRUE" in kontrol
    conn.commit.assert_called_once()


@pytest.mark.parametrize("degisiklik", [{"aktif_mi": True}, {"oda_adi": "Yeni Ad"}, {"kapasite": 3}])
def test_pasife_alma_disindaki_guncellemeler_psikolog_kontrolu_yapmaz(degisiklik):
    _, cursor, sonuc, hata = oda_guncelle_dene(degisiklik, fetchall=[])
    assert hata is None and sonuc["durum"] == "basarili"
    assert not any("psikolog_odalar" in s for s in sorgular(cursor))


# ------------------------------------------------------------------ /api/personel
def personel_cagir(satirlar):
    conn = MagicMock()
    conn.cursor.return_value.fetchall.return_value = satirlar
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        return personel_listele(islem_yapan_id=1), conn.cursor.return_value


def test_personel_listesi_gorunen_adi_da_dondurur():
    sonuc, cursor = personel_cagir([(9, 11, "psikolog1", "PER-PSK-001", "PSIKOLOG", True, None, "Psikolog")])
    assert sonuc[0]["rol_adi"] == "PSIKOLOG"          # karşılaştırmalar için kod
    assert sonuc[0]["gorunen_ad"] == "Psikolog"        # ekranda gösterilecek ad
    assert "r.gorunen_ad" in sorgular(cursor)[0]


def test_personel_listesi_gorunen_ad_yoksa_rol_adina_duser():
    sonuc, _ = personel_cagir([(9, 11, "psikolog1", "PER-PSK-001", "PSIKOLOG", True, None, None)])
    assert sonuc[0]["gorunen_ad"] == "PSIKOLOG"
