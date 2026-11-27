"""GET /api/psikologlar: varsayılan yalnızca aktif psikologlar (randevu formundaki seçim); pasifler_dahil=true ad gösterimi içindir.

pasifler_dahil=true: randevusu ya da danışan kodu olan pasif / başka role geçmiş eski psikologlar da gelir, her kayıtta aktif_mi bulunur.
"""
from unittest.mock import MagicMock, patch

from server.sunucu import app, aktif_psikologlari_listele


def _duz_rotalar(rotalar):
    """`include_router` ile eklenen uçlar `app.routes` içinde doğrudan görünmez; yönlendirici sarmalayıcılarının içine de bakılır."""
    for r in rotalar:
        asil = getattr(r, "original_router", None)
        if asil is not None:
            yield from _duz_rotalar(asil.routes)
        else:
            yield r


def _cagir(satirlar, **kwargs):
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchall.return_value = satirlar
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        sonuc = aktif_psikologlari_listele(kullanici_id=1, **kwargs)
    return sonuc, " ".join(imlec.execute.call_args.args[0].split())


def test_varsayilan_yalnizca_aktif_psikologlar_ve_yanit_degismez():
    sonuc, sql = _cagir([(3, "ayse", 13)])
    assert sonuc == [{"personel_id": 3, "ad_soyad": "ayse", "kullanici_id": 13}]                    # eski istemciler için aynı biçim
    assert "p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG'" in sql
    assert "EXISTS" not in sql and "aktif_mi," not in sql


def test_pasifler_dahil_eski_psikologlari_aktiflik_bilgisiyle_getirir():
    sonuc, sql = _cagir([(3, "ayse", 13, True), (19, "eski_psikolog", 40, False)], pasifler_dahil=True)
    assert sonuc == [{"personel_id": 3, "ad_soyad": "ayse", "kullanici_id": 13, "aktif_mi": True},
                     {"personel_id": 19, "ad_soyad": "eski_psikolog", "kullanici_id": 40, "aktif_mi": False}]
    assert "EXISTS (SELECT 1 FROM randevular x WHERE x.psikolog_id = p.personel_id)" in sql              # randevusu olan eski psikolog
    assert "EXISTS (SELECT 1 FROM danisan_kodlari d WHERE d.olusturan_psikolog_id = p.personel_id)" in sql  # danışan kodu olan eski psikolog
    assert "UPPER(r.rol_adi) = 'PSIKOLOG') AS aktif_mi" in sql                                          # başka role geçen aktif sayılmaz


def test_uc_noktada_pasifler_dahil_sorgu_parametresi_var_varsayilan_kapali():
    yol = next(r for r in _duz_rotalar(app.routes) if getattr(r, "path", None) == "/api/psikologlar")
    parametre = next(p for p in yol.dependant.query_params if p.name == "pasifler_dahil")
    assert parametre.default is False
