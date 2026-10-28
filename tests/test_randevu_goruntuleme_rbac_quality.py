"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: Randevu Goruntuleme ve Danisan Kodu RBAC

Amac:
Yetkisiz rollerin randevulari goruntulemesini
ve danisan kodu olusturmasini engellemek.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from sunucu import randevulari_listele, danisan_kodu_olustur


@pytest.mark.parametrize("rol", [None, ("MEMUR",)])
def test_quality_yetkisiz_rol_randevulari_goremez(rol):
    """
    QA-001 #186:
    Yetkisiz kullanici randevu listesini gorememeli.
    """

    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = rol

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            randevulari_listele(kullanici_id=10)

    assert hata.value.status_code == 403

    conn.commit.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


@pytest.mark.parametrize("rol", [None, ("MEMUR",)])
def test_quality_yetkisiz_rol_danisan_kodu_olusturamaz(rol):
    """
    QA-001 #186:
    Yetkisiz kullanici danisan kodu olusturamamali.
    """

    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = rol

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            danisan_kodu_olustur(
                ucretli_mi=True,
                istisna_turu="YOK",
                kullanici_id=10,
            )

    assert hata.value.status_code == 403

    conn.commit.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()
