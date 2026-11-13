"""Uç koruma taraması (SEC-T02 regresyon testi).

Uygulamadaki her API ucu için hangi bağımlılıkla korunduğunu FastAPI'nin
bağımlılık ağacından okur. Bir uç yalnızca "giriş yapmış olmayı" istiyorsa
(mevcut_kullanici_id) veya hiç kimlik istemiyorsa ve aşağıdaki bilinçli
istisna listesinde yoksa test başarısız olur.

Yeni bir uç eklerken:
  * Normalde `Depends(izin_kontrol("IZIN_ADI"))` kullanın; test geçer.
  * Bilinçli olarak izinsiz bırakılacaksa (örn. giriş ucu), ucu ISTISNALAR'a
    gerekçesiyle ekleyin. Bu, kod incelemesinde görünür bir karardır.
"""
from fastapi.routing import APIRoute

from sunucu import app

# (yöntem, yol): gerekçe
ISTISNALAR = {
    # Bu dört uç izinsiz değildir. JWT kimlik doğrulamasından sonra
    # bakım/kalibrasyon izinleri sunucuda plan türüne göre denetlenir.
    # GET: yetkili türleri filtreler.
    # POST: oluşturulacak türü kontrol eder.
    # PUT: mevcut ve yeni türün izinlerini kontrol eder.
    # DELETE: silinecek planın türünü kontrol eder.
    ("GET", "/api/bakim-planlari"):
        "JWT ve _plan_yetkileri ile tür bazlı filtreleme.",
    ("POST", "/api/bakim-planlari"):
        "JWT ve _plan_turu_yetkisini_dogrula ile tür bazlı izin.",
    ("PUT", "/api/bakim-planlari/{plan_id}"):
        "JWT ile mevcut ve yeni plan türünün izni doğrulanır.",
    ("DELETE", "/api/bakim-planlari/{plan_id}"):
        "JWT ile kayıt türünün silme izni doğrulanır.",
    ("POST", "/api/login"): "Giriş öncesi çağrılır; kimlik istenemez.",
    ("POST", "/api/parola-sifirlama-talebi"): "Parolasını unutan kullanıcı giriş yapamaz; yalnızca kullanıcı adı alınır, "
                                               "yanıt kullanıcının var olup olmadığını belli etmez, kullanıcı başına tek açık talep tutulur.",
    ("POST", "/api/sifre-degistir"): "İlk girişte şifre değiştirmek için yalnızca token yeterli olmalı.",
    ("GET", "/api/korumali-test"): "Token doğrulama deneme ucu; veri döndürmez.",
    ("GET", "/api/saglik"): "Sunucunun ayakta olduğunu gösterir; veri döndürmez, veritabanına bağlanmaz.",
    ("GET", "/api/yetkilerim"): "Kullanıcı yalnızca kendi rolünün izinlerini görür; ayrıca izin gerektirmez.",
}


def _bagimlilik_adlari(bagimlilik):
    adlar = []
    for alt in bagimlilik.dependencies:
        adlar.append(getattr(alt.call, "__name__", type(alt.call).__name__))
        adlar.extend(_bagimlilik_adlari(alt))
    return adlar


def _tum_uclar():
    for rota in app.routes:
        if not isinstance(rota, APIRoute):
            continue
        for yontem in sorted(rota.methods - {"HEAD", "OPTIONS"}):
            yield yontem, rota.path, _bagimlilik_adlari(rota.dependant)


def test_uygulamada_taranacak_uc_var():
    assert len(list(_tum_uclar())) > 50


def test_her_uc_izinle_korunur_veya_bilincli_istisnadir():
    korumasiz = [
        f"{yontem} {yol}"
        for yontem, yol, adlar in _tum_uclar()
        if "kontrol" not in adlar and (yontem, yol) not in ISTISNALAR
    ]
    assert not korumasiz, (
        "Şu uçlar izin kontrolü (izin_kontrol) olmadan tanımlanmış: "
        + ", ".join(korumasiz)
        + ". Depends(izin_kontrol('IZIN_ADI')) ekleyin veya gerekçesiyle "
        "ISTISNALAR listesine alın."
    )


def test_istisna_listesinde_olmayan_uc_yok():
    """Silinen/yeniden adlandırılan bir uç istisna listesinde asılı kalmasın."""
    mevcut = {(yontem, yol) for yontem, yol, _ in _tum_uclar()}
    eskimis = sorted(set(ISTISNALAR) - mevcut)
    assert not eskimis, f"ISTISNALAR'da artık var olmayan uçlar: {eskimis}"


def test_istisnalar_gercekten_izinsiz():
    """Bir istisna sonradan izin kontrolü alırsa listeden çıkarılmalı."""
    izinli = [
        f"{yontem} {yol}"
        for yontem, yol, adlar in _tum_uclar()
        if (yontem, yol) in ISTISNALAR and "kontrol" in adlar
    ]
    assert not izinli, f"Artık izin kontrolü olan uçlar istisnadan çıkarılmalı: {izinli}"
    