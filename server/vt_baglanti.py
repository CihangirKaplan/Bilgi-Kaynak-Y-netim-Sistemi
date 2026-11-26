"""Veritabanı bağlantısı açar; isteği yapan istemcinin adresini oturum ayarı olarak bağlantıya iliştirir.

Denetim tablosundaki tetikleyici (`denetim_istemci_adresi_yaz`) bu ayarı `denetim_kayitlari.istemci_adresi` sütununa yazar; böylece
denetim kaydı yazan her kod yolu (hangi ucun yazdığına bakılmadan) istemci adresini taşır. İstek bağlamı dışında (betikler, testler)
ayar eklenmez ve bağlantı eskisi gibi açılır.
"""
import atexit
import os
import re
import threading
import time
from contextvars import ContextVar

import psycopg2
import psycopg2.extensions

_istemci_adresi: ContextVar[str | None] = ContextVar("tkys_istemci_adresi", default=None)
_GECERLI_ADRES = re.compile(r"^[0-9A-Fa-f:.]{2,45}$")      # yalnızca IPv4/IPv6 karakterleri (bağlantı seçeneğine kontrolsüz metin girmesin)


def adresi_ayarla(adres):
    """Geçerli bir IP adresi değilse None sayar. Geri alma için ContextVar belirtecini döndürür."""
    temiz = adres if isinstance(adres, str) and _GECERLI_ADRES.match(adres) else None
    return _istemci_adresi.set(temiz)


def adresi_sifirla(belirtec):
    _istemci_adresi.reset(belirtec)


def mevcut_adres():
    return _istemci_adresi.get()


# ---------------------------------------------------------------------------------------------------------------------------------
# Bağlantı havuzu
#
# Her istekte yeni PostgreSQL bağlantısı açmak (özellikle Windows'ta ayrı işlem + parola doğrulaması) istek başına onlarca ms tutar ve
# bir istek 2-3 bağlantı açar. Kapatılan bağlantıları atmak yerine boşta bekletip yeniden kullanıyoruz. Çağıran kod değişmez: `conn.close()`
# bağlantıyı gerçekten kapatmaz, temizleyip havuza geri verir.
#
#   * Boşta tutulan bağlantı sayısı TKYS_DB_HAVUZ_BOYUTU ile ayarlanır (varsayılan 10; 0 = havuz kapalı, eski davranış).
#   * Havuz sınırı eşzamanlı bağlantıyı SINIRLAMAZ: boşta bağlantı yoksa yenisi açılır (eskisi gibi); fazlası dönüşte kapatılır.
#   * Havuza dönen bağlantıda açık işlem geri alınır, "autocommit" sıfırlanır; böylece bir isteğin durumu diğerine sızmaz.
#   * İstemci adresi (denetim kaydı için) her kullanımda doğru değere ayarlanır.
#   * Uzun süre boşta kalan bağlantı kullanılmadan önce yoklanır; ölmüşse (sunucu yeniden başlamış vb.) atılıp yenisi açılır.
# ---------------------------------------------------------------------------------------------------------------------------------
HAVUZ_ORTAM_ADI = "TKYS_DB_HAVUZ_BOYUTU"
VARSAYILAN_HAVUZ_BOYUTU = 10
YOKLAMA_ESIGI_SN = 5.0          # bu süreden uzun boşta kalan bağlantı kullanılmadan önce SELECT 1 ile yoklanır
BAGLANTI_OMRU_SN = 1800.0       # bu kadar eski bağlantı yenilenir


def havuz_boyutu() -> int:
    """Boşta tutulacak bağlantı sayısı (0 = havuz kapalı). Geçersiz değerde varsayılan kullanılır."""
    ham = os.getenv(HAVUZ_ORTAM_ADI)
    if ham is None or not str(ham).strip():
        return VARSAYILAN_HAVUZ_BOYUTU
    try:
        return max(int(str(ham).strip()), 0)
    except ValueError:
        return VARSAYILAN_HAVUZ_BOYUTU


class HavuzluBaglanti(psycopg2.extensions.connection):
    """`close()` bağlantıyı kapatmaz, havuza geri verir (havuz yoksa normal kapanır)."""

    havuz = None
    havuzda = False
    dogum = 0.0
    adres = None

    def close(self):
        havuz = self.havuz
        if havuz is None:
            psycopg2.extensions.connection.close(self)
        else:
            havuz.geri_ver(self)

    def gercekten_kapat(self):
        try:
            psycopg2.extensions.connection.close(self)
        except Exception:
            pass


class _Havuz:
    def __init__(self, ayarlar: dict, boyut: int):
        self.ayarlar = ayarlar
        self.boyut = boyut
        self.kilit = threading.Lock()
        self.bosta = []                          # [(bağlantı, son kullanım zamanı)]; son eklenen önce kullanılır
        self.pid = os.getpid()

    def _catal_kontrolu(self):
        """Süreç çatallandıysa (fork) üst sürecin bağlantıları bu süreçte kullanılmaz; ortak soketi bozmamak için kapatılmaz, bırakılır."""
        if self.pid != os.getpid():
            self.bosta = []
            self.pid = os.getpid()

    def _yeni(self, adres):
        ayarlar = {**self.ayarlar, "options": f"-c tkys.istemci_adresi={adres}"} if adres else self.ayarlar
        conn = psycopg2.connect(**ayarlar, connection_factory=HavuzluBaglanti)
        conn.havuz = self
        conn.dogum = time.monotonic()
        conn.adres = adres
        return conn

    @staticmethod
    def _canli_mi(conn, son_kullanim) -> bool:
        if conn.closed:
            return False
        simdi = time.monotonic()
        if simdi - conn.dogum > BAGLANTI_OMRU_SN:
            return False
        if simdi - son_kullanim > YOKLAMA_ESIGI_SN:
            try:
                conn.autocommit = True                  # yoklama açık işlem bırakmasın
                try:
                    with conn.cursor() as imlec:
                        imlec.execute("SELECT 1")
                finally:
                    conn.autocommit = False
            except Exception:
                return False
        return True

    @staticmethod
    def _adresi_ayarla(conn, adres):
        """Denetim tetikleyicisinin okuduğu oturum ayarını bu isteğin adresine getirir (yalnızca değiştiyse)."""
        if conn.adres == adres:
            return
        conn.autocommit = True                          # işlem içinde yapılan ayar sonraki geri almayla kaybolurdu
        try:
            with conn.cursor() as imlec:
                imlec.execute("SELECT set_config('tkys.istemci_adresi', %s, false)", (adres or "",))
        finally:
            conn.autocommit = False
        conn.adres = adres

    def al(self, adres):
        while True:
            with self.kilit:
                self._catal_kontrolu()
                oge = self.bosta.pop() if self.bosta else None
            if oge is None:
                return self._yeni(adres)
            conn, son_kullanim = oge
            conn.havuzda = False
            if self._canli_mi(conn, son_kullanim):
                try:
                    self._adresi_ayarla(conn, adres)
                    return conn
                except Exception:
                    pass
            conn.gercekten_kapat()

    def geri_ver(self, conn):
        if conn.havuzda:                                # aynı bağlantı iki kez kapatılırsa havuza iki kez girmez
            return
        try:
            if conn.closed:
                return
            durum = conn.get_transaction_status()
            if durum == psycopg2.extensions.TRANSACTION_STATUS_UNKNOWN:
                conn.gercekten_kapat()
                return
            if durum != psycopg2.extensions.TRANSACTION_STATUS_IDLE:
                conn.rollback()                         # açık/bozuk işlem bir sonraki isteğe taşınmaz
            if conn.autocommit:
                conn.autocommit = False
        except Exception:
            conn.gercekten_kapat()
            return
        with self.kilit:
            self._catal_kontrolu()
            if len(self.bosta) < self.boyut:
                conn.havuzda = True
                self.bosta.append((conn, time.monotonic()))
                return
        conn.gercekten_kapat()

    def bosalt(self):
        with self.kilit:
            bosta, self.bosta = self.bosta, []
        for conn, _ in bosta:
            conn.havuzda = False
            conn.gercekten_kapat()


_havuzlar: dict = {}
_havuzlar_kilidi = threading.Lock()


def _havuz_al(ayarlar: dict, boyut: int) -> _Havuz:
    anahtar = tuple(sorted((str(k), str(v)) for k, v in ayarlar.items()))
    with _havuzlar_kilidi:
        havuz = _havuzlar.get(anahtar)
        if havuz is None:
            havuz = _havuzlar[anahtar] = _Havuz(dict(ayarlar), boyut)
        havuz.boyut = boyut
        return havuz


def havuzlari_bosalt():
    """Boşta bekleyen tüm bağlantıları kapatır (süreç kapanırken ve testlerde)."""
    with _havuzlar_kilidi:
        havuzlar = list(_havuzlar.values())
        _havuzlar.clear()
    for havuz in havuzlar:
        havuz.bosalt()


atexit.register(havuzlari_bosalt)


def vt_baglan(ayarlar: dict):
    adres = _istemci_adresi.get()
    boyut = havuz_boyutu()
    if boyut <= 0:                                      # havuz kapalı: eski davranış
        if adres:
            ayarlar = {**ayarlar, "options": f"-c tkys.istemci_adresi={adres}"}
        return psycopg2.connect(**ayarlar)
    return _havuz_al(ayarlar, boyut).al(adres)
