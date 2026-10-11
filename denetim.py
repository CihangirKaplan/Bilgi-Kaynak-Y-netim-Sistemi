import psycopg2


def denetim_kaydi_olustur(
    vt_ayarlari: dict,
    olay_turu: str,
    kullanici_id: int | None = None,
    hedef_tablo: str | None = None,
    hedef_kayit_id: int | None = None
) -> None:
    conn = None
    cursor = None

    try:
        conn = psycopg2.connect(**vt_ayarlari)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO denetim_kayitlari (
                kullanici_id,
                olay_turu,
                hedef_tablo,
                hedef_kayit_id
            )
            VALUES (%s, %s, %s, %s);
            """,
            (
                kullanici_id,
                olay_turu,
                hedef_tablo,
                hedef_kayit_id
            )
        )

        conn.commit()

    finally:
        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()
            