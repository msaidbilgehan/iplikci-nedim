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

## Uygulama notu (Aşama 5, 2026-11-02)

- **Kurallar:** `rules/alerts.yaml`; anahtarlar Türkçe (`ad`, `olay`, `kosul`, `kanallar`, `ayrinti`, `sessiz_saat`,
  `acik`).
  - Kullanıcı bir kuralı değiştirene dek uygulamayla gelen 16 kural geçerlidir: mimari §14'teki 12 kural, ay bitti ve
    F01'in eklenti uyarıları (bir gündür görünmüyor, Gmail sayfasını tanımadı).
  - Koşullar: `gun` (en çok kaç gün kala), `tutar` (en az kaç TL), `metin` (başlıkta geçen yazı). Her biri yalnızca onu
    taşıyan olaylarda kullanılabilir.
  - Okunamayan dosyanın tamamı reddedilir. Elle bozulmuş bir dosyada uygulamayla gelen kurallar geçer ve neden
    ekranda yazar.
- **Bildirim kaydı** (göç 15, `notifications`): kural, olay anahtarı (türü ve hedefi) ve kanal başına tek satır;
  metin gönderildiği gibi saklanır.
  - Aynı olayın ikinci kez gelmesi ve bir son ödemenin sonraki eşikleri (7, 3, 1, 0 gün) yeni bildirim doğurmaz.
  - Birincil veridir: dökümün 3. sürümü onu da taşır.
- **Sıra:** servis olayları kaldığı yerden okur. İlk çalıştırma en yeni olaydan başlar, öncesi haber sayılmaz. İş
  beş dakikada bir ve her analizden hemen sonra çalışır.
- **İlk okuma** (Aşama 6, temiz kurulum denemesinden): e-posta geçmişi baştan okunurken olaylar yalnızca uygulama içi
  kutuya düşer. Eklentide ilk tarama bitene, IMAP'te geçmiş sonuna dek okunana kadar sürer; IMAP'te başlangıç günü ya
  da göndericiler değişince kutu yeniden baştan okunur. Geçmişin bir parçasından çıkan tahmin ve uyarılar (henüz
  okunmamış gelirsiz bir tahmin, ödeyen satırı gelmemiş bir ödeme) geçmişin geri kalanı gelince kaybolabilir.
- **Uygulama içi kutu** her bildirimi hemen ve tam ayrıntıyla alır. Diğer kanallar kuralın ya da kanalın ayrıntı
  düzeyini kullanır.
- **Yeniden deneme:** başarısız deneme bir dakika, sonra her seferinde iki katı (en çok bir saat) bekler. Sekizinci
  başarısızlıkta bırakılır. Gönderilen bildirim bir daha gönderilmez.
- **Sessiz saat ve sıklık:**
  - Sessiz saatte gelen ve kanalın sıklık sınırını aşan bildirimler özete kalır. Sınır saatte 10 (e-postada 4).
  - Özet bir iletidir ve kanal başına en çok saatte bir gider.
  - `sessiz_saat: false` olan kural sessiz saatte de hemen gönderir; sıklık sınırı yine geçerlidir.
- **Reddedilen giriş:** SMTP girişi ya da Telegram belirteci reddedilince kanal durur. Kullanıcı kanalı yeniden açana ya
  da kurana dek denenmez; bir programın yeniden denemesi hesabı kilitletebilir.
- **Telegram:**
  - Belirteç BotFather'ın biçiminde olmalıdır; `getMe` ile denenip anahtar zincirine yazılır, arayüze geri dönmez.
  - Eşleştirme kodu on dakika geçerlidir. Bota `/start <kod>` gönderen sohbet eşleşir ve karşılanır; diğer iletiler
    yok sayılır.
  - Uzun yoklama yerine `getUpdates` eşleştirme sırasında bekletmeden okunur. Arayüz kodu açıkken üç saniyede bir
    sorar.
  - `api.telegram.org`'a yalnızca `egress` üzerinden gidilir; yönlendirme izlenmez, hata iletisi yolu (belirteci)
    göstermez.
- **E-posta:** IMAP bağlayıcısının uygulama şifresiyle, SMTP (465, TLS) üzerinden kullanıcının kendi adresine gider.
  Tarayıcı eklentisiyle bağlı hesapta (Gelişmiş Koruma) kanal kullanılamaz ve ekran nedenini söyler.
- **Masaüstü:** macOS'ta `osascript`, Linux'ta `notify-send`; metin betiğe değil argüman olarak verilir. Windows'ta
  şimdilik yok.
- **Ayarlar:** `[notify]` bölümüne `channels` (açık kanallar; varsayılan masaüstü ve Telegram) ve `telegram_chat`
  (eşleşen sohbet) eklendi.

## Not (2026-11-08, ADR-0021)

Telegram botu artık belge de alır. Botun iletilerini servisin dinleyicisi uzun yoklamayla okur: eşleşmiş sohbet
belge alımı açıkken (varsayılan) ve bir eşleştirme kodu açıkken. Eşleştirme kodunu dinleyici de bulabilir; arayüzün
denetimi aynı işlemeyi kullanır ve her ileti bir kez işlenir. Okuma 401 alırsa kanal, gönderimdeki gibi durur.
Karşılama iletisi belge göndermeyi de anlatır. Ayrıntılar [ADR-0021](0021-telegram-documents.md)'de.

## Not (2026-11-11, v0.9.18)

Özet düzeyindeki bir bildirim hangi ödemeden söz ettiğini söylemiyordu: "İptal ettiğiniz bir abonelikten ödeme
alındı: 249,90 TL." Kullanıcı hangisi olduğunu bilemiyordu. Artık özet, olayın neyle ilgili olduğunu da yazar:

- Ödeme, gelir ve harcamada kategorisini: "İptal ettiğiniz bir abonelikten ödeme alındı (İnternet & Telefon): 249,90
  TL."
- Kartın son ödemesinde, kredi taksitinde, bir hesabın öngörüsünde ve dekontta hesabın bankasını: "Kart son ödemesi
  (TEB) yarın: …".

İşyerinin ya da kişinin adı ve hesabın son haneleri özet düzeyinde yine yazmaz; onlar tam düzeyindedir. Bu sürümden
önce kaydedilmiş olaylar bu bilgiyi taşımaz ve özetleri eskisi gibidir. Alan mimarinin 13. bölümünde (`about`).

## Değerlendirilen seçenekler

- **Web Push:** PWA'nın telefonda kurulu olmasını gerektirir; şimdilik kullanılmıyor (K5).
- **ntfy:** ek bir servis kurmak gerekir.
- **Yalnızca masaüstü bildirimi:** kullanıcı uzaktayken haber alamaz.
