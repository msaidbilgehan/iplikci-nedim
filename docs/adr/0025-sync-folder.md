# ADR-0025: Veriler, Google Drive'ın (ya da başka bir eşitleme uygulamasının) klasörü üzerinden bilgisayarlar arasında eşitlenir; klasör verilerin bilgisayar dışındaki kopyasıdır

Durum: Kabul edildi · Tarih: 2026-11-24 · Dayanak: K33, K14, K3, K17 · [Mimari](../v1/architecture.md) §3'ün "bulut
eşitleme kapsam dışı" maddesini değiştirir; [ADR-0004](0004-sqlite-primary-store.md)'ün tek veritabanını ve
[ADR-0010](0010-notification-channels.md)'un kanallarını birden çok bilgisayar için genişletir

## Bağlam

- Kullanıcı 2026-11-24'te verilerin Google Drive ile eşitlenmesini istedi
  ([K33](../v1/requirements.md#kararlar)): veriler kaybolmasın, yedek ücretsiz ve kolay olsun. Program birden çok
  bilgisayarda kurulu olabilmeli ve her birinde güncel akış sorunsuz çalışmalı.
- Bugünkü yedekler (F20) veri klasörünün içindedir. Disk bozulursa ya da bilgisayar kaybolursa yedekler de gider. Asıl
  belgelerin çoğu Gmail'de durur, ama kullanıcının notları, kuralları, hesap adları, Claude'un notları ve elle
  eklenen belgeler yalnızca bu bilgisayardadır.
- Veritabanı SQLite'tır (WAL). Eşitleme uygulamaları dosyayı bütün olarak taşır: yazılmakta olan bir veritabanını,
  `-wal` ve `-shm` dosyalarıyla birlikte tutarlı taşıyamazlar. İki bilgisayar aynı dosyaya yazınca biri ötekinin
  yazdığını ezer ya da uygulama "çakışma kopyası" bırakır. Veritabanı eşitleme klasörüne konamaz.
- Kullanıcının Google hesabı Gelişmiş Koruma'dadır (ADR-0016). Gelişmiş Koruma, yalnızca Google'ın doğruladığı üçüncü
  taraf uygulamaların Gmail ve Drive verilerine erişmesine izin verir. Drive API'sine bağlanan bir OAuth uygulamasının
  önce Google'ın doğrulamasından geçmesi gerekirdi. Ayrıca bu, ADR-0009'a yeni bir dış bağlantı ekleyen bir ADR
  isterdi (`www.googleapis.com`, `oauth2.googleapis.com`).
- Kullanıcının Mac'inde Google Drive masaüstü uygulaması kurulu. Uygulama Drive'ı bilgisayarda bir klasör olarak
  gösterir ve o klasöre yazılanı kendisi yükler.

## Seçenekler

| Seçenek | Özü | Neden seçilmedi / seçildi |
|---|---|---|
| A — Veri klasörünü Drive'a koymak | `~/Library/Application Support/iplikci` yerine Drive'daki bir klasör | SQLite eşitleme klasöründe bozulur; iki bilgisayar aynı dosyalara yazar; tek kopya kilidi yalnızca bir bilgisayarda geçerlidir. |
| B — Yedekleri Drive'a koymak | `[backup] folder` Drive'daki bir klasörü gösterir | Kayıp önlenir, ama ikinci bilgisayar yalnızca yedeği geri yükleyebilir: iki bilgisayar aynı anda çalışamaz. Her gün 12 MB'lık bir veritabanı kopyası yüklenir. Bu yol ayrıca hep açıktır. |
| C — Drive API'si | Program OAuth ile Drive'a kendisi yükler | Yeni dış bağlantı ve OAuth istemcisi gerekir; Gelişmiş Koruma doğrulanmamış uygulamanın Drive'a erişmesine izin vermez; Google'ın doğrulaması kişisel bir hobi projesi için ağırdır; Linux'ta da Windows'ta da aynı kod gerekir. |
| **D — Eşitleme klasörü** | Program Drive'ın klasörüne yazar ve oradan okur; taşımayı Drive uygulaması yapar. Her bilgisayar yalnızca kendi alt klasörüne yazar, ötekilerin yazdığını parça parça birleştirir | **Seçildi:** yeni dış bağlantı yok, OAuth yok, Gelişmiş Koruma'ya takılmaz. iCloud Drive, Dropbox, OneDrive ve Syncthing'le de aynı biçimde çalışır. Veritabanı klasöre girmez. |

## Karar

### Klasör

- Kullanıcı Ayarlar'daki "Eşitleme ve yedek" kartında Google Drive'ın klasörünü seçer (program onu bulur:
  `~/Library/CloudStorage/GoogleDrive-<hesap>/My Drive`, Windows'ta `G:\My Drive`). İçinde `İplikçi Nedim` klasörü
  açılır. Başka bir eşitleme uygulamasının klasörü ya da herhangi bir klasörün tam yolu da olur. Eşitleme isteğe
  bağlıdır ve kapalı gelir. Kapalıyken program bugünkü gibi çalışır.
- Klasörün düzeni:

  ```text
  İplikçi Nedim/
    iplikci-esitleme.json      # veri kümesinin kimliği; klasörü açan ilk bilgisayar bir kez yazar
    BENİOKU.txt                # klasörü açan kişi için ne olduğu ve yeni bilgisayarda nasıl geri getirileceği
    cihaz-<kimlik>/            # her bilgisayarın kendi alt klasörü; yalnızca o bilgisayar yazar
      cihaz.json               # adı, sürümü, son görülmesi, gönderebildiği kanallar, eşitlemeyi kapatıp kapatmadığı
      durum.json               # bildiği bütün paylaşılan parçalar, damgalarıyla
      belgeler/ab/<sha256>     # getirdiği ve klasörde başka hiçbir bilgisayarda olmayan asıl belgeler
  ```

- Her dosyanın tek bir yazanı vardır, bu yüzden Drive iki bilgisayarın aynı dosyayı değiştirdiğini hiç görmez. Dosya
  önce yanına kendi adıyla yazılır, sonra yerine taşınır. Okuyan bilgisayar ya eski dosyayı ya yenisini görür. Drive'ın
  yarım getirdiği bir dosyayı okuyan reddeder ve bir sonraki turda yeniden okur. Asıllar içerikleriyle adlandırılır ve
  değişmez. Kullanılmadan önce her kopyanın içeriği adıyla karşılaştırılır.
- Program klasörü kendiliğinden yeniden açmaz: işaret dosyası bulunamazsa (Drive çalışmıyor, klasör silindi, taşındı)
  tur yapılmaz ve sorun Ayarlar'da yazar. Boş olmayan ve işareti olmayan bir klasör reddedilir: program kullanıcının
  kendi dosyalarının arasına yazmaz.

### Ne paylaşılır, ne her bilgisayarın kendisinindir

| Paylaşılır | Her bilgisayarın kendisinindir |
|---|---|
| Belgeler: asılları, adları, gelişleri, kaldırılmaları | Okuyucuların okudukları (belgelerden yeniden okunur), analiz, ay kapanışları |
| Kullanıcının düzeltmeleri ve notları (parmak izine bağlı) | Olay kaydı, akış ve bildirimler (her bilgisayar kendi analizinden üretir) |
| Hesap adları | Denetim kaydı (öteki bilgisayardan gelen değişiklik "Eşitleme" diye yazılır) |
| Claude'un notları | E-posta hesabı ve şifresi, tarayıcı eklentisinin eşleşmesi, Telegram belirteci |
| `rules/personal.yaml` ve `rules/alerts.yaml` | `rules/history/` (her bilgisayar kendi eski sürümlerini tutar) |
| Ayarlardan: adlar ve şirket adları, banka ve diğer göndericiler, göndericinin denetlenmesi, sessiz saat ve ayrıntı düzeyleri, kur sağlayıcıları, MCP maskeleme | Ayarlardan: port, uzaktan erişim, e-posta bağlantısı, açık kanallar, Telegram sohbeti, yedekler, güncelleme biçimi, eşitleme klasörü ve bilgisayarın adı |
| Telegram'ı ve e-postayı hangi bilgisayarın gönderdiği | Döviz kurları ve TÜFE (her bilgisayar kendisi çeker), doğrulama tabanı, yedekler |

Şirket belgeleri arşive hiç girmediği için klasöre de gitmez. Okuma sırasında şirket belgesi çıkan bir belge
kaldırılır. Kaldırılması öteki bilgisayarlara yayılır, aslı da klasörden çıkar (çöp kutusuna).

### Birleştirme

- Paylaşılan her parçanın bir türü ve anahtarı vardır: notun parmak izi, belgenin sha256'sı, ayarın bölümü ve adı. Her
  parça son değişikliğinin damgasını ve o değişikliğin verdiği değeri taşır. Değer yoksa parça kaldırılmıştır.
- Damga karma mantıksal saattir (`sync/clock`): duvar saatinin milisaniyesi, aynı milisaniyedeki sayaç ve bilgisayarın
  kimliği. Saat kendi verdiği ya da gördüğü damgaların hiçbirinden geri bir damga vermez. Böylece öteki bilgisayarın
  değişikliği birleştikten sonra yapılan değişiklik, iki bilgisayarın saati ne derse desin, ondan sonra gelir. Aynı
  milisaniyede iki bilgisayarda yapılan değişikliklerde bilgisayarın kimliği karar verir.
- İki sürümden damgası sonra olan kazanır. Bir belgenin kaldırılması, belgeyi tutan her sürümü yener: kaldırma geri
  alınmaz (ADR-0003). Birleştirmenin sonucu sürümlerin geliş sırasına ve kaç kez geldiklerine bağlı değildir. Aynı
  sürümleri görmüş her bilgisayar aynı parçaları tutar (`tests/test_sync.py`'deki özellik testleri).
- Bir bilgisayarın durum dosyası kendi parçalarını ve birleştirdiklerini, yani bildiği her şeyi taşır. Tek bir dosya
  bütün veri kümesini taşır. Alt klasörü kaybolan bilgisayar kayıp değildir.
- Bir tur kendi bilgisayarındaki değerleri son karşılaştırıldıkları hâlleriyle karşılaştırır (`sync_entries.local`).
  Değişenleri şimdi damgalar. Sonra ötekilerin parçalarını birleştirir, kazananları yerine koyar. Her kazanan yalnızca
  o bilgisayarın kendi değeri o arada değişmediyse konur. Değişmişse bir sonraki tur o değişikliği damgalar ve o
  kazanır.
- Yerine konan değer geri okunur. Bir sonraki tur geri okunanın özetiyle karşılaştırır. Böylece bu sürümün tam
  tutamadığı bir değer (daha yeni bir sürümün alanı) kendi değişikliği sanılmaz. Bir değeri biraz farklı yazan iki
  bilgisayar da birbirinin değişikliğini sonsuza dek yanıtlamaz.

### Belgeler

- Bir bilgisayar, ötekilerin tuttuğu ve kendisinde olmayan belgelerin asıllarını klasörden arşivine alır. Her biri
  adıyla karşılaştırılır; bozuk bir kopya alınmaz, yayılmaz. Belge okunmamış olarak gelir ve sıradaki analiz onu
  okur. Akış "Yeni bir belge geldi" der: belge ilk geldiği bilgisayardaki geliş yoluyla, tek tek. Bir turda 50'den çok
  belge gelirse hepsi tek bir olayda sayılır.
- Bir bilgisayar kendi asıllarından klasörde hiçbir bilgisayarda olmayanları kendi alt klasörüne koyar. Kaldırılan
  bir belgenin kendi kopyasını alt klasöründen çıkarır (çöp kutusuna; Drive kendi çöp kutusunda bir süre daha tutar).
  Kimse başka bir bilgisayarın alt klasörüne yazmaz.
- Bir turda en çok 300 belge ya da 200 MB taşınır. İş kaldıysa bir sonraki tur iki saniye sonra gelir. Bütün bir
  arşivin ilk kopyası böylece başka bir işi bekletmeden sürer. Kullanıcı bir alt klasörü silerse, aslını tutan
  bilgisayarlar onu yarım saat içinde kendi alt klasörlerine yeniden koyar.

### Katılmak, geri yüklemek, başka bilgisayara taşınmak

- Eşitleme ilk kez açılırken klasörde veri kümesi yoksa bu bilgisayar onu başlatır. Verisi gerçek damgalarla gider.
- Klasörde veri kümesi varsa bilgisayar ona katılır. Kendi eski verisi bütün damgalardan önceki bir damgayla gider.
  İki bilgisayarda da olan bir parçada klasördeki geçerli olur; yalnızca bu bilgisayarda olan kalır ve ötekilere
  gider. Kuralları değişen bilgisayarın eski kuralları `rules/history/`'de kalır.
- Yedekten geri yüklenen veritabanı eşitlemenin kayıtlarını da geri getirir. Bilgisayar kendi yazdığı durum
  dosyasıyla ötekilerinkini birleştirir ve kaldığı yerden yetişir. Geri yükleme öteki bilgisayarların sonraki
  değişikliklerini geri almaz.
- Veri klasörü başka bir bilgisayara kopyalanınca (Taşıma Yardımcısı, yeni disk) kopya yeni bir kimlik alır. İki
  bilgisayar asla aynı alt klasöre yazmaz. Makinenin kimliği sistemin kendi kimliğinin özetiyle tanınır (macOS'ta
  IOPlatformUUID, Linux'ta machine-id, Windows'ta MachineGuid); kimliğin kendisi saklanmaz.

### Bildirimler ve Telegram

- Telegram'ın ve e-postanın bildirimleri tek bilgisayardan gider. O kanalı gönderebilen ve kanalı tutan bilgisayar
  gönderir. Paylaşılan bir parça (`sender`) kanalı hangi bilgisayarın tuttuğunu söyler. Botun iletilerini yalnızca o
  bilgisayar okur: iki bilgisayar botu birlikte okusaydı Telegram okumaları birbirine kestirirdi.
- Kanalı kimse tutmuyorsa onu gönderebilen ilk bilgisayar alır. Tutan bilgisayar yarım saat görünmezse, kanalı artık
  gönderemiyorsa ya da eşitlemeyi kapattıysa, gönderebilen başka bir bilgisayar devralır. Kullanıcı Ayarlar'dan
  "Bu bilgisayar göndersin" diyerek de alır.
- Kanalı tutmayan bilgisayarda o kanal için bekleyen bildirimler bırakılır ("başka bir bilgisayar gönderiyor"). Bir
  bildirim iki kez ya da günler sonra gitmez.
- Uygulama içi kutu ve masaüstü bildirimleri her bilgisayarın kendisinindir. Her bilgisayar akışını kendi analizinden
  üretir ve kendi ekranında gösterir.

### Turlar

- Servis dakikada bir tur yapar (`sync/watcher`, `app/sync.run_round`). Her analizden sonra ve kullanıcı istediğinde
  hemen bir tur daha yapar. Ötekilerin değişikliği gelince analizi yeniden yapar; akış ve bildirimler oradan sürer.
- Tur ötekilerin durum dosyalarından yalnızca değişenleri okur. Kendi durum dosyasını bir parça değişince, kendi
  `cihaz.json`'unu beş dakikada bir yazar.
- Tur altı saat boyunca işini yapamazsa `sync.failed` olayı günde bir kez yazılır, Pano'da da uyarı çıkar. Örnek
  nedenler: klasör yok, daha yeni bir sürümün dosyası, yazma hatası.

### Sürümler

- Durum dosyası biçimini ve sürümünü taşır. Daha yeni bir sürümün yazdığı dosya okunmaz: o bilgisayar "bu bilgisayarı
  güncelleyin" der ve güncelleme (ADR-0022) üç saat içinde gelir. Bu sürümün bilmediği türdeki parçalar olduğu gibi
  saklanır ve yayılır. Bu sürümün kabul etmediği bir ayar ya da kural dosyası beklemede kalır.

## Sonuçlar

- Veriler bilgisayarın dışında da durur: yeni bir bilgisayarda İplikçi Nedim kurulup aynı klasör seçilince belgeler,
  kararlar ve ayarlar gelir, belgeler yeniden okunur ve defter aynı çıkar. Taşınmayan şeyler bu bilgisayarın akış
  geçmişi, bildirim kutusu ve denetim kaydıdır.
- Gizlilik: belgeler ve kararlar kullanıcının kendi Google Drive'ına gider ve Google'ın sunucularında durur. Banka
  belgelerinin çoğu zaten aynı hesabın Gmail'indedir. Klasörün güvenliği Google hesabının güvenliğidir (Gelişmiş
  Koruma). Uygulama düzeyinde şifreleme yoktur: anahtarı kaybeden kullanıcı yedeğini de kaybederdi. İstenirse
  biçimin sürümüyle sonra eklenebilir.
- Ağ: program yeni bir yere bağlanmaz (ADR-0009 değişmez). Yüklemeyi ve indirmeyi Drive uygulaması yapar.
- Google Drive'ın masaüstü uygulaması kullanıcıdan istenen ek bir uygulamadır (K15'in sözü e-posta köprüsü içindi).
  Eşitleme isteğe bağlıdır; Drive uygulaması yoksa iCloud Drive, Dropbox ya da OneDrive aynı biçimde çalışır.
- Yer: ilk kopya arşivin boyu kadardır (bugün yaklaşık 155 MB). Durum dosyası bin belgede yaklaşık 1 MB'tır. Google
  Drive'ın ücretsiz 15 GB'ı yıllarca yeter.

## Sınırlar

- Aynı parça iki bilgisayarda bir dakika içinde değişirse sonra damgalanan kazanır. Öteki bilgisayardaki değişiklik
  kaybolur; kural dosyalarında o bilgisayarın geçmişinde kalır.
- Telegram'ı tutan bilgisayarın Drive'ı uzun süre eşitleyemezse öteki bilgisayar kanalı devralır. Aradaki sürede bir
  bildirim iki kez gidebilir.
- Belgenin metni OCR ile okunuyorsa, onu yalnızca macOS'taki bir bilgisayar okuyabilir (mimari §2).
- İki bilgisayar boş bir klasörde aynı anda başlarsa iki ayrı veri kümesi olabilir. Drive uygulaması yeni kurulan
  bilgisayarda klasörü henüz indirmeden eşitleme açılırsa da bu olur. Ayarlar, klasörde öteki bilgisayarın adı
  görünmeden katılmamayı söyler.
- Kurlar paylaşılmaz: kurları çekemeyen bir bilgisayarın döviz satırları birkaç kuruş farklı olabilir. Bu fark
  bilgisayar kurları çekince kapanır.
