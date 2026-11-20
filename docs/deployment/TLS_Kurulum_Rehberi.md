# TLS (HTTPS) Kurulum Rehberi

Sunucu ağa açılıyorsa (başka bilgisayarlardaki istemciler bağlanıyorsa) **HTTPS kullanılmalıdır**. HTTP ile giden parolalar ve oturum anahtarları ağdaki herkes tarafından okunabilir. Sunucu HTTPS olmadan `0.0.0.0` üzerinde açılırsa `logs/sunucu.log` dosyasına **UYARI** yazılır.

İki yol vardır; **A** daha basittir, **B** kurumsal ağlar için daha uygundur.

## A) Sunucunun kendisi HTTPS verir (uvicorn)

1. Sertifika ve anahtar üretin. Kurumunuzun bir sertifikası varsa onu kullanın. Yoksa kendi kendine imzalı bir sertifika (PowerShell, yönetici olarak değil, proje klasöründe):

   ```powershell
   $s = New-SelfSignedCertificate -DnsName "tkys-sunucu","localhost" -CertStoreLocation Cert:\CurrentUser\My -NotAfter (Get-Date).AddYears(2)
   ```

   Sertifikayı PEM olarak dışa aktarmak için `openssl` en kolayıdır (Git for Windows ile gelir):

   ```powershell
   openssl req -x509 -newkey rsa:3072 -nodes -days 730 -keyout sertifika\anahtar.pem -out sertifika\sertifika.pem -subj "/CN=tkys-sunucu" -addext "subjectAltName=DNS:tkys-sunucu,DNS:localhost,IP:127.0.0.1"
   ```

   `-addext` içindeki **DNS/IP değerleri istemcilerin sunucuya bağlandığı ad/adresle aynı olmalıdır** (örn. sunucuya `https://192.168.1.20:8443` ile bağlanılıyorsa `IP:192.168.1.20` ekleyin). `anahtar.pem` gizlidir: **depoya koymayın**, yalnızca sunucu bilgisayarda kalsın.

2. Sunucunun `.env` dosyasına ekleyin:

   ```
   TKYS_SSL_CERTFILE=C:\TKYS\sertifika\sertifika.pem
   TKYS_SSL_KEYFILE=C:\TKYS\sertifika\anahtar.pem
   TKYS_PORT=8443
   ```

   Sunucuyu `python scripts/windows/sunucu_baslat.py` (ya da görev zamanlayıcıyla) başlatın. İkisinden biri eksikse ya da dosya yoksa başlatıcı açık bir hatayla durur.

3. **Her istemci bilgisayarda** adresi HTTPS yapın ve (kendi kendine imzalı sertifika kullanıyorsanız) sertifika dosyasını güvenilir sayın:

   ```powershell
   setx TKYS_API_URL "https://192.168.1.20:8443"
   setx TKYS_CA_BUNDLE "C:\TKYS\sertifika\sertifika.pem"
   ```

   Yalnızca **açık sertifika dosyası** (`sertifika.pem`) istemciye kopyalanır; anahtar dosyası asla. Sertifika doğrulaması **kapatılmaz**: dosya yanlışsa ya da adres sertifikayla uyuşmazsa istemci bağlanmaz. Kurumun kendi güvenilir sertifikası varsa `TKYS_CA_BUNDLE` gerekmez.

## B) Ters vekil (Caddy / nginx / IIS) HTTPS'i sonlandırır

Vekil 443 numaralı portta HTTPS alır, isteği `http://127.0.0.1:8000` adresine iletir. Bu durumda TKYS sunucusunu yalnızca yerel adreste açın:

```
TKYS_HOST=127.0.0.1
TKYS_GUVENILIR_VEKIL=1
```

`TKYS_GUVENILIR_VEKIL=1` yalnızca vekilin `X-Forwarded-Proto: https` başlığını **kendisi koyduğundan** eminseniz verilmelidir (vekil istemciden gelen aynı başlığı ezmelidir). Verildiğinde sunucu yanıtlara `Strict-Transport-Security` başlığını ekler.

Örnek Caddy (otomatik sertifika yönetimi, kurumsal alan adı varsa):

```
tkys.kurum.local {
    reverse_proxy 127.0.0.1:8000
}
```

## Sunucunun eklediği başlıklar

- Her yanıtta `X-Content-Type-Options: nosniff`.
- HTTPS ile gelen isteklerde ayrıca `Strict-Transport-Security: max-age=31536000`.

## Doğrulama

```powershell
curl.exe --cacert sertifika\sertifika.pem https://192.168.1.20:8443/api/saglik
```

`{"durum":"calisiyor"}` dönmelidir. Tarayıcıda/istemcide sertifika uyarısı çıkıyorsa adres ile sertifikadaki DNS/IP uyuşmuyordur.

## Sertifika yenileme

Kendi kendine imzalı sertifika süresi dolunca (yukarıdaki örnekte 2 yıl) yenisini aynı adlarla üretin, dosyaları değiştirin ve sunucuyu yeniden başlatın; istemcilerdeki `sertifika.pem` kopyasını da yenileyin.
