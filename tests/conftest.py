"""
TKYS QA-001 #186
Gercek PostgreSQL entegrasyon testleri icin merkezi guvenlik kontrolu.
"""

import gc
import os

import psycopg2
import pytest


TEST_DB = "crkys_alembic_test"

IZINLI_HOSTLAR = {
    "localhost",
    "127.0.0.1",
    "::1",
    "",
}

POSTGRESQL_TEST_DOSYALARI = {
    "test_rezervasyon_psikolog_yaris_pg.py",
    "test_oda_etkinlikleri_rbac.py",
    "test_oda_etkinlikleri_eszamanlilik.py",
    "test_oda_etkinlikleri_ters_api_cakisma.py",
    "test_oda_etkinlikleri_psikolog_odasi_pg.py",
    "test_oda_etkinlikleri_es_zamanli_guncelleme.py",
    "test_oda_etkinlikleri_cok_gun_rapor.py",
    "test_oda_etkinlikleri_cok_gun_duzenleme.py",
    "test_oda_etkinlikleri_bes_gun_gercek_pg.py",
    "test_oda_etkinlikleri_bagimsiz_oturumlar.py",
    "test_oda_etkinlikleri_api_cakisma.py",
    "test_veri_butunlugu_pg_quality.py",
    "test_denetim_silinen_veri_pg_quality.py",
    "test_giris_siniri_pg_quality.py",
    "test_performans_indeksleri_pg_quality.py",
    "test_rapor_tutarliligi_pg_quality.py",
    "test_son_paket_pg_quality.py",
    "test_liste_pencereleme_pg_quality.py",
    "test_ogrenci_yonetimi_postgresql_quality.py",
    "test_psikolog_planli_randevu_pg_quality.py",
    "test_faaliyet_turleri_postgresql_quality.py",
    "test_kullanici_personel_postgresql_quality.py",
    "test_parola_sifirlama_pg_quality.py",
    "test_transaction_quality.py",
    "test_randevu_transaction_quality.py",
    "test_randevu_eszamanlilik_quality.py",
    "test_audit_postgresql_quality.py",
    "test_cihaz_odalari_psikolog_haric_pg_quality.py",
    "test_api_audit_rollback_quality.py",
    "test_admin_tum_izinler_pg_quality.py",
    "test_kisisel_veri_ayrimi_pg_quality.py",
    "test_randevu_iptal_durum_pg_quality.py",
    "test_yas_terapi_gorusme_pg_quality.py",
    "test_randevu_raporu_pg_quality.py",
    "test_psikolog_pasif_oda_pg_quality.py",
    "test_vt_havuzu_pg_quality.py",
    "test_oda_kullanimi_pg_quality.py",
    "test_girdi_fuzz_pg_quality.py",
    "test_sema_dogrulama_pg_quality.py",
    "test_yabanci_anahtar_indeks_pg_quality.py",
    "test_kisitli_kullanici_pg_quality.py",
    "test_gecici_parola_suresi_pg_quality.py",
    "test_cihaz_odasi_atama_pg_quality.py",
}


@pytest.fixture(autouse=True)
def postgresql_test_guvenligi(request, monkeypatch):
    """
    Gercek PostgreSQL testlerinde yanlis veritabanina
    baglanilmasini engeller.
    """

    dosya_adi = request.node.path.name
    test_adi = request.node.name

    gercek_pg_testi = (
        dosya_adi in POSTGRESQL_TEST_DOSYALARI
        or (
            dosya_adi == "test_cihaz_rezervasyon_eszamanlilik.py"
            and test_adi == "test_gercek_eszamanli_cihaz_rezervasyonu"
        )
    )

    if not gercek_pg_testi:
        return

    # Testlerin yanlislikla calistirilmasini engelle.
    if os.getenv("TKYS_PG_TEST_ONAY") != "EVET":
        pytest.fail(
            "Gercek PostgreSQL testleri kapali. "
            "Calistirmak icin TKYS_PG_TEST_ONAY=EVET gerekli."
        )

    from server.sunucu import VT_AYARLARI

    db_adi = VT_AYARLARI.get("dbname")
    db_host = str(VT_AYARLARI.get("host") or "").lower().strip()

    if db_adi != TEST_DB:
        pytest.fail(
            "Guvenlik engeli: Yalnizca "
            f"{TEST_DB} veritabaninda test yapilabilir."
        )

    if db_host not in IZINLI_HOSTLAR:
        pytest.fail(
            "Guvenlik engeli: Gercek PostgreSQL testleri "
            "yalnizca yerel sunucuda calisabilir."
        )

    orijinal_connect = psycopg2.connect

    def guvenli_connect(*args, **kwargs):
        # Bu testlerde baglanti parametreleri acik verilmelidir.
        if args or kwargs.get("dsn"):
            raise RuntimeError(
                "Guvenlik engeli: DSN ile baglantiya izin verilmiyor."
            )

        hedef_db = kwargs.get("dbname")
        hedef_host = str(kwargs.get("host") or "").lower().strip()

        if hedef_db != TEST_DB:
            raise RuntimeError(
                "Guvenlik engeli: Yanlis veritabani baglantisi."
            )

        if hedef_host not in IZINLI_HOSTLAR:
            raise RuntimeError(
                "Guvenlik engeli: Yerel olmayan PostgreSQL sunucusu."
            )

        conn = orijinal_connect(**kwargs)

        try:
            # Gercekte baglanilan veritabanini dogrula.
            with conn.cursor() as cursor:
                cursor.execute("SELECT current_database();")
                aktif_db = cursor.fetchone()[0]

            if aktif_db != TEST_DB:
                raise RuntimeError(
                    "Guvenlik engeli: Beklenmeyen aktif veritabani."
                )

            conn.rollback()
            return conn

        except Exception:
            conn.close()
            raise

    monkeypatch.setattr(psycopg2, "connect", guvenli_connect)


@pytest.fixture(autouse=True)
def veritabani_havuzu_testlerde_kapali(monkeypatch):
    """Bağlantı havuzu üretimde varsayılan açıktır; testler her çağrıda `psycopg2.connect`'in doğrudan çağrıldığını varsayar
    (sahte bağlantılar, çağrı sayıları). Havuzu sınayan testler değeri kendileri açar.
    Tüm testleri havuz AÇIK koşturmak için: TKYS_TEST_HAVUZ_BOYUTU=10 (yerel doğrulama)."""
    monkeypatch.setenv("TKYS_DB_HAVUZ_BOYUTU", os.getenv("TKYS_TEST_HAVUZ_BOYUTU", "0"))
    yield
    from server import vt_baglanti
    vt_baglanti.havuzlari_bosalt()


@pytest.fixture(autouse=True)
def cop_toplama_ana_is_parcaciginda():
    """Çöp toplamayı testin içinde kapatır, test bitince ana iş parçacığında çalıştırır.

    PySide6'da döngüsel referanslı bir pencere/widget, çöp toplayıcı başka bir iş
    parçacığında (ör. FastAPI TestClient) çalışınca Shiboken'ın
    `runDeletionInMainThread` yolunda aralıklı "Segmentation fault" ile çöküyor
    (CI'da exit 139). Bu yüzden Qt nesneleri yalnızca ana iş parçacığında toplanır.
    """
    gc.disable()
    try:
        yield
    finally:
        gc.enable()
        gc.collect()


# TKYS ortak QApplication yasam dongusu
@pytest.fixture(scope="session", autouse=True)
def tkys_qapplication():
    """Qt kullanan testlerde QApplication referansını korur."""
    from PySide6.QtWidgets import QApplication

    uygulama = QApplication.instance()

    if uygulama is None:
        uygulama = QApplication([])

    yield uygulama


@pytest.fixture(autouse=True)
def randevu_formu_tarih_alt_sinirini_sabitle(monkeypatch):
    """Randevu formunun tarih alt sınırını (geçmiş tarihe randevu verilemez) testlerde çok eski bir tarihe sabitler.

    Sabit tarihli arayüz testleri (ör. Aralık 2026) zamanla geçmişte kalıp tarih seçicide reddedilmesin diye. Alt sınırı sınayan
    testler kendi değerini monkeypatch eder. Yalnızca testin zaten içe aktardığı durumda uygulanır."""
    import sys

    modul = sys.modules.get("client.randevu_ekranlari")
    if modul is None:
        return
    from PySide6.QtCore import QDate

    monkeypatch.setattr(modul, "bugunun_tarihi", lambda: QDate(2000, 1, 1))


# Giriş sınırı testlerinin bulunduğu modüller: bunlarda sınırlayıcı gerçek çalışır.
GIRIS_SINIRI_TEST_MODULLERI = {"test_giris_siniri", "test_giris_siniri_pg_quality"}


@pytest.fixture(autouse=True)
def giris_siniri_diger_testlerde_kapali(request, monkeypatch):
    """IP bazlı giriş sınırı, kendi testleri dışında devre dışıdır.

    Diğer testler psycopg2.connect'i sahte bağlantıyla değiştirir; sınırlayıcı o sahte bağlantıyı gerçek sanıp girişi
    engellemesin. Üretimde sınırlayıcı her zaman açıktır.
    """
    if request.module.__name__.split(".")[-1] in GIRIS_SINIRI_TEST_MODULLERI:
        return
    monkeypatch.setattr("server.giris_siniri.istemci_anahtari", lambda istek: None)


# "Hangi türde kaydetmek istersiniz?" penceresi modaldır; testte kimse tıklamayacağı için varsayılan olarak Excel seçilir.
# Pencerenin kendi testleri (ve PDF yolunu deneyenler) bicim_sec'i kendileri yamar.
BICIM_SECIMI_GERCEK_TEST_MODULLERI = {"test_rapor_cikti_pdf"}


@pytest.fixture(autouse=True)
def dis_aktar_bicim_secimi_testte_excel(request, monkeypatch):
    import sys
    modul = sys.modules.get("client.rapor_cikti")
    if modul is None or request.module.__name__.split(".")[-1] in BICIM_SECIMI_GERCEK_TEST_MODULLERI:
        return
    monkeypatch.setattr(modul, "bicim_sec", lambda pencere=None, baslik="Dışa Aktar": "xlsx")
