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

## Uygulama notu (Aşama 3, 2026-11-01)

- **Tek hat, iki bağlayıcı:** IMAP (`ingest/mail/imap.py`, `app/mail.py`) ve tarayıcı eklentisinin alım ucu
  (`POST /api/ingest/mail`, [ADR-0016](0016-mail-connectors.md)) iletiyi aynı yoldan geçirir. Seçili bağlayıcı
  `settings.toml`'daki `[mail] connector`'dır.
- **Güven kuralı** iki bağlayıcıda da aynıdır. Güvenilmeyen ileti sayılır, iz bırakmaz.
  - `Authentication-Results` RFC 8601'e göre okunur: yorumlar çıkarılır, tırnak içindeki noktalı virgül başlığı
    bölmez ve yalnızca `dmarc=` ile başlayan bölüm sayılır.
  - Böylece göndericinin yazabildiği bir yere konmuş sahte bir "dmarc=pass header.from=banka" metni eşleşmez. Bu
    yer, SPF yorumundaki zarf adresi ya da tırnaklı bir adres olabilir.
- **İleti:** konusu ya da herhangi bir eki şirkete ait olan ileti saklanmaz. Diğerleri `.eml` olarak, her eki (zip
  üyeleri dahil) iletiye bağlı ayrı bir belge olarak saklanır. `.eml`'ler Aşama 4'e dek "işlenmedi" kalır; gövdeler o
  aşamada okunur. 40 MB'tan büyük ileti alınmaz.
- **IDLE** elle yazıldı (Python 3.13'ün `imaplib`'inde yok). Yeni iletide işçiden bir alım ister ve 25 dakikada bir
  yenilenir. Kopan bağlantıyı her seferinde iki katı bekleyerek, en çok 15 dakika arayla yeniden açar. Yedek yoklama 15
  dakikada birdir; bir alım en çok 300 ileti alır, sonraki kaldığı yerden sürer.
- **Konum** veritabanındaki bağlayıcı tablosundadır. Klasörün UIDVALIDITY'si, son UID ve bir tarama anahtarı tutulur.
  Tarama anahtarı gönderici listelerini, başlangıç gününü ve klasörü kapsar; biri değişince kutu baştan taranır.
- **Reddedilen giriş** bağlayıcıyı durdurur ve bir kez `mail.auth_failed` kaydedilir. Kullanıcı bağlantıyı yeniden
  kurana dek ne yoklama ne IDLE yeniden dener.
- **Kurulum:** IMAP şifresinin kurulum ekranı Aşama 6'nın kurulum sihirbazıyla gelir; o zamana dek hesap
  `iplikci eposta kur` ile kurulur. Kullanıcının kendi hesabı tarayıcı eklentisini kullanır; eklentinin eşleştirmesi
  arayüzdedir.

## Değerlendirilen seçenekler

- **Gmail API (OAuth):** dar ve salt okunur yetki verir, ama uygulama doğrulaması ve belirteç süresi kişisel kullanımda
  zahmetli. Gerekirse ileride yeni bir ADR ile eklenir.
- **Yalnızca yoklama:** bildirimler 15 dakikaya kadar gecikir.
