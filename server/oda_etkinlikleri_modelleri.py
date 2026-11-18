"""Oda Etkinlikleri API veri modelleri."""

from datetime import datetime, timedelta, time

from pydantic import BaseModel, ConfigDict, Field, model_validator



def etkinlik_gunluk_araliklari(baslangic, bitis):
    """Seçilen tüm günlerde aynı saatleri kullan."""
    if baslangic.date() > bitis.date():
        raise ValueError("Bitiş tarihi başlangıçtan önce olamaz.")

    ilk = baslangic.time()
    son = bitis.time()

    if not (
        time(8, 0) <= ilk < son <= time(18, 0)
        and ilk.second == 0
        and ilk.microsecond == 0
        and son.second == 0
        and son.microsecond == 0
    ):
        raise ValueError(
            "Etkinlik saatleri 08:00-18:00 arasında olmalıdır."
        )

    gun_sayisi = (bitis.date() - baslangic.date()).days + 1
    if gun_sayisi > 366:
        raise ValueError("Etkinlik en fazla 366 gün sürebilir.")

    return [
        (
            datetime.combine(
                baslangic.date() + timedelta(days=i), ilk
            ),
            datetime.combine(
                baslangic.date() + timedelta(days=i), son
            ),
        )
        for i in range(gun_sayisi)
    ]


def etkinlik_oturumlarini_dogrula(araliklar):
    """Bağımsız etkinlik oturumlarını doğrula ve sırala."""
    if not araliklar:
        raise ValueError("En az bir etkinlik günü eklenmelidir.")

    if len(araliklar) > 366:
        raise ValueError("En fazla 366 oturum eklenebilir.")

    sirali = sorted(araliklar, key=lambda x: x[0])

    for bas, bit in sirali:
        if bas.date() != bit.date():
            raise ValueError(
                "Her oturum aynı takvim günü içinde bitmelidir."
            )

        if not (
            time(8, 0) <= bas.time() < bit.time() <= time(18, 0)
        ):
            raise ValueError(
                "Her oturum 08.00-18.00 arasında olmalı; "
                "bitiş saati başlangıçtan sonra gelmelidir."
            )

        if any(
            x.second or x.microsecond
            for x in (bas, bit)
        ):
            raise ValueError(
                "Oturum saatleri dakika hassasiyetinde olmalıdır."
            )

    for onceki, sonraki in zip(sirali, sirali[1:]):
        if onceki[1] > sonraki[0]:
            raise ValueError(
                "Aynı etkinliğin oturumları birbiriyle çakışamaz."
            )

    if (sirali[-1][1].date() - sirali[0][0].date()).days >= 366:
        raise ValueError(
            "Etkinliğin ilk ve son günü arasında "
            "en fazla 366 gün olabilir."
        )

    return sirali


class OdaEtkinlikGunModeli(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baslangic_zamani: datetime
    bitis_zamani: datetime

    @model_validator(mode="after")
    def saat_kontrolu(self):
        etkinlik_oturumlarini_dogrula([
            (self.baslangic_zamani, self.bitis_zamani)
        ])
        return self


class OdaEtkinlikOlusturModeli(BaseModel):
    model_config = ConfigDict(extra="forbid")

    oda_id: int = Field(gt=0)
    organize_eden_personel_id: int = Field(gt=0)
    etkinlik_adi: str = Field(min_length=1, max_length=150)
    katilimci_sayisi: int | None = Field(default=None, ge=0)
    baslangic_zamani: datetime | None = None
    bitis_zamani: datetime | None = None
    gunler: list[OdaEtkinlikGunModeli] | None = Field(
        default=None, min_length=1, max_length=366
    )

    @model_validator(mode="after")
    def zaman_kontrolu(self):
        if self.gunler is not None:
            etkinlik_oturumlarini_dogrula([
                (g.baslangic_zamani, g.bitis_zamani)
                for g in self.gunler
            ])
        elif (
            self.baslangic_zamani is not None
            and self.bitis_zamani is not None
        ):
            etkinlik_gunluk_araliklari(
                self.baslangic_zamani, self.bitis_zamani
            )
        else:
            raise ValueError(
                "Etkinlik günleri veya başlangıç ve bitiş "
                "zamanları belirtilmelidir."
            )
        return self


class OdaEtkinlikGuncelleModeli(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gunler: list[OdaEtkinlikGunModeli] | None = Field(
        default=None, min_length=1, max_length=366
    )

    oda_id: int | None = Field(default=None, gt=0)
    organize_eden_personel_id: int | None = Field(default=None, gt=0)
    etkinlik_adi: str | None = Field(default=None, min_length=1, max_length=150)
    katilimci_sayisi: int | None = Field(default=None, ge=0)
    baslangic_zamani: datetime | None = None
    bitis_zamani: datetime | None = None
