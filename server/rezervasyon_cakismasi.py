"""Rezervasyon çakışması yardımcıları (bakım/kalibrasyon ve cihaz rezervasyonu ortak kullanır). `server/sunucu.py` içinden ayrıldı."""
from fastapi import HTTPException


REZERVASYON_CAKISMA_KODU = "REZERVASYON_CAKISMASI"


def rezervasyon_cakisma_detayi(mesaj, kayitlar):
    """409 yanıtı gövdesi: istemci çakışan rezervasyonları tek tek gösterip iptal ettirebilsin."""
    return {
        "kod": REZERVASYON_CAKISMA_KODU,
        "mesaj": mesaj,
        "rezervasyonlar": [
            {
                "rezervasyon_id": k[0],
                "baslangic": k[1].isoformat(),
                "bitis": k[2].isoformat(),
                "rezerve_eden": k[3],
            }
            for k in kayitlar
        ],
    }


def cakisan_rezervasyonlari_denetle(cursor, cihaz_id, baslangic, bitis):
    """Bakım/kalibrasyon tarih aralığıyla (başlangıç ve bitiş günü dahil) kesişen, henüz bitmemiş
    aktif cihaz rezervasyonu varsa 409 + rezervasyon listesi döner.

    Rezervasyonları sunucu kendiliğinden iptal etmez; istemci her birini kullanıcıya gösterir,
    kullanıcı tek tek iptal eder (iptal ucu denetim kaydı yazar) ve işlemi yeniden dener.
    Geçmişte kalmış rezervasyonlar çakışma sayılmaz.
    """
    cursor.execute(
        """
        SELECT r.rezervasyon_id, r.baslangic_zamani, r.bitis_zamani, COALESCE(k.kullanici_adi, '-')
        FROM cihaz_rezervasyonlari r
        LEFT JOIN personel p ON r.rezervasyonu_yapan_personel_id = p.personel_id
        LEFT JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id
        WHERE r.cihaz_id = %s
          AND COALESCE(r.iptal_edildi_mi, FALSE) = FALSE
          AND r.bitis_zamani > NOW()
          AND r.baslangic_zamani < (%s::date + 1)
          AND r.bitis_zamani > %s::date
        ORDER BY r.baslangic_zamani;
        """,
        (cihaz_id, bitis, baslangic),
    )
    kayitlar = cursor.fetchall()
    if kayitlar:
        raise HTTPException(
            status_code=409,
            detail=rezervasyon_cakisma_detayi(
                f"Bu tarihlerde cihaz için {len(kayitlar)} aktif rezervasyon var.", kayitlar
            ),
        )
