"""SEC-001 canlı ortam denemeleri (SEC-T01, T02, T03, T07, T08): istemci bilgisayardan, sunucuya HTTP(S) istekleriyle.

Bu betik GÜVENLİK RAPORUNDAKİ "Canlı ⏳" satırlarının API tarafını otomatik yapar ve her adımın beklenen / gerçek sonucunu
yazar. Sunucudaki işleri (SEC-T10 .env, T11 pip-audit, T12 psql, T13 icacls) yapmaz; onlar rapordaki komutlarla elle yapılır.

KULLANIM (proje klasöründe, sanal ortam açıkken):

    python scripts/canli_guvenlik_denemesi.py --adres https://SUNUCU:8443 --ca sertifika.pem --yetkisiz psikologA

Hiçbir parola komut satırına yazılmaz: betik her hesap için parolayı gizli olarak sorar (ya da SEC_PAROLA_<HESAP> ortam değişkeninden okur;
örn. hesap "psikologA" için SEC_PAROLA_PSIKOLOGA). Çıktıda parola ve oturum anahtarı (token) YAZILMAZ; kanıt dosyası olduğu gibi rapora eklenebilir.

HESAPLAR (gerçek kullanıcı değil, bu iş için açılmış TEST hesapları kullanın):
  --yetkisiz HESAP         SEC-T02, T08: yönetim yetkisi olmayan hesap (örn. Psikolog)
  --psikolog-a / -b HESAP  SEC-T03: iki farklı psikolog (A'nın planlı randevusu olmalı)
  --asistan HESAP          SEC-T03: cihaz rezervasyonu iznine sahip ama rezervasyonu yönetemeyen hesap (örn. Proje Asistanı);
                           başkasına ait aktif bir rezervasyon bulunmalı
  --kilit-hesabi HESAP     SEC-T07: kilitlenmesi önemli olmayan test hesabı (1 dakika kilitlenir)
  --yonetici HESAP + --pasiflestirme-hesabi HESAP   SEC-T08: yönetici test hesabını pasifleştirir, token'ın geçersiz olduğunu görür,
                           hesabı geri açar (pasifleştirilecek hesap Psikolog OLMAMALI: psikolog aktifleştirmede oda ister)

VERİYİ DEĞİŞTİREBİLECEK adımlar (T03: yetkisizlik çalışmazsa başkasının kaydı iptal olur; T07: hesap 1 dk kilitlenir;
T08: hesap kısa süre pasif olur) yalnızca --onay verilirse çalışır. Verilmeyen adımlar "ATLANDI" yazılır.
Çıkış kodu: 0 = çalışan her adım PASS, 1 = en az bir FAIL, 2 = kullanım hatası.
"""
import argparse
import base64
import datetime
import getpass
import json
import os
import re
import sys
import time

import requests

ADIMLAR = ("T01", "T02", "T03", "T07", "T08")
ZAMAN_ASIMI = 20


class Sonuclar:
    """Adım sonuçlarını toplar; ekrana ve kanıt dosyasına parola/token içermeyen satırlar yazar."""

    def __init__(self, kanit_yolu):
        self.satirlar = []
        self.kanit_yolu = kanit_yolu
        self.kanit = open(kanit_yolu, "w", encoding="utf-8")

    def yaz(self, metin=""):
        print(metin, flush=True)
        self.kanit.write(metin + "\n")
        self.kanit.flush()

    def adim(self, kimlik, aciklama, beklenen, gercek, gecti):
        durum = "PASS" if gecti else "FAIL"
        self.satirlar.append((kimlik, durum))
        self.yaz(f"  [{durum}] {kimlik} {aciklama}\n         beklenen: {beklenen} | gerçek: {gercek}")

    def atla(self, kimlik, aciklama, neden):
        self.satirlar.append((kimlik, "ATLANDI"))
        self.yaz(f"  [ATLANDI] {kimlik} {aciklama}\n         neden: {neden}")

    def kapat(self):
        self.kanit.close()


class Istemci:
    def __init__(self, adres, dogrulama):
        self.adres = adres.rstrip("/")
        self.oturum = requests.Session()
        self.oturum.verify = dogrulama

    def istek(self, yontem, yol, token=None, govde=None):
        basliklar = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            yanit = self.oturum.request(yontem, self.adres + yol, headers=basliklar, json=govde, timeout=ZAMAN_ASIMI)
        except requests.exceptions.SSLError as hata:
            raise SystemExit(f"TLS hatası: {hata}\n  Kendi imzalı sertifika için --ca sertifika.pem verin.")
        except requests.exceptions.RequestException as hata:
            raise SystemExit(f"Sunucuya ulaşılamadı ({self.adres}): {hata}")
        return yanit

    def giris(self, kullanici, parola):
        yanit = self.istek("POST", "/api/login", govde={"kullanici_adi": kullanici, "parola": parola})
        govde = _json(yanit)
        return yanit, govde.get("access_token") if yanit.status_code == 200 else None


def _json(yanit):
    try:
        veri = yanit.json()
        return veri if isinstance(veri, (dict, list)) else {}
    except ValueError:
        return {}


def _ayrinti(yanit):
    """Yanıtın kısa, güvenli özeti: HTTP kodu ve (varsa) detail metni; token ya da parola içermez."""
    veri = _json(yanit)
    detay = veri.get("detail") if isinstance(veri, dict) else None
    if isinstance(detay, list):
        detay = "doğrulama hatası"
    metin = f"HTTP {yanit.status_code}" + (f" \"{str(detay)[:70]}\"" if detay else "")
    return metin


_PAROLALAR = {}                       # aynı çalıştırmada bir hesabın parolası yalnızca bir kez sorulur (bellekte kalır, diske yazılmaz)


def parola_al(hesap):
    if hesap not in _PAROLALAR:
        ortam = "SEC_PAROLA_" + re.sub(r"[^A-Za-z0-9]", "_", hesap).upper()
        _PAROLALAR[hesap] = os.environ.get(ortam) or getpass.getpass(f"  '{hesap}' hesabının parolası (ekranda görünmez): ")
    return _PAROLALAR[hesap]


def oturum_ac(sonuc, istemci, hesap):
    """Hesapla giriş yapar; başarısızsa None döner (ve nedenini yazar)."""
    yanit, token = istemci.giris(hesap, parola_al(hesap))
    if token is None:
        sonuc.yaz(f"  ! '{hesap}' ile giriş yapılamadı: {_ayrinti(yanit)}")
    return token, _json(yanit)


# ---------------------------------------------------------------------------------------------------------- adımlar
def t01(sonuc, istemci, _args):
    sonuc.yaz("\nSEC-T01 — Authentication Bypass (token yok / bozuk token)")
    yanit = istemci.istek("GET", "/api/saglik")
    sonuc.adim("T01.1", "/api/saglik tokensiz açık (sağlık kontrolü)", "200", _ayrinti(yanit), yanit.status_code == 200)
    for yol in ("/api/cihazlar", "/api/randevular", "/api/yetkilerim", "/api/audit-kayitlari"):
        yanit = istemci.istek("GET", yol)
        sonuc.adim("T01.2", f"GET {yol} tokensiz", "401", _ayrinti(yanit), yanit.status_code == 401)
    yanit = istemci.istek("GET", "/api/cihazlar", token="abc.def.ghi")
    sonuc.adim("T01.3", "GET /api/cihazlar bozuk token ile", "401", _ayrinti(yanit), yanit.status_code == 401)


def t02(sonuc, istemci, args):
    sonuc.yaz("\nSEC-T02 — Function-Level Authorization (yetkisiz rol yönetim uçlarına erişemez)")
    if not args.yetkisiz:
        return sonuc.atla("T02", "yetkisiz hesapla yönetim uçları", "--yetkisiz HESAP verilmedi")
    token, _ = oturum_ac(sonuc, istemci, args.yetkisiz)
    if token is None:
        return sonuc.adim("T02.0", f"'{args.yetkisiz}' girişi", "200", "giriş yapılamadı", False)
    istekler = [
        ("GET", "/api/yonetim-raporlari/randevu-ozet", None),
        ("GET", "/api/audit-kayitlari", None),
        ("POST", "/api/kullanicilar", {"kullanici_adi": "sec_deneme_hesabi", "rol_id": 1}),
        ("PATCH", "/api/kullanicilar/1/rol", {"rol_id": 1}),
    ]
    for yontem, yol, govde in istekler:
        yanit = istemci.istek(yontem, yol, token=token, govde=govde)
        sonuc.adim("T02.1", f"{yontem} {yol} ({args.yetkisiz})", "403", _ayrinti(yanit), yanit.status_code == 403)


def t03(sonuc, istemci, args):
    sonuc.yaz("\nSEC-T03 — Object-Level Authorization (başkasının kaydı değiştirilemez)")
    if not args.onay:
        return sonuc.atla("T03", "başkasının randevusu / rezervasyonu", "--onay verilmedi (yetkisizlik çalışmazsa gerçek kayıt iptal olur)")
    # --- randevu: psikolog B, psikolog A'nın randevusunu iptal etmeyi dener
    if args.psikolog_a and args.psikolog_b:
        token_a, _ = oturum_ac(sonuc, istemci, args.psikolog_a)
        token_b, _ = oturum_ac(sonuc, istemci, args.psikolog_b)
        if token_a and token_b:
            liste = _json(istemci.istek("GET", "/api/randevular", token=token_a))
            planli = next((r for r in (liste if isinstance(liste, list) else []) if str(r.get("durum", "")).upper() == "PLANLANDI"), None)
            if planli is None:
                sonuc.atla("T03.1", "psikolog B → A'nın randevusu", f"{args.psikolog_a} hesabının planlı randevusu yok (bir test randevusu açın)")
            else:
                yanit = istemci.istek("PATCH", f"/api/randevular/{planli['randevu_id']}/iptal", token=token_b, govde={"iptal_nedeni": "HATALI_KAYIT"})
                sonuc.adim("T03.1", f"{args.psikolog_b}, {args.psikolog_a} kullanıcısının randevusunu iptal etmeye çalışır", "403 ya da 404", _ayrinti(yanit),
                           yanit.status_code in (403, 404))
                sonra = _json(istemci.istek("GET", "/api/randevular", token=token_a))
                ayni = next((r for r in (sonra if isinstance(sonra, list) else []) if r.get("randevu_id") == planli["randevu_id"]), None)
                sonuc.adim("T03.2", "A'nın randevusu hâlâ planlı (kayıt değişmedi)", "PLANLANDI", (ayni or {}).get("durum", "bulunamadı"),
                           bool(ayni) and str(ayni.get("durum", "")).upper() == "PLANLANDI")
    else:
        sonuc.atla("T03.1", "psikolog B → A'nın randevusu", "--psikolog-a ve --psikolog-b verilmedi")
    # --- cihaz rezervasyonu: yönetemeyen hesap başkasının rezervasyonunu iptal etmeyi dener
    if args.asistan:
        token, _ = oturum_ac(sonuc, istemci, args.asistan)
        if token:
            liste = _json(istemci.istek("GET", "/api/rezervasyonlar", token=token))
            hedef = next((r for r in (liste if isinstance(liste, list) else []) if r.get("durum") == "Aktif" and r.get("yonetebilir") is False), None)
            if hedef is None:
                sonuc.atla("T03.3", "yetkisiz hesap → başkasının cihaz rezervasyonu", "başkasına ait, yönetilemeyen aktif rezervasyon yok (bir test rezervasyonu açın)")
            else:
                yanit = istemci.istek("PATCH", f"/api/rezervasyonlar/{hedef['rezervasyon_id']}/iptal", token=token)
                sonuc.adim("T03.3", f"{args.asistan}, başkasının rezervasyonunu iptal etmeye çalışır", "403", _ayrinti(yanit), yanit.status_code == 403)
                sonra = _json(istemci.istek("GET", "/api/rezervasyonlar", token=token))
                ayni = next((r for r in (sonra if isinstance(sonra, list) else []) if r.get("rezervasyon_id") == hedef["rezervasyon_id"]), None)
                sonuc.adim("T03.4", "rezervasyon hâlâ aktif (kayıt değişmedi)", "Aktif", (ayni or {}).get("durum", "bulunamadı"), bool(ayni) and ayni.get("durum") == "Aktif")
    else:
        sonuc.atla("T03.3", "yetkisiz hesap → başkasının cihaz rezervasyonu", "--asistan verilmedi")


def t07(sonuc, istemci, args):
    sonuc.yaz("\nSEC-T07 — Rate / Brute-Force (hesap kilidi)")
    if not args.kilit_hesabi:
        return sonuc.atla("T07", "5 yanlış parola ile hesap kilidi", "--kilit-hesabi HESAP verilmedi")
    if not args.onay:
        return sonuc.atla("T07", "5 yanlış parola ile hesap kilidi", "--onay verilmedi (hesap 1 dakika kilitlenir)")
    dogru = parola_al(args.kilit_hesabi)
    kodlar = []
    son = None
    for _ in range(5):
        son = istemci.giris(args.kilit_hesabi, "Yanlis-Parola-Denemesi-1!")[0]
        kodlar.append(son.status_code)
        if son.status_code == 429:
            break
    sonuc.adim("T07.1", "yanlış parolalar: ilk denemeler 401, kilit eşiğinde 429", "…401, 401, 429 (en geç 5. denemede)", ", ".join(map(str, kodlar)),
               kodlar[-1] == 429 and set(kodlar[:-1]) <= {401})
    yanit, token = istemci.giris(args.kilit_hesabi, dogru)
    sonuc.adim("T07.2", "kilit sürerken DOĞRU parola da kabul edilmez", "429, token yok", _ayrinti(yanit) + (" (token verildi!)" if token else ""),
               yanit.status_code == 429 and token is None)
    bekle = int(yanit.headers.get("Retry-After", "0") or 0)
    sonuc.adim("T07.3", "Retry-After başlığı kalan süreyi bildirir", "1-900 sn", f"{bekle} sn", 1 <= bekle <= 900)
    if 1 <= bekle <= 90:
        sonuc.yaz(f"         kilidin açılması bekleniyor ({bekle + 1} sn)…")
        time.sleep(bekle + 1)
        yanit, token = istemci.giris(args.kilit_hesabi, dogru)
        sonuc.adim("T07.4", "kilit süresi dolunca doğru parola kabul edilir", "200 + token", _ayrinti(yanit), yanit.status_code == 200 and token is not None)
    else:
        sonuc.atla("T07.4", "kilit süresi dolunca giriş", f"kilit {bekle} sn; beklenmedi (15 dk kilit olabilir: önceki denemelerden kalan sayaç)")


def _sahte_imza(token):
    """İmzası bozulmuş token: son karakter değiştirilir."""
    ana, _, imza = token.rpartition(".")
    return ana + "." + imza[:-1] + ("A" if imza[-1] != "A" else "B")


def _alg_none(token):
    """Aynı yük, imzasız ('alg': 'none') token."""
    parcalar = token.split(".")
    ust = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    return f"{ust}.{parcalar[1]}."


def t08(sonuc, istemci, args):
    sonuc.yaz("\nSEC-T08 — Token (değiştirilmiş token, pasifleştirilen kullanıcının token'ı)")
    if not args.yetkisiz:
        sonuc.atla("T08.1", "değiştirilmiş token", "--yetkisiz HESAP verilmedi")
    else:
        token, _ = oturum_ac(sonuc, istemci, args.yetkisiz)
        if token:
            yanit = istemci.istek("GET", "/api/yetkilerim", token=token)
            sonuc.adim("T08.0", "geçerli token ile kontrol isteği", "200", _ayrinti(yanit), yanit.status_code == 200)
            yanit = istemci.istek("GET", "/api/yetkilerim", token=_sahte_imza(token))
            sonuc.adim("T08.1", "imzası bozulmuş token", "401", _ayrinti(yanit), yanit.status_code == 401)
            yanit = istemci.istek("GET", "/api/yetkilerim", token=_alg_none(token))
            sonuc.adim("T08.2", "imzasız ('alg: none') token", "401", _ayrinti(yanit), yanit.status_code == 401)
    if not (args.yonetici and args.pasiflestirme_hesabi):
        return sonuc.atla("T08.3", "pasifleştirilen kullanıcının token'ı", "--yonetici ve --pasiflestirme-hesabi verilmedi")
    if not args.onay:
        return sonuc.atla("T08.3", "pasifleştirilen kullanıcının token'ı", "--onay verilmedi (test hesabı kısa süre pasif olur)")
    yonetici_token, _ = oturum_ac(sonuc, istemci, args.yonetici)
    hedef_token, hedef = oturum_ac(sonuc, istemci, args.pasiflestirme_hesabi)
    if not (yonetici_token and hedef_token and hedef.get("kullanici_id")):
        return sonuc.adim("T08.3", "yönetici ve hedef hesap girişi", "200", "giriş yapılamadı", False)
    yol = f"/api/kullanicilar/{hedef['kullanici_id']}/durum-degistir"
    yanit = istemci.istek("PATCH", yol, token=yonetici_token)
    pasif = yanit.status_code == 200
    sonuc.adim("T08.3", f"yönetici '{args.pasiflestirme_hesabi}' hesabını pasifleştirir", "200", _ayrinti(yanit), pasif)
    try:
        if pasif:
            yanit = istemci.istek("GET", "/api/yetkilerim", token=hedef_token)
            # Sunucu, pasifleştirilen hesabın token'ına 403 "Kullanıcı hesabı aktif değil." verir (401 değil); önemli olan hiçbir veri dönmemesidir.
            # İstemcinin bu yanıtta giriş ekranına dönmesi ayrıca elle denenir (rehber, SEC-T08).
            sonuc.adim("T08.4", "pasifleştirilen hesabın eski token'ı reddedilir", "401 ya da 403 (veri dönmez)", _ayrinti(yanit),
                       yanit.status_code in (401, 403))
    finally:
        if pasif:
            geri = istemci.istek("PATCH", yol, token=yonetici_token)
            if geri.status_code == 200:
                sonuc.yaz(f"         '{args.pasiflestirme_hesabi}' hesabı yeniden AKTİF edildi.")
            else:
                sonuc.yaz(f"  !!! '{args.pasiflestirme_hesabi}' hesabı yeniden aktif EDİLEMEDİ ({_ayrinti(geri)}); Kullanıcı & Personel ekranından elle aktif edin.")


ADIM_FONKSIYONLARI = {"T01": t01, "T02": t02, "T03": t03, "T07": t07, "T08": t08}


def argumanlar(argv=None):
    ap = argparse.ArgumentParser(description="SEC-001 canlı ortam denemeleri (T01, T02, T03, T07, T08).")
    ap.add_argument("--adres", required=True, help="Sunucu adresi, örn. https://172.24.4.66:8443")
    ap.add_argument("--ca", default=os.environ.get("TKYS_CA_BUNDLE"), help="Kendi imzalı sertifika dosyası (sertifika doğrulaması için)")
    ap.add_argument("--adimlar", default=",".join(ADIMLAR), help="Çalışacak adımlar (virgülle), varsayılan: hepsi")
    ap.add_argument("--yetkisiz", help="T02/T08: yönetim yetkisi olmayan test hesabı (örn. Psikolog)")
    ap.add_argument("--psikolog-a", help="T03: planlı randevusu olan test psikologu")
    ap.add_argument("--psikolog-b", help="T03: A'nın randevusuna yetkisi olmayan ikinci test psikologu")
    ap.add_argument("--asistan", help="T03: cihaz rezervasyonu izni olan ama rezervasyonları yönetemeyen test hesabı (örn. Proje Asistanı)")
    ap.add_argument("--kilit-hesabi", help="T07: kilitlenmesinde sakınca olmayan test hesabı")
    ap.add_argument("--yonetici", help="T08: test hesabını pasifleştirecek yönetici hesabı")
    ap.add_argument("--pasiflestirme-hesabi", help="T08: pasifleştirilip geri açılacak test hesabı (Psikolog olmamalı)")
    ap.add_argument("--onay", action="store_true", help="Veriyi değiştirebilecek adımlara (T03, T07, T08 pasifleştirme) izin verir")
    ap.add_argument("--kanit", help="Kanıt dosyası yolu (varsayılan: sec001_canli_kanit_<tarih>.txt)")
    args = ap.parse_args(argv)
    gecersiz = [a for a in (x.strip().upper() for x in args.adimlar.split(",") if x.strip()) if a not in ADIM_FONKSIYONLARI]
    if gecersiz:
        ap.error(f"bilinmeyen adım: {', '.join(gecersiz)} (geçerli: {', '.join(ADIMLAR)})")
    return args


def main(argv=None):
    args = argumanlar(argv)
    adimlar = [a.strip().upper() for a in args.adimlar.split(",") if a.strip()]
    kanit = args.kanit or f"sec001_canli_kanit_{datetime.datetime.now():%Y%m%d_%H%M}.txt"
    sonuc = Sonuclar(kanit)
    istemci = Istemci(args.adres, args.ca if args.ca else True)
    sonuc.yaz(f"SEC-001 canlı ortam denemeleri — {datetime.datetime.now():%d.%m.%Y %H:%M}")
    sonuc.yaz(f"Sunucu: {istemci.adres} | Adımlar: {', '.join(adimlar)} | Onay (veri değiştiren adımlar): {'EVET' if args.onay else 'HAYIR'}")
    for adim in adimlar:
        ADIM_FONKSIYONLARI[adim](sonuc, istemci, args)
    gecen = sum(1 for _, d in sonuc.satirlar if d == "PASS")
    kalan = sum(1 for _, d in sonuc.satirlar if d == "FAIL")
    atlanan = sum(1 for _, d in sonuc.satirlar if d == "ATLANDI")
    sonuc.yaz(f"\nÖZET: {gecen} PASS, {kalan} FAIL, {atlanan} ATLANDI")
    sonuc.yaz(f"Kanıt dosyası: {kanit}")
    sonuc.kapat()
    return 1 if kalan else 0


if __name__ == "__main__":
    sys.exit(main())
