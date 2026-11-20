"""Rol hiyerarşisi: kullanıcı yönetimi yetkisi olan biri, kendi seviyesindeki ya da daha yüksek bir rolü atayamaz ve o roldeki
kullanıcıları yönetemez (oluşturma, rol değiştirme, aktif/pasif yapma). ADMIN en üsttür; ADMIN için mevcut özel korumalar ayrıca sürer.

Seviyeler burada tek yerde tutulur. Listede olmayan (sonradan oluşturulan) roller en düşük seviyede sayılır.
"""

ROL_SEVIYELERI = {
    "ADMIN": 100,
    "MUDUR": 80,
    "MEMUR": 50,
    "PSIKOLOG": 40,
    "PROJE ASISTANI": 30,
    "DANISMA OGRENCISI": 20,
}
VARSAYILAN_SEVIYE = 10
HIYERARSI_MESAJI = "Kendi rolünüzle aynı ya da daha yüksek seviyedeki bir rolü atayamaz veya bu roldeki kullanıcıları yönetemezsiniz."


def _ad(rol_adi) -> str:
    return str(rol_adi or "").strip().upper().replace("_", " ")


def rol_seviyesi(rol_adi) -> int:
    return ROL_SEVIYELERI.get(_ad(rol_adi), VARSAYILAN_SEVIYE)


def hiyerarsi_ihlali_var_mi(islem_yapan_rol, *hedef_roller) -> bool:
    """Hedef rollerden biri işlemi yapanın seviyesine eşit ya da üstündeyse True. ADMIN işlemi yapıyorsa hiyerarşi engel olmaz."""
    if _ad(islem_yapan_rol) == "ADMIN":
        return False
    seviye = rol_seviyesi(islem_yapan_rol)
    return any(rol_seviyesi(hedef) >= seviye for hedef in hedef_roller if hedef is not None)
