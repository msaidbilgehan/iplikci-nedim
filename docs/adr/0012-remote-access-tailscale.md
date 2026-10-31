# ADR-0012: Uzaktan erişim yalnızca Tailscale ile

Durum: Kabul edildi · Tarih: 2026-10-31 · Dayanak: K5

## Bağlam

PWA şimdilik yalnızca bu bilgisayarda kullanılacak. Kullanıcı uzaktayken bilgiyi bildirimlerden alacak; uzaktan erişim
gerektiğinde Tailscale kullanılacak (K5).

## Karar

- Servis varsayılan olarak yalnızca `127.0.0.1`'de dinler.
- Uzaktan erişim isteğe bağlıdır ve iki adımda açılır:
  1. Ayarlarda `server.remote = "tailscale"` yapılır.
  2. Kullanıcı `tailscale serve` ile kendi tailnet adında HTTPS'i yerel servise yönlendirir.
- Servis tailnet ana bilgisayar adını ancak bu ayar açıkken kabul eder.
- Uzaktan oturumlar passkey ister (ADR-0007).
- Port yönlendirme ve internete açma (Tailscale Funnel dahil) kullanılmaz.

## Sonuçlar

- Olumlu: internete açık bir port yoktur; geçerli sertifikalı HTTPS alınır; yalnızca kullanıcının kendi cihazları
  erişebilir.
- Olumsuz: telefonda Tailscale uygulaması gerekir; passkey kaydı bu bilgisayardan bir kez yapılır.

## Değerlendirilen seçenekler

- **Yerel ağda dinlemek:** TLS yoktur; ağdaki her cihaz servise ulaşır.
- **İnternete açık ters vekil:** saldırı yüzeyi oluşur; sertifika ve kimlik doğrulama yükü getirir.
