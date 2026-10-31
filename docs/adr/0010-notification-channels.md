# ADR-0010: Bildirim kanalları ve içerik düzeyleri

Durum: Kabul edildi · Tarih: 2026-10-31 · Dayanak: K10, G12, tasarım

## Bağlam

Kullanıcı e-posta ve Telegram bildirimlerini istiyor (K10). Telegram bot iletileri uçtan uca şifreli değildir.
Bildirim e-postaları Gmail'den geçer, ama Gmail banka e-postalarını zaten tutuyor. Bildirimler finanstan anlamayan bir
kullanıcıya da hiçbir ayar yapmadan fayda sağlamalı.

## Karar

### Kanallar

| Kanal | Nasıl gönderilir | Varsayılan ayrıntı |
|---|---|---|
| `in_app` | Uygulamadaki bildirim kutusu; her zaman açık. | tam |
| `desktop` | macOS'ta `osascript`, Linux'ta `notify-send`. | özet |
| `email` | Kullanıcının kendi adresine SMTP ile; aynı uygulama şifresi kullanılır. | tam |
| `telegram` | Kullanıcının kendi botu; uzun yoklama (long polling). | özet |

Telegram kanalının ayrıntıları:

- Bot belirteci anahtar zincirinde tutulur.
- Sohbet, `/start <kod>` eşleştirmesiyle bağlanır; yalnızca eşleşmiş sohbet kimliği kabul edilir.
- Uzun yoklama yalnızca dışarıya bağlantı kurduğu için servis internete açılmaz.

### Ayrıntı düzeyleri

| Kod | Kural dosyasındaki adı | İçerik |
|---|---|---|
| `full` | `tam` | olay, tutar, işyeri ya da karşı taraf, hesabın son haneleri |
| `summary` | `ozet` | olay ve tutar |
| `minimal` | `asgari` | yalnızca olay türü ve "ayrıntı uygulamada" |

### Kurallar ve teslim

- Kurallar `rules/alerts.yaml` dosyasındadır; değişiklikler doğrulanır ve önceki sürüm saklanır.
- Hazır kurallar baştan açık gelir.
- Aynı kural ve olay anahtarı için tek teslim yapılır.
- Sessiz saatlerde gelen bildirimler özete eklenir.
- Kanal başına bir sıklık sınırı vardır.
- Başarısız teslim artan aralıklarla yeniden denenir; başarılı teslim tekrarlanmaz.
- Her teslim kaydedilir.

## Sonuçlar

- Olumlu: kullanıcı hangi bilginin hangi sunucudan geçeceğini kanal başına seçer; aynı haber iki kez gelmez.
- Olumsuz: Telegram kurulumu kullanıcının bir bot oluşturmasını gerektirir. Kurulum sihirbazı bunu adım adım anlatır.

## Değerlendirilen seçenekler

- **Web Push:** PWA'nın telefonda kurulu olmasını gerektirir; şimdilik kullanılmıyor (K5).
- **ntfy:** ek bir servis kurmak gerekir.
- **Yalnızca masaüstü bildirimi:** kullanıcı uzaktayken haber alamaz.
