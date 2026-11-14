# ADR-0024: Programı bulamayan eklenti, son kurulum paketinin indirilmesine yeni bir sekmede yol gösterir

Durum: Kabul edildi · Tarih: 2026-11-14 · Dayanak: K31, K32, K29, K14, K22 · [ADR-0016](0016-mail-connectors.md)'nın
listelenmemiş yayın kararını değiştirir; eklentinin davranışını ADR-0016'nın ve
[ADR-0009](0009-network-egress-policy.md)'un eklenti satırının dışına bir sekmeyle genişletir

## Bağlam

- Kullanıcı 2026-11-14'te eklentinin Chrome Web Store'a şimdi gönderilmesine karar verdi
  ([K31](../v1/requirements.md#kararlar)). Eklenti, programı olmayan kullanıcıyı sürümlerin durduğu herkese açık
  depodaki son kurulum paketine götürmeli ve kurulumu anlatmalı: ertesi gün bu, kod deposunun kendisi oldu
  (`msaidbilgehan/iplikci-nedim`, [K32](../v1/requirements.md#kararlar)). Ayrı bir web sayfası şimdilik yoktur.
  Aynı gün iki karar daha geldi: eklenti mağazada herkese açık listelenir; mağazaya ilk giden sürüm 0.9.0'dır, 0.8.0
  yüklenmez.
- Mağazadan kurulan eklenti, bilgisayarda program yoksa hiçbir şey yapamaz. Eşleşmemiştir ve 127.0.0.1:8643'te yanıt
  veren yoktur. 0.8.0'ın sayfaları yalnızca "Eşleşmedi" der ve kodu İplikçi Nedim'den almayı söylerdi: programı hiç
  görmemiş biri ne yapacağını bilemezdi.
- Eklentinin adresleri `mail.google.com`, Gmail'in ek sunucusu ve 127.0.0.1'dir (ADR-0016). GitHub yoktur. Yeni bir dış
  bağlantı ancak bir ADR ile eklenir (ADR-0009).
- Sürümler paketleri sürüm numarası taşıyan adlarla tutuyordu (`iplikci-nedim-0.11.1-macos-aarch64.dmg`). Bu yüzden son
  sürümün paketinin değişmeyen bir adresi yoktu.

## Karar

### Eklenti programı bulamayınca

- Eklenti eşleşmemişse sayfaları (araç çubuğundaki düğmenin penceresi ve ayarlar sayfası) servis çalışanına
  programın orada olup olmadığını sorar. Servis çalışanı servisin sağlık denetimine bakar: `GET
  http://127.0.0.1:8643/healthz`. Uç belirteç istemez ([ADR-0007](0007-api-and-auth.md)); istek belirteç ve çerez
  taşımaz, en çok iki saniye bekler. Gelen her yanıt "orada" sayılır. Karşıdakinin eşleşilen servis olduğunu eşleşmeden
  sonraki kanıt gösterir (ADR-0016).
- Yanıt yoksa sayfalar sade bir Türkçeyle şunu söyler: eklenti bilgisayardaki İplikçi Nedim programıyla çalışır ve bu
  bilgisayarda programa ulaşılamadı. Program kuruluysa açmak yeter, kurulu değilse indirilip kurulur. Durum kartının
  sözcüğü "Program gerekli", simgesi aşağı ok olur. Altında "İplikçi Nedim'i indir" düğmesi ve kurulum adımları durur.
  "İplikçi Nedim'i aç" ve "Şimdi denetle" o sırada gizlidir: açılacak bir şey yoktur.
- Sistem `chrome.runtime.getPlatformInfo()`'dan okunur. Her sürüm şu sistemlerin paketini taşır:
  - macOS, Apple Silicon (`mac`, `arm64`): `iplikci-nedim-macos-aarch64.dmg`;
  - Windows, Intel ya da AMD işlemci (`win`, `x86-64`): `iplikci-nedim-windows-x86_64.exe`;
  - Linux, Intel ya da AMD işlemci (`linux`, `x86-64`): `iplikci-nedim-linux-x86_64.AppImage`.

  Paketi olmayan bir sistem sürüm sayfasını (`…/releases/latest`) ve bunu söyleyen bir cümleyi alır: ChromeOS, Intel
  işlemcili Mac, ARM işlemcili Windows ya da Linux gibi. Cümle hangi sistemlerin paketi olduğunu da yazar.
- Adımlar bilgisayardan anlamayan biri için yazılır. Uyarıların sözcükleri sistemlerin kendi Türkçe sözcükleridir:
  - **macOS:** indirilen `.dmg` açılır; pencerede uygulama yanındaki "Applications" klasörünün üzerine sürüklenir
    (bağlantının adı pencerede İngilizce görünür); Uygulamalar klasöründen açılır. Uygulama Apple'a onaylatılmadığı
    için (K22) macOS ilk açılışta "“İplikçi Nedim” Açılmadı" der. Kullanıcı "Bitti"ye basar. Sonra Sistem Ayarları →
    Gizlilik ve Güvenlik'te "Yine de Aç"a basar ve parolasını girer; macOS bir kez daha sorarsa yine "Yine de Aç"ı
    seçer. Sözcükler 2026-11-14'te macOS 27.2.1'in Türkçe metinlerinden doğrulandı. Pencerenin başlığı ve "Bitti"
    `CoreServicesUIAgent`'tan; bölmenin adı, "“%@”, Mac’inizi korumak için engellendi." ve "Yine de Aç" Gizlilik ve
    Güvenlik bölmesinden alındı.
  - **Windows:** kurulum programı açılır. SmartScreen uygulamayı tanımadığını söylerse "Ek bilgi", sonra "Yine de
    çalıştır" seçilir (ADR-0017'nin sözcükleri; Windows denemesinde doğrulanacak). Kurulum yönetici izni istemez,
    bitince uygulamayı açar.
  - **Linux:** AppImage'ın dosya özelliklerinden program olarak çalıştırılmasına izin verilir, sonra dosyaya çift
    tıklanır. İlk açılışta uygulama kendini menüye ekler.
  - Ayarlar sayfası bir cümle daha ekler: Chrome dosyanın "yaygın indirilen bir öğe değil" olduğunu söyleyip
    indirmeyi durdurursa, indirmeler simgesinden dosya yine de indirilir. Bu sözcükler 2026-11-14'te Chrome 157'nin
    Türkçe metinlerinden alındı. Her sürüm yeni bir dosyadır ve ilk günlerde az indirilmiş görünür.
- **İlk kurulumda** (`chrome.runtime.onInstalled`, neden `install`) ayarlar sayfası kendiliğinden açılır. Programı
  olmayan kullanıcı rehberi orada görür; programı olan doğrudan eşleştirmeye geçer.
- **Bekleme:** açık bir sayfa, program eksik kaldıkça üç saniyede bir yeniden sorar. Arkada kalan sekmeyi tarayıcı
  seyrek çalıştırır; sekme yeniden görününce sayfa hemen sorar. Program yanıt verince rehber kaybolur ve eşleştirme
  bugünkü gibi sürer. Ayarlar sayfası programın açıldığını söyler, kodun nereden alınacağını anlatır ve odağı kod
  alanına taşır.

### İndirme tarayıcının sekmesinde

- Düğme indirme adresini yeni bir sekmede açar (`chrome.tabs.create`):
  `https://github.com/msaidbilgehan/iplikci-nedim/releases/latest/download/<kararlı ad>`. GitHub adresi son
  sürümün dosyasına yönlendirir, dosyayı tarayıcı indirir. Tarayıcının kendi denetimleri (Güvenli Tarama) her
  indirmede olduğu gibi çalışır.
- Eklenti GitHub'a istek yapmaz, oraya veri göndermez ve yeni bir izin istemez. Sekme açmak izin istemez. Gidecek
  adres programın taşıdığı bir sabittir; kullanıcıdan ya da bir yanıttan gelmez.
- Ayarlar sayfasında sürüm sayfasına giden bir bağlantı da vardır: bütün sistemlerin paketleri ve yenilikler orada.

### Kurulum paketlerinin kararlı adları

- Sürüm işi (`packaging/release.py`) her kurulum paketini yayımlamadan önce sürüm numarası olmayan bir adla yeniden
  adlandırır: `iplikci-nedim-<sistem>-<mimari>.<dmg|AppImage|exe>`. Böylece `releases/latest/download/<ad>` her zaman
  son sürümün paketidir.
- Bildirge kurulum paketlerini bu adlarla yazar. Windows'ta kurulum programı güncelleme dosyası da olduğundan
  güncelleme girişi de onu bu adla yazar. macOS'un `.zip`'i ve Linux'un `.tar.gz`'si sürümlü adlarını korur. Kurulu
  kopyalar bildirgenin yazdığı dosyayı sürümün kendi etiketinin adresinden indirir (`releases/download/<etiket>/<ad>`).
  Bu yüzden adlar onlar için bir şey değiştirmez.
- Eklentinin sunduğu her sistemin paketi sürümde bulunmalıdır, yoksa sürüm yapılmaz. Bu sistemler
  `release.OFFERED`'dadır: iş akışının makineleri.
- Sürüm yayımlanınca iş akışı her kararlı adresi hesapsız indirmeyi dener. Olmazsa bir uyarı yazar; sürüm zaten
  yayımlanmıştır, mağaza adımı yine çalışır.
- Tek kaynak: depo `extension/src/bridge/program.ts`'deki `REPO` sabitidir. Testler onun
  `iplikci.update.source.REPO`'ya, paket adlarının `release.stable_name`'e ve `OFFERED`'ın "Paketler" iş akışının
  makinelerine eşit olduğunu denetler (`tests/test_release.py`).

### Mağazada herkese açık

- Eklenti mağazada herkese açık listelenir. ADR-0016 listelenmemiş yayını öngörüyordu, kullanıcı 2026-11-14'te bunu
  değiştirdi. Gerekçe: eklenti artık programın kapısıdır. Programın bir web sayfası yoktur. Adını duyan biri eklentiyi
  mağazada arayıp bulur, eklenti de onu programa götürür. Listelenmemiş bir eklentiye ancak bağlantısını bilen
  ulaşırdı.
- Mağazaya ilk giden sürüm 0.9.0'dır: programı olmayanı indirmeye götüren ilk sürüm.

### Mağaza incelemesi ne görür

- Programı olmayan bir bilgisayarda eklentiyi kuran inceleyici, ayarlar sayfasını kendiliğinden açılmış bulur. Sayfa
  programın gerektiğini söyler ve rehberi gösterir. Düğme GitHub'daki indirmeyi yeni bir sekmede açar. Eklenti başka
  hiçbir istekte bulunmaz; yalnızca 127.0.0.1:8643'ün sağlık denetimine bakar.
- İnceleme notu ([mağaza metni](../../extension/store/listing.md)) bunu ve eşleştirmenin neden yalnızca programla
  denenebileceğini anlatır.

## Sonuçlar

- Olumlu:
  - Programı olmayan kullanıcı ne yapacağını eklentinin kendisinden öğrenir; web sayfası gerekmez.
  - Yeni izin ve yeni ağ isteği yoktur. Eklentinin kendi istekleri yine yalnızca Gmail'e ve 127.0.0.1'e gider.
  - Son sürümün paketinin değişmeyen bir adresi olur; README ve başka yerler de ona bağlantı verebilir.
- Olumsuz:
  - Düğme GitHub'ın "son sürüm" yönlendirmesine ve kararlı adlara dayanır. Bunları taşımayan bir sürüm düğmeyi
    bozar. Bunu testler, sürüm işinin denetimi ve iş akışının uyarısı önler.
  - v0.11.1'in paketleri sürümlü adlarla duruyor. Kararlı adları taşıyan ilk sürüm herkese açık depoda yayımlanmadan
    düğme GitHub'ın "bulunamadı" sayfasını açar. Bu yüzden 0.9.0 mağazaya o sürümden sonra gönderilir.
  - İndirilen program imzasızdır (K22). Rehber, sistemin ve tarayıcının uyarılarının nasıl geçileceğini söyler.
  - Herkese açık listelenen eklenti daha çok kişiye görünür. Puanlar ve yorumlar herkese açıktır; incelemenin soruları
    artabilir.
  - Program bilgisayarda kurulu ama kapalıysa eklenti bunu "kurulu değil"den ayıramaz. Rehber önce "kuruluysa açın"
    der.

## Değerlendirilen seçenekler

- **`downloads` izniyle `chrome.downloads.download`:** yeni bir izin olurdu; kurulumda "İndirmelerinizi yönetme"
  uyarısı çıkar, incelemede gerekçe ister. Sekme aynı indirmeyi izinsiz yapar.
- **Eklentinin GitHub API'sine sorup son sürümün dosyasını bulması:** yeni adres izinleri (`api.github.com`, dosya
  sunucuları) ve eklentiden dışarıya istekler demektir; GitHub'ın istek sınırları da vardır. Kararlı adlar bunu
  gereksiz kılar.
- **Yalnızca sürüm sayfasına bağlantı:** kullanıcı üç sistemin kurulum paketleri ve güncelleme dosyaları arasından
  doğrusunu seçmek zorunda kalırdı. Paketi olmayan sistem için yine bu yol kullanılır.
- **Bir web sayfası (ör. GitHub Pages) ve oraya bağlantı:** kullanıcı web sayfasını sonraya bıraktı (K31).
- **Listelenmemiş yayın (ADR-0016'nın ilk kararı):** eklentiye yalnızca bağlantıyı bilen ulaşırdı; kapı işini
  göremezdi.
