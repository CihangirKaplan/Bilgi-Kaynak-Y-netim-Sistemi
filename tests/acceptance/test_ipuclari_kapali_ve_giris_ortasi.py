"""Fare üzerine gelince açılan ipuçları uygulama genelinde kapalıdır; oturum kapanınca giriş ekranı ekranın ortasında açılır."""
from PySide6.QtCore import QEvent, QPoint
from PySide6.QtGui import QGuiApplication, QHelpEvent
from PySide6.QtWidgets import QApplication, QPushButton

from client.ipucu_kapat import ipuclarini_kapat


class _Dugme(QPushButton):
    def __init__(self):
        super().__init__("x")
        self.ipucu_olaylari = 0

    def event(self, olay):
        if olay.type() == QEvent.ToolTip:
            self.ipucu_olaylari += 1
        return super().event(olay)


def _ipucu_gonder(dugme):
    QApplication.sendEvent(dugme, QHelpEvent(QEvent.ToolTip, QPoint(2, 2), QPoint(2, 2)))


def test_ipucu_olayi_bilesene_ulasmaz(tkys_qapplication):
    ipuclarini_kapat()
    dugme = _Dugme()
    dugme.setToolTip("Bu bir ipucu")
    dugme.show()
    _ipucu_gonder(dugme)
    assert dugme.ipucu_olaylari == 0


def test_istemci_kodu_ipucu_kutusunu_dogrudan_gostermez():
    """QToolTip.showText olay süzgecini aşar; yeni ipucu eklenirse bu test uyarır."""
    from pathlib import Path
    kok = Path(__file__).resolve().parents[2] / "client"
    ihlal = [str(d.name) for d in kok.glob("*.py") if "QToolTip.showText" in d.read_text(encoding="utf-8")]
    assert ihlal == []


def test_susturucu_tekrar_cagrilsa_da_bir_kez_kurulur(tkys_qapplication):
    import client.ipucu_kapat as modul
    ipuclarini_kapat()
    ilk = modul._SUSTURUCU
    ipuclarini_kapat()
    assert modul._SUSTURUCU is ilk and ilk is not None


def test_giris_ekrani_oturum_kapaninca_ekranin_ortasinda_acilir(tkys_qapplication):
    from client.login_ekrani import LoginEkrani
    giris = LoginEkrani()
    assert giris.property("ortalama_kapali") is True            # ana pencere içerik alanına göre kaydırılmaz
    giris.setFixedSize(400, 300)                                # test ekranına sığsın
    giris.move(0, 0)
    giris.oturum_kapandi()
    alan = QGuiApplication.primaryScreen().availableGeometry()
    merkez = giris.frameGeometry().center()
    assert abs(merkez.x() - alan.center().x()) <= 2 and abs(merkez.y() - alan.center().y()) <= 2
    giris.close()
