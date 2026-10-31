# ADR-0015: E-posta alımı: IDLE, güven kuralı, gövde okuma, `.eml` saklama

Durum: Kabul edildi · Tarih: 2026-10-31 · Dayanak: G1, G10, G13, K11, K12

## Bağlam

MVP, Gmail'i IMAP üzerinden salt okunur okuyor ve şu sınırlarla çalışıyor:

- Yalnızca listedeki banka alan adlarından gelen ve DMARC'tan geçen e-postaların eklerini alıyor.
- Kutuya en çok 15 dakikada bir bakıyor.
- Her okuyucu güncellemesinde kutuyu baştan tarıyor.

V1'in istekleri:

- E-posta gövdesindeki bildirimler ve hatırlatmalar okunmalı (G1).
- Banka dışı e-postalar da alınmalı (G13).
- Yeni bilgi hemen görünmeli (G10).
- İşlenmeyen belgeler saklanmalı (K11).

## Karar

**Bağlantı**

- IMAP TLS üzerinden ve sertifika denetimiyle kullanılır.
- Kutu salt okunur açılır: `EXAMINE` ve `BODY.PEEK[]`. Hiçbir ileti işaretlenmez, taşınmaz ya da silinmez.
- Okunan klasör Gmail'de "Tüm Postalar"dır; ayarlardan değiştirilebilir.

**Ne zaman okunur**

- IDLE dinleyicisi yeni iletiyi hemen alır.
- Yedek olarak 15 dakikada bir yoklama yapılır.
- Uykudan uyanınca kaçırılan iletiler alınır.

**Güven kuralı**

- Gönderici alan adı iki listeden birinde olmalıdır: banka göndericileri ya da diğer göndericiler (fatura, abonelik,
  e-ticaret).
- Ayrıca en üstteki `Authentication-Results` başlığı, From alan adı için DMARC pass göstermelidir.

**İleti başına işlem**

1. İleti bellekte açılır.
2. Şirket belgesi denetimi yapılır.
3. İleti `.eml` olarak arşive yazılır; şirket içeriği taşıyorsa yazılmaz.
4. Ekler ayrı belgeler olarak arşive yazılır. Zip içleri bellekte açılır; 50 MB'tan büyük üyeler atlanır.
5. Gövde ve her ek için okuma işi kuyruğa eklenir.

**Konum ve yeniden tarama**

- Klasör başına UIDVALIDITY ve son UID veritabanında tutulur.
- İlk kurulumda kutu, ayarlanan başlangıç gününden itibaren okunur; partiler halinde ilerler ve kaldığı yerden devam
  eder.
- Gönderici listeleri, başlangıç günü ya da klasör değişince kutu yeniden taranır.
- Okuyucu güncellemesinde kutu yeniden taranmaz; arşiv her şeyi saklar (ADR-0005).

**Hatalar ve sırlar**

- Giriş reddedilirse alım durur ve kullanıcıya bir kez bildirilir. Otomatik yeniden deneme yapılmaz, çünkü tekrarlanan
  başarısız girişler Google hesabını kilitleyebilir. Kullanıcı şifreyi kurulum ekranından ya da kendi terminalinde
  `iplikci eposta kur` ile yeniden girer.
- Şifre yalnızca anahtar zincirindedir (`iplikci` hizmeti). Masaüstü olmayan Linux'ta ortam değişkeninden okunur.
- E-posta adresi günlüklere ve çıktılara yazılmaz.

## Sonuçlar

- Olumlu: bildirimler saniyeler içinde akışa düşer; her bilginin kaynağı olan e-posta saklanır ve gösterilebilir;
  okuyucu geliştirmek için posta kutusuna yeniden gitmek gerekmez.
- Olumsuz: ilk kurulumda bütün kutunun okunması zaman alır (partiler halinde, kaldığı yerden devam ederek).

## Değerlendirilen seçenekler

- **Gmail API (OAuth):** dar ve salt okunur yetki verir, ama uygulama doğrulaması ve belirteç süresi kişisel kullanımda
  zahmetli. Gerekirse ileride yeni bir ADR ile eklenir.
- **Yalnızca yoklama:** bildirimler 15 dakikaya kadar gecikir.
