"""Giriş ekranı hata mesajları: sertifika sorunu ağ sorunundan ayrı söylenir, mesajda denenen adres görünür.

Pencere AYRI süreçte açılır (test_login_stil_yolu.py ile aynı gerekçe: Qt'nin çıkıştaki bellek temizliği pytest sürecini çökertebiliyor).
"""
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

KOD = r"""
from unittest.mock import MagicMock, patch
import sys
import requests
import client.login_ekrani as L
from PySide6.QtWidgets import QApplication

sys.excepthook = sys.__excepthook__     # giriş ekranının hata kutusu yerine: başarısız doğrulama süreci hemen sonlandırsın
app = QApplication([])
L.API_URL = "https://10.0.0.5:8443"
ekran = L.LoginEkrani()
ekran.kullanici_input.setText("kisi")
ekran.sifre_input.setText("parola")


def dene(**ayar):
    with patch("client.login_ekrani.requests.post", **ayar):
        ekran.giris_yap()
    return ekran.hata_lbl.text()


# Sertifika doğrulanamıyor: ağ sorunu gibi anlatılmaz, adres ve çözüm yolu yazılır
m = dene(side_effect=requests.exceptions.SSLError("certificate verify failed"))
assert "sertifika" in m and "TKYS_CA_BUNDLE" in m and "https://10.0.0.5:8443" in m, m
assert "Ağ bağlantınızı kontrol edin" not in m, m

# Sunucuya ulaşılamıyor: denenen adres mesajda görünür
m = dene(side_effect=requests.exceptions.ConnectionError("refused"))
assert m.startswith("⚠  Sunucuya bağlanılamadı") and "https://10.0.0.5:8443" in m, m

# SSLError, ConnectionError'ın alt sınıfıdır: sıralama bozulursa sertifika hatası ağ hatasına karışırdı
assert issubclass(requests.exceptions.SSLError, requests.exceptions.ConnectionError)

# Boş yanıt: geliştirici dili yok
boş = MagicMock(status_code=502, text="  ")
m = dene(return_value=boş)
assert "bomboş" not in m and "502" in m and "Lütfen tekrar deneyin" in m, m

# Zaman aşımı mesajı değişmedi
m = dene(side_effect=requests.exceptions.Timeout())
assert "Sunucu yanıt vermedi" in m, m

# Yanlış parola (401): sunucunun mesajı olduğu gibi gösterilir
yanlis = MagicMock(status_code=401, text="x", headers={})
yanlis.json.return_value = {"detail": "Kullanıcı adı veya parola hatalı."}
m = dene(return_value=yanlis)
assert "Kullanıcı adı veya parola hatalı." in m, m
assert ekran.sifre_input.text() == ""

# İlk giriş şifre değiştirme penceresi iptal edilince "Şifreyi göster" kapanır, parola yeniden gizlenir
ekran.goster.setChecked(True)
ekran.sifre_input.setText("gizli")
ekran.ilk_giris_iptal()
assert not ekran.goster.isChecked() and ekran.sifre_input.echoMode() == ekran.sifre_input.EchoMode.Password
assert ekran.sifre_input.text() == ""

# Kaldırılan ölü durum geri gelmedi
assert not hasattr(ekran, "kalan") and not hasattr(ekran, "hatali_deneme") and not hasattr(L, "MAX_DENEME")
ekran.close()
print("giris hata mesajlari tamam")
"""


def test_giris_ekrani_hata_mesajlari():
    proje = Path(__file__).resolve().parents[2]
    ortam = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    sonuc = subprocess.run([sys.executable, "-c", KOD], cwd=proje, env=ortam, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert sonuc.returncode == 0, sonuc.stdout + sonuc.stderr
    assert "giris hata mesajlari tamam" in sonuc.stdout
