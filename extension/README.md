# İplikçi Nedim Köprüsü

Chromium tabanlı tarayıcılar (Chrome, Edge, Brave) için Manifest V3 eklentisi. Gmail'deki banka iletilerini, tarayıcının
açık Gmail oturumuyla okuyup bu bilgisayardaki İplikçi Nedim servisine taşır. Uygulama şifresi olmayan hesaplar,
örneğin Gelişmiş Koruma'daki Gmail, için yoldur ([ADR-0016](../docs/adr/0016-mail-connectors.md)).

## Durum

- **Eklentinin penceresi** (0.5.0): araç çubuğundaki düğme küçük bir pencere açar. Üstte logo, ad ve sürüm; altında
  durum, simgesi ve tek sözcüğüyle: eşleşmedi, çalışıyor (son denetimin saatiyle), dikkat (son denetimin söyledikleri),
  taranıyor ya da kapalı (İplikçi Nedim bu bilgisayarda çalışmıyor). Sonra "İplikçi Nedim'i aç", "Şimdi denetle" ve
  "Eşleştirme ve ayarlar" gelir.
  - Pencere odak dışına çıkınca kapanır. Bu yüzden eşleştirme, Gmail hesabının seçimi ve "Gmail'de eksikleri tara"
    ayarlar sayfasındadır; "Eşleştirme ve ayarlar" onu açar.
  - Ayarlar sayfası da durumu, "Şimdi denetle"yi ve "İplikçi Nedim'i aç"ı gösterir; doğrulama sayfasına oradan gidilir.
    Üç sayfa tek bir stil dosyasını paylaşır, açık ve koyu temayla.
- **İplikçi Nedim'in sözü** (0.6.0, [ADR-0020](../docs/adr/0020-bridge-sayings.md)): pencerenin başında, logonun
  altındaki balonda, Pano'daki söz durur; logo paranın durumuna göre renk alır (`icons/face-*.png`). "Başka bir söz"
  o gün doğru olan öbür sözleri gösterir.
  - Eklenti önce servisten kanıt, sonra `GET /api/bridge/sayings` ile sözleri ister; sözün cümlesi tutar, hesap ya da
    ad taşımaz.
  - Eşleşmemişse, servis çalışmıyorsa, yerinde başka bir program yanıt veriyorsa ya da servis bu uçtan eskiyse söz
    gösterilmez; durum kartı nedenini söyler.
- **"İplikçi Nedim'i aç"** ([ADR-0019](../docs/adr/0019-bridge-login-link.md)) arayüzü bu tarayıcıda açar:
  - Arayüzü gösteren bir sekme açıksa onu öne getirir. O sekme zaten öndeyse onu giriş bağlantısıyla yeniden açar:
    oturumu kapanmış ya da servis kapalıyken açılmış olabilir.
  - Eşleşmişse servisten önce kanıt, sonra tek kullanımlık bir giriş bağlantısı ister. Bağlantıyı yalnızca
    `http://127.0.0.1:8643/giris?` ile başlıyorsa, giriş sayfasını gösteren sekmede ya da yeni bir sekmede açar.
  - Eşleşmemişse ya da servis bağlantı vermezse adresi bağlantısız açar; tarayıcıda oturum olabilir. Servis
    çalışmıyorsa ya da yerinde başka bir program yanıt veriyorsa hiçbir şey açmaz ve pencere nedenini söyler.
- **Doğrulama sayfası** (ADR-0016, Aşama 3'ün ilk işi) dört şeyi denetler: gelen kutusu akışını, ham iletiyi ve DMARC'ı,
  tam taramayı ve platformu. Ayarlar sayfasından açılır.
- **Eşleştirme:** ayarlar sayfasına, İplikçi Nedim'in "Tarayıcı eklentisi" sayfasından alınan tek kullanımlık kod
  girilir. Eklenti her istekten önce servisten bir kanıt ister (HMAC). Kanıtlayamayan bir programa hiçbir ileti
  gönderilmez.
- **Yeni iletiler (1. ve 3. katman):** eklenti her dakika ve tarayıcı açılınca gelen kutusu akışına bakar. Listedeki
  bankalardan gelen ve servisin henüz almadığı okunmamış iletileri "Orijinali göster" yoluyla indirir ve servise ham
  hâliyle teslim eder.
  - Güven kuralını (DMARC) servis uygular. Teslimin nerede kaldığını da servis tutar.
  - Servisin hiç alamayacağı bir ileti (boş ya da 40 MB'tan büyük) atlanır ve yeniden indirilmez.
- **Gmail'de görünen iletiler** (0.7.0, ADR-0016'nın 2026-11-10 notu): Gmail bu tarayıcıda açıkken sekmesinde görünen
  banka iletileri, okunmuş olsun olmasın, kendiliğinden alınır. Akış yalnızca okunmamış iletileri gösterdiği için,
  bir sonraki denetimden önce okunan ileti önceden ancak taramayla gelirdi.
  - Gmail sekmelerinde çalışan içerik betiği (`src/content.ts`, sayfayı okuyan kısmı `src/gmail/visible.ts`) konuşma
    listesinin satırlarından konuşmanın ve son iletinin kimliğini, açılmış bir konuşmadan iletilerin kimliklerini
    okur. Göndericinin adresine yalnızca alan adı için bakar; konu, önizleme, metin ve ad okumaz.
  - Yalnızca listedeki bankaların iletilerinin kimliklerini, yalnızca eklentinin okuduğu hesabın sekmesinden ve
    yalnızca eklentiye bildirir. Sayfayı yalnızca sekme görünürken ve en çok beş saniyede bir okur.
  - Kimlikler bir sonraki teslim turunu bekler. Tur önce gelen kutusu akışını okur; sonra servisin tutmadıklarını
    "Orijinali göster" yoluyla, en eskiden başlayarak, saniyede bir indirir. Bunların tarihi yoktur; servisin konumu
    yerinde kalır.
  - Konuşmaların ortasındaki iletiler ve açık bir Gmail sekmesinde hiç görünmeyenler (bu bilgisayar kapalıyken
    telefonda okunup arşivlenenler gibi) taramaya kalır.
- **Sorunlar:**
  - Tanınmayan bir Gmail sayfası o katmanı durdurur ve servise bir kez bildirilir (biçim alarmı). Düzeltme eklentinin
    yeni sürümüyle gelir.
  - "Orijinali göster" bir iletinin metnini göstermezse, örneğin büyük bir iletide, o ileti atlanır. Eklentinin
    penceresi, iletiyi Gmail'den indirip İplikçi Nedim'e yüklemenizi söyler. Art arda üç ileti gösterilmezse sayfa
    değişmiş sayılır. Alarm sayfanın metnini değil yalnızca özelliklerini taşır.
  - Gmail yavaşlamayı isterse ya da başka bir sorun çıkarsa sonraki deneme her seferinde daha geç yapılır: önce bir
    dakika sonra, en geç bir saat sonra.
- **Geçmiş ve kaçan iletiler ("Gmail'de eksikleri tara"):** doğrulamada tam tarama (3. madde) tutmadı; Gmail'in konu
  listesi adresi oturum açma sayfasına yönlendiriyor. Bu yüzden ADR-0016'nın yedek yolu kullanılır. Açık sekmede
  görünenler kendiliğinden alındığı için düğme eski ya da arşivlenmiş iletiler içindir:
  - Ayarlar sayfasındaki düğme Gmail'i yeni bir sekmede açar ve listedeki bankaların başlangıç gününden beri gelen
    iletilerini arar.
  - Sekmede çalışan küçük bir betik sonuç listesinden yalnızca konuşma kimliklerini okur; konu, adres ya da metin
    okumaz. Sayfalar bitince sekme kapanır.
  - Servis hangi iletilerin eksik olduğunu söyler. Eksikler "Orijinali göster" yoluyla indirilip teslim edilir.
  - Hiçbir konuşma açılmaz, çünkü açmak iletileri okundu yapar. Liste bir konuşmanın yalnızca ilk ve son iletisini
    gösterir.
  - Baştan sona okunmuş bir konuşmanın ortasındaki ekli iletiler, konuşmanın yazdırma görünümünden alınır: o sayfadan
    yalnızca ekli iletilerin kimlikleri ve göndericilerin alan adları okunur. Okunmamış konuşmaların yazdırma görünümü
    istenmez. Eki olmayan ya da okunmamış konuşmalarda kalan iletilerin sayısı raporda yazar.
  - Tarama eşleşince kendiliğinden başlar. Biten bir tarama neyi aradığını servise bildirir: başlangıç gününü ve banka
    listesini. İkisinden biri değişince eklentinin penceresi ve ayarlar sayfası yeniden taramayı ister; "Şimdi
    denetle" önce onu yapar.
    Kendiliğinden başka tarama yoktur, çünkü sekmesi o an yapılan işin önüne çıkardı.

## İlkeler

- İzinler yalnızca `alarms`, `scripting` (taramada Gmail sekmesindeki listeyi okumak ve eklenti kurulunca ya da
  güncellenince açık Gmail sekmelerine içerik betiğini koymak için) ve `storage`, artı üç
  adres: `https://mail.google.com/*`, Gmail'in ek sunucusu `https://mail-attachment.googleusercontent.com/*` ve
  `http://127.0.0.1:8643/*`. Gmail sekmelerindeki içerik betiği ilk adresin izniyle çalışır; yeni bir izin istemez.
- İçerik betiği istek yapmaz ve tarayıcının deposunu okumaz; depo yalnızca eklentinin kendi sayfalarına ve servis
  çalışanına açıktır. Servis çalışanı bir Gmail sekmesinden yalnızca iki şey kabul eder: neye bakılacağını sormak ve
  ondalık ileti kimlikleri bildirmek.
- `tabs` izni yoktur. "İplikçi Nedim'i aç" açık sekmelerden yalnızca `http://127.0.0.1:8643/` adresindekilerin adresini
  ve başlığını görür; bunu adres izni sağlar. Eklenti oturum çerezini okumaz ve servise çerez göndermez.
- "Orijinali göster" eklerin içeriğini boş verir. Bu yüzden bir dosya adı geçen ileti "Orijinali indir" ile, bayt bayt
  ve tam alınır; Gmail bu indirmeyi ek sunucusuna yönlendirir.
- Gmail'e yalnızca okuma istekleri gider: okundu işareti, etiket, taşıma ya da silme yoktur.
- İstekler sıralıdır ve aralarında en az bir saniye vardır.
- Uzaktan yüklenen kod, dış yazı tipi ya da dış betik yoktur.
- Gmail'e dokunan kod yalnızca `src/gmail/` altındadır. Kayıtlı sahte yanıtlarla ve sahte bir Gmail listesiyle test
  edilir; testlerde gerçek adres, konu ya da ileti yoktur.
- Doğrulama raporu e-posta adresi, konu ya da ileti içeriği taşımaz.

## Geliştirme

```bash
npm ci              # sabitlenmiş bağımlılıklar (package-lock.json)
npm run typecheck   # TypeScript, katı denetim
npm test            # vitest
npm run build       # dist/: tarayıcıya yüklenecek klasör; programın taşıdığı kopya da (src/iplikci/browser_extension)
npm run package     # dist/ ve mağazaya yüklenecek iplikci-kopru.zip (macOS ve Linux)
```

Geliştirme sırasında `dist/` klasörü tarayıcıda "Paketlenmemiş öğe yükle" ile yüklenir. `dist/` yeniden derlenince
tarayıcının eklentiler sayfasında eklentiyi yeniden yükleyin; bunu bir tarama sürerken yapmayın. Açık Gmail
sekmelerindeki eski içerik betiği o zaman kendiliğinden durur ve eklenti yeni sürümünkini o sekmelere hemen koyar.

Eklenti mağazada yayımlanana dek kullanıcılar da onu paketlenmemiş yükler; yayımlamayı kullanıcı yapacak
([K29](../docs/v1/requirements.md#kararlar)). Kurulum paketi derlenmiş eklentiyi taşır (`src/iplikci/browser_extension`,
`npm run build` yazar). Tarayıcı eklentisi ekranındaki "Eklenti klasörünü aç" servisten onu veri klasörünün
`extension/` klasörüne kopyalamasını ve klasörü dosya yöneticisinde göstermesini ister; ekran tarayıcıya yüklemeyi adım
adım anlatır. Program güncellenince servis bir sonraki açılışında klasörü yeniler.

**Kendini yenileme** (0.8.0, [ADR-0022](../docs/adr/0022-releases-and-updates.md)): servisin imleci
(`/api/ingest/mail/cursor`, `extension_version`) programın taşıdığı eklentinin sürümünü söyler. Paketlenmemiş yüklenen
eklenti (`chrome.management.getSelf`: `development`) bundan eskiyse, bir teslim çalışmasının ardından ve tarama yokken
kendini yeniden yükler (`chrome.runtime.reload`, `bridge/renew.ts`). Bir sürüm için bir kez: başka bir klasörden
yüklenmiş, değişmeyen bir eklenti tekrar tekrar yüklenmez. Mağazadan kurulan eklentiyi mağaza günceller.

Mağaza paketi `npm run package` ile yapılır (`iplikci-kopru-<sürüm>.zip`); sürüm iş akışı onu GitHub sürümüne koyar ve
mağaza ayarları varsa mağazaya yükler. Mağaza metni, gizlilik politikası ve yayın adımları [store/](store/README.md)
klasöründedir.
