import requests

# Sunucunun ana adresi (bunu bir kere tanımlamak işleri kolaylaştırır)
BASE_URL = "http://127.0.0.1:8000/api"

def personel_listesini_getir(token):
    """Sunucudan personel verilerini çeker ve liste olarak döndürür."""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/personel"
    
    try:
        cevap = requests.get(url, headers=headers)
        
        if cevap.status_code == 200:
            return cevap.json()  # Veriyi başarıyla aldık, geri gönderiyoruz
        else:
            print("Sunucudan veri çekilemedi. Hata Kodu:", cevap.status_code)
            return []  # Hata varsa boş liste dön
            
    except requests.exceptions.ConnectionError:
        print("Sunucuya ulaşılamıyor. FastAPI'nin çalıştığından emin ol.")
        return []  # Sunucu kapalıysa boş liste dön