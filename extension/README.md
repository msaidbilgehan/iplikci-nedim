# İplikçi Nedim Köprüsü

Chromium tabanlı tarayıcılar (Chrome, Edge, Brave) için Manifest V3 eklentisi. Gmail'deki banka iletilerini, tarayıcının
açık Gmail oturumuyla okuyup bu bilgisayardaki İplikçi Nedim servisine taşır. Uygulama şifresi olmayan hesaplar,
örneğin Gelişmiş Koruma'daki Gmail, için yoldur ([ADR-0016](../docs/adr/0016-mail-connectors.md)).

## Durum

- **Doğrulama sayfası** (ADR-0016, Aşama 3'ün ilk işi) dört şeyi denetler: gelen kutusu akışını, ham iletiyi ve DMARC'ı,
  tam taramayı ve platformu. Eklentinin penceresinden açılır.
- **Eşleştirme:** eklentinin penceresine, İplikçi Nedim'in "Tarayıcı eklentisi" sayfasından alınan tek kullanımlık kod
  girilir. Eklenti her istekten önce servisten bir kanıt ister (HMAC). Kanıtlayamayan bir programa hiçbir ileti
  gönderilmez.
- **Yeni iletiler (1. ve 3. katman):** eklenti her dakika ve tarayıcı açılınca gelen kutusu akışına bakar. Listedeki
  bankalardan gelen ve servisin henüz almadığı okunmamış iletileri "Orijinali göster" yoluyla indirir ve servise ham
  hâliyle teslim eder.
  - Güven kuralını (DMARC) servis uygular. Teslimin nerede kaldığını da servis tutar.
  - Servisin hiç alamayacağı bir ileti (boş ya da 40 MB'tan büyük) atlanır ve yeniden indirilmez.
- **Sorunlar:**
  - Tanınmayan bir Gmail sayfası o katmanı durdurur ve servise bir kez bildirilir (biçim alarmı). Düzeltme eklentinin
    yeni sürümüyle gelir.
  - Gmail yavaşlamayı isterse ya da başka bir sorun çıkarsa sonraki deneme her seferinde daha geç yapılır: önce bir
    dakika sonra, en geç bir saat sonra.
- **Geçmiş ve kaçan iletiler ("Gmail'de eksikleri tara"):** doğrulamada tam tarama (3. madde) tutmadı; Gmail'in konu
  listesi adresi oturum açma sayfasına yönlendiriyor. Bu yüzden ADR-0016'nın yedek yolu kullanılır:
  - Eklentinin penceresindeki düğme Gmail'i yeni bir sekmede açar ve listedeki bankaların başlangıç gününden beri
    gelen iletilerini arar.
  - Sekmede çalışan küçük bir betik sonuç listesinden yalnızca konuşma kimliklerini okur; konu, adres ya da metin
    okumaz. Sayfalar bitince sekme kapanır.
  - Servis hangi iletilerin eksik olduğunu söyler. Eksikler "Orijinali göster" yoluyla indirilip teslim edilir.
  - Hiçbir konuşma açılmaz, çünkü açmak iletileri okundu yapar. Bu yüzden bir konuşmanın yalnızca ilk ve son iletisi
    alınır; aradakilerin sayısı raporda yazar.
  - Tarama eşleşince kendiliğinden başlar. Biten bir tarama neyi aradığını servise bildirir: başlangıç gününü ve banka
    listesini. İkisinden biri değişince pencere yeniden taramayı ister ve "Şimdi denetle" önce onu yapar.
    Kendiliğinden başka tarama yoktur, çünkü sekmesi o an yapılan işin önüne çıkardı.

## İlkeler

- İzinler yalnızca `alarms`, `scripting` (taramada Gmail sekmesindeki listeyi okumak için) ve `storage`, artı iki
  adres: `https://mail.google.com/*` ve `http://127.0.0.1:8643/*`.
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
npm run build       # dist/: tarayıcıya yüklenecek klasör
```

Geliştirme sırasında `dist/` klasörü tarayıcıda "Paketlenmemiş öğe yükle" ile yüklenir. Kullanıcılar eklentiyi Chrome
Web Store'dan kuracak; bu yol yalnızca geliştirme ve doğrulama içindir.
