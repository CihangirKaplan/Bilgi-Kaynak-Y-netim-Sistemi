"""Veritabanı şemasını değiştiren işler (alembic, geri yükleme) için kullanılacak kimliği seçer.

Normalde sunucu ve betikler DB_USER / DB_PASSWORD ile bağlanır. Güvenlik için sunucu, yalnızca veri okuyup yazabilen
kısıtlı bir kullanıcıyla (bkz. scripts/uygulama_kullanicisi_olustur.py) çalıştırılabilir; bu kullanıcı tablo
oluşturamaz/silemez. Şemayı güncelleyen işler (alembic upgrade, yedekten geri yükleme) ise tam yetkili bir kullanıcı ister;
onun bilgileri .env içinde DB_MIGRATION_USER ve DB_MIGRATION_PASSWORD olarak verilir.

Bu ikisi tanımlı değilse eski davranış sürer (hepsi DB_USER ile çalışır), yani mevcut kurulumlar bozulmaz.
"""

import os


class SemaKimligiHatasi(Exception):
    """.env içindeki şema kullanıcısı ayarı eksik ya da tutarsız."""


def sema_kimligi(ortam=None):
    """(kullanıcı, parola) döndürür: DB_MIGRATION_* varsa o, yoksa DB_USER / DB_PASSWORD."""
    ortam = os.environ if ortam is None else ortam
    kullanici = (ortam.get("DB_MIGRATION_USER") or "").strip()
    parola = ortam.get("DB_MIGRATION_PASSWORD")

    if kullanici:
        if not parola:
            raise SemaKimligiHatasi(
                "DB_MIGRATION_USER tanımlı ama DB_MIGRATION_PASSWORD boş. "
                ".env dosyasına şema kullanıcısının parolasını da yazın."
            )
        return kullanici, parola
    if parola:
        raise SemaKimligiHatasi(
            "DB_MIGRATION_PASSWORD tanımlı ama DB_MIGRATION_USER boş. "
            ".env dosyasına şema kullanıcısının adını da yazın."
        )
    return ortam.get("DB_USER"), ortam.get("DB_PASSWORD")
