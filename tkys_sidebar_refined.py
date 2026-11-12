from PySide6.QtCore import Qt, QSize, QByteArray, QPoint, QObject
from PySide6.QtGui import QPixmap, QPainter, QIcon
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QPushButton, QLabel, QFrame, QVBoxLayout


PATHS = {
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18m5 6 2 2 4-4"/>',
    "chip": '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4"/>',
    "users": '<circle cx="9" cy="8" r="3"/><path d="M2 20v-2a7 7 0 0 1 14 0v2M17 5a3 3 0 0 1 0 6m2 3a6 6 0 0 1 3 6"/>',
    "settings": '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="16" cy="17" r="3"/>',
    "door": '<path d="M5 21V3h14v18M3 21h18M15 12h.01"/>',
    "clipboard": '<rect x="5" y="4" width="14" height="18" rx="2"/><path d="M9 4V2h6v2M9 11h6m-6 4h6"/>',
    "home": '<path d="m3 10 9-7 9 7v11H3z"/><path d="M9 21v-8h6v8"/>',
    "dashboard": '<path d="M4.5 18a8.5 8.5 0 1 1 15 0"/><path d="M12 16l4-6"/><circle cx="12" cy="16" r="1.5"/><path d="M5 20h14"/>',
    "chart": '<path d="M4 21V12m6 9V5m6 16v-7M2 21h20"/>',
    "edit": '<path d="m4 20 4-1 12-12-3-3L5 16zM15 6l3 3"/>',
    "search": '<circle cx="10" cy="10" r="7"/><path d="m15.5 15.5 5.5 5.5"/>',
    "pin": '<path d="M8 3h8l-2 6 4 4v2H6v-2l4-4zM12 15v7"/>',
    "wrench": '<path d="M14 7a5 5 0 0 0-6 6L3 18l3 3 5-5a5 5 0 0 0 6-6l-3 3-3-3z"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "warning": '<path d="m12 3 10 18H2zM12 9v5m0 3v.2"/>',
    "file": '<path d="M6 2h8l5 5v15H6zM14 2v6h5M9 13h7m-7 4h7"/>',
    "building": '<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M9 7h2m3 0h2M9 11h2m3 0h2M10 21v-4h4v4"/>',
    "shield": '<path d="m12 2 9 4v6c0 5-4 8.5-9 10-5-1.5-9-5-9-10V6zM8 12l3 3 5-6"/>',
    "trophy": '<path d="M7 4h10v5a5 5 0 0 1-10 0zM17 6h3v2a3 3 0 0 1-3 3M7 6H4v2a3 3 0 0 0 3 3M12 14v4M8 21h8M10 18h4"/>',
}

CATEGORY_ICONS = {
    "GENEL": "grid",
    "KLİNİK OPERASYON": "calendar",
    "CİHAZ YAŞAM DÖNGÜSÜ": "chip",
    "YÖNETİM & DENETİM": "users",
    "SİSTEM": "settings",
}

PAGE_ICONS = {
    "Ana Kontrol Paneli": "home",
    "Randevu Takvimi": "calendar",
    "Oda Kullanımı": "door",
    "Danışma Masası": "calendar",
    "Danışma Masası Yönetimi": "clipboard",
    "Danışma Masası Raporları": "chart",
    "Faaliyet Kayıtları": "edit",
    "Puan Raporu": "trophy",
    "Cihaz Uygunluğu": "search",
    "Cihaz Envanteri": "chip",
    "Cihaz Rezervasyonu": "pin",
    "Bakım Kayıtları": "wrench",
    "Bakım Planları": "calendar",
    "Kalibrasyon": "target",
    "Arıza Kayıtları": "warning",
    "Cihaz Raporları": "chart",
    "Kullanıcı & Personel": "users",
    "Audit Kayıtları": "file",
    "Oda Yönetimi": "building",
    "Rol & İzin Yönetimi": "shield",
}


def svg_icon(kind, color="#BFD1E9"):
    body = PATHS.get(kind, PATHS["file"])

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 24 24" fill="none" stroke="'
        + color +
        '" stroke-width="1.65" stroke-linecap="round" '
        'stroke-linejoin="round">'
        + body + '</svg>'
    )

    pixmap = QPixmap(44, 44)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    QSvgRenderer(
        QByteArray(svg.encode("utf-8"))
    ).render(painter)
    painter.end()

    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


class ElegantSidebar(QObject):

    def __init__(self, window):
        super().__init__(window)
        self.w = window
        self.groups = {}
        self.popup = None
        self.changing = False
        self.create_groups()

    def create_groups(self):
        layout = self.w.nav_layout

        names = {
            id(button): name
            for name, button in self.w.nav_btnler.items()
        }

        widgets = [
            layout.itemAt(i).widget()
            for i in range(layout.count())
        ]

        current = None

        for widget in widgets:

            if (
                isinstance(widget, QLabel)
                and widget.objectName() == "bolum"
            ):
                name = widget.text()

                if name not in CATEGORY_ICONS:
                    current = None
                    continue

                header = QPushButton()
                header.setObjectName("tkysKategoriBaslik")
                header.setCursor(Qt.PointingHandCursor)
                header.setToolTip(name)

                header.clicked.connect(
                    lambda checked=False, n=name:
                    self.toggle(n)
                )

                index = layout.indexOf(widget)
                layout.removeWidget(widget)

                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

                layout.insertWidget(index, header)

                current = {
                    "header": header,
                    "items": [],
                    "open": name == "GENEL",
                }

                self.groups[name] = current

            elif (
                current is not None
                and isinstance(widget, QPushButton)
                and widget.objectName() == "nav"
            ):
                name = names.get(id(widget))

                if name is None:
                    continue

                category = next(reversed(self.groups))
                current["items"].append((name, widget))

                widget.setText(name.replace("&", "&&"))
                widget.setIcon(
                    svg_icon(PAGE_ICONS.get(name, "file"))
                )
                widget.setIconSize(QSize(17, 17))
                widget.setFixedHeight(35)

                widget.setStyleSheet("""
                    QPushButton#nav {
                        background: transparent;
                        color: #CEDCED;
                        border: none;
                        border-left: 2px solid transparent;
                        border-radius: 7px;
                        text-align: left;
                        padding: 6px 10px 6px 24px;
                        font-size: 12px;
                        font-weight: 500;
                    }

                    QPushButton#nav:hover {
                        background: #24466F;
                        color: white;
                    }

                    QPushButton#nav:checked {
                        background: #2A5181;
                        color: white;
                        border-left: 2px solid #93C5FD;
                        font-weight: 700;
                    }
                """)

                widget.toggled.connect(
                    lambda checked, c=category:
                    self.selected(c) if checked else None
                )

    def selected(self, category):
        if self.changing:
            return

        for name, group in self.groups.items():
            group["open"] = name == category

        self.refresh()

    def toggle(self, category):
        if self.w._sol_menu_dar:
            self.open_popup(category)
            return

        opening = not self.groups[category]["open"]

        for name, group in self.groups.items():
            group["open"] = (
                opening if name == category else False
            )

        self.refresh()

    def open_popup(self, category):
        if self.popup is not None and self.popup.isVisible():
            self.popup.close()

            if getattr(self, "last_popup", None) == category:
                return

        panel = QFrame(
            self.w,
            Qt.Popup | Qt.FramelessWindowHint
        )

        panel.setObjectName("tkysKategoriPopup")

        panel.setStyleSheet("""
            QFrame#tkysKategoriPopup {
                background: #112B4F;
                border: 1px solid #3B618F;
                border-radius: 11px;
            }

            QLabel#tkysPopupTitle {
                color: #A5C4E9;
                font-size: 11px;
                font-weight: 700;
                padding: 6px;
            }

            QPushButton#tkysPopupItem {
                color: #E0EAF7;
                text-align: left;
                background: transparent;
                border: none;
                border-radius: 7px;
                padding: 8px 10px;
                font-size: 12px;
            }

            QPushButton#tkysPopupItem:hover {
                background: #28507F;
                color: white;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(3)

        title = QLabel(category)
        title.setObjectName("tkysPopupTitle")
        layout.addWidget(title)

        for name, original in self.groups[category]["items"]:
            button = QPushButton(
                name.replace("&", "&&")
            )

            button.setObjectName("tkysPopupItem")
            button.setIcon(
                svg_icon(PAGE_ICONS.get(name, "file"))
            )
            button.setIconSize(QSize(17, 17))
            button.setFixedHeight(36)
            button.setCursor(Qt.PointingHandCursor)

            button.clicked.connect(
                lambda checked=False, b=original:
                self.choose(panel, b)
            )

            layout.addWidget(button)

        panel.setFixedWidth(280)
        panel.adjustSize()

        rect = self.w.screen().availableGeometry()

        x = self.w.sidebar.mapToGlobal(
            QPoint(self.w.sidebar.width() + 5, 0)
        ).x()

        y = self.groups[category]["header"].mapToGlobal(
            QPoint(0, 0)
        ).y()

        panel.move(
            max(
                rect.left() + 8,
                min(x, rect.right() - panel.width() - 8)
            ),
            max(
                rect.top() + 8,
                min(y, rect.bottom() - panel.height() - 8)
            )
        )

        self.popup = panel
        self.last_popup = category
        panel.show()

    def choose(self, panel, original):
        panel.close()
        original.click()

    def refresh(self):
        if self.changing:
            return

        self.changing = True

        try:
            collapsed = self.w._sol_menu_dar

            self.w.sidebar.setFixedWidth(
                76 if collapsed else 280
            )

            self.w.logo_karti.setVisible(not collapsed)
            self.w.rol_karti.setVisible(False)

            self.w.btn_cikis.setText(
                "⏻" if collapsed else "⏻   Oturumu Kapat"
            )

            self.w.btn_cikis.setToolTip("Oturumu Kapat")

            for name, group in self.groups.items():
                active = any(
                    button.isChecked()
                    for _, button in group["items"]
                )

                header = group["header"]

                header.setIcon(
                    svg_icon(
                        CATEGORY_ICONS[name],
                        "#FFFFFF" if active else "#C3D5EC"
                    )
                )

                header.setIconSize(QSize(20, 20))
                header.setFixedHeight(
                    43 if collapsed else 38
                )

                if collapsed:
                    header.setText("")
                else:
                    label = name.replace("&", "&&")
                    arrow = "⌄" if group["open"] else "›"
                    header.setText(f"{label}  {arrow}")

                if collapsed:
                    header.setFixedWidth(45)
                    self.w.nav_layout.setAlignment(
                        header, Qt.AlignHCenter
                    )
                else:
                    header.setMinimumWidth(0)
                    header.setMaximumWidth(16777215)
                    self.w.nav_layout.setAlignment(
                        header, Qt.Alignment()
                    )

                header.setStyleSheet("""
                    QPushButton#tkysKategoriBaslik {
                        background: %s;
                        color: %s;
                        border: none;
                        border-left: 2px solid %s;
                        border-radius: 8px;
                        text-align: %s;
                        padding: %s;
                        font-size: 11px;
                        font-weight: 600;
                    }

                    QPushButton#tkysKategoriBaslik:hover {
                        background: #24466F;
                        color: white;
                    }
                """ % (
                    "transparent",
                    "white" if active else "#B8CDE8",
                    "transparent",
                    "center" if collapsed else "left",
                    "0px" if collapsed else "6px 9px"
                ))

                for _, button in group["items"]:
                    button.setVisible(
                        not collapsed and group["open"]
                    )

            self.w.btn_menu.setToolTip(
                "Sol menüyü genişlet"
                if collapsed else "Sol menüyü daralt"
            )

        finally:
            self.changing = False
