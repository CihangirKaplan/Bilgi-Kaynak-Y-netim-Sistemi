"""izinler tablosuna gorunen_ad ekle

Revision ID: 74fe75570ae7
Revises: 6c3b4cc159c2
Create Date: 2026-10-26 14:03:18.614308

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '74fe75570ae7'
down_revision: Union[str, Sequence[str], None] = '6c3b4cc159c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


GORUNEN_ADLAR = {
    "RANDEVU_OLUSTUR": "Randevu Oluştur",
    "RANDEVU_DUZENLE": "Randevu Düzenle",
    "RANDEVU_IPTAL": "Randevu İptal",
    "TAKVIM_GORUNTULE": "Takvim Görüntüle",
    "ODA_DURUMU_GORUNTULE": "Oda Durumu Görüntüle",
    "ODA_EKLE": "Oda Ekle",
    "ODA_DUZENLE": "Oda Düzenle",
    "CIHAZ_EKLE": "Cihaz Ekle",
    "CIHAZ_ENVANTER_YONET": "Cihaz Envanter Yönet",
    "CIHAZ_REZERVASYON": "Cihaz Rezervasyon",
    "CIHAZ_UYGUNLUK_GORUNTULE": "Cihaz Uygunluk Görüntüle",
    "BAKIM_KAYITLARI_YONET": "Bakım Kayıtları Yönet",
    "KALIBRASYON_KAYITLARI_YONET": "Kalibrasyon Kayıtları Yönet",
    "ARIZA_KAYITLARI_YONET": "Arıza Kayıtları Yönet",
    "FAALIYET_KAYITLARI_DUZENLE": "Faaliyet Kayıtları Düzenle",
    "FAALIYET_BIRIMI_DUZENLE": "Faaliyet Birimi Düzenle",
    "KULLANICI_OLUSTUR": "Kullanıcı Oluştur",
    "KULLANICI_PASIFLESTIR": "Kullanıcı Pasifleştir",
    "PERSONEL_TANIMLA": "Personel Tanımla",
    "ROL_ATAMA_DEGISTIRME": "Rol Atama Değiştirme",
    "ROL_IZIN_YONET": "Rol İzin Yönet",
    "ROL_OLUSTUR": "Rol Oluştur",
    "ROL_DUZENLE": "Rol Düzenle",
    "IZIN_TANIMLA": "İzin Tanımla",
    "IZIN_DUZENLE": "İzin Düzenle",
    "AUDIT_KAYITLARI_INCELE": "Audit Kayıtları İncele",
    "DANISMA_OTURUMU_YONET": "Danışma Oturumu Yönet",
    "DANISMA_OTURUMU_YONETIM": "Danışma Oturumu Yönetim",
    "DANISMA_OTURUMU_GORUNTULE": "Danışma Oturumu Görüntüle",
}


def upgrade() -> None:
    op.add_column("izinler", sa.Column("gorunen_ad", sa.String(100), nullable=True))
    conn = op.get_bind()
    for izin_adi, gorunen in GORUNEN_ADLAR.items():
        conn.execute(
            sa.text("UPDATE izinler SET gorunen_ad = :g WHERE izin_adi = :a"),
            {"g": gorunen, "a": izin_adi},
        )
    # Sözlükte olmayanlar için yedek: alt çizgi yerine boşluk, baş harfler büyük
    op.execute("UPDATE izinler SET gorunen_ad = initcap(replace(izin_adi, '_', ' ')) WHERE gorunen_ad IS NULL")


def downgrade() -> None:
    op.drop_column("izinler", "gorunen_ad")
