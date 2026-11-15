
import psycopg2


def denetim_kaydi_olustur(
    vt_ayarlari: dict,
    olay_turu: str,
    kullanici_id: int | None = None,
    hedef_tablo: str | None = None,
    hedef_kayit_id: int | None = None,
    mevcut_cursor=None
) -> None:
    conn = None
    cursor = mevcut_cursor

    try:
        # Mevcut cursor verilmediyse yeni bağlantı aç.
        if cursor is None:
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

        # Yalnızca bağlantıyı bu fonksiyon açtıysa commit yap.
        if conn is not None:
            conn.commit()

    except Exception:
        if conn is not None:
            conn.rollback()
        raise

    finally:
        # Dışarıdan verilen cursor ve bağlantı burada kapatılmaz.
        if conn is not None:
            cursor.close()
            conn.close()
