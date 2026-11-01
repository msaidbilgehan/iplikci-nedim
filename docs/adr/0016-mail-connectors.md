# ADR-0016: E-posta bağlayıcıları; uygulama şifresi olmayan Gmail için tarayıcı eklentisi köprüsü

Durum: **Kabul edildi** (okuma yolu kullanıcının kararıyla Gmail'in web arayüzü) · Tarih: 2026-10-31 · Dayanak: G1,
G10, G12, K5, K10, K14, K15, K16 · ADR-0015'in bağlantı bölümünü ve ADR-0009'un izin listesini genişletir

## Bağlam

ADR-0015, e-postayı IMAP ve uygulama şifresiyle okur; ADR-0010'daki e-posta bildirim kanalı da aynı şifreyle SMTP
kullanır. Google'ın Gelişmiş Koruma Programı'ndaki (Advanced Protection) bir Gmail hesabında bu yol kapalıdır:
uygulama şifreleri sayfası "bu ayar hesabınızda kullanılamıyor" der ve eski uygulama şifreleriyle giriş reddedilir.

Google'ın belgelerine göre (2026-10-31'de bakıldı; kaynaklar en sonda):

- Gelişmiş Koruma'daki hesapta uygulama şifresi oluşturulamaz. Kayıt sırasında mevcut uygulama şifreleri iptal edilir;
  uygulama şifresi kullanan uygulamalar engellenir.
- Gmail ve Drive verisine yalnızca Google uygulamaları ve doğrulanmış üçüncü taraf uygulamalar erişebilir. Kendi OAuth
  istemcimiz doğrulanmamış olur; Gmail kapsamlarının doğrulaması ücretli bir güvenlik denetimi ister.
- Apps Script kullanılabilir; ama e-posta gibi verilere erişen betikler engellenebilir.
- Bu kısıtlar uygulama şifreleri ve uygulamalara verilen erişim izinleri içindir. Tarayıcıda açık oturumla çalışan bir
  eklentiden söz etmezler.
- Chrome, bir eklentinin izinli olduğu adreslere yaptığı istekleri aynı site sayar ve tarayıcının çerezlerini gönderir.
  Eklenti bu yüzden kullanıcının açık Google oturumuyla çalışabilir: uygulama şifresi, OAuth izni ya da yeni bir kimlik
  bilgisi gerekmez.
- Gmail'in gelen kutusu akışı (Atom) Google'ın belgelediği bir uçtur ve oturumla okunabilir. Yalnızca okunmamış
  iletileri, en çok yirmi tane listeler.

Kullanıcının kararları (2026-10-31):

- **K14:** son kullanıcı hiçbir iş için terminal açmamalı.
- **K15:** çözüm Windows, macOS ve Linux'ta çalışmalı ve kullanıcıdan kullanmadığı bir uygulamayı kurması
  istenmemeli. Bu yüzden ilk taslaktaki Thunderbird köprüsü bırakıldı. Kullanıcının önerisi bir Chrome eklentisiydi.
- **K16:** eklenti postayı Gmail'in web arayüzünden okumalı. Apps Script yolu bırakıldı: kurulumu son kullanıcıya göre
  değil ve kendiliğinden kurulamıyor (aşağıda, değerlendirilen seçenekler).

## Karar

### Bağlayıcılar

E-posta alımı, ham iletiyi (RFC 822) getiren değiştirilebilir bir bağlayıcıya ayrılır. ADR-0015'teki adımlar her
bağlayıcıda aynıdır: güven kuralı, şirket denetimi, `.eml` saklama, eklerin ayrılması, gövde okuma ve kuyruk.

| Bağlayıcı (`mail.connector`) | Nasıl okur | Kimin için |
|---|---|---|
| `imap` | ADR-0015'teki gibi: IMAP, IDLE, uygulama şifresi | Uygulama şifresine izin veren hesaplar |
| `browser_bridge` | Kullanıcının tarayıcısındaki İplikçi Nedim eklentisi, Gmail'in web arayüzünden, açık oturumla | Gelişmiş Koruma'daki Gmail hesapları ve isteyen herkes |

Hesabın kendi şifresi hiçbir bağlayıcıda istenmez. Uygulama korumayı aşmaya çalışmaz.

### Eklenti: İplikçi Nedim Köprüsü

- **Tarayıcı ve platform:** Chromium tabanlı tarayıcılar (Chrome, Edge, Brave) için, Manifest V3. Windows, macOS ve
  Linux'ta aynı paket. Firefox sonra.
- **Kurulum**
  - Chrome Web Store'dan tek tıkla kurulur (önce listelenmemiş yayın). Tarayıcı onu kendiliğinden günceller.
  - Gelişmiş Koruma'daki hesaplarda Güvenli Tarama'nın gelişmiş koruması açıktır. Yeni bir geliştiricinin eklentisi
    ilk aylarda kurulurken "dikkatli ilerleyin" uyarısı çıkar. Kurulum rehberi bunu söyler; uyarı "kuruluma devam et"
    ile geçilir.
  - "Paketlenmemiş yükle" yalnızca geliştirme içindir.
- **Eşleştirme**
  - Kullanıcı kurulum sayfasını açtığında sayfa eklentiyi bulur ve eşleştirmeyi başlatır. Eklenti kendi penceresinde
    bir kez onay ister; kod yazmak gerekmez. Sayfa eklentiye ulaşamazsa kurulum sayfası kısa bir kod gösterir.
  - Servis eklentiye yalnızca e-posta alım ucuna yetkili bir belirteç verir; belirteç arayüzden iptal edilir.
  - Eklenti ilk eşleştiği servisi tanır ve iletileri göndermeden önce, karşısındaki servisin eşleştirme sırrını
    bildiğini doğrular. 127.0.0.1:8643'te başka bir süreç dinliyorsa iletiler ona gitmez. Yeniden eşleştirme kullanıcı
    onayı ister.
- **İzinler**
  - Yalnızca `alarms` ve `storage`, artı iki adres: `https://mail.google.com/*` ve `http://127.0.0.1:8643/*`.
  - `externally_connectable` yalnızca `http://127.0.0.1:8643/*` içindir (eşleştirme için).
  - `tabs`, `<all_urls>` ve uzaktan yüklenen kod yoktur.
- **Ne gönderir:** yalnızca gönderici listesindeki alan adlarından gelen iletilerin ham hâlini. Servis bunları
  `POST /api/ingest/mail` ile alır. Güven kuralı, şirket denetimi ve saklama ADR-0015'teki gibi serviste yapılır.
  Gmail'in eklediği en üstteki `Authentication-Results` başlığı ham iletide aynen durur.
- **Salt okuma:** Gmail'de hiçbir şeyi değiştirmez: okundu işareti, etiket, taşıma ya da silme yoktur. Yalnızca okuma
  istekleri yapılır.
- **Konum:** son alınan iletinin kimliği ve tarihi serviste tutulur; eklenti durumsuzdur.
- **Hesap seçimi:** tarayıcıda birden çok Google hesabı varsa hangisinin kullanılacağı eklentinin penceresinde seçilir.
  Adres servise ve günlüklere gitmez.
- **Sağlık:** servis eklentinin son görülme zamanını Sistem ekranında gösterir. Tarayıcı bir günden uzun kapalı kalırsa
  bir kez bildirir; tarayıcı açılınca kaçırılan iletiler alınır.

### Gmail'den okuma: üç katman

| Katman | Ne yapar | Uç | Belgelenmiş mi | Ne zaman |
|---|---|---|---|---|
| 1 — Yeni ileti | Okunmamış iletileri fark eder | Gmail gelen kutusu akışı (Atom); gelen kutusu ve kategoriler | Evet | Dakikada bir |
| 2 — Tam tarama | Okunmuş ve arşivlenmiş iletileri, geçmişi bulur | Gmail web araması (`from:(…) after:…`) | Hayır | Tarayıcı açılışında ve saatte bir; ilk kurulumda partilerle |
| 3 — Ham ileti | İletiyi ekleriyle birlikte indirir (RFC 822) | "Orijinali göster" / "İletiyi indir" | Hayır | İleti başına bir kez |

- **Bağımsız bozulma:** katmanlar birbirinden bağımsız bozulur. 2 bozulursa 1 ve 3 yeni iletileri almaya devam eder.
- **Tek bağdaştırıcı:** Gmail'e dokunan kod tek bir modüldedir (`extension/src/gmail/`) ve kayıtlı sahte yanıtlarla
  test edilir.
- **Biçim alarmı:** bir yanıtın biçimi tanınmazsa o katman durur ve `mail.bridge_alarm` olayı üretilir. Kullanıcıya bir
  kez bildirilir; düzeltme eklentinin güncellemesiyle gelir.
- **Seyrek istek:** istekler sıralıdır; ham ileti en çok saniyede bir indirilir. Hata ve 429 yanıtında bekleme süresi
  artar. Böylece Google'ın kötüye kullanım koruması tetiklenmez.
- **Adresler:** yalnızca `mail.google.com`. ADR-0009'un izin listesine eklentinin satırı olarak girer; servisin kendisi
  e-posta için ağa çıkmaz.

### Bildirimler

- Bu hesapta SMTP girişi yoktur. Varsayılan kanallar Telegram ve masaüstüdür (ADR-0010'un e-posta kanalı kapalı
  başlar).
- E-posta kanalı istenirse, uygulama şifresine izin veren ayrı bir gönderici hesapla kurulur; alıcı kullanıcının kendi
  adresidir. Gönderici Gmail dışında bir sağlayıcıysa ADR-0009'a ek gerekir.

### MVP

MVP bu köprüyü almaz. 2026-10-31'de emekliye ayrıldı ([ADR-0018](0018-retire-mvp-clean-start.md)). Aşama 3'e dek
bankaların e-postaları Gmail'de bekler; eklenti kutuyu başlangıç gününden itibaren baştan okur.

## Doğrulama (Aşama 3'ün ilk işi)

Eklentinin servis çalışanında (içerik betiğinde değil) şu dört şey gösterilir:

1. Gelen kutusu akışı oturum çerezleriyle okunur ve ileti kimlikleri alınır.
2. Bir banka iletisinin ham hâli indirilir. En üstteki `Authentication-Results` başlığı DMARC pass gösterir ve ileti
   okunmamış olarak kalır.
3. Okunmuş ve arşivlenmiş eski bir banka iletisi tam taramayla bulunur.
4. Chrome'da macOS ve Windows'ta çalışır.

Sonuca göre:

- 3 tutmazsa yeni iletiler 1 ve 3 ile alınır. Geçmiş ve kaçanlar için arayüzde "Gmail'de eksikleri tara" düğmesi
  olur: açık bir Gmail sekmesinde içerik betiği görünen iletileri toplar.
- 1 ya da 2 tutmazsa yeni bir ADR yazılır.

## Uygulama notu (Aşama 3, 2026-11-01)

- **Doğrulama sayfası** eklentinin içindedir (`extension/src/verify/`). Dört maddeyi servis çalışanında dener; raporu
  adres, konu ya da ileti metni taşımaz.
- **Eşleştirme:** servisin oturum açılmış bir sayfası 8 karakterlik, 10 dakika geçerli, tek kullanımlık bir kod verir;
  beş yanlış kod açık kodları kapatır. Eklenti kodu kendi kökeninden belirtece çevirir. Servis belirtecin yalnızca
  SHA-256'sını saklar. Belirteç yalnızca eklentinin alım uçlarını açar: `/api/ingest/mail`, `/api/ingest/mail/cursor`,
  `/api/ingest/mail/known`, `/api/ingest/mail/scanned` ve `/api/ingest/mail/alarm`.
- **Servisin kanıtı:** eklenti her çalışmada önce `/api/bridge/hello`'ya rastgele bir değer (nonce) gönderir. Servis,
  belirtecin SHA-256'sının onaltılık yazımını anahtar alan HMAC-SHA256 ile yanıt verir. 127.0.0.1:8643'te servisin
  yerinde başka bir program varsa eklenti ona hiçbir şey göndermez.
- **1. ve 3. katman uygulandı.** Eklenti dakikada bir ve tarayıcı açılınca çalışır.
  - Teslim en eski iletiden başlar. Servis konumu (Gmail'in ileti kimliği ve tarihi) her teslimde ilerletir; eklenti
    konum tutmaz.
  - Servisin hiç alamayacağı ileti (boş ya da 40 MB'tan büyük) atlanır ve son 500'ü hatırlanır. Böylece aynı ileti her
    dakika yeniden indirilmez.
- **Seyrek istek:** Gmail istekleri arasında bir saniye vardır. 429'da ve başka bir sorunda bekleme bir dakikadan
  başlar, her seferinde ikiye katlanır ve en çok bir saat olur. Kullanıcının elle istediği denetim beklemeyi bir kez
  atlar.
- **Biçim alarmı:** tanınmayan bir sayfa o katmanı, eklentinin o sürümü için durdurur. Eklenti bunu
  `POST /api/ingest/mail/alarm` ile bildirir ve `mail.bridge_alarm` her katman ve sürüm için bir kez kaydedilir. Yeni
  bir sürüm katmanı yeniden dener.
  - "Orijinali göster" sayfası iletinin metnini göstermeyebilir. İlk gerçek taramada (2026-11-01) yüzlerce iletiden
    sonra bu oldu ve 3. katman durdu.
  - Bu yüzden 3. katman böyle bir sayfayı önce o iletinin sorunu sayar: ileti atlanır, raporda sayılır ve kullanıcıya
    Gmail'den indirip yüklemesi söylenir. Gmail büyük bir iletiyi göstermiyor olabilir.
  - Art arda üç ileti gösterilmezse sayfa değişmiş sayılır ve katman durur. Bu iletiler atlanmaz; düzelten sürüm onları
    yeniden dener. Gösterilmeyen her sayfadan sonra Gmail'e 10 saniye ara verilir.
  - Alarm, sayfanın metnini değil özelliklerini taşır: uzunluğu, başlığı (rakamlar maskeli, adres gibi sözcükler
    çıkarılmış), "Orijinali indir" bağlantısının ve ham metin öğesinin olup olmadığı. Servis bunları olayın ayrıntısında
    saklar.
- **Sağlık:** servis saatte bir bakar. Etkin bir eklenti bir gündür görünmediyse `mail.bridge_silent` bir kez
  kaydedilir; eklenti dönüp yeniden susarsa yeniden kaydedilir.
- **Doğrulamanın sonucu (2026-11-01, macOS'ta Chrome):**
  - 1. ve 2. madde tuttu: gelen kutusu akışı oturumla okundu. Ham ileti "Orijinali göster"den indirildi; Gmail'in
    eklediği en üstteki `Authentication-Results` DMARC pass gösterdi ve ileti okunmamış kaldı. "İletiyi indir"
    bağlantısı yönlendirdi; yol "Orijinali göster"dir.
  - 3. madde tutmadı: konu listesi adresi (`view=tl`) oturum açma sayfasına yönlendiriyor.
  - Windows (4. madde) henüz denenmedi.
- **2. madde ekler için tutmadı (2026-11-01, ilk gerçek tarama):**
  - "Orijinali göster" ek parçasını başlıklarıyla verir ama içeriğini boş bırakır. Örneğin bir dekont iletisinin
    sayfası 10 KB'tı, iletinin tamamı ise 103 KB. Doğrulama yalnızca başlıklara ve DMARC'a baktığı için bu
    görünmemişti.
  - Sayfadaki "Orijinali indir" bağlantısı (`view=att&attid=0&disp=comp`) Gmail'in ek sunucusuna,
    `mail-attachment.googleusercontent.com`'a yönlendirir. Oradan iletinin tamamı, bayt bayt gelir: Gmail'in eklediği
    en üstteki `Authentication-Results` dahil, yani güven kuralı aynen çalışır.
- **Karar (kullanıcı, 2026-11-01):** eklentiye bu ek sunucusu için izin eklendi (eklenti 0.4.0). Dosya adı geçen bir
  ileti "Orijinali indir" ile tam alınır; indirme yalnızca Gmail'de ya da ek sunucusunda biterse kabul edilir.
  Oturum kapalıysa giriş sayfasına yönlendirilen bir indirme reddedilir. Yeni bir dış adres olduğu için ADR-0009'un
  listesine eklendi.
- **Eksik saklanan iletiler** (göç 10): servis, ekleri boş saklanmış iletileri tanır ve taramada yeniden ister.
  İletinin tamamı gelince eksik kopya çöp kutusuna gider (ADR-0003). Eksik kopyanın Gmail'in gösterdiği metin ekleri
  tam iletiye bağlanır. İkisi birden kalsaydı ileti iki kez okunurdu.
- **"Gmail'de eksikleri tara"** (yalnız 3. madde tutmadığında öngörülen yol) uygulandı.
  - Eklentinin penceresindeki düğme Gmail'i yeni bir sekmede, listedeki göndericilerin başlangıç gününden beri gelen
    iletilerinin aramasıyla açar.
  - Sekmede çalışan toplayıcı (`chrome.scripting`) görünen listeden yalnızca konuşma kimliklerini okur. Kimlikler
    satırların `data-legacy-thread-id` ve `data-legacy-last-message-id` öznitelikleridir. Sayfalar adresin `/pN`
    ekiyle çevrilir; sekme iş bitince kapanır.
  - Servis, teslim ettiği iletileri Gmail kimlikleriyle hatırlar (göç 8). Eklenti `POST /api/ingest/mail/known` ile
    yalnızca eksikleri sorar; eksikler 3. katmanla indirilir. Bu teslimlerin tarihi yoktur; akışın konumu yerinde kalır.
  - Servisin almadığı iletiler de hatırlanır (göç 9): listede olmayan gönderici, doğrulanamayan gönderen ya da şirket
    iletisi. Saklanan yalnızca Gmail kimliği, ne olduğu, nedeni ve listedeki gönderenin alan adıdır.
    - Böyle bir ileti, reddedildiği ayarlar değişmedikçe yeniden indirilmez. Bu ayarlar gönderici listesi, gönderen
      denetimi, güven kuralının sürümü ve şirket adlarıdır.
    - İlk gerçek taramada iletilerin yarıdan fazlası doğrulanamadı ve her tarama bunları yeniden indiriyordu.
  - Doğrulanamayan iletinin nedeni en üstteki `Authentication-Results`'ın gösterdiğidir: başlık yok, başlığı Gmail
    eklememiş, DMARC sonucu yok, DMARC sonucu "pass" değil ya da DMARC başka bir alan adı için geçti. Sistem ekranı
    alınmayan iletileri nedenleri ve alan adlarıyla sayar.
  - Bir konuşmayı açmak iletilerini okundu yapar, bu yüzden tarama hiçbir konuşmayı açmaz. Liste bir konuşmanın ilk
    (konuşmanın kimliği) ve son iletisini adlandırır.
  - **Konuşmaların ortası** (2026-11-01): ilk gerçek taramada bazı konuşmaların ortasında ileti kaldı. Bankalar
    aynı konulu iletileri dakikalar içinde art arda gönderiyor (dekontlar, birkaç hesabın özeti), Gmail de bunları tek
    konuşmada topluyor.
    - Konuşmanın yazdırma görünümü (`view=pt&search=all&permthid=thread-f:<kimlik>`, mail.google.com'a bir GET)
      bütün iletileri göndericileriyle gösterir. Bir iletinin eklerinin bağlantıları o iletinin kimliğini taşır
      (`view=att&th=<kimlik>`). Tarama bu sayfadan yalnızca ekli iletilerin kimliklerini ve göndericilerin alan
      adlarını okur; listedeki bankaların iletilerini 3. katmanla indirir.
    - Bu sayfanın iletileri okundu yapıp yapmadığı bilinmiyor. Bu yüzden yalnızca satırı baştan sona okunmuş görünen
      konuşmalar için istenir (satırın `yO` sınıfı var, `zE` yok). Satır ikisini de söylemezse konuşma okunmamış
      sayılır. İlk taramada bu sınıflar, okunmamış konuşmaların araması (`is:unread`) ile 100 satırın 100'ünde
      uyuştu.
    - Eki olmayan iletiler kimliklerini göstermez; okunmamış konuşmaların ortası da alınmaz. Rapor ikisini ayrı sayar.
      Kullanıcı okunmamış bir konuşmayı Gmail'de açarsa sonraki tarama onun ekli iletilerini alır.
    - İlk taramada okunmuş 17 konuşmanın ortasındaki 52 iletiden 16'sı ekliydi ve servis hiçbirini tutmuyordu.
    - Yeni bir adres yok; izinler değişmedi.
  - Tanınmayan bir liste 2. katmanın biçim alarmıdır. İzinlere `scripting` eklendi; adresler değişmedi.
- **Geçmişin taranıp taranmadığını servis bilir** (eklenti konum tutmaz).
  - Biten bir tarama neyi aradığını `POST /api/ingest/mail/scanned` ile bildirir: başlangıç gününü ve gönderici
    listesini. Servis bunu eklentinin e-posta durumunda saklar (`scan_key`, IMAP'in baştan okuma anahtarı gibi).
  - İmleç (`/api/ingest/mail/cursor`) `history_due` ile geçmişin yeniden taranması gerekip gerekmediğini söyler.
    Gerekir: hiç taranmadıysa ya da başlangıç günü veya gönderici listesi o zamandan beri değiştiyse.
  - Eşleşme bitince, servis geçmişi istiyorsa tarama kendiliğinden başlar. Aynı servise yeniden eşleşmek taramayı
    yinelemez.
  - Kendiliğinden başka tarama yoktur: sekmesi kullanıcının işinin önüne çıkardı. Geçmiş gerekiyorsa eklentinin
    penceresi, Sistem sayfası ve eklenti sayfası bunu söyler; "Şimdi denetle" de önce taramayı yapar.
- Başlangıç gününün arayüzden seçilmesi sonra gelecek; varsayılanı iki yıl öncesinin 1 Ocak'ıdır.

## Sonuçlar

- Olumlu:
  - Gelişmiş Koruma açık kalır ve yeni bir kimlik bilgisi doğmaz.
  - Servis e-posta için ağa çıkmaz.
  - Her işletim sisteminde aynı yol kullanılır: kullanıcının zaten kullandığı tarayıcı.
  - Kullanıcının işi eklentiyi kurmak ve bir kez onaylamaktır; terminal gerekmez.
- Olumsuz:
  - Tarayıcı açık olmalıdır; kapalıyken gelenler tarayıcı açılınca alınır.
  - Gecikme saniyeler değil dakikalardır (≤ 5 dk).
  - 2. ve 3. katman Gmail'in belgelenmemiş web uçlarına dayanır. Google değiştirince bozulurlar; biçim alarmı bunu
    hemen gösterir ve düzeltme eklenti güncellemesiyle gelir.
  - Yeni geliştirici uyarısı birkaç ay sürer. Mağaza yayını ve politikalarıyla uğraşmak gerekir.

## Değerlendirilen seçenekler

- **Apps Script (taslaktaki A yolu):** kullanıcının hesabındaki bir betik Gmail'i Google'ın belgelenmiş hizmetiyle okur;
  eklenti onu oturumla çağırır. Kullanıcı reddetti (K16). Nedenleri:
  - Kurulumu son kullanıcıya göre değil: betiği kopyalamak, yetki vermek, yayımlamak.
  - Kendiliğinden kurulamaz. Kullanıcının hesabında betik oluşturup yayımlamak Apps Script API'sini ister. Bu API'ye
    kendi OAuth iznimizle erişmek gerekir; Gelişmiş Koruma bunu engeller. Ayrıca kullanıcının Apps Script ayarlarında
    API'yi elle açması gerekir.
  - Gmail'i okuma izni Google'ın onay ekranında kullanıcı tarafından verilir; bu bilerek otomatikleştirilemez.
  - Gelişmiş Koruma'da e-postaya erişen betikler engellenebilir.
  - Kullanıcının eski, tek seferlik betiği altı dakikalık çalışma sınırına takılıp yarıda kesiliyordu.
- **Thunderbird köprüsü (ilk taslak):** Thunderbird Windows, macOS ve Linux'ta çalışır ve Google'ın istisna
  listesindedir. Ama kullanıcıya kullanmadığı bir e-posta istemcisini kurdurur ve açık tutturur (K15).
- **Apple Mail:** yalnızca macOS'ta var; deposunu okumak Tam Disk Erişimi ister.
- **Kendi OAuth istemcimiz (IMAP XOAUTH2 ya da Gmail API):** Gelişmiş Koruma doğrulanmamış uygulamaları engeller;
  doğrulama ücretli denetim ister; "Test" durumunda belirteç 7 günde düşer.
- **Apps Script ve Drive masaüstü eşitlemesi:** Drive masaüstü uygulaması Linux'ta yok ve ek bir uygulama ister.
- **Gelişmiş Koruma'yı kapatıp uygulama şifresine dönmek:** hesabın en güçlü koruması gider; uygulama şifresi iki
  adımlı doğrulamayı atlar ve bütün kutuya erişir. Karar kullanıcınındır; önerilmez.
- **Başka bir posta kutusuna yönlendirme:** banka e-postaları daha zayıf korunan ikinci bir hesapta toplanır. Güven,
  yönlendirmede DKIM imzasının bozulmamasına kalır. Önerilmez.

## Kaynaklar

- Uygulama şifreleri: <https://support.google.com/accounts/answer/185833>
- Gelişmiş Koruma, sık sorulanlar: <https://support.google.com/accounts/answer/7539956>
- Gelişmiş Koruma, Workspace SSS'si:
  <https://knowledge.workspace.google.com/admin/security/advanced-protection-program-faq>
- OAuth belirteç süreleri: <https://developers.google.com/identity/protocols/oauth2>
- Gmail gelen kutusu akışı: <https://developers.google.com/workspace/gmail/gmail_inbox_feed>
- Chrome eklentilerinde çerezler: <https://developer.chrome.com/docs/extensions/develop/concepts/storage-and-cookies>
- Chrome eklentilerinde başka sitelere istek: <https://developer.chrome.com/docs/extensions/mv3/xhr/>
- Güvenli Tarama'nın gelişmiş korumasında eklenti uyarısı: <https://support.google.com/chrome/answer/2664769>
