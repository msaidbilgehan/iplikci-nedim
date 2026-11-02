# ADR-0019: Eşleşmiş tarayıcı eklentisi arayüzü tek kullanımlık giriş bağlantısıyla açar

Durum: Kabul edildi · Tarih: 2026-11-02 · Dayanak: K14, tasarım · [ADR-0007](0007-api-and-auth.md)'nin kimliklerini
ve [ADR-0016](0016-mail-connectors.md)'nın eklenti belirtecinin kapsamını genişletir

## Bağlam

- Arayüz oturum ister ([ADR-0007](0007-api-and-auth.md)). Oturum tek kullanımlık bir giriş bağlantısıyla açılır:
  `/giris?anahtar=…` iki dakika geçerlidir ve bir kez kullanılır. `HttpOnly; SameSite=Strict` bir çerez bırakır,
  anahtarı da yönlendirmeyle adres çubuğundan çıkarır.
- Bu bağlantıyı şimdiye dek yalnızca anahtar zincirindeki API belirteci isteyebiliyordu (`POST /api/login-links`):
  kurulu uygulamanın açılışı ve CLI'nin `iplikci ac` komutu.
- Tarayıcı eklentisi kullanıcının her gün baktığı yerde, araç çubuğunda durur. Kullanıcı 2026-11-02'de eklentiye
  arayüzü doğrudan açan bir düğme istedi.
- Eklentinin belirteci ise yalnızca e-posta alım uçlarını açıyordu ([ADR-0016](0016-mail-connectors.md)). Eklenti
  arayüzün adresini açabilirdi; ama oturumu olmayan bir tarayıcı orada yalnızca giriş sayfasını görürdü.

## Karar

- **Yeni uç:** eşleşmiş eklentinin belirteci bir uç daha açar, `POST /api/bridge/login-link`.
  - Yanıt `POST /api/login-links`'inkiyle aynı giriş bağlantısıdır (`{url}`): iki dakika, tek kullanım, yalnızca
    `http://127.0.0.1:8643/giris?…`.
  - Uç yalnızca etkin bir eklentinin belirteciyle açılır. API belirteci, tarayıcı oturumu ve iptal edilmiş bir
    eşleşmenin belirteci reddedilir.
- **Eklentinin penceresi:** araç çubuğundaki düğme küçük bir pencere açar. Pencerede durum, "İplikçi Nedim'i aç",
  "Şimdi denetle" ve ayarlar sayfasına giden "Eşleştirme ve ayarlar" vardır. Pencere odak dışına çıkınca kapanır; bu
  yüzden eşleştirme ve Gmail taraması ayarlar sayfasında kalır.
- **"İplikçi Nedim'i aç"** arayüzü şu sırayla açar:
  1. Arayüzü gösteren bir sekme açıksa o öne getirilir ve ağa istek gitmez. O sekme zaten öndeyse bağlantıyla
     yeniden açılır: oturumu kapanmış ya da servis kapalıyken açılmış bir sekme olabilir.
  2. Eklenti eşleşmişse önce servisten kanıt ister (ADR-0016'daki HMAC), sonra giriş bağlantısını. Bağlantıyı
     yalnızca `http://127.0.0.1:8643/giris?` ile başlıyorsa açar: servisin giriş sayfasını gösteren sekmede, yoksa
     yeni bir sekmede.
  3. Eşleşme yoksa, eşleşme iptal edilmişse ya da servis eklentiden eskiyse arayüzün adresi bağlantısız açılır;
     tarayıcıda geçerli bir oturum olabilir.
  4. Adreste hiçbir program yanıt vermiyorsa ya da yanıt veren program kanıtı veremiyorsa hiçbir şey açılmaz.
     Pencere nedenini söyler.
- **Servisin sayfaları:** "Önce giriş yapın" ve "Bu giriş bağlantısı artık geçerli değil" sayfalarının başlığı
  "Giriş · İplikçi Nedim"dir. Eklenti giriş sayfasını gösteren sekmeyi bu başlıktan tanır. Sayfalar logoyu gösterir
  ve arayüzün İplikçi Nedim uygulamasından ya da eklentinin "İplikçi Nedim'i aç" düğmesinden açıldığını söyler.
  Betik, satır içi stil ve dış kaynak taşımazlar.
- **İzinler değişmez.** Açık sekmeyi bulmak için `tabs` izni gerekmez: `http://127.0.0.1:8643/*` adres izni yalnızca
  o adresteki sekmelerin adresini ve başlığını görmeye yeter. Eklenti oturum çerezini okumaz ve servise çerez
  göndermez.

## Güvenlik

- Eklentinin belirteci artık bir tarayıcı oturumu, yani arayüzün bütün yetkisi demektir. Bu, bu bilgisayardaki bir
  saldırganın yapabileceğini genişletmez:
  - Belirteç tarayıcı profilinde durur. Profili okuyabilen program bu kullanıcı olarak çalışıyordur ve veri klasörünü
    de okuyup yazabilir: veritabanı, arşiv ve ayarlar oradadır. Tarayıcının kendi oturum çerezi de aynı profildedir.
  - Bilgisayardaki başka bir kullanıcı ne profili ne de veri klasörünü okuyabilir. 127.0.0.1'e ulaşsa da belirteç
    olmadan bir şey alamaz.
  - Web sayfaları belirtece ulaşamaz. Belirteç eklentinin servis çalışanından çıkmaz; servis çalışanı yalnızca
    eklentinin kendi sayfalarının isteklerini dinler.
- Bağlantı yine tek kullanımlıktır, iki dakikada düşer ve yalnızca 127.0.0.1'e gider.
- Eklenti belirteci göndermeden önce servisten kanıt ister. 127.0.0.1:8643'te servisin yerinde başka bir program
  dinliyorsa ne belirteç ne istek ona gider, onun sayfası da açılmaz.
- Eşleşme arayüzden iptal edilince belirteç giriş bağlantısı da alamaz.

## Sonuçlar

- Olumlu:
  - Kullanıcı arayüzü tarayıcının araç çubuğundan, tek tıkla ve terminalsiz açar (K14). Oturumu kapanmış bir tarayıcı
    da tek tıkla yeniden girer.
  - Açık bir arayüz sekmesi yeniden yüklenmez, öne gelir; sekmeler çoğalmaz.
- Olumsuz:
  - Eklenti belirtecinin değeri API belirtecininkiyle aynı düzeye çıkar: e-posta alımının yanında bir de oturum.
  - Her bağlantı yeni bir oturum açar (90 gün, kullanıldıkça uzar); süresi dolan oturumlar silinir.
  - Eklenti giriş sayfasını başlığından tanır. Başlık değişirse eklenti o sekmeyi arayüz sanıp öne getirir; bir test
    servisin başlığının eklentinin aradığıyla aynı kaldığını denetler.

## Değerlendirilen seçenekler

- **Yalnızca adresi açmak:** belirtecin kapsamı değişmezdi; ama oturumu olmayan tarayıcı yalnızca giriş sayfasını
  görür ve kullanıcı arayüzü yine uygulamadan açardı.
- **Giriş bağlantısı için ayrı, ikinci bir belirteç:** iki belirteç aynı tarayıcı profilinde durur; birini okuyan
  ötekini de okur. Güvenlik kazancı yoktur, eşleştirme karmaşıklaşır.
- **Eklentiden uygulamanın açılışını çağırmak (native messaging):** her işletim sisteminde ayrı bir kayıt ve yeni bir
  izin ister; kurulum paketinin bunu her sistemde yazması gerekir.
