from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean
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
    olusturulma_tarihi: Optional[datetime] = None


# AUTH-002: Role Modeli
class RolModeli(BaseModel):
    rol_id: Optional[int] = None
    rol_adi: str


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
    olusturulma_tarihi: Optional[datetime] = None


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
    baslangic_zamani: datetime
    bitis_zamani: datetime
    durum: str = "PLANLANDI"
    olusturulma_tarihi: Optional[datetime] = None


# APT-API-001 / SEC-APT-002: Randevu Oluşturma Modeli
class RandevuOlusturModeli(BaseModel):
    danisan_kod_id: str = Field(min_length=1)
    psikolog_id: int = Field(gt=0)
    oda_id: int = Field(gt=0)
    baslangic_zamani: datetime
    bitis_zamani: datetime

    @field_validator("danisan_kod_id")
    @classmethod
    def danisan_kodu_dogrula(cls, deger: str) -> str:
        if not deger.strip():
            raise ValueError("Danışan kodu boş olamaz.")
        return deger



# APT-API-001 / SEC-APT-002: Randevu Güncelleme Modeli
class RandevuGuncelleModeli(BaseModel):
    danisan_kod_id: Optional[str] = Field(default=None, min_length=1)
    psikolog_id: Optional[int] = Field(default=None, gt=0)
    oda_id: Optional[int] = Field(default=None, gt=0)
    baslangic_zamani: Optional[datetime] = None
    bitis_zamani: Optional[datetime] = None

    @field_validator("danisan_kod_id")
    @classmethod
    def danisan_kodu_dogrula(cls, deger: Optional[str]) -> Optional[str]:
        if deger is not None and not deger.strip():
            raise ValueError("Danışan kodu boş olamaz.")
        return deger

class OdaOlusturModeli(BaseModel):
    oda_adi: str = Field(min_length=1, max_length=50)
    kapasite: int = Field(default=1, ge=1)
    aktif_mi: bool = True

class OdaGuncelleModeli(BaseModel):
    oda_adi: str | None = Field(default=None, min_length=1, max_length=50)
    kapasite: int | None = Field(default=None, ge=1)
    aktif_mi: bool | None = None
