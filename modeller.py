import datetime
from datetime import date
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional
from enum import Enum
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Date
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# ROOM-001: Oda Veritabanı Modeli (SQL Şeması ile Birebir Uyumlu)
class Oda(Base):
    __tablename__ = "odalar"

    oda_id = Column(Integer, primary_key=True, autoincrement=True)
    oda_adi = Column(String(50), unique=True, nullable=False)
    kapasite = Column(Integer, default=1)
    aktif_mi = Column(Boolean, default=True, nullable=False)

# DEV-001: Device Temel Modeli
class CihazModeli(BaseModel):
    envanter_kodu: str
    cihaz_adi: str
    marka_model: Optional[str] = None  # Opsiyonel alan (boş bırakılabilir)
    seri_no: Optional[str] = None      # Opsiyonel alan
    durum: str = "Kullanima_Hazir"     # Varsayılan olarak cihaz kullanıma hazır gelir

# AUTH-001: User Modeli
class KullaniciModeli(BaseModel):
    kullanici_id: Optional[int] = None
    kullanici_adi: str
    parola_hash: str
    rol_id: int
    aktif_mi: bool = True
    olusturulma_tarihi: Optional[datetime.datetime] = None

# AUTH: Yeni kullanıcı oluşturma modeli
class KullaniciOlusturModeli(BaseModel):
    kullanici_adi: str = Field(min_length=3, max_length=100)
    rol_id: int = Field(gt=0)

# ADM-API-004: Personel Oluşturma İstek Modeli
class PersonelOlusturModeli(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kullanici_id: int = Field(gt=0)
    personel_kodu: str = Field(
        min_length=1,
        max_length=50,
        pattern=r"^\s*\S(?:.*\S)?\s*$"
    )

# İlk girişte zorunlu şifre değiştirme ve mevcut şifreyi güncelleme modeli
class SifreDegistirModeli(BaseModel):
    eski_parola: str
    yeni_parola: str = Field(min_length=8, max_length=72)
    yeni_parola_tekrar: str

# AUTH-002: Role Modeli
class RolModeli(BaseModel):
    rol_id: Optional[int] = None
    rol_adi: str

# ADM-API-002: Kullanıcı Rol Değiştirme İstek Modeli
class RolDegistirModeli(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rol_id: int = Field(gt=0)

# AUTH-004: Login İstek Modeli
class GirisModeli(BaseModel):
    kullanici_adi: str
    parola: str

# ==========================================
# ÖĞRENCİ A MODÜLLERİ (CLI, ROOM, APT)
# ==========================================

# CLI-001: Danışan Kodu Modeli -> danisan_kodlari tablosu
class DanisanKoduModeli(BaseModel):
    danisan_kod_id: str  # Örn: DAN-2026-0001
    ucretli_mi: bool = True
    istisna_turu: str = "YOK"
    aktif_mi: bool = True
    olusturulma_tarihi: Optional[datetime.datetime] = None

# ROOM-001: Oda Modeli -> odalar tablosu
class OdaModeli(BaseModel):
    oda_id: Optional[int] = None
    oda_adi: str
    kapasite: int = 1
    aktif_mi: bool = True

# APT-001: Randevu Modeli -> randevular tablosu
class RandevuModeli(BaseModel):
    randevu_id: Optional[int] = None
    danisan_kod_id: str
    psikolog_id: int
    oda_id: int
    baslangic_zamani: datetime.datetime
    bitis_zamani: datetime.datetime
    durum: str = "PLANLANDI"
    olusturulma_tarihi: Optional[datetime.datetime] = None

# APT-API-001 / SEC-APT-002: Randevu Oluşturma Modeli
class RandevuOlusturModeli(BaseModel):
    psikolog_id: int = Field(gt=0)
    oda_id: int = Field(gt=0)
    baslangic_zamani: datetime.datetime
    bitis_zamani: datetime.datetime

# APT-API-001 / SEC-APT-002: Randevu Güncelleme Modeli
class RandevuGuncelleModeli(BaseModel):
    danisan_kod_id: Optional[str] = Field(
    default=None,
    min_length=1,
    pattern=r".*\S.*"
)
    psikolog_id: Optional[int] = Field(default=None, gt=0)
    oda_id: Optional[int] = Field(default=None, gt=0)
    baslangic_zamani: Optional[datetime.datetime] = None
    bitis_zamani: Optional[datetime.datetime] = None

class OdaOlusturModeli(BaseModel):
    oda_adi: str = Field(min_length=1, max_length=50)
    kapasite: int = Field(default=1, ge=1)
    aktif_mi: bool = True

class OdaGuncelleModeli(BaseModel):
    oda_adi: str | None = Field(default=None, min_length=1, max_length=50)
    kapasite: int | None = Field(default=None, ge=1)
    aktif_mi: bool | None = None

class CihazDurumu(str, Enum):
    KULLANIMA_HAZIR = "Kullanima_Hazir"
    REZERVE = "Rezerve"
    KULLANIMDA = "Kullanimda"
    ARIZALI = "Arizali"
    BAKIMDA = "Bakimda"
    KALIBRASYONDA = "Kalibrasyonda"
    KULLANIM_DISI = "Kullanim_Disi"
# ==========================================
# ÖĞRENCİ B MODÜLLERİ (DEVICE, RES)
# ==========================================

# DEVICE-001: Cihaz Çıktı Modeli
class CihazModeli(BaseModel):
    cihaz_id: Optional[int] = None
    envanter_kodu: str
    cihaz_adi: str
    marka_model: Optional[str] = None
    seri_no: Optional[str] = None
    zimmetli_oda_id: Optional[int] = None
    durum: CihazDurumu = CihazDurumu.KULLANIMA_HAZIR

# DEVICE-002: Cihaz Ekleme Modeli (Girdi)
class CihazOlusturModeli(BaseModel):
    envanter_kodu: str = Field(min_length=1, max_length=50)
    cihaz_adi: str = Field(min_length=1, max_length=100)
    marka_model: Optional[str] = Field(default=None, max_length=100)
    seri_no: Optional[str] = Field(default=None, max_length=100)
    zimmetli_oda_id: Optional[int] = Field(default=None, gt=0)
    durum: CihazDurumu = CihazDurumu.KULLANIMA_HAZIR

# DEVICE-003, DEVICE-004, DEVICE-005: Cihaz Güncelleme/Durum Değiştirme Modeli
class CihazGuncelleModeli(BaseModel):
    cihaz_adi: Optional[str] = Field(default=None, min_length=1, max_length=100)
    marka_model: Optional[str] = Field(default=None, max_length=100)
    seri_no: Optional[str] = Field(default=None, max_length=100)
    zimmetli_oda_id: Optional[int] = Field(default=None, gt=0)
    durum: Optional[CihazDurumu] = None

# RES-001: Cihaz Rezervasyonu Oluşturma Modeli
class RezervasyonOlusturModeli(BaseModel):
    cihaz_id: int = Field(gt=0)
    kullanilacak_oda_id: Optional[int] = Field(default=None, gt=0)
    baslangic_zamani: datetime.datetime
    bitis_zamani: datetime.datetime
    proje_turu: Optional[str] = Field(default=None, max_length=50)
    proje_adi_aciklamasi: Optional[str] = Field(default=None, max_length=255)

    @field_validator("baslangic_zamani", "bitis_zamani", mode="before")
    @classmethod
    def tarih_formati(cls, deger):
        if isinstance(deger, str):
            return datetime.datetime.fromisoformat(deger.replace("Z", ""))
        return deger

# FAIL-001: Arıza Bildirim Modeli
class ArizaBildirimModeli(BaseModel):
    cihaz_id: int = Field(gt=0)
    ariza_baslik: str = Field(min_length=3, max_length=150)
    ariza_aciklama: str = Field(min_length=5)
    aciliyet: str # Düşük, Orta, Yüksek, Kritik

# FAIL-003: Arıza Güncelleme Modeli
class ArizaGuncelleModeli(BaseModel):
    ariza_baslik: str = Field(min_length=3, max_length=150)
    ariza_aciklama: str = Field(min_length=2)
    aciliyet: str # Düşük, Orta, Yüksek, Kritik
    cozuldu_mu: bool # True ise çözüldü, False ise devam ediyor
# ADM-API-004: Personel Güncelleme İstek Modeli
class PersonelGuncelleModeli(BaseModel):
    model_config = ConfigDict(extra="forbid")

    personel_kodu: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        pattern=r"^\s*\S(?:.*\S)?\s*$"
    )
    aktif_mi: bool | None = None

# ==========================================
# KALİBRASYON YÖNETİMİ MODELLERİ (CALB)
# ===================================
class KalibrasyonOlusturModeli(BaseModel):
    cihaz_id: int
    kalibrasyon_yapan_kurum: str
    gecerlilik_tarihi: date
    sertifika_no: str

class KalibrasyonGuncelleModeli(BaseModel):
    kalibrasyon_yapan_kurum: Optional[str] = None
    gecerlilik_tarihi: Optional[date] = None
    sertifika_no: Optional[str] = None
# BAKIM YÖNETİMİ MODELLERİ (MNT)
# ==========================================
class BakimOlusturModeli(BaseModel):
    cihaz_id: int
    bakim_tarihi: date
    bakim_yapan_kisi: str
    yapilan_islem: str
    maliyet: Optional[float] = 0.0
    sonraki_bakim_tarihi: Optional[date] = None  # YENİ EKLENDİ

class BakimGuncelleModeli(BaseModel):
    bakim_tarihi: Optional[date] = None
    bakim_yapan_kisi: Optional[str] = None
    yapilan_islem: Optional[str] = None
    maliyet: Optional[float] = None
    sonraki_bakim_tarihi: Optional[date] = None  # YENİ EKLENDİ

# ==========================================
# DASHBOARD VE RAPORLAMA MODELLERİ (DASH)
# ==========================================

class DashboardOzetModeli(BaseModel):
    toplam_cihaz: int
    aktif_cihaz: int
    arizali_cihaz: int
    bakimdaki_cihaz: int
    acik_ariza_sayisi: int
    bugunku_randevu_sayisi: int

class YaklasanIslemModeli(BaseModel):
    cihaz_adi: str
    islem_turu: str # 'Bakım' veya 'Kalibrasyon'
    tarih: str
    kalan_gun: int
    durum_kodu: str # 'KRITIK' (Süresi geçmiş/Çok yakın), 'UYARI' (Yaklaşıyor)
