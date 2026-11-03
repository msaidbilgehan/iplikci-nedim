# ADR-0009: Ağ çıkışı politikası

Durum: Kabul edildi · Tarih: 2026-10-31 · Dayanak: K8, K10, K5

## Bağlam

MVP'de ağa yalnızca e-posta okuması çıkıyordu. Kullanıcı kur servislerini (K8) ve telefona bildirim gönderilmesini
(K10) onayladı; uzaktan erişim gerektiğinde Tailscale kullanılacak (K5).

## Karar

Uygulama yalnızca aşağıdaki dış bağlantıları kurar. Hepsi tek bir `egress` modülünden ve bir sunucu adı izin
listesinden geçer.

| Amaç | Hedef | Giden veri |
|---|---|---|
| E-posta okuma | IMAP (Gmail): TLS, sertifika denetimi | giriş bilgisi; kutu salt okunur açılır |
| E-posta okuma, tarayıcı eklentisiyle (ADR-0016) | `mail.google.com` ve Gmail'in ek sunucusu `mail-attachment.googleusercontent.com`: HTTPS, tarayıcının açık Gmail oturumuyla | yalnızca okuma istekleri (GET); iletiler yalnızca bu bilgisayardaki servise (127.0.0.1) gider |
| Bildirim e-postası | SMTP (Gmail): TLS | kullanıcının kendi adresine, seçilen ayrıntı düzeyinde ileti |
| Telegram | `api.telegram.org`: HTTPS | seçilen ayrıntı düzeyinde ileti; sohbet eşleştirmesi |
| Döviz kurları | TCMB, ECB ya da Frankfurter | yalnızca tarih |
| Enflasyon ve altın (isteğe bağlı) | TCMB EVDS | API anahtarı ve seri kodları |

- Telemetri, güncelleme denetimi, dış yazı tipi ya da dış betik yoktur.
- Ağ yoksa bu özellikler dışında her şey çalışır; kur çevirisi belgelerdeki kurlara döner.
- Tailscale uygulamanın değil, kullanıcının ağ katmanıdır (ADR-0012).
- Tarayıcı eklentisi servisin `egress` modülünden geçmez. Onun sınırı manifestteki adreslerdir: `mail.google.com`,
  Gmail'in "Orijinali indir"in yönlendirdiği ek sunucusu `mail-attachment.googleusercontent.com` (2026-11-01'de
  eklendi: "Orijinali göster" eklerin içeriğini vermiyor) ve `127.0.0.1:8643` (ADR-0016). Servisin kendisi eklenti
  yolunda e-posta için ağa çıkmaz.
- Yeni bir dış bağlantı ancak yeni bir ADR ile eklenir.

## Sonuçlar

- Olumlu: neyin ne zaman dışarı çıktığı tek bir yerden görülür ve test edilir; izin listesi dışındaki bir istek hata
  verir.
- Olumsuz: her yeni veri kaynağı bir karar gerektirir. Bu bilinçli bir tercihtir.

## Uygulama notu (Aşama 8, 2026-11-03)

Kur sağlayıcılarının sunucuları, 2026-11-03'te denenmiş adresleriyle:

| Sağlayıcı | Sunucu | Yol | Giden veri |
|---|---|---|---|
| TCMB günlük kurları | `www.tcmb.gov.tr` | `/kurlar/today.xml`, `/kurlar/YYYYAA/GGAAYYYY.xml` (hafta sonu ve tatilde 404) | yalnızca tarih |
| ECB referans kurları | `www.ecb.europa.eu` | `/stats/eurofxref/eurofxref-daily.xml`, `eurofxref-hist-90d.xml`, `eurofxref-hist.zip` | hiçbir şey |
| Frankfurter (ECB verisinin kopyası) | `api.frankfurter.dev` | `/v1/<başlangıç>..<bitiş>?base=EUR&symbols=…` | tarih aralığı ve birim kodları |
| TCMB EVDS (isteğe bağlı) | `evds3.tcmb.gov.tr` | `/igmevdsms-dis/series=…&startDate=…&endDate=…&type=json` | API anahtarı (istek başlığında) ve seri kodları |

- `evds2.tcmb.gov.tr` artık `evds3`'e yönlendiriyor; uygulama yönlendirme izlemez, doğrudan `evds3`'e gider.
- `evds3.tcmb.gov.tr` izin listesine TÜFE özelliğiyle girdi. Yalnızca kullanıcı Ayarlar'da kendi anahtarını
  girdiyse çağrılır; anahtar `key` başlığındadır, adreste ve günlükte yer almaz.
- Sağlayıcılar `egress` üzerinden yalnızca GET ile çağrılır: sertifika ve sunucu adı denetlenir, yönlendirme izlenmez,
  yanıt 1 MB ile sınırlıdır (ECB'nin bütün geçmişi zip olarak 642 KB). Yol `/` ile başlamalıdır: izinli sunucudan sonra
  gelen `@başka.adres/` gibi bir yol isteği başka bir sunucuya götürürdü.
- ECB'nin sunucusu macOS'taki Python'un sertifika denetiminden geçmedi (`CERTIFICATE_VERIFY_FAILED`): Python'un
  okuduğu kök sertifika dosyasında Sectigo'nun E46 kökü yok, sunucu da oraya götüren ara sertifikayı göndermiyor.
  Güven ayarı değiştirilmedi. Bu yüzden TCMB'ye ulaşılamazsa ECB'nin kurları önce Frankfurter'den istenir; ayarlardaki
  varsayılan sıra `document`, `tcmb`, `frankfurter`, `ecb`.
