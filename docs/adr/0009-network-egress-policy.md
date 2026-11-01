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
