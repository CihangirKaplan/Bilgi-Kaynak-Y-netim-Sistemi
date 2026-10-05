from pydantic import BaseModel
<<<<<<< HEAD
from typing import Optional
=======
from typing import Optionalsss
>>>>>>> 0e4f0a9a1883017875c9b722dac8d9c4b26ea0d5

# DEV-001: Device Temel Modeli
class CihazModeli(BaseModel):
    envanter_kodu: str
    cihaz_adi: str
    marka_model: Optional[str] = None  # Opsiyonel alan (boş bırakılabilir)
    seri_no: Optional[str] = None      # Opsiyonel alan
    durum: str = "Kullanima_Hazir"     # Varsayılan olarak cihaz kullanıma hazır gelir