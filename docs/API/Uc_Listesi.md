# TKYS API Uç Listesi

Bu dosya **sunucu kodundan otomatik üretilir** (`python scripts/api_uc_listesi_uret.py`); elle düzenlemeyin.
Toplam **136** uç. **İzin** sütunu, ucu çağırmak için rolün sahip olması gereken izindir (`—`: yalnızca giriş yapmış olmak yeterli ya da uç kendi kuralını uygular;
gerekçeler `tests/security/test_uc_koruma_taramasi.py` içindedir).

Etkileşimli API belgesi (`/docs`) **varsayılan olarak kapalıdır**; yalnızca teknik kişi gerektiğinde sunucunun `.env` dosyasına `TKYS_API_DOCS=1` yazarak açar.

Kimlik doğrulama: `Authorization: Bearer <JWT>` başlığı (giriş: `POST /api/login`). Hatalar `{"detail": "..."}` biçimindedir; yetki yoksa **403**, oturum geçersizse **401**, doğrulama hatasında **422**.

## /api/arizalar

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/arizalar` | ARIZA_KAYITLARI_YONET | arizalari_listele |
| POST | `/api/arizalar` | ARIZA_KAYITLARI_YONET | ariza_bildir |
| PUT | `/api/arizalar/{ariza_id}` | ARIZA_KAYITLARI_YONET | ariza_guncelle |

## /api/audit-kayitlari

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/audit-kayitlari` | AUDIT_KAYITLARI_INCELE | audit_kayitlarini_getir |

## /api/bakim-plani-raporu

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/bakim-plani-raporu` | CIHAZ_ENVANTER_YONET | Geciken Bakım Planı Raporu: bugünkü durum. Geciken (sonraki görev tarihi geçmiş), yaklaşan ve planlı planlar,  |

## /api/bakim-planlari

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/bakim-planlari` | — | Cihazların tekrarlayan bakım/kalibrasyon planları (en yakın tarih önce). |
| POST | `/api/bakim-planlari` | — | bakim_plani_ekle |
| DELETE | `/api/bakim-planlari/{plan_id}` | — | bakim_plani_sil |
| PUT | `/api/bakim-planlari/{plan_id}` | — | bakim_plani_guncelle |

## /api/bakimlar

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/bakimlar` | BAKIM_KAYITLARI_GORUNTULE, BAKIM_KAYITLARI_YONET | bakimlari_listele |
| POST | `/api/bakimlar` | BAKIM_KAYITLARI_YONET | bakim_kaydi_ekle |
| DELETE | `/api/bakimlar/{bakim_id}` | BAKIM_KAYITLARI_YONET | bakim_kaydi_sil |
| PUT | `/api/bakimlar/{bakim_id}` | BAKIM_KAYITLARI_YONET | bakim_guncelle |

## /api/bolumler

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/bolumler` | CIHAZ_REZERVASYON | Rezervasyon formundaki bölüm listesi (yalnızca aktif bölümler). |
| POST | `/api/bolumler` | CIHAZ_REZERVASYON | bolum_olustur |

## /api/cihaz-odalari

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/cihaz-odalari` | CIHAZ_REZERVASYON | Cihaz rezervasyonunda seçilebilen odalar: aktif bir psikologa atanmamış aktif odalar. |

## /api/cihaz-raporlari

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/cihaz-raporlari` | CIHAZ_ENVANTER_YONET | Bakım, kalibrasyon ve arıza kayıtlarını tarih/cihaz filtresiyle listeler (salt okunur). |

## /api/cihaz-rezervasyon-raporu

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/cihaz-rezervasyon-raporu` | CIHAZ_ENVANTER_YONET | Cihaz Rezervasyon Raporu: cihaz, proje türü ve bölüm bazlı rezervasyon sayısı ve planlanan kullanım saati. |

## /api/cihaz-uygunluk

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/cihaz-uygunluk` | CIHAZ_UYGUNLUK_GORUNTULE | Seçilen tarih aralığında her cihazın rezervasyon, bakım, kalibrasyon, arıza ve kullanım dışı dönemleri. |

## /api/cihazlar

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/cihazlar` | CIHAZ_UYGUNLUK_GORUNTULE | cihazlari_listele |
| POST | `/api/cihazlar` | CIHAZ_EKLE | cihaz_ekle |
| GET | `/api/cihazlar/{cihaz_id}` | CIHAZ_UYGUNLUK_GORUNTULE | cihaz_detayi_getir |
| PATCH | `/api/cihazlar/{cihaz_id}` | CIHAZ_ENVANTER_YONET | cihaz_guncelle |
| GET | `/api/cihazlar/{cihaz_id}/gecmis` | CIHAZ_ENVANTER_YONET | Bir cihazın yaşam döngüsü: bakım, kalibrasyon, arıza ve rezervasyon kayıtları tek zaman çizgisinde (en yeni ön |

## /api/cikis

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| POST | `/api/cikis` | — | Oturumu kapatır: kullanıcının oturum sürümü artar, bu kullanıcıya ait TÜM açık oturum anahtarları (token) geçe |

## /api/danisan-kodlari

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/danisan-kodlari` | RANDEVU_OLUSTUR | Aktif danışan kodlarını (kişisel veri içermez) döndürür; pasifler_dahil=true ise pasifleri de ekler. |
| POST | `/api/danisan-kodlari` | RANDEVU_OLUSTUR | Yeni danışan kodu üretir. |
| PATCH | `/api/danisan-kodlari/{danisan_kod_id}/bilgiler` | RANDEVU_OLUSTUR | Danışanın yaş grubunu günceller (kapalı liste; serbest metin yoktur). Terapi türü randevuda tutulur. |
| PATCH | `/api/danisan-kodlari/{danisan_kod_id}/durum` | RANDEVU_OLUSTUR | Danışanı pasife alır ya da yeniden aktif eder. |

## /api/danisma

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/danisma/oturum/aktif` | DANISMA_OTURUMU_YONET | danisma_aktif_oturum |
| POST | `/api/danisma/oturum/baslat` | DANISMA_OTURUMU_YONET | danisma_oturumu_baslat |
| PATCH | `/api/danisma/oturum/bitir` | DANISMA_OTURUMU_YONET | danisma_oturumu_bitir |
| GET | `/api/danisma/oturum/gecmis` | DANISMA_OTURUMU_YONET | danisma_oturum_gecmisi |
| GET | `/api/danisma/raporlar` | DANISMA_OTURUMU_GORUNTULE | danisma_raporlari |
| GET | `/api/danisma/yonetim/ogrenciler` | DANISMA_OTURUMU_YONETIM | danisma_yonetim_ogrencileri |
| GET | `/api/danisma/yonetim/onay-bildirimleri` | DANISMA_OTURUMU_YONETIM | Tamamlanmis ve onay bekleyen danisma masasi gorevleri. |
| GET | `/api/danisma/yonetim/oturumlar` | DANISMA_OTURUMU_YONETIM | danisma_yonetim_oturumlari |
| POST | `/api/danisma/yonetim/oturumlar` | DANISMA_OTURUMU_YONETIM | danisma_yonetim_oturum_olustur |
| PATCH | `/api/danisma/yonetim/oturumlar/{oturum_id}` | DANISMA_OTURUMU_YONETIM | danisma_yonetim_oturum_duzenle |
| PATCH | `/api/danisma/yonetim/oturumlar/{oturum_id}/onay-geri-al` | DANISMA_OTURUMU_YONETIM | Onaylanmış görevin onayını kaldırır; görev yeniden onay bekler ve düzenlenebilir. |
| PATCH | `/api/danisma/yonetim/oturumlar/{oturum_id}/onayla` | DANISMA_OTURUMU_YONETIM | danisma_yonetim_oturum_onayla |

## /api/dashboard

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/dashboard/bugunku-randevular` | TAKVIM_GORUNTULE | dashboard_bugunku_randevular |
| GET | `/api/dashboard/bugunku-rezervasyonlar` | CIHAZ_ENVANTER_YONET | dashboard_bugunku_rezervasyonlar |
| GET | `/api/dashboard/ozet` | CIHAZ_ENVANTER_YONET | dashboard_ozet_getir |
| GET | `/api/dashboard/yaklasan-islemler` | BAKIM_KAYITLARI_GORUNTULE, BAKIM_KAYITLARI_YONET, CIHAZ_ENVANTER_YONET, KALIBRASYON_KAYITLARI_GORUNTULE, KALIBRASYON_KAYITLARI_YONET | Ana panel/zil bildirimleri için yaklaşan ve geciken bakım ve kalibrasyonlar. Cihaz envanterini yönetenler heps |

## /api/faaliyet-birimleri

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/faaliyet-birimleri` | FAALIYET_KAYITLARI_DUZENLE | faaliyet_birimleri_getir |
| POST | `/api/faaliyet-birimleri` | FAALIYET_BIRIMI_DUZENLE | faaliyet_birimi_ekle |
| DELETE | `/api/faaliyet-birimleri/{birim_id}` | FAALIYET_BIRIMI_DUZENLE | faaliyet_birimi_sil |
| PUT | `/api/faaliyet-birimleri/{birim_id}` | FAALIYET_BIRIMI_DUZENLE | faaliyet_birimi_guncelle |

## /api/faaliyet-kayitlari

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/faaliyet-kayitlari` | FAALIYET_KAYITLARI_DUZENLE | Faaliyet kayıtları (en yeni önce). limit verilirse toplam sayı X-Toplam-Kayit başlığında döner. |
| POST | `/api/faaliyet-kayitlari` | FAALIYET_KAYITLARI_DUZENLE | faaliyet_kaydi_ekle |
| DELETE | `/api/faaliyet-kayitlari/{takip_id}` | FAALIYET_KAYITLARI_DUZENLE | faaliyet_kaydi_sil |
| PUT | `/api/faaliyet-kayitlari/{takip_id}` | FAALIYET_KAYITLARI_DUZENLE | faaliyet_kaydi_guncelle |

## /api/faaliyet-raporu

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/faaliyet-raporu` | FAALIYET_KAYITLARI_DUZENLE | Faaliyet Raporu: dönemdeki (faaliyet tarihi) kayıtların faaliyet türü, birim ve öğrenci türü dağılımı ve puanl |

## /api/faaliyetler

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/faaliyetler` | FAALIYET_KAYITLARI_DUZENLE | faaliyetleri_getir |
| POST | `/api/faaliyetler` | FAALIYET_KAYITLARI_DUZENLE | faaliyet_turu_ekle |
| PUT | `/api/faaliyetler/{faaliyet_id}` | FAALIYET_KAYITLARI_DUZENLE | faaliyet_turu_duzenle |

## /api/izinler

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| POST | `/api/izinler` | ROL_DUZENLE | izin_ekle |
| PUT | `/api/izinler/{izin_id}` | IZIN_DUZENLE | Bir iznin GÖRÜNEN ADINI ve hangi rollere verildiğini günceller. |

## /api/kalibrasyonlar

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/kalibrasyonlar` | KALIBRASYON_KAYITLARI_GORUNTULE, KALIBRASYON_KAYITLARI_YONET | kalibrasyonlari_listele |
| POST | `/api/kalibrasyonlar` | KALIBRASYON_KAYITLARI_YONET | kalibrasyon_kaydi_ekle |
| DELETE | `/api/kalibrasyonlar/{kalibrasyon_id}` | KALIBRASYON_KAYITLARI_YONET | kalibrasyon_kaydi_sil |
| PUT | `/api/kalibrasyonlar/{kalibrasyon_id}` | KALIBRASYON_KAYITLARI_YONET | kalibrasyon_guncelle |

## /api/korumali-test

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/korumali-test` | — | korumali_test |

## /api/kullanicilar

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| POST | `/api/kullanicilar` | KULLANICI_OLUSTUR | kullanici_olustur |
| GET | `/api/kullanicilar/musait-kullanici-adi` | KULLANICI_OLUSTUR | Verilen ad boşsa onu, doluysa sonuna sayı ekleyerek ilk boş adı döndürür. |
| GET | `/api/kullanicilar/personel-olmayanlar` | PERSONEL_TANIMLA | personel_olmayan_kullanicilari_listele |
| GET | `/api/kullanicilar/{hedef_kullanici_id}/odalar` | ROL_ATAMA_DEGISTIRME | psikolog_oda_yetkilerini_getir |
| PUT | `/api/kullanicilar/{hedef_kullanici_id}/odalar` | ROL_ATAMA_DEGISTIRME | Psikologun görüşme odalarını verilen kümeye eşitler. Her psikologun en az bir (aktif) odası olmalıdır. |
| PATCH | `/api/kullanicilar/{kullanici_id}/durum-degistir` | KULLANICI_PASIFLESTIR | Kullanıcıyı aktif/pasif yapar (geçiş). |
| GET | `/api/kullanicilar/{kullanici_id}/ogrenci-kayit-durumu` | ROL_ATAMA_DEGISTIRME | kullanici_ogrenci_kayit_durumu |
| POST | `/api/kullanicilar/{kullanici_id}/parola-sifirla` | KULLANICI_PAROLA_SIFIRLA | Yalnızca ADMIN başka bir aktif kullanıcının parolasını sıfırlar. |
| PATCH | `/api/kullanicilar/{kullanici_id}/rol` | ROL_ATAMA_DEGISTIRME | kullanici_rol_degistir |

## /api/liste-aktarim-kaydi

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| POST | `/api/liste-aktarim-kaydi` | — | liste_aktarim_kaydi |

## /api/login

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| POST | `/api/login` | — | giris_yap |

## /api/oda-kullanim-raporu

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/oda-kullanim-raporu` | YONETIM_RAPORLARI_GORUNTULE | Oda Kullanım Raporu: oda bazlı randevu, cihaz rezervasyonu ve etkinlik saatleri, mesai doluluk oranı ve haftan |

## /api/oda-kullanimi

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/oda-kullanimi` | ODA_DURUMU_GORUNTULE | Oda Kullanımı sayfası: odalar, seçilen tarih aralığındaki (başlangıç ve bitiş günü dahil) iptal edilmemiş rand |

## /api/oda-psikolog-atamalari

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/oda-psikolog-atamalari` | ODA_DUZENLE, ODA_EKLE | Oda Yönetimi ekranındaki "Psikologlar" sütunu için (bilgi amaçlı). Ekranı görenler görebilir. |

## /api/odalar

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/odalar` | ODA_DURUMU_GORUNTULE | odalari_listele |
| POST | `/api/odalar` | ODA_EKLE | oda_olustur |
| GET | `/api/odalar/{oda_id}` | ODA_DURUMU_GORUNTULE | oda_detay |
| PATCH | `/api/odalar/{oda_id}` | ODA_DUZENLE | oda_guncelle |

## /api/ogrenci-ekle

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| POST | `/api/ogrenci-ekle` | FAALIYET_KAYITLARI_DUZENLE | ogrenci_ekle |

## /api/ogrenci-raporu

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/ogrenci-raporu` | FAALIYET_KAYITLARI_DUZENLE | Öğrenci Raporu: tür ve bölüm dağılımı, aktif/pasif, Gönüllü öğrenci kayıt saklama süresi (10 yıl) durumu, faal |

## /api/ogrenciler

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| PATCH | `/api/ogrenciler/{ogrenci_id}/aktiflik` | FAALIYET_KAYITLARI_DUZENLE | ogrenci_aktiflik_duzenle |
| DELETE | `/api/ogrenciler/{ogrenci_id}/on-yil-sil` | OGRENCI_KAYDI_SIL | ogrenci_on_yil_sil |
| GET | `/api/ogrenciler/{ogrenci_id}/puanlar` | FAALIYET_KAYITLARI_DUZENLE | ogrenci_puan_detayi |
| PATCH | `/api/ogrenciler/{ogrenci_id}/silme-ertele` | FAALIYET_KAYITLARI_DUZENLE | ogrenci_silme_ertele |

## /api/ogrenciler-liste

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/ogrenciler-liste` | FAALIYET_KAYITLARI_DUZENLE | ogrencileri_getir |

## /api/ogrenciler-yonetim

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/ogrenciler-yonetim` | FAALIYET_KAYITLARI_DUZENLE | ogrenciler_yonetim_listesi |

## /api/parola-sifirlama-talebi

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| POST | `/api/parola-sifirlama-talebi` | — | Giriş yapmadan parola sıfırlama talebi açar. |

## /api/parola-sifirlama-talepleri

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/parola-sifirlama-talepleri` | KULLANICI_PAROLA_SIFIRLA | Bekleyen (açık) parola sıfırlama talepleri; en eski talep önce. |
| PATCH | `/api/parola-sifirlama-talepleri/{talep_id}/kapat` | KULLANICI_PAROLA_SIFIRLA | Bekleyen bir talebi parolayı sıfırlamadan kapatır (örn. kullanıcı parolasını hatırladı). |

## /api/personel

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/personel` | PERSONEL_TANIMLA | personel_listele |
| POST | `/api/personel` | PERSONEL_TANIMLA | personel_olustur |
| GET | `/api/personel/{personel_id}` | PERSONEL_TANIMLA | personel_detay |
| PATCH | `/api/personel/{personel_id}` | PERSONEL_TANIMLA | personel_guncelle |

## /api/proje-turleri

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/proje-turleri` | CIHAZ_REZERVASYON | Rezervasyon formundaki proje türü listesi. |
| POST | `/api/proje-turleri` | CIHAZ_REZERVASYON | proje_turu_olustur |

## /api/psikologlar

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/psikologlar` | TAKVIM_GORUNTULE | Aktif psikologlar (randevu formundaki psikolog seçimi bunu kullanır). |
| GET | `/api/psikologlar/{personel_id}/odalar` | RANDEVU_OLUSTUR | psikolog_odalarini_getir |

## /api/puan-raporu

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/puan-raporu` | FAALIYET_KAYITLARI_DUZENLE | Öğrenci puan sıralaması: seçilen dönemdeki toplam puana göre en yüksekten en düşüğe. |

## /api/randevu-raporu

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/randevu-raporu` | TAKVIM_GORUNTULE | Randevu raporu: seçilen dönemde (randevunun başlangıç günü) durum sayıları, psikolog bazlı döküm, iptal nedenl |
| GET | `/api/randevu-raporu/secenekler` | TAKVIM_GORUNTULE | Randevu raporu süzgeç listeleri: aktif psikologlar ve onların aktif odaları, ayrıca randevu geçmişi olan pasif |

## /api/randevular

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/randevular` | TAKVIM_GORUNTULE | Randevu listesi. Süzgeçler isteğe bağlıdır; hiçbiri verilmezse eskisi gibi tüm kayıtlar döner. |
| POST | `/api/randevular` | RANDEVU_OLUSTUR | randevu_olustur |
| GET | `/api/randevular/doluluk` | TAKVIM_GORUNTULE | Seçilen gün için oda ve/veya psikologun dolu saat aralıklarını döndürür. |
| GET | `/api/randevular/siradaki-kod` | RANDEVU_OLUSTUR | siradaki_danisan_kodunu_ver |
| PATCH | `/api/randevular/{randevu_id}` | RANDEVU_DUZENLE | randevu_guncelle |
| PATCH | `/api/randevular/{randevu_id}/durum` | RANDEVU_DUZENLE | Başlangıcı geçmiş randevuyu Tamamlandı ya da Gelmedi olarak işaretler (ikisi arasında düzeltme yapılabilir). |
| PATCH | `/api/randevular/{randevu_id}/iptal` | RANDEVU_IPTAL | randevu_iptal_et |

## /api/rezervasyonlar

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/rezervasyonlar` | CIHAZ_REZERVASYON | rezervasyonlari_listele |
| POST | `/api/rezervasyonlar` | CIHAZ_REZERVASYON | cihaz_rezervasyonu_yap |
| PUT | `/api/rezervasyonlar/{rezervasyon_id}` | CIHAZ_REZERVASYON | Rezervasyonu düzenler (cihaz değişmez). Yalnızca oluşturan kişi ya da cihaz yöneticisi; iptal edilmiş/bitmiş r |
| PATCH | `/api/rezervasyonlar/{rezervasyon_id}/iptal` | CIHAZ_REZERVASYON | rezervasyon_iptal |

## /api/rol-izin-matrisi

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/rol-izin-matrisi` | ROL_IZIN_YONET | rol_izin_matrisi_getir |

## /api/roller

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/roller` | ROL_IZIN_YONET | rolleri_listele |
| POST | `/api/roller` | ROL_OLUSTUR | rol_olustur |
| GET | `/api/roller/atanabilir/degistirme` | ROL_ATAMA_DEGISTIRME | degistirme_rolleri |
| GET | `/api/roller/atanabilir/olusturma` | KULLANICI_OLUSTUR | olusturma_rolleri |
| DELETE | `/api/roller/{rol_id}` | ROL_DUZENLE | rol_sil |
| PUT | `/api/roller/{rol_id}` | ROL_DUZENLE | Rolün görünür adını ve aktiflik durumunu günceller. |
| GET | `/api/roller/{rol_id}/yetki-ozeti` | KULLANICI_OLUSTUR | Bir rolün yapabildiği işlemlerin özeti (kullanıcı oluştururken 'bu rol neler yapabilir?'). |

## /api/saglik

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/saglik` | — | Sunucunun ayakta olduğunu gösterir (kimlik doğrulama ve veritabanı gerektirmez). |

## /api/sifre-degistir

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| POST | `/api/sifre-degistir` | — | sifre_degistir |

## /api/sistem-durumu

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/sistem-durumu` | AUDIT_KAYITLARI_INCELE | Yönetici için sistem durumu: sürüm, şema, son yedek, son girişler, başarısız girişler ve temel sayılar. |

## /api/surum

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/surum` | — | Hakkında penceresi için sunucu sürümü ve veritabanı şema sürümü (giriş yapmış herkes görebilir; kişisel veri i |

## /api/yetki-raporu

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/yetki-raporu` | AUDIT_KAYITLARI_INCELE | Yetki Raporu: kullanıcılar, rolleri, son giriş zamanları, kilit/pasiflik durumu ve rollere göre izin sayıları. |

## /api/yetkilerim

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/yetkilerim` | — | Giriş yapan kullanıcının rolünü ve o role açık olan izinleri döndürür. |

## /api/yonetim-raporlari

| Yöntem | Yol | İzin | Açıklama |
|---|---|---|---|
| GET | `/api/yonetim-raporlari/bugun-merkezde` | YONETIM_RAPORLARI_GORUNTULE | Günlük merkez özeti ve zamanlı operasyon kayıtları. |
| GET | `/api/yonetim-raporlari/cihaz-ozet` | YONETIM_RAPORLARI_GORUNTULE | Cihaz işlemlerinin dönemsel kayıt istatistikleri. |
| GET | `/api/yonetim-raporlari/gunluk-detay` | YONETIM_RAPORLARI_GORUNTULE | Yönetim panelindeki özetlerin salt okunur kayıt listeleri. |
| GET | `/api/yonetim-raporlari/kullanim-ozet` | YONETIM_RAPORLARI_GORUNTULE | Oda ve cihaz KULLANIM raporu (kayıt sayısı değil, ne kadar kullanıldı). |
| GET | `/api/yonetim-raporlari/ogrenci-ozet` | YONETIM_RAPORLARI_GORUNTULE | Öğrenci faaliyetlerinin dönemsel istatistikleri. |
| GET | `/api/yonetim-raporlari/proje-etkinlik-ozet` | YONETIM_RAPORLARI_GORUNTULE | Proje türü rezervasyonları ve oda etkinliği kayıtları. |
| GET | `/api/yonetim-raporlari/randevu-ozet` | YONETIM_RAPORLARI_GORUNTULE | Yetkili yöneticiler için dönemsel randevu istatistikleri. |

