# İplikçi Nedim

İngilizce alternatif adı: **Money-Grubber**. Adını bir filmde paraları tutan karakterden alır.

Depo: <https://github.com/msaidbilgehan/iplikci-nedim> · Komut ve Python paketi kısa adla `iplikci`'dir.

Kişisel finans asistanı platformu:

- Bankaların e-postayla gönderdiği ekstreleri, dekontları, bildirimleri ve ödeme hatırlatmalarını kendiliğinden
  toplar, doğrular ve belgeleriyle birlikte saklar.
- Harcamaları, gelirleri, hesapları, abonelikleri ve döviz varlıklarını yorumlar.
- Aylık raporların yanında güncel akışı da anlık izletir; her rakamdan dayandığı belgeye gidilebilir.
- Bilgisayarda bir servis olarak çalışır; tarayıcıdan (PWA) ve MCP üzerinden Claude ile kullanılır.

## Durum

Uygulama [yol haritası](docs/v1/roadmap.md)'nı izler. Aşama 0 (Zemin, v0.1.0) başlangıç sürümünün (MVP,
`gider-analizi`) kodunu `iplikci` paketi olarak depoya getirdi. Kod kişisel izlerden temizlendi; uygulamayla gelen genel
kategori kuralları, bir doğrulama tabanı ve sahte belgelerle bir demo çalışma alanı eklendi.

Aşama 1 (Veri çekirdeği, v0.2.0) her şeyi bilgisayardaki veri klasörüne taşıdı:

- Belgeler içerik adresli bir arşivde aslıyla durur.
- Okunan satırlar ve kullanıcının düzeltmeleri SQLite veritabanındadır.
- Tutarlar kesin ondalık sayılardır.
- Arşivin bozulmadığı ve veritabanının arşivden aynen yeniden kurulabildiği birer komutla denetlenir.

Aşama 2 (Okuyucu eklentileri, v0.3.0) belgeleri okuyan okuyucuları ayrı eklentilere çevirdi:

- Her belgeyi tanıyan tek bir okuyucu okur; iki okuyucu tanırsa belge "okunamadı" olur, sıraya bırakılmaz.
- Her okuyucunun kendi sürümü vardır: bir okuyucu değişince yalnızca onun belgeleri yeniden okunur.
- Belgeler ayrı bir süreçte, süre ve bellek sınırıyla okunur; bozuk bir belge uygulamayı durduramaz.
- Her satır, belgede yazdığı yeri (sayfa ve kutu, satır ya da tablo satırı) bilir.
- Bir banka biçimini değiştirirse biçim alarmı kaydedilir.
- Her okuyucunun kodla üretilen sahte belgeleri ve testleri vardır.

Aşama 3 (Servis, v0.4.0) uygulamayı bilgisayarda kendi başına çalışan bir servise çevirdi:

- Servis yalnızca bu bilgisayardan (127.0.0.1) erişilen bir API sunar. Tarayıcıdan giriş tek kullanımlık bir
  bağlantıyla yapılır.
- İşler bir kuyrukta yürür; yeniden başlatmada ya da uykudan sonra kaybolmaz. Analiz değişince olay akışı güncellenir.
- E-posta iki yoldan gelir:
  - Uygulama şifresi olan hesaplar IMAP ile okunur: yalnızca okuma, yeni ileti IDLE ile anında.
  - Uygulama şifresi olmayan hesaplar, örneğin Gelişmiş Koruma'daki Gmail, tarayıcı eklentisiyle okunur. Eklenti
    Gmail'in açık oturumunu kullanır ve Gmail'de hiçbir şeyi değiştirmez. Gmail açıkken görünen banka iletilerini,
    okunmuş olsalar da, alır. Geçmişi "Gmail'de eksikleri tara" ile okur.
  - İki yolda da yalnızca listedeki bankaların, DMARC'tan geçen iletileri alınır. İleti ekleriyle birlikte saklanır;
    şirket iletileri saklanmaz.
- Gelen klasörüne bırakılan dosyalar kendiliğinden alınır. Arayüzden yüklenenlerde ise önce ne olacağı gösterilir;
  onaylanınca alınır.
- Her gece bir yedek alınır ve 14 gün saklanır. Her ay en yeni yedek geçici bir klasöre geri yüklenip denetlenir.
- Servis macOS'ta launchd, Linux'ta systemd, Windows'ta Görev Zamanlayıcı ile kaydedilir. Her veri klasörü için tek bir
  servis çalışır.
- Arayüzün iskeleti: Sistem ekranı, Belgeler listesi ve yükleme, tarayıcı eklentisinin eşleştirilmesi.
- Posta kutusu baştan okundu ve ilk gerçek doğrulama tabanı alındı.

İki koşul açık kaldı: servisin yedi gün kendi başına çalışması ve eklentinin Windows'ta denenmesi. Deneme önce
macOS'ta yapılıyor. Eklenti şimdilik Chrome Web Store'da değil, geliştirici modunda yükleniyor.

Aşama 4 (E-postanın tamamı, v0.5.0) bankaların bütün e-postalarını işe kattı:

- Posta kutusunun envanteri çıkarılır: iletiler gönderen alan adına ve konu kalıbına göre sayılır.
- E-posta gövdeleri okunur. Vakıfbank, Garanti BBVA ve QNB'nin para transferi bildirimleri ile İş Bankası'nın kart
  borcu tahsilatı bildirimi dekont gibi kanıttır ve ekstrelerle uzlaştırılır. Aynı hareketi anlatan bir dekont ile
  bir bildirim bir kez sayılır; bildirimin yazdığı bakiye saklanır.
- Okuyucusu olmayan banka iletileri ne olduklarına göre sınıflanır: kampanya, duyuru, güvenlik ya da kart bildirimi,
  ödeme hatırlatması. Banka iletilerinin ne kadarının işlendiği ya da bilerek sınıflandığı Sistem ekranında görünür.
- Selamlaması bir şirketi anan ileti ve işveren olarak ödenen primler şirket belgesi sayılır.
- Kart ekstrelerinde son ödeme tarihi, asgari ödeme ve kart limiti okunur.
- Altı ayda ya da yılda bir yapılan ödemeler, önümüzdeki 60 günün takvimi ve her TL hesabın gün gün bakiye tahmini
  gelir: Düzenli ödemeler (o zamanki adıyla Abonelikler) ve Takvim ekranları.
- Banka dışı faturalar ve makbuzlar alınır. e-Fatura ve e-Arşiv faturaları (UBL-TR XML) okunur ve banka satırlarıyla
  eşleştirilir; eşleşmeyenler yalnızca bilgi olarak görünür, toplamları değiştirmez. Banka dışı göndericiler Sistem
  ekranından eklenir; faturalar Faturalar ekranında listelenir.

Aşama 5 (Bildirimler, v0.6.0) önemli olayları kullanıcıya ulaştırır:

- Yaklaşan bir son ödeme, öngörüde eksiye düşecek bir hesap, gelmeyen bir ödeme ya da gecikmiş bir maaş, bir abonelik
  zammı, büyük bir harcama, ekstrede görünmeyen bir dekont, ayın kapanması ve sistem uyarıları birer olaydır.
- Bildirim kuralları hangi olayın hangi kanala ne ayrıntıyla gideceğini söyler. 16 hazır kural baştan açıktır; kurallar
  Bildirimler ekranından değiştirilir ve bir kuralın son 30 günde kaç kez konuşacağı önceden görülür.
- Kanallar: uygulamadaki bildirim kutusu, masaüstü, Telegram (kendi botunuzla) ve kendinize e-posta (uygulama şifresine
  izin veren hesaplarda). Telegram botu Bildirimler ekranından bağlanır: BotFather'ın verdiği belirteç bir kez girilir,
  bota gönderilen kodla sohbet eşleşir. Eşleşen sohbetten bota belge de gönderilebilir (v0.9.13).
- Bir olay için her kanala tek bildirim gider. Gönderilemeyen bildirim yeniden denenir; sessiz saatte gelenler sabah
  tek bir özetle gider. Gönderilen her bildirim teslim kaydında görünür.

Aşama 6 (Arayüz, v0.7.0) uygulamayı terminal açmadan kurulan ve kullanılan bir programa çevirdi:

- Arayüzün bütün ekranları geldi: Pano, Akış, Hesaplar, İşlemler, Düzenli ödemeler, Takvim, Döviz, Değerlendirme, Ay
  sonu, Belgeler, Faturalar, Bildirimler, Kurallar, Yapılacaklar, Sistem, Kurulum sihirbazı, Ayarlar ve Tarayıcı
  eklentisi.
  MVP raporunun bütün bölümleri Değerlendirme'de ve ilgili ekranlarda; her ayın sayfası uygulamanın içinde.
- Her ekranın sade (bir cümle ve sonraki adım) ve ayrıntılı (tablolar) görünümü, açık ve koyu teması vardır. Her
  grafiğin bir tablo görünümü vardır. Arayüz telefonda da yana taşmadan açılır ve uygulama gibi kurulabilir (PWA).
- Her rakamdan dayandığı satırlara, her satırdan belgesine gidilir. Belge görüntüleyici PDF'te satırın kutusunu,
  tabloda satırını, e-postada satırın sözcüklerini işaretler.
- Kurulum paketleri: macOS'ta `.dmg`, Windows'ta kurulum programı, Linux'ta AppImage; şimdilik imzasız (K22). Uygulama
  açılınca servisi kaydeder ve ilk açılışta kurulum sihirbazına götürür. Tarayıcı eklentisi programla gelir; sihirbaz
  eklentinin klasörünü açar ve tarayıcıya yüklenişini adım adım anlatır.
- Servis Ayarlar'dan durdurulur, yeniden başlatılır, bir yedekten geri yüklenir ve bilgisayardan kaldırılır; veri
  klasörü yalnızca istenirse çöp kutusuna taşınır.
- Uçtan uca testler demo çalışma alanında koşar: her ekran iki temada, telefon genişliğinde ve axe denetimiyle.
- macOS'ta temiz kurulum 2026-11-02'de denendi. Paketten kurulan uygulama servisi kaydetti ve
  sihirbazı açtı; sihirbaz eklentinin klasörünü hazırladı, eklenti eşleşti ve Gmail'deki geçmişi getirdi; Pano ve
  Değerlendirme ilk raporu gösterdi. Ayarlar'dan yeniden başlatma ve veri klasörüyle birlikte kaldırma da çalıştı.

Aşama 6'nın ardından arayüz sadeleşti ve hesap kitabı daha açık anlatır oldu:

- Pano'nun sade görünümü paranızı resimlerle anlatır: son kapanan ayda gelen, giden ve kalan para; aylara göre gelen
  ve giden; paranın nereye gittiği; önümüzdeki 30 günde hesabınızda ne kalacağı ve ne yapmanız gerektiği. Her
  grafiğin üstünde nasıl okunacağı yazar. Ayrıntılı görünümde ilk satır dört rakamı gösterir, kartlar tablolarıyla.
- Menü simgeli, logo her yerde; görünüm ve tema üst çubuktaki tek menüde. Sade görünümde menü sık kullanılan sekiz
  ekranı gösterir, diğerleri "Diğer ekranlar" altında; ayrıntılı görünümde bütün ekranlar gruplarıyla.
- Bir güncellemeden sonra arayüz yeni sürümü hemen gösterir.
- Bankadan elle indirilen belgeler "Belge ekle" ekranından eklenir: bir klasör seçilir ya da sürüklenir. Dosya ve klasör
  adlarının önemi yoktur; her belge içeriğinden tanınır, arşivdekilerle eşleşir, dosyalar yerinde kalır.
- Uzun ekranlar bölümlere ayrıldı: Akış, Değerlendirme, Bildirimler, Kurallar ve hesap sayfası. İşlemler'in süzgeçleri
  bir düğmenin altında; toplamlar giren, çıkan, fark ve harcama olarak ayrı ayrı yazar.
- Bir rakamın nasıl hesaplandığı "Nasıl hesaplandı?" altında. Kapanmamış bir ayın rakamları eksik olabileceğini
  söyler; bir hesap toplama girmiyorsa nedeni yazar. Abonelikler ekranının adı artık "Düzenli ödemeler".
- Tarayıcı eklentisinin araç çubuğundaki düğmesi küçük bir pencere açar. Penceredeki "İplikçi Nedim'i aç" arayüzü tek
  tıkla, oturum açılmış olarak açar.

Aşama 7 (MCP, v0.8.0) Claude'u İplikçi Nedim'e bağlar:

- Claude, paranıza dair sorularınızı İplikçi Nedim'deki verilere ve belgelere bakarak yanıtlar. Hesaplara, işlemlere,
  düzenli ödemelere, takvime, değerlendirmeye, ay sonuna ve bildirimlere bakar; belgeleri okuyup onlara dayanır. Hazır
  istemler en sık sorulanları sorar: aylık değerlendirme, abonelik denetimi, bu ay neden fazla harcandığı, ay kapanışı
  ve işlenmeyen bir belge.
- Bağlantı bu bilgisayarda kalır: Claude yalnızca bu bilgisayardaki servise, API belirteciyle bağlanır.
- Bir şeyi değiştiren araçlar (kategori ve bildirim kuralları, bir işleme not, bir belgeyi yeniden okutmak) önce ne
  değişeceğini gösterir; değişiklik ancak siz onaylayınca yapılır.
- Claude'a giden yanıtlarda hesap numaraları ve IBAN'lar, isterseniz kişi adları da gizlenir. Claude'un her çağrısı
  denetim kaydına yazılır.
- Claude terminal açmadan bağlanır. "Claude bağlantısı" ekranı claude-SAK'a ya da Claude Desktop'a yapıştırılacak
  yapılandırmayı verir. Belirteç Claude'un ayar dosyasına yazılmaz.

Aşama 8 (Döviz, v0.9.0) resmî kurları getirdi:

- Kurlar her gün TCMB'den alınır; belgelerinizin kapsadığı günlerin geçmiş kurları bir kez, kendiliğinden çekilir.
  TCMB'ye ulaşılamayan günlerin kuru ECB'nin referans kurundan gelir. İnternet yokken bankaların belgelerindeki kurlar
  kullanılır. Kurun kaynağı ve günü, gösterildiği her yerde yazar.
- Dövizli varlıklar döviz alış, borçlar satış kuruyla değerlenir; net varlık euro, dolar ve gram altın olarak da
  görünür.
- Döviz ekranı dört bölüm: Varlıklar; Kurlar (son 90 gün grafikte); Kur makası (son 12 ayda bankaların kurunun TCMB'ye
  göre size maliyeti, işlemleriyle); Döviz geliri (bugünkü kurla TL karşılığı, TL'ye çevrildiği günler ve "EUR/TRY %5
  düşerse" duyarlılığı).
- İsteğe bağlı enflasyondan arındırma: Ayarlar'daki "Enflasyondan arındırma (EVDS)" kartı ne işe yaradığını bir
  örnekle anlatır ve TCMB EVDS'de ücretsiz anahtarın nasıl alınacağını gösterir. Anahtarı girerseniz Değerlendirme,
  harcamanızın gerçekten mi yoksa yalnızca fiyatlar yüzünden mi arttığını da gösterir. Anahtar girilmedikçe özellik
  kapalıdır ve EVDS'ye hiçbir istek gitmez. Anahtar yalnızca bu bilgisayarın anahtar zincirinde saklanır.

İplikçi Nedim kendi sözleriyle de konuşur (v0.9.2):

- Pano'nun en üstünde ve tarayıcı eklentisinin penceresinde İplikçi Nedim'in yüzü ve dizideki sözlerinden biri durur.
  Söz paranızın durumuna göre seçilir: ay eksiyle kapandıysa başka, iyi geçtiyse başka, hesabınızın eksiye düşeceği
  öngörülüyorsa başka bir söz. Altında hangi durum için söylendiği yazar; eklentide tutar görünmez.
- Yüz durumun rengini alır: iyi giderken yeşil, dikkat isteyen durumda turuncu, kötü durumda kırmızı. "Başka bir söz"
  o gün doğru olan öbür sözleri gösterir. Sözlerin listesi [İplikçi Nedim'in sözleri](docs/İplikçi_Nedim_Sözler.md)
  belgesindedir.

Grafikler birer kısayoldur (v0.9.4):

- Bir grafikte bir aya, bir dilime, bir güne ya da bir akışa tıklayınca onu oluşturan işlemler açılır; listenin
  toplamı tıkladığınız rakamla aynıdır. Ör. Ay sonu'nda "Son 12 ayın gideri"nde Haziran'a tıklayınca Haziran'ın
  giderleri listelenir; Takvim'in öngörüsünde bir güne tıklayınca o gün beklenenler gösterilir.
- Telefonda ilk dokunuş değeri gösterir, ikinci dokunuş ya da ipucundaki "Aç" açar. Klavyeyle aynı yerlere grafiğin
  tablo görünümündeki bağlantılarla gidilir.

Belgeler Telegram'dan da eklenir (v0.9.13):

- Telegram botunuz eşleştiyse, bankanın uygulamasından indirdiğiniz ekstreyi, hesap dökümünü ya da dekontu bota dosya
  olarak gönderin (ataç → Dosya). İplikçi Nedim belgeyi Belge ekle ekranındaki gibi içeriğinden tanır, arşive alır ve
  ne olduğunu sohbette yazar: arşive alındı, zaten arşivde, okunamadı ya da neden alınmadığı.
- Belgeler yalnızca eşleşen sohbetten alınır; başka sohbetlerden gelen dosyalar hiç indirilmez. Fotoğraf okunmaz;
  Telegram bir bota en çok 20 MB büyüklüğünde dosya verir, daha büyükleri Belge ekle ekranından eklenir.
- Telegram iletileri uçtan uca şifreli değildir: gönderdiğiniz belge Telegram'ın sunucularında da durur. İsterseniz
  Bildirimler → Kanallar → Telegram kartındaki "Bota gönderilen belgeleri arşive al" anahtarıyla kapatabilirsiniz;
  kapalıyken servis botun iletilerini okumaz.

Gmail açıkken okunan banka iletileri de alınır (v0.9.14):

- Eklenti eskiden her dakika yalnızca okunmamış iletileri alıyordu. Bir sonraki denetimden önce Gmail'de açtığınız
  ileti ancak "Gmail'de eksikleri tara" ile geliyordu. Artık Gmail bu tarayıcıda açıkken listede ya da açtığınız
  konuşmada görünen banka iletileri, okunmuş olsalar da, kendiliğinden alınır. Eklenti bunun için yalnızca iletilerin
  kimliklerine ve göndericinin alan adına bakar; konu ve metin okumaz.
- Gmail'de hiç görünmeyen iletiler için "Gmail'de eksikleri tara" kalır. Örneğin bilgisayar kapalıyken telefonda
  okunup arşivlenen iletiler.
- TEB'in "Dijital Hesap Cüzdanı" PDF'i de okunur. TEB hesap hareketlerini e-postayla bildirmez; TEB hesaplarınızın
  güncel bakiyesi bu belgeyle gelir. Belgeyi TEB'in uygulamasından indirip Belge ekle ekranından ya da Telegram
  botuna göndererek ekleyin.
- Bir hesabın bakiyesi son belgesinin günündedir. O günden sonra o hesaba ya da o bankadaki bir hesabınıza
  gönderdiğiniz para bakiyenin notunda yazar.

Uygulamalardan paylaşılan dekontlar da okunur (v0.9.16):

- Vakıfbank'ın uygulamasından paylaşılan dekont ve TEB'in iki TEB hesabınız arasındaki havalenin dekontu ("Banka İçi
  Para Transfer Dekontu") okunur. Onları Belge ekle ekranından ya da Telegram botuna göndererek ekleyin. Dekont,
  hesap dökümü gelmeden önce parayı gösterir. Döküm gelince onun satırı sayılır; aynı hareket iki kez sayılmaz.
- TEB'in hesap cüzdanında iki satıra bölünen açıklamalar artık okunur. Önceden bu hareketler atlanıyor, cüzdan
  doğrulanmıyordu. Faiz işleyen TEB hesabı (ör. CEPTETEB Marifetli) vadeli hesap sayılır.

Açık kalanlar: servisin yedi gün kendi başına çalışması (K19). Windows ve Linux'ta denemeler bekletiliyor (K25).

MVP 2026-10-31'de emekliye ayrıldı. İplikçi Nedim onun kodundan başlar ama verisini devralmaz; belgeleri kendisi toplar.

## Kurulum

İplikçi Nedim her işletim sistemi için bir kurulum paketiyle gelir; Python ya da başka bir program kurmanız gerekmez.
Paketler şimdilik imzasızdır ve bir mağazada ya da indirme sayfasında yayımlanmıyor: her sürümde bu deponun "Paketler"
iş akışı üretir.

1. Paketi açın:
   - **macOS:** `.dmg` dosyasını açın ve İplikçi Nedim'i Uygulamalar klasörüne sürükleyin; uygulamayı oradan açın. İlk
     açılışta macOS uygulamanın geliştiricisini doğrulayamadığını söyler. Sistem Ayarları → Gizlilik ve Güvenlik'te
     "Yine de aç"a basın.
   - **Windows:** kurulum programını çalıştırın. "Windows bilgisayarınızı korudu" uyarısında "Ek bilgi"ye, sonra "Yine
     de çalıştır"a basın. Program yönetici izni istemeden kendi klasörünüze kurulur ve Başlat menüsünden açılır.
   - **Linux:** AppImage dosyasının özelliklerinden program olarak çalıştırılmasına izin verin ve dosyaya çift
     tıklayın.
2. Uygulama arka plan servisini bilgisayarınıza kaydeder ve tarayıcıda kurulum sihirbazını açar. Servis her oturum
   açılışında kendiliğinden başlar; uygulamayı sonra açtığınızda arayüz doğrudan açılır. Tarayıcı eklentisi
   eşleştikten sonra arayüzü eklentinin penceresindeki "İplikçi Nedim'i aç" düğmesiyle de açabilirsiniz.
3. Sihirbaz adlarınızı, e-postanın nasıl geleceğini, bankaları ve bildirimleri sorar. Gmail hesabınız uygulama
   şifresine izin vermiyorsa (örneğin Gelişmiş Koruma'daysa) e-postalar tarayıcı eklentisiyle gelir. Eklenti
   programla gelir: sihirbaz eklentinin klasörünü açar ve tarayıcıya nasıl yükleneceğini adım adım gösterir.
4. Claude'la kullanmak isterseniz Kurulum → Claude bağlantısı ekranını açın. Ekran, İplikçi Nedim'in Claude Code'a
   claude-SAK ile, Claude Desktop'a ise ayar dosyası yoluyla nasıl ekleneceğini adım adım gösterir. Yapılandırmayı
   kopyalayıp yapıştırmanız yeter.

Güncellemek için yeni paketi aynı yoldan açın; verileriniz yerinde kalır. Kaldırmak için önce Ayarlar'daki "Kaldır"
servisi bilgisayardan kaldırır; veri klasörü yalnızca siz isterseniz çöp kutusuna taşınır. Sonra uygulamayı sisteminizin
olağan yoluyla kaldırın: macOS'ta çöp kutusuna sürükleyerek, Windows'ta Ayarlar → Uygulamalar'dan.

## Belgeler

- [Belge dizini ve okuma sırası](docs/README.md)
- [V1 gereksinimleri ve kararlar](docs/v1/requirements.md)
- [Mimari](docs/v1/architecture.md) · [Özellikler](docs/v1/features.md) · [Yol haritası](docs/v1/roadmap.md) ·
  [MVP'den geçiş](docs/v1/migration.md)
- [Mimari karar kayıtları](docs/adr/README.md)
- Geliştiriciler ve ajanlar için kurallar: [`CLAUDE.md`](CLAUDE.md)

## Geliştiriciler için

Son kullanıcı terminal kullanmaz; aşağıdaki komutlar geliştirme içindir. Gerekenler: [uv](https://docs.astral.sh/uv/),
[gitleaks](https://github.com/gitleaks/gitleaks) ve arayüzle eklenti için [Node.js](https://nodejs.org/) 24 (CI'ın
sürümü).

```bash
uv sync                                          # Python 3.13 ve kilitli bağımlılıklar
uv run pre-commit install                        # her commit'ten önce ruff ve gitleaks
uv run pytest -q                                 # testler; demo çalışma alanının altın tabanı dahil
uv run ruff check && uv run ruff format --check  # biçim ve kod denetimi
uv run pyright                                   # yeni paketlerde katı tip denetimi
uv run iplikci dev demo /tmp/iplikci-demo        # sahte belgelerle demo veri klasörü (boş ya da yeni klasör)
IPLIKCI_HOME=/tmp/iplikci-demo uv run iplikci dogrula --taban --tarih 2026-11-15   # demonun doğrulama tabanı
IPLIKCI_HOME=/tmp/iplikci-demo uv run iplikci dogrula --arsiv                      # arşiv ve veritabanı tutarlı mı
IPLIKCI_HOME=/tmp/iplikci-demo uv run iplikci dogrula --yeniden-kur                # arşivden aynen kurulur mu
IPLIKCI_HOME=/tmp/iplikci-demo uv run iplikci islem ara MIGROS                     # işlemler, parmak izleriyle
uv run iplikci dev parser probe belge.pdf        # okuyucular belgeyi tanıyor mu, neden
uv run iplikci dev parser debug belge.pdf        # okuyan okuyucu ne okuyor: satır satır, yerleriyle
uv run iplikci dev parser test                   # okuyucular sahte belgelerini doğru okuyor mu
uv run iplikci dev eposta-envanteri [--csv]      # saklanan e-postalar, gönderen ve konu kalıbına göre
```

Servis, arayüz ve tarayıcı eklentisi:

```bash
(cd web && npm ci && npm run build)              # arayüz; çıktı pakete girer (src/iplikci/api/ui)
(cd e2e && npm ci && npx playwright test)        # uçtan uca: demo veri klasöründe, iki temada, axe ile
uv run iplikci dev api-tipleri web/src/api/schema.ts   # API'nin modelleri değişince arayüzün tipleri
uv run iplikci servis calistir                   # servis ön planda: http://127.0.0.1:8643
uv run iplikci ac                                # arayüzü tek kullanımlık giriş bağlantısıyla açar
uv run iplikci servis durum                      # servis çalışıyor mu; kuyruk, e-posta ve kapsamı, yedek ve disk
uv run iplikci yedek al | liste | geri-yukle | prova
uv run iplikci eposta kur | durum | kaldir | al  # IMAP hesabı; şifre yalnızca anahtar zincirinde
uv run iplikci kurlar al [--gecmis] | durum   # döviz kurları: şimdi çek (servis çalışıyorsa ona sorar), durumu
uv run iplikci mcp                               # MCP'nin stdio köprüsü: servis çalışıyorsa ona, değilse salt okunur
uv run iplikci mcp baslik                        # Claude Code'un başlık yardımcısı: belirteçli Authorization başlığı
(cd extension && npm ci && npm test && npm run build)   # eklenti; extension/dist ve pakete giren kopyası
uv run python packaging/build.py                 # bu sistemin kurulum paketi dist/paket/'e; önce web/ ve extension/
```

`iplikci servis kur | kaldir | yeniden-baslat` servisi sistemin servis yöneticisine kaydeder. `kur` geliştirme
klasöründen çalışmaz: servis, `uv tool install` ile kurulmuş sabit bir kopyayı çalıştırır. Böylece bir dal değişince ya
da bir dosya yarım kalınca o kod gerçek veriyle çalışmaz. Eklentinin geliştirme ve doğrulama adımları
[`extension/README.md`](extension/README.md)'dedir. Deponun `.mcp.json`'u bu klasörde açılan Claude Code'u servisin
`/mcp` adresine bağlar; belirteci `IPLIKCI_API_TOKEN` ortam değişkeninden okur.

Veri klasörü macOS'ta `~/Library/Application Support/iplikci/`'dir; `IPLIKCI_HOME` onu değiştirir. Gerçek belgeler
depoya hiç girmez: testler ve demo, kodla üretilen sahte belgelerle ve kendi klasörlerinde çalışır.

## İlkeler

- Banka akışları esastır: her para hareketi bir banka belgesine dayanır; diğer e-postalar kanıt ve bilgi katmanıdır.
- Yerel öncelik: belgeler ve veriler bu bilgisayarda, deponun dışındaki veri klasöründe durur. Ağa yalnızca e-posta
  okumak, döviz kurlarını (ve anahtar girildiyse TÜFE'yi) almak ve bildirim göndermek için çıkılır.
- Yalnızca kişisel para hareketleri; şirket belgeleri kapsam dışıdır.
- Hiçbir belge kalıcı silinmez.
- Finanstan anlayan da anlamayan da kullanmak istemeli.
- Kişisel ihtiyaçlar için yapılan bir hobi projesi, kurumsal bir ürün değil; yine de her kullanıcıya azami verim
  sağlamalı.

## Lisans

[BSD 3-Clause](LICENSE.txt).
