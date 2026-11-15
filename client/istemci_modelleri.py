from dataclasses import dataclass

@dataclass
class IstemciRandevu:
    """Arayüzden toplanıp API'ye gönderilecek Randevu Verisi (APT-001)"""
    danisan_kod_id: str
    psikolog_id: int
    oda_id: int
    baslangic_zamani: str  # Format: "YYYY-MM-DDTHH:MM:SS"
    bitis_zamani: str      # Format: "YYYY-MM-DDTHH:MM:SS"

    def to_dict(self):
        """Bu fonksiyon veriyi API'ye göndermeden önce JSON/Sözlük formatına çevirir."""
        return {
            "danisan_kod_id": self.danisan_kod_id.strip(),
            "psikolog_id": self.psikolog_id,
            "oda_id": self.oda_id,
            "baslangic_zamani": self.baslangic_zamani,
            "bitis_zamani": self.bitis_zamani
        }