"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: JWT_SECRET Ortam Degiskeni Guvenligi

Amac:
JWT_SECRET eksik oldugunda uygulamanin
guvenli bicimde baslatilmasinin engellendigini
dogrulamak.
"""

import importlib.util
import os
from unittest.mock import patch

import pytest
import guvenlik


def test_quality_jwt_secret_eksikse_hata_olusur():
    """
    QA-001 #186

    JWT_SECRET bos oldugunda RuntimeError olusmali.
    """

    # Mevcut guvenlik.py dosyasini yeni bir modul
    # gibi yuklemek icin hazirla.
    spec = importlib.util.spec_from_file_location(
        "qa001_guvenlik_test_modulu",
        guvenlik.__file__,
    )

    assert spec is not None
    assert spec.loader is not None

    modul = importlib.util.module_from_spec(spec)

    # Gercek .env dosyasini degistirmiyoruz.
    # Test sirasinda JWT_SECRET bos gorunecek.
    with (
        patch.dict(os.environ, {"JWT_SECRET": ""}),
        patch("dotenv.load_dotenv", return_value=False),
    ):
        with pytest.raises(
            RuntimeError,
            match="JWT_SECRET ortam değişkeni tanımlı değil",
        ):
            spec.loader.exec_module(modul)
