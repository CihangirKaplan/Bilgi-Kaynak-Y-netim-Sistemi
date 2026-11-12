import os

import requests
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QHeaderView, QMessageBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
import turkce_mesaj_kutusu as tmk


def rol_etiketi(rol):
    """Veritabanındaki görünen adı kullanır, yoksa teknik adı okunur hale getirir."""
    ad = rol.get("gorunen_ad") or rol["rol_adi"].replace("_", " ").title()
    return ad.replace(" ", "\n", 1)  # başlıkta iki satıra böl


def izin_etiketi(izin):
    return izin.get("gorunen_ad") or izin["izin_adi"].replace("_", " ").title()


# Tek bir stil bloğu: setStyleSheet her çağrıldığında öncekini tamamen siler.
STIL = """
QTableWidget {
    background-color: white;
    alternate-background-color: #F3F7FF;
    color: #0A1F5C;
    border: 1px solid #D0D7E5;
    border-radius: 8px;
    gridline-color: #E2E8F0;
    outline: none;
    selection-background-color: #2563EB;
    selection-color: white;
}
QTableWidget::item { padding: 4px; }
QHeaderView::section {
    background-color: #0A1F5C;
    color: white;
    font-weight: 800;
    padding: 8px;
    border: none;
    border-right: 1px solid #1D4ED8;
    border-bottom: 1px solid #1D4ED8;
}
"""


class RolIzinSayfasi(QWidget):
    """Rol-izin matrisi (SALT OKUNUR).

    İzinleri değiştirmek için 'İzin Düzenle' penceresi kullanılır.
    Satıra tıklanırsa o izin, pencere açıldığında hazır seçili gelir.
    """

    def __init__(self, ebeveyn=None, token="", api_url=None):
        super().__init__(ebeveyn)
        self.token = token
        self.api_url = (api_url or os.getenv("TKYS_API_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.matris_verisi = None
        self.roller = []          # main_window.rol_duzenle_diyalog_ac bunları kullanır
        self.rol_izin_map = {}
        self._ilk_yukleme_yapildi = False

        self.ana_layout = QVBoxLayout(self)
        self.ana_layout.setContentsMargins(0, 0, 0, 0)

        self.tablo = QTableWidget()
        self.ana_layout.addWidget(self.tablo)

        self.tablo.setStyleSheet(STIL)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.verticalHeader().setDefaultSectionSize(40)
        self.tablo.horizontalHeader().setMinimumHeight(56)
        self.tablo.horizontalHeader().setMinimumSectionSize(110)
        self.tablo.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tablo.setAlternatingRowColors(True)
        self.tablo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def showEvent(self, event):
        """Veri, sayfa ilk kez görüntülendiğinde çekilir (giriş sırasında değil)."""
        super().showEvent(event)
        if not self._ilk_yukleme_yapildi:
            self._ilk_yukleme_yapildi = True
            self.verileri_yukle()

    def verileri_yukle(self):
        try:
            yanit = requests.get(
                f"{self.api_url}/api/rol-izin-matrisi",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5,
            )
        except requests.exceptions.RequestException as e:
            tmk.hata(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı:\n{e}")
            return

        if yanit.status_code != 200:
            try:
                detay = str(yanit.json().get("detail", ""))
            except ValueError:
                detay = ""
            tmk.uyari(
                self, "Hata", f"Matris alınamadı (Kod {yanit.status_code}).\n{detay}"
            )
            return

        self.matris_tablosunu_doldur(yanit.json())

    def matris_tablosunu_doldur(self, matris_verisi):
        self.matris_verisi = matris_verisi
        roller = matris_verisi["roller"]
        izinler = matris_verisi["izinler"]
        rol_izin_map = matris_verisi["rol_izin_map"]  # {"rol_id": [izin_id, ...]}
        self.roller = roller
        self.rol_izin_map = rol_izin_map

        self.tablo.clear()
        self.tablo.setRowCount(len(izinler))
        self.tablo.setColumnCount(len(roller) + 1)
        self.tablo.setHorizontalHeaderLabels(
            ["İzin Adı / Roller"] + [rol_etiketi(rol) for rol in roller]
        )

        for satir, izin in enumerate(izinler):
            izin_id = izin["izin_id"]

            izin_item = QTableWidgetItem(izin_etiketi(izin))
            izin_item.setData(Qt.ItemDataRole.UserRole, izin_id)
            izin_item.setToolTip(izin["izin_adi"])  # teknik ad
            yazi = izin_item.font()
            yazi.setBold(True)
            izin_item.setFont(yazi)
            self.tablo.setItem(satir, 0, izin_item)

            for sutun, rol in enumerate(roller, start=1):
                verilmis = izin_id in rol_izin_map.get(str(rol["rol_id"]), [])

                hucre = QTableWidgetItem("✔" if verilmis else "—")
                hucre.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                hucre.setForeground(QColor("#1D4ED8" if verilmis else "#CBD5E1"))
                if verilmis:
                    yazi = hucre.font()
                    yazi.setBold(True)
                    hucre.setFont(yazi)
                hucre.setToolTip(
                    f"{rol.get('gorunen_ad') or rol['rol_adi']}: "
                    f"{'izin verilmiş' if verilmis else 'izin verilmemiş'}"
                )
                self.tablo.setItem(satir, sutun, hucre)

        baslik = self.tablo.horizontalHeader()
        baslik.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for i in range(1, len(roller) + 1):
            baslik.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

    def secili_izin_id(self):
        """Tabloda seçili satırdaki iznin ID'si; seçim yoksa None."""
        secili = self.tablo.selectionModel().selectedRows()
        if not secili:
            return None
        oge = self.tablo.item(secili[0].row(), 0)
        return oge.data(Qt.ItemDataRole.UserRole) if oge else None