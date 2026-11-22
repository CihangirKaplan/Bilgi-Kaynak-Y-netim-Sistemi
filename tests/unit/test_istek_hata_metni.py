"""Ekranlarda gösterilen hata metinleri: sunucunun Türkçe açıklaması ya da anlaşılır bağlantı mesajı; teknik metin yok."""
import ast
import inspect
import json
import re
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests

from client.api_yoneticisi import istek_hatasi_metni


def yanit(durum, detay=None, url="http://127.0.0.1:8000/api/danisma/yonetim/oturumlar/5/onayla"):
    r = requests.models.Response()
    r.status_code = durum
    r.url = url
    r._content = json.dumps({"detail": detay}).encode("utf-8") if detay is not None else b"<html>hata</html>"
    r._tkys_oturum_reddedildi = False
    return r


def http_hatasi(durum, detay=None):
    r = yanit(durum, detay)
    return requests.HTTPError(f"{durum} Client Error: Conflict for url: {r.url}", response=r)


# ------------------------------------------------------------------ ortak yardımcı
def test_sunucu_yanit_verdiyse_onun_turkce_aciklamasi_gosterilir():
    metin = istek_hatasi_metni(http_hatasi(409, "Onaylanmış görev düzenlenemez."))
    assert metin == "Onaylanmış görev düzenlenemez."
    assert "Client Error" not in metin and "http" not in metin


def test_sunucu_aciklama_gondermediyse_durum_koduna_gore_anlasilir_mesaj():
    assert istek_hatasi_metni(http_hatasi(500)) == "Sunucuda bir hata oluştu. Lütfen daha sonra tekrar deneyin."
    assert "yetkiniz" in istek_hatasi_metni(http_hatasi(403))


def test_dogrulama_hatasi_listesi_okunur_metne_cevrilir():
    detay = [{"loc": ["body", "bitis_zamani"], "msg": "Bitiş zamanı geçersiz", "type": "value_error"}]
    metin = istek_hatasi_metni(http_hatasi(422, detay))
    assert "[{" not in metin and "Bitiş zamanı geçersiz" in metin


@pytest.mark.parametrize("hata, beklenen", [
    (requests.ConnectionError("HTTPConnectionPool(host='127.0.0.1', port=8000): Max retries exceeded"),
     "Sunucuya bağlanılamadı. Bağlantınızı kontrol edin."),
    (requests.Timeout("Read timed out. (read timeout=10)"), "Sunucu yanıt vermedi. Lütfen tekrar deneyin."),
])
def test_sunucuya_ulasilamazsa_teknik_metin_yerine_baglanti_mesaji(hata, beklenen):
    assert istek_hatasi_metni(hata) == beklenen


def test_ekranin_kendi_turkce_hatasi_aynen_beklenmeyen_veri_ise_genel_mesaj():
    assert istek_hatasi_metni(RuntimeError("Zaten açık göreviniz var.")) == "Zaten açık göreviniz var."
    assert istek_hatasi_metni(KeyError("toplam_saniye")).startswith("Sunucudan beklenmeyen bir yanıt alındı")


# ------------------------------------------------------------------ ekranlar
def test_danisma_masasi_ekrani_mesajin_basina_durum_kodu_eklemez():
    from client.danisma_masasi_ekrani import DanismaMasasiEkrani

    sahte = SimpleNamespace(api_url="http://s", token="t")
    with patch("client.danisma_masasi_ekrani.oturum_kontrollu_istek", return_value=yanit(409, "Zaten açık göreviniz var.")):
        with pytest.raises(RuntimeError) as hata:
            DanismaMasasiEkrani._istek(sahte, "POST", "/api/danisma/oturum/baslat")
    assert str(hata.value) == "Zaten açık göreviniz var."


def test_oda_etkinlikleri_liste_bicimli_hatayi_okunur_gosterir():
    from client.oda_etkinlikleri_ekrani import OdaEtkinlikleriEkrani

    sahte = SimpleNamespace(api_url="http://s", token="t")
    detay = [{"loc": ["body", "oda_id"], "msg": "Oda seçilmelidir", "type": "value_error"}]
    with patch("client.oda_etkinlikleri_ekrani.oturum_kontrollu_istek", return_value=yanit(422, detay)):
        with pytest.raises(ValueError) as hata:
            OdaEtkinlikleriEkrani.istek(sahte, "POST", "/api/oda-etkinlikleri")
    assert "[{" not in str(hata.value) and "Oda seçilmelidir" in str(hata.value)


@pytest.mark.parametrize("modul", [
    "client.danisma_masasi_ekrani", "client.danisma_masasi_yonetimi", "client.danisma_masasi_raporlari",
    "client.audit_kayitlari_ekrani", "client.oda_etkinlikleri_ekrani",
])
def test_istek_hatalari_ham_haliyle_kullaniciya_gosterilmez(modul):
    """Ağ hatası yakalanan her blokta metin istek_hatasi_metni ile üretilir; {hata} ya da str(hata) yalnızca ekranın
    kendi tarih/dosya hatalarında kalabilir."""
    import importlib

    kaynak = inspect.getsource(importlib.import_module(modul))
    agac = ast.parse(kaynak)
    for dugum in ast.walk(agac):
        if not isinstance(dugum, ast.ExceptHandler) or dugum.name is None:
            continue
        yakalanan = ast.unparse(dugum.type) if dugum.type is not None else ""
        if "RequestException" not in yakalanan and "HTTPError" not in yakalanan:
            continue
        govde = "\n".join(ast.unparse(d) for d in dugum.body)
        ad = dugum.name
        assert not re.search(rf"\{{{ad}\}}|str\({ad}\)", govde), f"{modul}: satır {dugum.lineno} ham hata gösteriyor"


def test_ana_penceredeki_butun_istekler_zaman_asimi_icerir():
    """Sunucu yanıt vermezse ana pencere donmamalı (ör. faaliyet kayıtlarını listeleme ve silme)."""
    import client.main_window as mw

    agac = ast.parse(inspect.getsource(mw))
    cagrilar = [d for d in ast.walk(agac) if isinstance(d, ast.Call) and ast.unparse(d.func) == "oturum_kontrollu_istek"]
    eksik = [c.lineno for c in cagrilar if not any(k.arg == "timeout" for k in c.keywords)]
    assert cagrilar and eksik == []
