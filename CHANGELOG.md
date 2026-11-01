# Değişiklik günlüğü

Biçim [Keep a Changelog](https://keepachangelog.com/tr-TR/1.1.0/)'a, sürüm numaraları
[anlamsal sürümlemeye](https://semver.org/lang/tr/) dayanır. Her aşama bir sürümle biter
([yol haritası](docs/v1/roadmap.md)).

## [Yayımlanmamış] — Aşama 4: E-postanın tamamı

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
- Kart ekstrelerinde son ödeme tarihi, asgari ödeme ve kartın toplam limiti okunur (göç 0013):
  - İş Bankası Maximum üçünü de okur;
  - Garanti BBVA Bonus son ödeme tarihini ve kart limitini okur;
  - TEB Bonus ile QNB yalnızca son ödeme tarihini okur.
  Ekstrenin yazmadığı, bozuk yazdığı ya da iki yerde farklı yazdığı bilgi boş kalır; ekstre yine okunur.
  `iplikci dev parser debug` bu bilgileri de gösterir.

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
