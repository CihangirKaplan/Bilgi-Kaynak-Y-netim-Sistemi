"""IP bazlı giriş denemesi sınırı (giris_istek_limitleri tablosu).

Hesap bazlı kilit (5 hatada 1 dk, 10 hatada 15 dk) yalnızca VAR OLAN kullanıcı adlarını korur. Var olmayan kullanıcı
adlarıyla ya da çok sayıda hesabı sırayla deneyen biri hiç engellenmiyordu. Bu modül aynı istemciden (IP) gelen BAŞARISIZ
giriş denemelerini sayar; pencere içinde sınır aşılırsa o istemciden gelen giriş istekleri 429 ile geri çevrilir.

- Yalnızca başarısız denemeler sayılır: doğru giren kullanıcılar sınırdan etkilenmez, başarılı giriş sayacı sıfırlamaz.
- IP adresi ham saklanmaz; SHA-256 özeti anahtar olur (kişisel veri tutulmaz).
- İstemci adresi, denetim kayıtlarındakiyle aynı kaynaktan alınır (server.vt_baglanti.mevcut_adres): varsayılan olarak doğrudan bağlanan adres;
  yalnızca TKYS_GUVENILIR_VEKIL=1 ise vekilin eklediği X-Forwarded-For değeri. Böylece sunucu bir vekilin arkasındayken tüm istemciler
  tek anahtarda toplanıp birbirini kilitlemez. Başlığa varsayılan olarak güvenilmez (istemci sahteleyebilir).
- Sınırlayıcıda hata olursa giriş engellenmez (fail-open); veritabanı arızası herkesi dışarıda bırakmamalı.
"""
import hashlib
import logging

import psycopg2

from server.vt_baglanti import mevcut_adres

GUNLUK = logging.getLogger("uvicorn.error")

PENCERE_SANIYE = 300        # 5 dakikalık sayım penceresi
EN_FAZLA_BASARISIZ = 20     # pencere içinde bir istemciden en fazla bu kadar başarısız deneme
TEMIZLIK_SAAT = 1           # bu süreden eski sayaçlar silinir


def istemci_anahtari(request) -> str | None:
    """İsteğin geldiği istemci adresinin özeti; adres bilinmiyorsa None (sınır uygulanmaz)."""
    adres = mevcut_adres()                                  # istek ara katmanının belirlediği adres (vekil ayarına saygılı)
    if not adres:
        istemci = getattr(request, "client", None)
        adres = getattr(istemci, "host", None)
    if not adres:
        return None
    return hashlib.sha256(str(adres).encode("utf-8")).hexdigest()


def engel_suresi(vt_ayarlari: dict, anahtar: str | None) -> int:
    """İstemci sınırı aştıysa kalan bekleme süresi (saniye), değilse 0."""
    if not anahtar:
        return 0
    conn = None
    try:
        conn = psycopg2.connect(**vt_ayarlari)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT GREATEST(1, CEIL(EXTRACT(EPOCH FROM
                       (pencere_baslangici + make_interval(secs => %s) - NOW()))))::int
            FROM giris_istek_limitleri
            WHERE anahtar = %s AND istek_sayisi >= %s
              AND pencere_baslangici + make_interval(secs => %s) > NOW();
            """,
            (PENCERE_SANIYE, anahtar, EN_FAZLA_BASARISIZ, PENCERE_SANIYE),
        )
        satir = cursor.fetchone()
        return int(satir[0]) if satir else 0
    except Exception as hata:
        GUNLUK.warning("Giriş sınırı okunamadı (sınır uygulanmadı): %s", hata)
        return 0
    finally:
        if conn is not None:
            conn.close()


def basarisiz_girisi_kaydet(vt_ayarlari: dict, anahtar: str | None) -> None:
    """Başarısız denemeyi sayar (pencere dolduysa sayaç 1'den başlar)."""
    if not anahtar:
        return
    conn = None
    try:
        conn = psycopg2.connect(**vt_ayarlari)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO giris_istek_limitleri (anahtar, pencere_baslangici, istek_sayisi)
            VALUES (%s, NOW(), 1)
            ON CONFLICT (anahtar) DO UPDATE SET
                istek_sayisi = CASE
                    WHEN giris_istek_limitleri.pencere_baslangici + make_interval(secs => %s) <= NOW() THEN 1
                    ELSE giris_istek_limitleri.istek_sayisi + 1 END,
                pencere_baslangici = CASE
                    WHEN giris_istek_limitleri.pencere_baslangici + make_interval(secs => %s) <= NOW() THEN NOW()
                    ELSE giris_istek_limitleri.pencere_baslangici END;
            """,
            (anahtar, PENCERE_SANIYE, PENCERE_SANIYE),
        )
        cursor.execute(
            "DELETE FROM giris_istek_limitleri WHERE pencere_baslangici < NOW() - make_interval(hours => %s);",
            (TEMIZLIK_SAAT,),
        )
        conn.commit()
    except Exception as hata:
        GUNLUK.warning("Başarısız giriş sayılamadı: %s", hata)
        if conn is not None:
            conn.rollback()
    finally:
        if conn is not None:
            conn.close()
