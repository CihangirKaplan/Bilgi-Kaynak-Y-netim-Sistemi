from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# ==========================================
# CİHAZ VE KİMLİK DOĞRULAMA MODELLERİ
# ==========================================

# DEV-001: Device Temel Modeli
class CihazModeli(BaseModel):
    envanter_kodu: str
    cihaz_adi: str
    marka_model: Optional[str] = None
    seri_no: Optional[str] = None
    durum: str = "Kullanima_Hazir"

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
# DANIŞAN, ODA VE RANDEVU MODELLERİ
# ==========================================

# CLI-001 & CLI-002: Client Code (Danışan Kodu) Modeli
class ClientCodeModeli(BaseModel):
    id: Optional[int] = None
    kod: str  # Örn: DAN-2026-0001
    danisan_adi: str
    durum: str = "Aktif"
    olusturulma_tarihi: Optional[datetime] = None

# ROOM-001: Oda Modeli
class OdaModeli(BaseModel):
    oda_id: Optional[int] = None
    oda_adi: str
    kapasite: int
    durum: str = "Musait"

# APT-001 - APT-004: Randevu Modelleri
class RandevuModeli(BaseModel):
    randevu_id: Optional[int] = None
    danisan_kodu: str
    oda_id: int
    tarih_saat: datetime
    durum: str = "Planlandi"