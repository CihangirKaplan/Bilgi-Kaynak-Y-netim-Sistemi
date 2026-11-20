"""Personel alanlarının (personel_id, personel_kodu) kullanıcı satırına yazılması.

Personel ve kullanıcı tabloları birleştirildi; personel bilgisi kullanicilar tablosunda tutulur.
`personel` adı yalnızca eski sorgular için bırakılmış okuma görünümüdür.
"""

PERSONEL_KAYDI_ATA_SQL = (
    "UPDATE kullanicilar SET personel_id = nextval('personel_personel_id_seq'), "
    "personel_kodu = %s, personel_kaydi_tarihi = CURRENT_TIMESTAMP "
    "WHERE kullanici_id = %s AND personel_id IS NULL RETURNING personel_id;"
)


def personel_kaydi_ata(cursor, kullanici_id, personel_kodu):
    """Personel kaydı olmayan kullanıcıya personel kimliği ve kodu verir; kimliği döndürür.

    Kullanıcı yoksa ya da zaten personel kaydı varsa None döner. Kod başka kayıtta kullanılıyorsa UniqueViolation oluşur.
    """
    cursor.execute(PERSONEL_KAYDI_ATA_SQL, (personel_kodu, kullanici_id))
    satir = cursor.fetchone()
    return satir[0] if satir else None
