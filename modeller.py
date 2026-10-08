from pydantic import BaseModel
from typing import Optional
from datetime import datetime

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


# APT-API-001: Randevu Oluşturma Modeli
class RandevuOlusturModeli(BaseModel):
    danisan_kod_id: str
    psikolog_id: int
    oda_id: int
    baslangic_zamani: datetime
    bitis_zamani: datetime


# APT-API-001: Randevu Güncelleme Modeli
class RandevuGuncelleModeli(BaseModel):
    danisan_kod_id: Optional[str] = None
    psikolog_id: Optional[int] = None
    oda_id: Optional[int] = None
    baslangic_zamani: Optional[datetime] = None
    bitis_zamani: Optional[datetime] = None