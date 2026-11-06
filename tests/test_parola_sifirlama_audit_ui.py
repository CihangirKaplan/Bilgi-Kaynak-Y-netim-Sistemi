def test_parola_sifirlama_audit_etiketi():
    from audit_kayitlari_ekrani import OLAY_ADLARI

    assert OLAY_ADLARI["PASSWORD_RESET"] == "Parola Sıfırlama"
