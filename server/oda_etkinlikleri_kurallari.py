"""Oda etkinlikleri ve ortak oda doluluk kontrolleri."""


def oda_kilidini_al(cursor, oda_id):
    """Aynı odanın yazma işlemleri için transaction kilidi."""
    if oda_id is None:
        return

    cursor.execute(
        "SELECT pg_advisory_xact_lock(%s, %s)",
        (391284, int(oda_id)),
    )


def oda_cakismasi_bul(
    cursor,
    oda_id,
    baslangic,
    bitis,
    haric_etkinlik_id=None,
    haric_randevu_id=None,
):
    """
    Odanın istenen saatlerde dolu olup olmadığını kontrol eder.

    Dönüş:
        None: Çakışma yok
        'randevu': Randevuyla çakışıyor
        'cihaz': Cihaz rezervasyonuyla çakışıyor
        'etkinlik': Başka bir etkinlikle çakışıyor
    """
    if baslangic >= bitis:
        raise ValueError("Bitiş zamanı başlangıçtan sonra olmalıdır.")

    cursor.execute(
        """
        SELECT 1
        FROM randevular
        WHERE oda_id = %s
          AND durum <> 'IPTAL_EDILDI'
          AND (%s IS NULL OR randevu_id <> %s)
          AND baslangic_zamani < %s
          AND bitis_zamani > %s
        LIMIT 1
        """,
        (
            oda_id,
            haric_randevu_id,
            haric_randevu_id,
            bitis,
            baslangic,
        ),
    )
    if cursor.fetchone():
        return "randevu"

    cursor.execute(
        """
        SELECT 1
        FROM cihaz_rezervasyonlari
        WHERE kullanilacak_oda_id = %s
          AND COALESCE(iptal_edildi_mi, FALSE) = FALSE
          AND baslangic_zamani < %s
          AND bitis_zamani > %s
        LIMIT 1
        """,
        (oda_id, bitis, baslangic),
    )
    if cursor.fetchone():
        return "cihaz"

    cursor.execute(
        """
        SELECT 1
        FROM oda_etkinlik_gunleri g
        JOIN oda_etkinlikleri e
          ON e.etkinlik_id = g.etkinlik_id
        WHERE e.oda_id = %s
          AND COALESCE(e.iptal_edildi_mi, FALSE) = FALSE
          AND g.baslangic_zamani < %s
          AND g.bitis_zamani > %s
          AND (%s IS NULL OR e.etkinlik_id <> %s)
        LIMIT 1
        """,
        (
            oda_id,
            bitis,
            baslangic,
            haric_etkinlik_id,
            haric_etkinlik_id,
        ),
    )
    if cursor.fetchone():
        return "etkinlik"

    return None
