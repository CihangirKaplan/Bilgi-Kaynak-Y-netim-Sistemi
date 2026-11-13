def test_parola_sifirlama_audit_etiketi():
    from audit_kayitlari_ekrani import OLAY_ADLARI

    assert OLAY_ADLARI["PASSWORD_RESET"] == "Parola Sıfırlama"


def test_parola_degistirme_audit_etiketleri():
    from audit_kayitlari_ekrani import OLAY_ADLARI, OLAY_RENKLERI

    assert OLAY_ADLARI["PASSWORD_CHANGE"] == "Parola Değiştirme"
    assert OLAY_ADLARI["PASSWORD_CHANGE_FAILED"] == "Başarısız Parola Değiştirme"

    assert "PASSWORD_CHANGE" in OLAY_RENKLERI
    assert "PASSWORD_CHANGE_FAILED" in OLAY_RENKLERI
