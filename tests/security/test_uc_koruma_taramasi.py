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

from server.sunucu import app

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
    ("POST", "/api/cikis"): "Her oturum açık kullanıcı kendi oturumunu kapatabilmeli (ilk girişte şifre değiştirme bekleyen dahil); yalnızca kendi hesabının oturum sürümünü artırır, izin gerektirmez.",
    ("POST", "/api/sifre-degistir"): "İlk girişte şifre değiştirmek için yalnızca token yeterli olmalı.",
    ("GET", "/api/korumali-test"): "Token doğrulama deneme ucu; veri döndürmez.",
    ("GET", "/api/saglik"): "Sunucunun ayakta olduğunu gösterir; veri döndürmez, veritabanına bağlanmaz.",
    ("GET", "/api/yetkilerim"): "Kullanıcı yalnızca kendi rolünün izinlerini görür; ayrıca izin gerektirmez.",
    ("GET", "/api/dashboard/bugunku-etkinlikler"): "Ana panel: bugünkü oda etkinlikleri (saat, ad, oda, katılımcı sayısı); salt okunur, kişi adı "
                                                   "içermez; giriş yapmış herkes görebilir (etkinlik eklemek/düzenlemek ODA_ETKINLIK_YONET ister).",
    ("GET", "/api/dashboard/benim-gunum"): "Ana panel: yalnızca giriş yapan kişinin KENDİ bugünkü/yarınki randevu ve cihaz rezervasyonları; başkasının kaydı dönmez, izin gerektirmez.",
    ("GET", "/api/duyurular"): "Kurum içi duyuruları giriş yapmış herkes okur; yazan kişinin adı yalnızca DUYURU_YONET sahibine gösterilir "
                               "(yayınlama ve kaldırma DUYURU_YONET ister).",
    ("POST", "/api/duyurular/okundu"): "Çağıranın KENDİ okundu bilgisini değiştirir (duyuru silinmez, başkalarını etkilemez); yalnızca token yeterli.",
    ("POST", "/api/duyurular/{duyuru_id}/okundu"): "Çağıranın KENDİ okundu bilgisini değiştirir (duyuru silinmez, başkalarını etkilemez); yalnızca token yeterli.",
    ("DELETE", "/api/duyurular/{duyuru_id}/okundu"): "Çağıranın KENDİ okundu işaretini kaldırır; yalnızca token yeterli.",
    ("GET", "/api/surum"): "Hakkında penceresi için sürüm bilgisi; giriş yapmış herkes görebilir, kişisel veri ve ayar döndürmez.",
    ("POST", "/api/liste-aktarim-kaydi"): "JWT ile kimlik doğrulanır; kaydı yazmadan önce listenin kendi görüntüleme izni "
                                           "(LISTE_AKTARIM_HEDEFLERI) sunucuda denetlenir, izin yoksa 403 döner.",
}


def _bagimlilik_adlari(bagimlilik):
    adlar = []
    for alt in bagimlilik.dependencies:
        adlar.append(getattr(alt.call, "__name__", type(alt.call).__name__))
        adlar.extend(_bagimlilik_adlari(alt))
    return adlar


def _api_rotalari(rotalar, onek="", ek_bagimliliklar=()):
    """`include_router` ile eklenen yönlendiricileri de gezer (FastAPI bunları `_IncludedRouter` olarak sarar ve `app.routes`
    içinde APIRoute olarak göstermez). Yönlendirici düzeyindeki bağımlılıklar da uç korumasına sayılır."""
    for rota in rotalar:
        if isinstance(rota, APIRoute):
            yield rota, onek, [getattr(d.dependency, "__name__", "") for d in ek_bagimliliklar]
            continue
        asil = getattr(rota, "original_router", None)
        if asil is not None:
            baglam = getattr(rota, "include_context", None)
            yield from _api_rotalari(
                asil.routes,
                onek + (getattr(baglam, "prefix", "") or ""),
                tuple(ek_bagimliliklar) + tuple(getattr(baglam, "dependencies", None) or ()),
            )


def _tum_uclar():
    for rota, onek, ek_adlar in _api_rotalari(app.routes):
        for yontem in sorted(rota.methods - {"HEAD", "OPTIONS"}):
            yield yontem, onek + rota.path, _bagimlilik_adlari(rota.dependant) + ek_adlar


def test_uygulamada_taranacak_uc_var():
    assert len(list(_tum_uclar())) > 50


def test_tarama_uygulamanin_butun_uclarini_gorur_hicbiri_gizli_kalmaz():
    """Tarama, OpenAPI şemasındaki her (yöntem, yol) ikilisini görmeli: yönlendirici (include_router) ile eklenen uçlar taramanın dışında
    kalırsa korumasız bir uç fark edilmeden eklenebilir (FastAPI bunları `app.routes` içinde APIRoute olarak göstermez)."""
    sema = {(yontem.upper(), yol) for yol, islemler in app.openapi()["paths"].items() for yontem in islemler}
    taranan = {(yontem, yol) for yontem, yol, _ in _tum_uclar()}
    assert sema == taranan, f"şemada olup taramada olmayan: {sorted(sema - taranan)}; taramada olup şemada olmayan: {sorted(taranan - sema)}"


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
    