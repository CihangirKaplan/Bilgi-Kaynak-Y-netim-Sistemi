"""Oda etkinliği seçeneklerinde psikolog odası filtresi."""

import ast
import inspect
import textwrap

from server.oda_etkinlikleri_api import router_olustur


def test_seceneklerde_aktif_psikolog_odasi_haric():
    kaynak = textwrap.dedent(inspect.getsource(router_olustur))
    agac = ast.parse(kaynak)

    fonksiyon = next(
        dugum for dugum in ast.walk(agac)
        if isinstance(dugum, ast.FunctionDef)
        and dugum.name == "etkinlik_secenekleri"
    )

    sorgular = [
        dugum.value
        for dugum in ast.walk(fonksiyon)
        if isinstance(dugum, ast.Constant)
        and isinstance(dugum.value, str)
    ]

    oda_sorgusu = next(
        sorgu for sorgu in sorgular
        if "FROM odalar o" in sorgu
    )

    normal = " ".join(oda_sorgusu.split())

    assert "o.aktif_mi = TRUE" in normal
    assert "NOT EXISTS" in normal
    assert "FROM psikolog_odalar po" in normal
    assert "po.oda_id = o.oda_id" in normal
    assert "k.aktif_mi IS TRUE" in normal
