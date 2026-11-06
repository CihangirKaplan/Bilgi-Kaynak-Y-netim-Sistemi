"""Bakım ve kalibrasyon formlarındaki 'Bağlı plan' seçimi.

Cihazın aktif planı varsa kayıt o plana bağlanabilir: sonraki tarih plan periyoduna göre
(bitiş + periyot gün) ve bildirim zamanı plan uyarı süresine göre otomatik dolar. Kayıt
kaydedilince sunucu planın 'sonraki tarihini' de ilerletir; böylece plan ile kayıt hep aynı
tarihi gösterir. Plan seçmek zorunlu değildir; "Plan yok" seçiliyken form eskisi gibi çalışır.
"""
import datetime

from PySide6.QtCore import QDate, QObject
from PySide6.QtWidgets import QComboBox, QLabel

from api_yoneticisi import oturum_kontrollu_istek, oturum_hatasi_mi

PLAN_YOK = "Plan yok (tarihi kendim seçeceğim)"
IPUCU_STILI = "color: #6B7FA8; font-size: 11px;"


def kalibrasyon_plani_mi(gorev_turu):
    """Sunucudaki plan_kalibrasyon_mu ile aynı kural: 'Kalibrasyon...' ile başlayan türler."""
    return (gorev_turu or "").strip().lower().startswith("kalibrasyon")


class PlanSecimi(QObject):
    def __init__(self, api_url, token, kalibrasyon_mi, cihaz_alani, bitis_alani, tekrar, ebeveyn=None):
        super().__init__(ebeveyn)
        self.api_url = api_url
        self.token = token
        self.kalibrasyon_mi = kalibrasyon_mi
        self.cihaz_alani = cihaz_alani
        self.bitis = bitis_alani
        self.tekrar = tekrar
        self.planlar = []

        self.cmb_plan = QComboBox()
        self.cmb_plan.addItem(PLAN_YOK, None)
        self.lbl_ipucu = QLabel()
        self.lbl_ipucu.setWordWrap(True)
        self.lbl_ipucu.setStyleSheet(IPUCU_STILI)

        self.cihaz_alani.currentIndexChanged.connect(self.planlari_yukle)
        self.cmb_plan.currentIndexChanged.connect(self.plan_secildi)
        self.bitis.dateChanged.connect(self.plan_secildi)

    def satirlari_ekle(self, form_layout):
        form_layout.addRow("Bağlı plan:", self.cmb_plan)
        form_layout.addRow("", self.lbl_ipucu)

    def plan_id(self):
        return self.cmb_plan.currentData()

    def secili_plan(self):
        plan_id = self.plan_id()
        return next((p for p in self.planlar if p["plan_id"] == plan_id), None)

    def planlari_yukle(self, *_):
        """Seçili cihazın aktif planlarını (bu kayıt türüne uygun olanları) listeler."""
        self.planlar = []
        self.cmb_plan.blockSignals(True)
        self.cmb_plan.clear()
        self.cmb_plan.addItem(PLAN_YOK, None)
        cihaz_id = self.cihaz_alani.currentData()
        if cihaz_id is not None:
            try:
                cevap = oturum_kontrollu_istek(
                    "GET", f"{self.api_url}/api/bakim-planlari?cihaz_id={cihaz_id}&aktif_mi=true",
                    headers={"Authorization": f"Bearer {self.token}"})
                if not oturum_hatasi_mi(cevap) and cevap.status_code == 200:
                    self.planlar = [p for p in cevap.json()
                                    if kalibrasyon_plani_mi(p["gorev_turu"]) == self.kalibrasyon_mi]
            except Exception:
                self.planlar = []
        for plan in self.planlar:
            self.cmb_plan.addItem(f"{plan['gorev_turu']} — her {plan['periyot_gun']} günde bir", plan["plan_id"])
        self.cmb_plan.blockSignals(False)
        if len(self.planlar) == 1:                       # tek plan varsa otomatik seçilir
            self.cmb_plan.setCurrentIndex(1)
        else:
            self.plan_secildi()

    def plan_secildi(self, *_):
        plan = self.secili_plan()
        if plan is None:
            self.lbl_ipucu.setText(
                "Bu cihaz için uygun plan bulunamadı. Plan eklemek için Bakım Planları sayfasını kullanın."
                if not self.planlar and self.cihaz_alani.currentData() is not None else "")
            return
        sonraki = self.bitis.date().addDays(plan["periyot_gun"])
        self.tekrar.sec(None)                            # 'Tarih seç' kipi: tarihi biz yazarız, kullanıcı değiştirebilir
        self.tekrar.sonraki.setDate(sonraki)
        self.tekrar.uyari_ayarla(plan["uyari_suresi_gun"])
        self.lbl_ipucu.setText(
            f"Sonraki tarih plana göre {sonraki.toString('dd.MM.yyyy')}; kaydedince plan da buna ilerler.")
