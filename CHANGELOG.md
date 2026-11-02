# Değişiklik günlüğü

Biçim [Keep a Changelog](https://keepachangelog.com/tr-TR/1.1.0/)'a, sürüm numaraları
[anlamsal sürümlemeye](https://semver.org/lang/tr/) dayanır. Her aşama bir sürümle biter
([yol haritası](docs/v1/roadmap.md)).

## [Yayımlanmadı] — Aşama 6: Arayüz

Arayüz tamamlanıyor: ekranlar sırayla, açık ve koyu tema, sade ve ayrıntılı görünüm, çeviri altyapısı ve kurulabilir
uygulama (PWA). Her ekran demo çalışma alanında, iki temada ve axe denetimiyle uçtan uca sınanır.

### Eklenenler

- Arayüzün temeli: react-i18next ile Türkçe metinler, sayılardan ve yıllardan sonra gelen ekler için yardımcılar,
  açık, koyu ya da sistemin teması, sade ya da ayrıntılı görünüm (ikisi de hatırlanır), gruplu menüyle uygulama
  kabuğu, terimler sözlüğü, tutar, durum ve süzgeç bileşenleri, sabit renk yuvalı grafikler ve her grafiğin tablo
  görünümü.
- PWA: uygulama bildirgesi, simgeler ve yalnızca uygulamanın kabuğunu saklayan servis çalışanı; API yanıtları hiç
  saklanmaz, bildirge ve simgeler oturum istemez.
- Akış ekranı (`/akis`): "Şu an" (hesap başına tahmini bakiye, kart dönemleri, ay içi tempo), "Yaklaşanlar" (14 gün)
  ve olaylar, hesap, olay türü ve kesinlik süzgeciyle; yeni gelen olaylar işaretlenir.
- Pano ekranı (`/`): net varlık, nakit akışı, yaklaşanlar, tempo, uyarılar, yapılacaklar ve belgelerin tazeliği; her
  kart bir cümle ve ilgili ekranın bağlantısıyla.
- API: akışın sayfaları ve "Şu an" (`GET /api/feed`, `GET /api/feed/now`), pano kartları (`GET /api/dashboard`),
  hesap grupları, hesap sayfası, hesaplar arası akış ve hesaba verilen ad (`GET /api/accounts…`,
  `PUT /api/accounts/{id}/alias`).
- İşlemler API'si: süzgeçli, sıralı, sayfalı liste ve süzülenlerin toplamları; CSV; satırın ayrıntısı ve "Neden?"
  (kategori kuralı ve katmanı, transfer çözümünün adımı ve eşi, ilgili dekont ve bildirimler, fatura, kur ve günü);
  tek satıra ya da seçili satırlara düzeltme; kayıtlı görünümler.
- Satır bölme (F04): bir satır iki ile yirmi parçaya bölünür, her parça kendi kategorisinde sayılır, parçalar satırı
  kuruşu kuruşuna tutar (göç 0017). Seriler, büyük alışverişler, olağan dışı hareketler, belgenin satırları ve akışın
  haberleri satırın bütününe bakar; bölme bir aboneliği bozmaz, haber de olmaz. Birincil veri dökümünün 5. sürümü
  parçaları taşır.
- Her satır neden o kategoride olduğunu, transferinin nasıl çözüldüğünü ve hangi kurla değerlendiğini söyler.
- Belgeler: tam metin arama; tür, geliş yolu, hesap ve banka süzgeci; görüntüleyici için sayfa resmi, sayfadaki
  satırların kutuları ve e-postanın betiksiz özgün görünümü.
- Değerlendirme API'si: bulgular ve adımlar penceresiyle, alışkanlıklar, olağan dışı hareketler (`GET /api/insights`)
  ve İşlemler süzgeçleriyle harcama kartları ve üç aylık tahmin (`GET /api/spending`).
- Ay sonu kapanışı ay ay ve bir ayın tamamı; döviz: belgelerin kendi kurları ve her birimde net varlık.
- Yapılacaklar listesi, her maddeyi kapatacak adımlarla; kategori kuralları okunur, önizlenir, değiştirilir.
- Kurulum sihirbazı ve Ayarlar API'si: adlar ve şirket adları, yedeklerin saklanma süresi, e-posta bağlayıcısı, IMAP
  hesabını tek girişle kurma ve unutma; sihirbazın adımları ve ilk açılış.
- Servisin günlüğü indirilebilir: kişisel olabilecek yollar, adlar, adresler, IBAN'lar ve uzun numaralar çıkarılmış.
- Dışa aktarımlar listelenir ve indirilir.
- CI: uçtan uca testler her push'ta, her ekran iki temada axe ile.

### Düzeltilenler

- Aynı anda yapılan iki ayar değişikliği birbirini silebiliyor, ayar dosyasını okunamaz bırakabiliyordu; değişiklikler
  artık kilitle sırayla yapılır.
- Bir belge, okunmaya başladığı andaki şirket adlarıyla okunup kaydedildiği andakilerle damgalanıyordu; arada eklenen
  şirket adı belgeyi hiç yeniden okutmuyordu. Analiz de okuma sürerken kaydedilen adları görmeden güncel sayılıyordu.
- Harcama kartları ortalamalara kısmen kapsanan ayları da katıyordu; artık yalnızca tam aylar sayılır, gün aralığı
  İşlemler ekranındaki gibi sayılır, tahminin düzenli ödemeleri dönem dışındaki bütün süzgeçlere uyar.
- CSV ve Excel dışa aktarımında formül gibi başlayan metin artık metin olarak yazılır.
- Olağan dışı hareketler `docs/domain/interpretation.md`'deki eşiklere uyar; kart aidatı için iade adımı önerilir.
- Olay akışı baştan açılınca bütün kaydı yeniden göndermez; son dakikanın olaylarını yeniden söyler.
- Bölünmüş bir satır her sayımda tek ödemedir: ay sonu, alışkanlıklar, en çok harcanan yerler, kart dönemi ve
  dekont bulgusu onu bir kez sayar; büyük alışveriş satırın bütününe bakar. Üç aylık tahmin, son ödemesi bölünmüş
  düzenli ödemeyi parçalarının paylarıyla gösterir; kategori, grup ya da gereklilik süzgeci yalnızca tuttuğu
  parçaları sayar.
- Bir kural satırın türünü bölünmeyen bir türe çevirince ya da tutar bir parçayı sıfıra indirecek kadar değişince
  bölme sessizce kayboluyordu; artık Yapılacaklar'da "Uygulanamayan bölme" çıkar, satır paneli uyarır ve bölmeyi
  kaldırma yolu sunar. Kural önizlemesi böyle satırların değişikliğini de gösterir.
- Bölünmüş satırın kendisine verilen kategori ya da gereklilik görünmüyordu; artık reddedilir. Bir dekontun bölünmüş
  satırının parçalarına giden bağlantılar, dekontu ekstre gösterince ekstrenin aynı parçalarını açar.

## [0.6.0] — 2026-11-02 — Aşama 5: Bildirimler

Akışın olayları kurallara göre bildirime dönüşür ve uygulama içi kutuya, masaüstüne, Telegram'a ya da kişinin kendi
adresine gider. Her uyarı kanal başına bir kez gider; sessiz saatte ve sıklık sınırının üstünde gelenler özetle gider,
başarısız teslim yeniden denenir (F13). Akış yaklaşan son ödemeleri, eksiye düşecek bakiyeyi, gelmeyen ödemeleri,
geciken geliri, abonelik zamlarını ve büyük harcamaları da söyler. Kurallar, kanallar, Telegram eşleştirmesi ve teslim
kaydı Bildirimler ekranındadır.

### Eklenenler

- Bildirim kuralları (`rules/alerts.yaml`, Türkçe anahtarlar): her kural bir olayı izler. Koşulları `gun` (en çok kaç
  gün kala), `tutar` (en az kaç TL) ve `metin` (başlıkta geçen yazı) olabilir. Kanalları, ayrıntı düzeyi, sessiz
  saate uyup uymayacağı ve açık ya da kapalı oluşu kurala yazılır. Okunamayan dosya reddedilir; önceki sürüm kural
  geçmişinde saklanır.
- 16 hazır kural baştan açık: son ödemeye 3 gün, hesap eksiye düşecek, büyük harcama, abonelik zammı, iptalden sonra
  ödeme, beklenen ödeme gelmedi, maaş gecikti, ay bitti, ay kapandı, ay kontrol gerektiriyor, ekstrede görünmeyen
  dekont, e-posta girişi reddedildi, okuyucu biçim alarmı, tarayıcı eklentisi görünmüyor, eklenti Gmail sayfasını
  tanımadı, yedek alınamadı.
- Bildirim kaydı (göç 0015) ve kanallar:
  - Uygulama içi kutu her bildirimi hemen alır. Masaüstü (macOS ve Linux), Telegram ve kendine e-posta, kuralın ya
    da kanalın ayrıntı düzeyiyle gider (tam, özet, asgari).
  - Kural, olay ve kanal başına tek bildirim gider; yeniden başlatmadan sonra da.
  - Başarısız teslim artan aralıklarla yeniden denenir, sekizinci denemede bırakılır. Gönderilen bildirim bir daha
    gönderilmez.
  - Sessiz saatte ve kanalın sıklık sınırının üstünde gelenler saatte en çok bir özetle gider.
  - Reddedilen bir giriş ya da belirteç kanalı durdurur; kanal yeniden açılana dek denenmez.
- Telegram kanalı: kullanıcının kendi botu (ADR-0010). Belirteç anahtar zincirinde durur. Sohbet, bota on dakika
  içinde gönderilen `/start <kod>` ile eşleşir. Bot API'ye yalnızca `egress` üzerinden gidilir (ADR-0009).
- E-posta kanalı: IMAP bağlayıcısının uygulama şifresiyle, SMTP üzerinden kullanıcının kendi adresine. Tarayıcı
  eklentisiyle bağlı hesapta (Gelişmiş Koruma) kullanılamaz ve nedeni yazar.
- API: `GET /api/notifications`, `POST /api/notifications/read`, `GET/PUT /api/rules/alerts`,
  `POST /api/rules/alerts/preview` (bir kuralın son 30 günde kaç kez konuşacağı), `GET/PUT /api/notify/settings`,
  `POST /api/notify/test`, Telegram için `POST /api/notify/telegram/token|pairing|check` ve
  `DELETE /api/notify/telegram`.
- Komut satırı: `iplikci bildirim durum|kurallar|gecmis|dene` ve `iplikci telegram kur|eslestir|kaldir`. Belirteç
  gizli istemle sorulur, argüman olarak hiç alınmaz.
- MCP aracı `alerts`: kuralları listeler, ekler, kapatır ya da yeniden açar.
- Birincil veri dökümünün 3. sürümü bildirimleri de taşır; 2. sürüm dökümler yine okunur.
- Akışın yeni olayları (mimari §13; eşikler `docs/domain/interpretation.md`'nin "Akış olayları" bölümünde):
  - Yaklaşan ödeme, 7, 3, 1 ve 0 gün kala. Yalnızca kullanıcının ilgilenmesi gerekenler sayılır: kart son ödemesi,
    banka dışı fatura, kredi taksidi ve bir hesaptan yapılan düzenli ya da dönemsel ödeme.
  - Öngörüde eksiye düşen hesap: hesap yeni eksiye düşünce ya da gün öne gelince.
  - Gelmeyen ödeme ve gecikmiş gelir: hesabın belgeleri beklenen günü ve payını ödemesiz geçince; iptal edilen seri
    beklenmez.
  - Abonelik zammı ve iptalden sonra ödeme.
  - Gelen gelir ve büyük harcama: yalnızca son yedi günün satırları; geçmişi getiren bir ekstre bildirim yağdırmaz.
  - Ekstrede görünmeyen dekont.
  - Her olay bir kez söylenir. Bu olayları tanımayan eski anlık görüntüden sonraki ilk analiz onları yalnızca not
    eder.
- `iplikci servis durum` bildirim kanallarını ve bildirimlerin nasıl gittiğini de yazar.
- Bildirimler ekranı (`/bildirimler`):
  - Bildirim kutusu en yenisi önce gelir, okunmamışlar işaretlidir. "Tümünü okundu say" o ana dek görüneni okundu
    sayar; menüde okunmamışların sayısı görünür.
  - Kanallar kartı: sessiz saat, kanalları açıp kapama, her kanalın ayrıntı düzeyi, kanalın durumu ve her kanala
    deneme bildirimi.
  - Telegram kartı: BotFather adımları, bir daha gösterilmeyen bot belirteci, eşleştirme kodu ve sohbet bağlantısı.
    Eşleşme kendiliğinden görünür; Telegram buradan kaldırılır.
  - Kurallar kartı: her kural sözle ve açma kapama düğmesiyle listelenir. Düzenleyici yalnızca olayın izin verdiği
    koşulları sunar (gün, TL tutarı, metin); "Sessiz saatlere uy" seçeneği ve son 30 güne göre önizleme vardır.
  - Teslim kaydı: her kanaldaki bildirimin durumu, başarısız deneme sayısı, son hatası ve ilgili belge, işlem, ay ya
    da ekran.
- Olay akışı bir bildirim oluşunca ya da gidince bunu ayrı bir olayla söyler; bildirim kutusu beklemeden güncellenir.

### Değişenler

- Büyük alışveriş eşiği, iptalden sonraki ödemeler ve en yakın kur birer yardımcıda toplandı. Bulgular, akış ve
  defter aynı kuralı kullanır.

## [0.5.0] — 2026-11-02 — Aşama 4: E-postanın tamamı

E-postaların gövdeleri okunur. Banka bildirimleri kanıt olur; okuyucusu olmayan banka iletileri bilerek sınıflanır
ve F01'in kapsam ölçütü (en az %90) sağlanır. Kart ekstrelerinin son ödemesi, dönemsel seriler, 60 günlük takvim ve
nakit akışı öngörüsü defterden kurulur. Banka dışı faturalar ve makbuzlar banka satırlarıyla eşleştirilir; hiçbiri
toplamlara girmez (F14).

### Eklenenler

- `iplikci dev eposta-envanteri`: saklanan e-postalar gönderen alan adına ve konu kalıbına göre sayılır. İstenirse
  `exports/eposta-envanteri.csv`'ye yazılır.
- E-posta gövdeleri okunur. Seçici `Format.EMAIL` okuyucularına gönderenin alan adını, konuyu ve gövdenin görünen
  metnini gösterir. Okuyucusu olmayan ileti işlenmeden saklanır.
- Banka bildirimi diye yeni bir belge türü (`notice`). Satırları dekontunkiler gibi kanıttır ve ekstrelerle
  uzlaştırılır.
- `vakifbank.notice.transfer`: Vakıfbank'ın FAST ve para çıkışı bildirimleri okunur (K21). FAST bildiriminin yazdığı
  işlem sonrası bakiye satırla birlikte saklanır (göç 0012).
- Maskeli bir ad ("Ör**** Ku******"), kullanıcının adlarından biriyle kelime kelime uyuşuyorsa kullanıcının sayılır.
- Okuyucusu olmayan banka iletileri gönderene ve konuya göre adlandırılır:
  - kampanya, duyuru, güvenlik ve kart bildirimleri "para hareketi yok" diye sınıflanır;
  - belge taşıyan ileti ekleriyle okunur;
  - konusu para hareketi anan ileti, okuyucusu yazılana dek tanınmamış kalır.
- F01'in kapsam ölçütü: banka iletilerinin ne kadarının işlendiği ya da bilerek sınıflandığı Sistem ekranında ve
  `iplikci servis durum`'da görünür; tanınmayan ileti türleri listelenir.
- İmza sirküleri ve genel kurul iletileri şirket belgesi sayılır.
- `garanti.notice.transfer`: Garanti BBVA'nın para transferi bildirimleri, 2024'ün ve 2026'nın yerleşimleriyle okunur.
- Aynı hareketi anlatan bir dekont ile bir banka bildirimi bir kez sayılır: dekontun satırı kalır ve bildirimin
  yazdığı bakiyeyi alır.
- Ayrıntıyı internet şubesine bırakan, tutar içermeyen iletiler (Garanti'nin HGS iletisi) "e-postada para hareketi yok"
  diye sınıflanır.
- `qnb.notice.transfer`: QNB'nin FAST, havale/EFT ve para çıkışı bildirimleri okunur. Hesap numarası yazmayan FAST
  bildiriminin satırı, QNB'deki tek banka hesabına gider; bildirim, hesabın türünü (ek hesap ya da değil) e-dekontun
  ya da listenin dediğine bırakır.
- `isbank.notice.collection`: İş Bankası'nın gecikmiş kart borcunu hesaptan tahsil ettiği bildirim, karta yapılmış
  bir ödeme olarak okunur.
- Tutar içermeyen ve ücret değişikliğiyle ya da bir kredinin ilerleyişiyle açılan ileti, konusu para hareketi anlatsa
  da duyuru sayılır; metni yalnızca bankanın altbilgisi olan (iletisi resimde) ileti de duyurudur.
- Aynı eki taşıyan ikinci ileti (ekli bir iletinin iletilmesi) de ekiyle okunmuş sayılır: ek bir kez saklanır.
- Yaklaşan bir ödemeyi hatırlatan iletiler (haftalık kart ödemeleri, kredinin vade tarihi) "ödeme hatırlatması" diye
  sınıflanır.
- Okuyucusu olmayan bir iletinin selamlaması bir şirketi anıyorsa ("Merhaba ÖRNEK A.Ş.,") ileti şirket belgesi sayılır;
  gövdenin daha aşağısında geçen şirket adı sayılmaz. SGK işyeri sicil numarası altında ödenen primleri anan ileti de
  bir bordronun parçasıdır, şirket belgesi sayılır.
- Dönemsel seriler: aynı ödeme alanına yaklaşık altı ayda (160–200 gün) ya da yılda (330–400 gün) bir yapılan
  ödemeler; durumları aylık serilerin kurallarıyla bulunur. Aylık seriler ve bulgular değişmez.
- Takvim (F09): önümüzdeki 60 günün düzenli ve dönemsel ödemeleri, maaş ve düzenli gelirler (son üç tutarın
  medyanı), kartlardaki kalan taksitler, dekontlardan kredi taksitleri ve kart ekstrelerinin son ödemeleri (kesimden
  sonra yapılan ödemeler düşülür); her kalem hesabını, gününü, tutarını ve dayanağını yazar.
- Nakit akışı öngörüsü (F09): her TL banka hesabının 60 günlük bakiyesi gün gün, "tahmin" diye işaretli; belgedeki
  en yeni bakiyeden başlar, eksiye düştüğü günü ve tutarı gösterir.
- API `GET /api/subscriptions`, `/api/calendar`, `/api/forecast`; MCP araçları `subscriptions`, `upcoming_payments`,
  `cash_flow_forecast`; arayüzde Abonelikler (`/abonelikler`) ve Takvim (`/takvim`) ekranları.
- `invoice.ubl_tr`: e-Fatura ve e-Arşiv faturaları (UBL-TR XML) okunur; XML ekler ve yüklenen XML dosyaları belge
  olarak alınır. Şirkete kesilen ya da kullanıcının şirketinin kestiği fatura şirket belgesidir.
- Banka dışı faturalar ve makbuzlar (F14) saklanır (göç 0014) ve banka satırlarıyla eşleştirilir: aynı tutar,
  faturada son ödeme tarihine, makbuzda −1…+3 güne uzanan pencere ve satıcı adına benzeyen işyeri. Eşleşen satır
  belgeyi taşır; günleri geçmeyen ya da belgelerin henüz ulaşmadığı belge bekler, bekleyen TL faturası takvime düşer
  (yabancı para birimindeki, TL tutarı bilinmediğinden Faturalar ekranında kalır); eşleşmeyen belge olası nedenleriyle
  yalnızca bilgi olarak görünür. Hiçbiri toplamları değiştirmez.
- Kart ekstrelerinde son ödeme tarihi, asgari ödeme ve kartın toplam limiti okunur (göç 0013):
  - İş Bankası Maximum üçünü de okur;
  - Garanti BBVA Bonus son ödeme tarihini ve kart limitini okur;
  - TEB Bonus ile QNB yalnızca son ödeme tarihini okur.
  Ekstrenin yazmadığı, bozuk yazdığı ya da iki yerde farklı yazdığı bilgi boş kalır; ekstre yine okunur.
  `iplikci dev parser debug` bu bilgileri de gösterir.
- Eşleşen fatura ya da makbuz, hiçbir kuralın adlandırmadığı satıra satıcının tam adından kategori bulur ("IYZICO
  \*ORNEK" satırı, "ÖRNEK ECZANESİ" makbuzuyla eczane harcaması olur). Satırın türü ve tutarı değişmez; kullanıcının
  düzeltmesi yine son sözdür.
- Akışta faturalar: bir fatura ya da makbuz gelince ya da durumu değişince (bekliyor, eşleşti, eşleşmedi) olay olur.
- Faturalar ekranı (`/faturalar`, F14): banka dışı göndericilerin faturaları ve makbuzları duruma göre listelenir.
  Bekleyenler son ödeme gününe göre, banka satırının arandığı günlerle; eşleşmeyenler olası nedenleriyle ve "bilgi —
  toplamlara girmez" işaretiyle; eşleşenler onları ödeyen banka satırıyla görünür. API `GET /api/invoices`, MCP aracı
  `invoices`.
- Sistem ekranında "Banka dışı göndericiler" kartı: alan adları eklenir ve kaldırılır
  (`GET/PUT /api/settings/mail/other-senders`; listeyi yalnızca arayüz değiştirir). Bir bankanın alan adı (altı ya da
  üstü dahil), iki kez yazılan ve alan adı olmayan değer reddedilir. Yalnızca göndereni DMARC'tan geçen iletiler
  alınır; liste değişince geçmiş yeniden okunur.

### Düzeltilenler

- Yalnızca e-cüzdanından bilinen bir hesap, e-cüzdanından sonraki ayları kapanmaktan alıkoymaz (K21).

## [0.4.0] — 2026-11-01 — Aşama 3: Servis

Kutu baştan okundu ve ilk gerçek taban alındı. Aşama iki açık koşulla kapandı (K19): servisin yedi gün kendi başına
çalışması (en erken 2026-11-08) ve eklentinin Windows'ta denenmesi. Eklenti şimdilik paketlenmemiş yüklenir (K20).

### Eklenenler

- Servis (ADR-0007): FastAPI, yalnızca `127.0.0.1:8643`'te; `iplikci servis calistir` onu ön planda çalıştırır.
  - Her istek Host başlığında servisi anmalı ve kimliğini kanıtlamalıdır: komut satırının API belirteci, tarayıcının
    oturum çerezi ya da eklentinin belirteci.
  - Tarayıcının yazma istekleri ayrıca servisin kendi Origin'ini ve `X-Iplikci: 1` başlığını ister.
  - Hatalar Türkçe başlıklı `application/problem+json`'dır.
- Giriş: `iplikci ac` iki dakika geçerli, tek kullanımlık bir bağlantı açar. Bağlantı 90 gün geçerli,
  `HttpOnly; SameSite=Strict` bir oturum çerezine döner.
- İş kuyruğu ve zamanlayıcı (ADR-0014): işler SQLite'tadır. Başarısız deneme 30 sn, 1, 2 ve 4 dakika sonra yeniden
  çalışır. Yeniden başlatmada iş kaybolmaz; uykudan sonra kaçan periyodik iş bir kez çalışır.
- Olay akışı: her analiz bir öncekiyle karşılaştırılır. Yeni satırlar, ekstrenin kesinleştirdiği satırlar ve ay
  haberleri olay olur. `/api/events/stream` (SSE) koptuğu yerden sürer.
- E-posta alımı (ADR-0015): bir ileti, hangi bağlayıcı getirirse getirsin, aynı yoldan geçer.
  - Gönderici listede olmalı ve en üstteki `Authentication-Results` From alan adı için DMARC pass göstermelidir.
    Başlık RFC 8601'e göre bölümlerine ayrılır; yorumlardaki ya da tırnaklı adreslerdeki sahte bir "dmarc=pass"
    sayılmaz.
  - Kendi DMARC kaydı olmayan bir alt alan adı, ana alan adının kuralıyla geçer ve Gmail başlığa ana alan adını yazar.
    Bu ana alan adı listedeyse ileti geçerlidir. İlk gerçek taramada bir bankanın alt alan adlarından gelen yüzlerce
    ileti bu yüzden reddediliyordu.
  - İleti `.eml` olarak, ekleri (zip üyeleri dahil) ayrı belgeler olarak saklanır. Şirket iletisi saklanmaz.
- IMAP bağlayıcısı: salt okunur (`EXAMINE`, `BODY.PEEK[]`); yeni ileti IDLE ile anında, yedek yoklama 15 dakikada bir.
  - Reddedilen giriş alımı durdurur ve bir kez `mail.auth_failed` kaydeder; yeniden denenmez.
  - Komutlar: `iplikci eposta kur | durum | kaldir | al`.
- Tarayıcı eklentisi (ADR-0016, `extension/`):
  - doğrulama sayfası;
  - arayüzden alınan tek kullanımlık kodla eşleştirme;
  - servisin her çalışmada HMAC ile kendini kanıtlaması;
  - gelen kutusundaki okunmamış banka iletilerinin dakikada bir, ham hâliyle servise teslimi;
  - biçim alarmı (`mail.bridge_alarm`) ve bir gündür görünmeyen eklentinin bildirimi (`mail.bridge_silent`);
  - "Gmail'de eksikleri tara": geçmiş ve kaçan iletiler için Gmail'in araması yeni bir sekmede açılır. Konuşma
    kimlikleri sonuç listesinden okunur ve servisin eksik dediği iletiler taşınır. Hiçbir konuşma açılmaz; tam tarama
    (2. katman) doğrulamada tutmadığı için bu yol kullanılır.
  - Geçmiş taraması eşleşince kendiliğinden başlar. Servis son bitmiş taramanın başlangıç gününü ve gönderici
    listesini hatırlar. İkisinden biri değişince eklentinin penceresi, Sistem ve eklenti sayfaları yeniden taramayı
    ister; "Şimdi denetle" de önce onu yapar.
  - "Orijinali göster"in metnini göstermediği tek bir ileti katmanı durdurmaz. İleti atlanır ve kullanıcıya Gmail'den
    indirmesi söylenir; ancak art arda üç ileti gösterilmezse katman durur. Biçim alarmı sayfanın metnini değil,
    özelliklerini taşır.
  - Ekler: "Orijinali göster" eklerin içeriğini boş veriyor. Dosya adı geçen bir ileti artık "Orijinali indir" ile,
    Gmail'in ek sunucusundan (`mail-attachment.googleusercontent.com`, yeni izin, eklenti 0.4.0) tam ve bayt bayt
    alınır. Servis ekleri boş saklanmış iletileri taramada yeniden ister; tam hâli gelince eksik kopya çöp kutusuna
    gider.
  - Konuşmaların ortası: liste bir konuşmanın yalnızca ilk ve son iletisini gösterir. Baştan sona okunmuş bir
    konuşmanın ortasındaki ekli iletiler, konuşmanın yazdırma görünümünden alınır; okunmamış konuşmalarınki istenmez.
    Rapor, eki olmayan ve okunmamış konuşmalarda kalan iletileri ayrı sayar.
  - Servisin almadığı iletiler Gmail kimliği ve nedeniyle hatırlanır. Ayarlar değişmedikçe yeniden indirilmezler.
    Sistem ekranı onları nedenleriyle sayar: listede olmayan gönderici, şirket iletisi ya da güven kuralının gördüğü
    (DMARC sonucu yok, "pass" değil, başka bir alan adı için geçti…).
- Gelen klasörü izleyicisi: değişmeden 20 saniye bekleyen dosyalar plansız alınır (F02).
- Yükleme (F02): dosyalar bir partiye yüklenir ve plan her dosyaya ne olacağını gösterir. Yalnızca onaylanan plan
  uygulanır; plandan sonra değişen bir dosya planı yeniler. Uygulanmayan parti bir gün sonra çöp kutusuna gider.
- Ağ çıkışı (ADR-0009): dış bağlantıları yalnızca `egress` açar.
- Servis yöneticisi: `iplikci servis kur | kaldir | durum | yeniden-baslat`; macOS'ta launchd, Linux'ta systemd,
  Windows'ta Görev Zamanlayıcı.
  - Servis geliştirme klasöründen kurulmaz.
  - Her veri klasörünün tek bir servisi çalışır.
  - Günlük, `logs/servis.log`'a JSON satırları olarak yazılır.
- Yedek: her gece 03:30'da alınır ve 14 gün saklanır; en yenisi hep kalır.
  - Belge asılları yedeklerin kendi nesne deposuna bir kez kopyalanır.
  - Her ayın ilk günü en yeni yedek geçici bir klasöre geri yüklenir; arşiv ve yeniden kurma denetimlerinden geçer.
  - Komutlar: `iplikci yedek al | liste | geri-yukle | prova`.
- Arayüz iskeleti (ADR-0008, `web/`): Sistem ekranı (F18), Belgeler listesi ve yükleme (F03, F02), tarayıcı eklentisinin
  eşleştirilmesi. Servis derlenmiş arayüzü oturumun arkasından sunar; olay akışı ekranları günceller.
- API uçları: `/healthz`, `/api/system`, `/api/events`, `/api/documents`, `/api/labels`, `/api/backups`,
  `/api/mail/fetch`, yükleme, plan ve uygulama, eklentinin eşleştirme ve alım uçları.
- Arayüzün API tipleri servisin OpenAPI belgesinden üretilir (`iplikci dev api-tipleri`). Üretilen dosya güncel
  değilse bir test başarısız olur.

### Değişenler

- Komut satırı bir paket oldu (`iplikci.cli`) ve çalışan servisin istemcisine dönüştü. Servis çalışırken `eposta al`
  servisten ister; ikinci bir IMAP bağlantısı açılmaz.
- `sources.py`, `ingest/archives.py` oldu; zip, mbox ve e-posta ekleri daha sıkı denetlenir. Okuyucunun girdisi
  (`Document`) okuyucu sözleşmesine taşındı.
- `servis kaldir` servisin süreci bitene dek bekler (en çok 30 saniye); bitmezse 1 ile çıkar. Program güncellemesi
  çalışan bir servisin dosyalarını değiştirmez.

### Düzeltilenler

İlk gerçek verilerle bulunanlar:

- Şirket iletileri: ticari kartlar, ticari müşteriler ve KOBİ iletileri genel şirket işaretlerine eklendi. Saklanmış
  bir e-postanın konusu yeniden okumada da denetlenir. Sonradan girilen bir şirket adı, önce saklanmış iletileri de
  bulur. Şirket iletisi ekleriyle birlikte çöp kutusuna gider.
- İki eklenti aynı yeni iletiyi teslim edince, şirketinki diye reddedilen tam iletinin ardından eki boş kopyası
  saklanabiliyordu. Bu kopya artık reddin arkasında kalmaz ve tarama onu tamamlar.
- Adı numaralı parçalarla gelen bir ek (RFC 2231, uzun ya da Türkçe adlar) eklentide tanınmıyordu; ileti artık tam
  alınır.
- Aynı tarayıcıdan iki eklenti Sistem ekranında eşleşme zamanlarıyla ayrılır.

### Kaldırılanlar

- MVP'nin paneli ve `iplikci panel`: yerini arayüzün yükleme bölümü ve Sistem ekranı aldı.
- MVP'nin otomasyonu (launchd işi, gelen klasörü çalışması, ay haberleri): yerini servis, akış ve gelen klasörü
  izleyicisi aldı.

## [0.3.0] — 2026-11-01 — Aşama 2: Okuyucu eklentileri

### Eklenenler

- Okuyucu sözleşmesi ve kayıt defteri (ADR-0005): 17 okuyucu, mimarideki kimlikleriyle (`garanti.bonus_card` …)
  ayrı eklentilerdir. Kurulu paketler `iplikci.parsers` giriş noktasıyla okuyucu ekleyebilir; aynı kimlik iki kez
  olamaz.
- Seçim: her okuyucu belgeyi ucuzca tanır ya da tanımaz. Tanıyan tek okuyucu okur; iki okuyucu tanırsa belge
  "okunamadı: birden çok okuyucu tanıdı" olur.
- Okuyucu başına sürüm: bir okuyucu değişince yalnızca onun belgeleri yeniden okunur. Hiçbir okuyucunun almadığı
  belgeler, okuyucular değişince onlara yeniden gösterilir. Yeni bir okuyucu artık posta kutusunu baştan taratmaz.
- Okuma ayrı bir süreçte: belge başına 60 saniye ve Linux'ta 1 GiB bellek sınırı. Sınırı aşan, süreci düşüren ya da
  yanıtı anlaşılmayan belge "okunamadı" olur; uygulama sürer. Sonuç JSON olarak döner, pickle kullanılmaz.
- Her satırın belgedeki yeri: PDF'de sayfa ve kutu ya da satır numarası, tabloda sayfa adı ve satır, HTML'de metindeki
  aralık. Veritabanı yeri saklar (göç 2).
- Biçim alarmı: bir okuyucu belgesini tanıyıp okuyamazsa ya da okuduğu ekstre doğrulanmazsa olay kaydına
  `parser.format_alarm` yazılır (göç 3). Olay kaydı birincil veridir; döküm (2. sürüm) onu da taşır.
- Sahte belgeler (`iplikci.fakes`): her bankanın belgeleri kodla, bankanın düzeninde üretilir; kart ekstreleri,
  XLS (BIFF8) ve XLSX hesap dökümleri dahil. Her okuyucunun en az bir örneği vardır ve okunuşu denetlenir.
- `iplikci dev parser probe | debug | test`: okuyucuların bir belgeyi tanıyıp tanımadığı, okuyanın ne okuduğu
  (satır satır, yerleriyle; hata izi dahil) ve sahte belgelerin hâlâ doğru okunup okunmadığı.

### Düzeltilenler

- Garanti Yatırım ekstresinin nakit satırları ve TEB kart ödeme dekontu satırı belgedeki yerini taşımıyordu.
- OCR'ın `)))` diye okuduğu temassız ödeme simgesi TEB Bonus satırlarının sonunda kalıyordu.
- TEB Bonus ve İş Bankası Maximum okuyucuları ilk sayfanın ilerisinde gördükleri şirket kartını yalnızca "işlenmedi"
  sayıyordu; belge arşivde kalıyordu. Artık şirket belgesidir ve saklanmaz.

### Değişenler

- Okuyucular ve yardımcıları `parsers/<banka>/<belge>.py` düzenine taşındı; sahte belge üreticileri demodan
  `iplikci.fakes` paketine geçti. Demonun belgeleri ve altın tabanı değişmedi.
- v0.2.0'ın tek sürümüyle okunmuş belgeler, okuyucu başına sürüme geçmek için bir kez yeniden okunur.

## [0.2.0] — 2026-11-01 — Aşama 1: Veri çekirdeği

### Eklenenler

- Veri klasörü: macOS'ta `~/Library/Application Support/iplikci/`, Linux'ta XDG, Windows'ta `LOCALAPPDATA`;
  `IPLIKCI_HOME` onu değiştirir. Klasörler yalnızca kullanıcıya açıktır (0700).
- `settings.toml`: her bölüm denetlenir. Bilinmeyen ya da yanlış bir anahtar, adını ve düzeltmesini söyleyen bir
  hatadır. Sırlar sistemin anahtar zincirinde (`iplikci` hizmeti), anahtar zinciri olmayan sistemde ortam değişkeninde.
- Belge arşivi: her belge bir kez, sha256'sıyla ve salt okunur saklanır. Bozulan nesne raporlanır, üzerine yazılmaz;
  kaldırılan belge sistemin çöp kutusuna gider.
- SQLite veritabanı (WAL, numaralı göçler): belgeler ve gelişleri, okunan satırlar, dekont kanıtları, düzeltmeler,
  denetim kaydı ve tam metin arama. Tutarlar en küçük birimde tamsayıdır.
- Tek alım yolu: gelen klasörü, kullanıcının verdiği yollar ve e-posta ekleri önce dokunmayan bir plandan, sonra tam o
  plandan geçer. Kayıtlı bir ekstrenin başka bir dosyası "kopyası" olarak tutulur ve defterde birleşir.
- İşlem parmak izi: hesap, gün, tutar, para birimi, sadeleştirilmiş açıklama ve benzer satırlar arasındaki sıra.
- `iplikci islem ara | duzelt | yetimler`: bir işleme not, etiket, kategori ya da gereklilik düzeltmesi. Düzeltme
  belgeler yeniden okununca da kalır; hiçbir satırın taşımadığı düzeltme silinmez, gösterilir.
- `iplikci dogrula --arsiv`: arşivi yeniden özetler ve veritabanını onunla karşılaştırır.
- `iplikci dogrula --yeniden-kur`: veritabanını arşivden ve birincil verilerden yanında yeniden kurar, sonucun aynı
  çıktığını denetler.
- Kural katmanları: kişisel kurallar (`rules/personal.yaml`) uygulamayla gelen genel kuralların üstüne biner.
- `Money` ve `Quantity` tipleri, İngilizce alan kodları ve Türkçe etiketleri tek bir modülde.
- Geliştirme: pyright (yeni paketlerde katı) ve hypothesis, sabit sürümlü; pyright CI'da da çalışır.

### Değişenler

- MVP'nin çalışma alanı (`ayarlar.toml`, `kategoriler.yaml`, `cikti/`) yerine veri klasörünün düzeni geldi. Rapor,
  CSV, Excel ve ay sonu sayfaları `exports/`'a, doğrulama tabanı `baseline.json`'a yazılır.
- Tutarlar `float` yerine kesin ondalık sayı (`Decimal`); belgeden okunan tutar iki haneye, buçuklar yukarı yuvarlanır.
  Demonun tabanı, CSV ve Excel çıktısı değişmedi. Tam lira gösterimi de buçukları yukarı yuvarlar.
- Alan kodları İngilizce, lira ISO koduyla (`TRY`) taşınır. Kullanıcının okuduğu her yer Türkçe etiketleri yazar.
- Ekstre kontrolü en çok 1 kuruş farka izin verir; MVP'nin 0,015 eşiğiyle aynı sonuç.
- Okuyucuların sürümü 14 oldu: kayıtlı her belge yeniden okunur.
- E-postayla gelen belgeler doğrudan arşive girer ve bildirilir.

### Kaldırılanlar

- MVP'nin okuma önbelleği (`cikti/.onbellek.json`), düzenleyicisi ve işlem hattı; yerlerini arşiv, veritabanı ve alım
  aldı.

## [0.1.0] — 2026-11-01 — Aşama 0: Zemin

### Eklenenler

- MVP'nin (`gider-analizi`) kodu ve testleri `iplikci` paketi olarak depoda; komut `iplikci`.
- `iplikci dogrula --taban`:
  - belgelerin doğrulama tabanını alır ve kayıtlı tabanla karşılaştırır,
  - gerilemede 1 ile biter ve kayıtlı tabanı korur.
- `iplikci dev demo`: sahte banka belgeleriyle bir demo çalışma alanı kurar. Tabanı testlerde altın dosyadır.
- Uygulamayla gelen genel kategori kuralları: `src/iplikci/rules/default.yaml`.
- Şirket adları ayardan gelir: `ayarlar.toml` içinde `[identity] business_names`. Adın hukuki biçimi (A.Ş., Ltd. Şti.)
  nasıl yazılırsa yazılsın eşleşir; adlar değişince okuma önbelleği yenilenir.
- `IPLIKCI_HOME` çalışma alanının klasörünü belirler.
- Lisans: BSD 3-Clause (`LICENSE.txt`).
- Geliştirme ortamı:
  - uv projesi ve ruff,
  - pre-commit (ruff, gitleaks),
  - GitHub Actions: Linux'ta ruff, pytest ve gitleaks; macOS'ta pytest.

### Değişenler

- Teknik adlar `iplikci` oldu:
  - e-posta şifresi değişkeni `IPLIKCI_MAIL_PASSWORD`,
  - anahtar zinciri hizmeti `iplikci`,
  - `com.iplikci.*` etiketleri ve `X-Iplikci` başlığı,
  - panel portu 8643.
- Ekstre açıklamalarının sonundaki yer adları:
  - bütün iller ve sık görülen fatura şehirleri kırpılır,
  - soyadı da olan il adları (Aydın, Bingöl, Karaman, Tokat) kırpılmaz.
- Kod `ruff format` ile biçimlendirildi.

### Kaldırılanlar

- Kodda, testlerde ve yorumlarda kalan kişisel izler: şirket adı, gerçek ekstrelerden kalan yerler ve tutarlar, kart ön
  ekleri, bir portföy satırı ve abonelik geçmişi.
