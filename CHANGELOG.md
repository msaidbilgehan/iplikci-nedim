# Değişiklik günlüğü

Biçim [Keep a Changelog](https://keepachangelog.com/tr-TR/1.1.0/)'a, sürüm numaraları
[anlamsal sürümlemeye](https://semver.org/lang/tr/) dayanır. Her aşama bir sürümle biter
([yol haritası](docs/v1/roadmap.md)).

## [1.0.5] — 2026-11-16 — Yanlış zam bildirimleri, Google One ve öngörüde iki kez sayılan kart borcu

### Düzeltilenler

- Bir ödeme alanı aynı ay içinde aboneliğinin iki katı tutarında başka bir çekim yapınca (ikinci bir plan, ek
  kullanım) abonelik zamlanmış sanılıyordu, oysa abonelik birkaç gün sonra eski fiyatıyla ödenmişti. Artık aynı dönemde
  eski fiyat da ödendiyse yeni tutarlı ödeme ayrı bir çekimdir; abonelik eski fiyatıyla sürer, zam bildirimi gitmez.
- Yeni açılan bir aboneliğin kıst ilk faturası (ayın kalan günleri) "eski fiyat" sayılıyor, planın kendi fiyatı zam
  diye bildiriliyordu. Artık eski fiyatın da en az iki kez ödenmiş olması gerekir. Aynı ödeme alanının aynı tutardaki
  birkaç aboneliği birbirine karışmıyor.
- Google One'ın Kasım'dan beri ekstrede "GOOGLE*ONE 01M" diye yazan ödemesi tanınmıyor, "Diğer Harcamalar"a düşüyor ve
  Google One o ay ödenmemiş görünüyordu. Uygulamayla gelen kural artık bu yazımı da tanır.
- Bakiye öngörüsü bir kart ekstresini iki kez düşebiliyordu: bir kez kartı en son ödeyen hesaptan son ödeme tutarı
  olarak, bir kez de kartı daha önce aylarca ödemiş başka bir hesaptan "ayda şu kadar kart ödemesi" olarak, bugünden
  başlayarak. Artık bir hesabın kart ödemeleri, ödediği kartların takvimdeki son ödeme gününden sonra başlar.
  "Hesaplarınızın toplamı eksiye düşecek" bildirimi bu yüzden erken gelebiliyordu.

## [1.0.4] — 2026-11-16 — TEB ekstresinin OCR'ı, mevduat faizi ve fon alımı

### Düzeltilenler

- Sayfa resmi olarak gelen TEB Bonus ekstresinde OCR bir tutarın arkasındaki lekeyi nokta okuyunca ("TL.950,40.")
  o satır hiç okunmuyordu: ekstre bankanın toplamıyla tutmuyor, okuyucu biçim alarmı veriyor, ayı "kontrol gerekli"
  bırakıyordu. Artık satır okunur ve ekstre doğrulanır.
- Aynı ekstrelerde OCR "Yurtdışı"nın ş'sini Romence ș olarak okuyabiliyordu; o satırların yabancı para tutarı
  açıklamada kalıyordu. Artık orijinal tutar ("5,00 USD") yerine oturur.
- Temassız ödeme ikonu OCR'da "»))", "»)" ya da "1))" diye okununca açıklamada kalıyordu; aynı kafe ikonun okunuşuna
  göre iki ayrı işyeri görünüyordu. Artık atılır.
- Mevduatın kazandırdığı faiz (CEPTETEB Marifetli'nin "net faiz geliri") "Ek Hesap (KMH) Faizi" sayılıyor, gideri
  azaltıyordu. Artık gelirdir: yeni "Faiz Geliri" kategorisi. Ödenen faiz ve geri verilen faiz eskisi gibi Banka &
  Finans'tadır. Bu yüzden hesap dökümlerinin okuyucuları belgeleri bir kez yeniden okur.
- Hesaptan alınan fon ("… PORTFÖY PARA PİYASASI FONU alış bedeli") kişilere gönderilen para sayılıyordu. Artık
  birikimdir: yeni "Yatırım Fonu" kategorisi; fonun satışı da birikimden gelen paradır.

## [1.0.3] — 2026-11-15 — Eklentinin mağaza metni yeniden yazıldı

### Değişenler

- Tarayıcı eklentisi 0.9.2: Chrome Web Store'daki metni baştan yazıldı. Eski metin İplikçi Nedim'in ne olduğunu ve
  eklentinin ne işe yaradığını söylemiyordu, kullanıcıyı ilgilendirmeyen ayrıntılarla doluydu. Mağazada adın altında
  görünen özet artık "İplikçi Nedim kişisel finans programının Gmail eklentisi: bankaların gönderdiği ekstre, dekont ve
  bildirimleri programa aktarır." diyor. Uzun açıklama programın ne yaptığını, eklentinin neyi alıp neye
  dokunmadığını, üç adımda kurulumu ve desteklenen bankaları anlatıyor. Eklentinin çalışmasında değişen bir şey yok.

## [1.0.2] — 2026-11-15 — İlk analizde yakın son ödemeler, eklentide GitHub bağlantısı

### Düzeltilenler

- İlk analizini belgeleriyle yapan bir veri klasörü, örneğin demo, o gün son ödemesine bir haftadan az kalan
  ödemeleri hiç söylemiyordu: ilk analiz her şeyi yalnızca not ediyordu. Artık ilk analiz de önümüzdeki haftanın
  ödemelerini söyler; geçmişin olayları (gelmeyen ödemeler, zamlar, öngörüde eksiye düşen bakiye) ilk analizde yine
  yalnızca not edilir. Boş başlayan bir kurulum bu ödemeleri belgeler geldikçe zaten söylüyordu.

### Değişenler

- Tarayıcı eklentisi 0.9.1: ayarlar sayfası İplikçi Nedim'in GitHub sayfasına bağlantı verir: kaynak kodu, kurulum
  adımları ve sorular. Mağazadan kurulan eklentiyi Chrome kendisi günceller. Mağaza sayfasının açıklaması da kod
  deposunun adresini, destek adresi deponun soru ve sorun sayfasını gösterir.
- Yeni sayfa: desteklenen bankalar ve belgeler. Beş bankanın ve e-Faturanın hangi belgesinin okunduğunu, dosya
  biçimini (PDF, Excel, HTML, e-posta, XML) ve belgenin genelde nereden geldiğini söyler. README ona bağlanır; mağaza
  açıklaması da kısa listesini taşır:
  [docs/desteklenen-bankalar.md](https://github.com/msaidbilgehan/iplikci-nedim/blob/master/docs/desteklenen-bankalar.md).

## [1.0.1] — 2026-11-15 — Tarayıcı eklentisi Chrome Web Store'da

### Değişenler

- Tarayıcı eklentisi, İplikçi Nedim Köprüsü, Chrome Web Store'da herkese açık yayımlandı:
  <https://chromewebstore.google.com/detail/biegljgcnlkdokmfpdejecddgaekplof>. Tarayıcı eklentisi ekranı ve kurulum
  sihirbazı artık önce mağazayı gösterir: "Chrome Web Store'da aç" ile eklenti tek tıkla eklenir, geliştirici modu
  gerekmez ve eklentiyi tarayıcı kendisi günceller. Klasörden yükleme adımları "Mağazayı kullanamıyorsanız: klasörden
  yükleyin" altında durur.
- Eklentiyi daha önce klasörden yüklediyseniz mağazadakine geçin: mağazadan ekleyin, Tarayıcı eklentisi ekranında
  yeni bir eşleştirme kodu alıp mağazadan gelen eklentiye girin, sonra tarayıcının eklentiler sayfasından eskisini
  kaldırın. İkisi birden kalırsa aynı iletileri iki kez getirir. Eskisinin eşleşmesini "Eşleşmiş eklentiler"
  listesinden "İptal et" ile kapatabilirsiniz.

## [1.0.0] — 2026-11-15 — İlk herkese açık sürüm

### Eklenenler

- Tarayıcı eklentisi (0.9.0) İplikçi Nedim'e giden yol olur. Chrome Web Store'da herkese açık yayımlanacak; programı
  olmayan bir bilgisayara kurulunca ayarlar sayfası kendiliğinden açılır, eklentinin bu bilgisayardaki İplikçi Nedim
  programıyla çalıştığını söyler ve sisteminiz için "İplikçi Nedim'i indir" düğmesini gösterir. Düğme son sürümün
  kurulum paketini tarayıcının yeni bir sekmesinde indirir; altında paketi kurup açmanın adımları yazar: macOS'ta
  uygulamayı Uygulamalar'a sürüklemek ve ilk açılışta Gizlilik ve Güvenlik'teki "Yine de Aç", Windows'ta "Ek bilgi" →
  "Yine de çalıştır", Linux'ta dosyanın çalıştırılmasına izin vermek. Kurulum paketi olmayan bir sistemde düğme sürüm
  sayfasını açar ve bunu söyler. Sayfa programı bekler; program açılınca kendiliğinden eşleştirmeye geçer ve kodun
  nereden alınacağını söyler. Eklentinin penceresi de, eşleşmemişken program bulunamazsa, aynı düğmeyi gösterir.
- Eklenti bunun için yeni bir izin istemez ve GitHub'a kendisi bağlanmaz: indirmeyi tarayıcı yapar, eklenti yalnızca
  sekmeyi açar.
- macOS'ta İplikçi Nedim'i çöp kutusuna sürüklemek arka plan servisini de kaldırır. Servis uygulamanın gittiğini fark
  eder, iki dakika içinde bilgisayardaki kaydını siler ve kapanır. Servis o an çalışmıyorsa kayıt bir sonraki oturum
  açılışında kendini siler. Önceden servis çalışmayı sürdürüyor, macOS da artık olmayan programı her oturum açılışında
  ve ardından yarım dakikada bir yeniden başlatmaya çalışıyordu. Verileriniz yerinde kalır; onları da kaldırmak
  isterseniz önce Ayarlar'daki "Kaldır"ı kullanın. Güncellemeler ve o an takılı olmayan bir diskteki uygulama kaydı
  kaldırmaz.
- Linux'ta İplikçi Nedim uygulama menüsüne kendisi girer: AppImage ilk açılışta masaüstünün menüsüne simgesiyle bir
  "İplikçi Nedim" girişi ekler. Giriş, AppImage taşınsa ya da silinse de programın bilgisayardaki kopyasını açar;
  güncellemeler onu yeni sürüme taşır, Ayarlar'daki "Kaldır" onu da siler. Önceden AppImage'ı her seferinde
  indirildiği klasörden açmak gerekiyordu.
- Demo veri klasöründe dört kredi kartı var (TEB, Garanti BBVA, QNB, İş Bankası): mayıstan başlayarak sırayla açılmış,
  her biri kendi kesim gününde, bankanın kendi düzeniyle 18 ekstre. TEB kartı TEB hesabından ödenir; Takvim ve Pano
  kartların son ödemelerini asgari tutarlarıyla gösterir.

### Değişenler

- Her sürümün kurulum paketleri adında sürüm numarası olmadan yayımlanır: `iplikci-nedim-macos-aarch64.dmg`,
  `iplikci-nedim-windows-x86_64.exe`, `iplikci-nedim-linux-x86_64.AppImage`. Son sürümün paketi böylece hep aynı
  adrestedir; README bu adresleri verir. Kurulu uygulamalar güncellemelerini eskisi gibi alır.
- Güncellemeler yeniden programın kendi deposundan gelir: depo herkese açıktır ve sürümler onun sürüm sayfasında
  yayımlanır (https://github.com/msaidbilgehan/iplikci-nedim/releases). 0.11.1'in baktığı ayrı depo kaldırılacak;
  0.11.1'i kurmuş bir uygulama 1.0.0'ı bir kez de oradan alır, sonraki sürümleri bu depoda arar.

### Düzeltilenler

- QNB'nin, TEB'in ve Garanti BBVA'nın kart ekstrelerindeki asgari ödeme tutarı okunuyor; QNB'de ve TEB'de kart limiti
  de. Bu ekstrelerin hepsi bunları basıyordu, ama asgari tutarın ve limitin yazmadığı sanılıyordu: Takvim'deki kart
  son ödemelerinde, Şu an'daki kart kartlarında ve Hesaplar'da asgari ödeme boş kalıyordu. Asgari ödeme oranı, nakit
  avans ve kullanılabilir limit ile asgari tutarı anlatan yasal not bunlarla karışmaz. TEB'in sayfa resmi olarak gelen
  ekstrelerinde de okunur.
- Okunması bir dakikayı aşan bir belge okunamadı sayılmadan önce bir kez daha, üç dakikaya kadar beklenerek okunur.
  Program yeni kurulmuşken macOS'un yazı tanıması ilk seferde hazırlanırken bir dakikayı aşabiliyordu: sayfa resmi olan
  bir ekstre o zaman okunamamış görünüyor, geri yükleme provası da bu yüzden başarısız olabiliyordu.

## [0.11.1] — 2026-11-14 — Sürümler herkese açık depodan gelir

### Değişenler

- Kurulu uygulama yeni sürümleri artık herkese açık `iplikci-nedim-surumler` deposunda arar. Sürümler şimdiye dek
  programın kodunun durduğu özel depoya konuyordu: oradan ne siz ne de kurulu uygulama hesapsız indirebiliyordu,
  Ayarlar → Güncellemeler de "sürümler henüz herkese açık bir yerde değil" diyordu. O depo açılınca uygulama sonraki
  sürümleri oradan bulur ve, ayarınız "Kendiliğinden kur" ise, önce yedek alıp kendisi kurar. Depo açılana dek
  denetim eskisi gibi henüz herkese açık bir sürüm olmadığını söyler.

## [0.11.0] — 2026-11-14 — Claude'un hafızası İplikçi Nedim'de

### Eklenenler

- Claude paranızla ilgili konuşmalarda hatırlaması gerekenleri İplikçi Nedim'e not eder: sizinle yaptığı finansal
  kontrolleri ve sonuçlarını, aldığınız finansal kararları, hedeflerinizi ve yanıtları nasıl istediğinizi. Notlar
  veri klasöründe durur. Claude Code hangi klasörde açılırsa açılsın, Claude Desktop ya da başka bir MCP istemcisi
  bağlansa da aynı notlar okunur. Daha önce Claude'un notları açıldığı proje klasörüne bağlıydı: başka bir klasörde
  ya da uygulamada yoktu. Yazılımın, kodun ya da başka işlerin notları buraya yazılmaz; Claude onları kendi
  hafızasında tutar.
- Claude'un üç yeni aracı: `read_memory` notların listesini, istenen notların tamamını ya da bir aramanın bulduklarını
  verir (virgül aramayı İşlemler'deki gibi parçalara ayırır); `write_memory` not yazar ya da günceller;
  `delete_memory` siler. Notlar hiçbir rakamı ya da kuralı değiştirmediği için bu araçlar plan istemez. Servis
  kapalıyken notlar okunur, yazılmaz.
- Claude bağlantısı ekranında "Claude'un hafızası" kartı: notlar türlerine göre (sizin hakkınızdakiler, çalışma
  biçimi, kararlar ve kontroller, nerede ne var) listelenir; her notun tamamı açılır bölümde. Yanlış ya da
  istemediğiniz bir notu, sorulduktan sonra silersiniz.
- Notlar yedeklere ve veritabanının yeniden kurulmasına girer; `iplikci dogrula --yeniden-kur` notların aynı geldiğini
  de denetler. Denetim kaydı her değişikliği notun adıyla yazar, metnini yazmaz.
- Maskeleme açıkken notların metnindeki hesap numaraları ve kişi adları da gizlenir. Bir notun adı gizlenemeyeceği
  için yeni bir notun adında kişinin tam adı, hesap numarası ya da uzun bir rakam dizisi olamaz.
- Demo veri klasöründe Claude'un iki örnek notu var.

### Düzeltilenler

- Claude Code bir MCP sunucusunun talimatlarının yalnızca ilk 4096 karakterini gösterir. İplikçi Nedim'in talimatları
  5408 karakterdi: maskelemenin ne gizlediği, servis kapalıyken yalnızca okunabileceği, şirket belgelerinin kapsam
  dışı olduğu ve her rakamın araçlardan gelmesi gerektiği kesilen kısımdaydı, Claude Code'daki Claude bunları hiç
  okumuyordu. Talimatlar artık 4082 karakter ve hiçbir kural kesilmiyor; araçların kendi açıklamalarında yazanlar
  talimatlarda yinelenmiyor.

## [0.10.4] — 2026-11-13 — Virgülle birkaç şey birden aranır

### Eklenenler

- İşlemler'in arama kutusu birden çok şeyi birden arar: virgül aramayı parçalara ayırır ve bir parçanın tutması yeter.
  "market, kira" ikisinden birini içeren bütün işlemleri toplamlarıyla birlikte listeler. Boşlukla yazılan kelimeler
  eskisi gibi birlikte aranır ("migros kadıköy" ikisini birden içerenleri bulur). Tırnak içindeki ifade virgülüyle
  birlikte yazıldığı gibi aranır; iki rakam arasındaki virgül ondalık sayılır ("1,50"). Kutunun altındaki açıklama
  bunu söyler, arama çipi parçaları seçenek olarak okur: "Ara: market veya kira".
- Birden çok parçalı aramada listenin üstünde her parçanın kaç işlem bulduğu yazar. Hiçbir işlem bulamayan parça,
  örneğin yanlış yazılmış bir ad, "bulunamadı" der; öteki parçaların satırları arasında kaybolmaz. Bir parçanın adına
  tıklayınca yalnızca onun işlemleri toplamlarıyla açılır.
- Belgeler'in araması, Değerlendirme'nin düzenli ödemeleri, CSV, kayıtlı görünümler ve Claude'un arama aracı da
  virgülü aynı biçimde okur. Claude'un arama aracı her parçanın bulduğu işlem sayısını da verir.

### Düzeltilenler

- Önceden arama kutusu yazılan kelimelerin hepsini aynı işlemde arıyordu ve virgül kelimeye yapışık kalıyordu:
  "market, kira" hiçbir işlemi bulmazdı.
- Yapılacaklar'daki kategorisiz bir işyerinin bağlantısı adıyla arar; adında virgül olan bir işyeri, adının
  parçalarından birini içeren başka işlemleri de getirmez.

## [0.10.3] — 2026-11-12 — Kesim günü ekstreden okunur, beklenen ekstre kendi günleriyle adlandırılır

### Düzeltilenler

- Kapanmamış bir ayın beklediği kart ekstresi "21–31 Ekim ekstresi, kesim ~20.11" diye yazıyordu. Bu, Ekim'in
  ekstresi Kasım'ın ortasında kesiliyormuş gibi okunuyordu. Oysa kart ekstresi takvim ayını değil, iki kesim günü
  arasını kapsar: ayın kesimden sonraki günleri bir sonraki ayın kesimiyle gelen ekstrededir. Beklenen ekstre artık
  kendi günleriyle adlandırılır ve ayın hangi günlerinin onda olduğu yazılır: "21–31 Ekim, 21 Ekim–19 Kasım
  ekstresinde". Pano'da, İşlemler'de ve Ay sonu'nda aynı söz kullanılır.
- Sonraki kesim günü, son kesimin bir ay sonrası diye tahmin ediliyordu. Bankalar kesim gününü aydan aya birkaç gün
  oynatır; tahmin çoğu ay bir iki gün şaşıyordu. Her kart ekstresi bir sonrakinin kesim gününü yazar ve artık o gün
  okunur (Garanti, QNB, TEB ve İş Bankası). Ekstre yazmıyorsa tahmin "~" ile gösterilir. Ay sonu, Pano'nun ve
  İşlemler'in beklenen belgeleri, Hesaplar'daki "sonraki ekstre", Şu an'daki kartın dönemi ve taksitlerin kesim
  günleri bu günü kullanır.
- QNB kart ekstrelerinin son ödeme tarihi hiç okunmuyordu. QNB bu tarihi ay adıyla yazar ("28 Ağustos 2026") ve yazı
  tipi ayın Türkçe harflerini düşürür. Artık okunur; takvim ve bildirimler QNB kartının son ödeme gününü bilir.
- Sayfa resmi olarak gelen, OCR ile okunan TEB ekstrelerinin son ödeme tarihi okunmuyordu; artık okunur.
- Bir ay iki ekstre bekliyorsa (aradaki ekstre gelmemişse) gecikme sonraki ekstrenin kesimine göre ölçülüyordu ve
  gelmeyen ekstre "gecikti" sayılmıyordu. Artık beklenen ilk ekstrenin kesimine göre ölçülür.

## [0.10.2] — 2026-11-12 — Kapanmamış ay neyi beklediğini söyler, süzgeç penceresi ekrana sığar

### Düzeltilenler

- İşlemler'de bir süzgecin seçenek penceresi, altında yer kalmayınca yukarı açılıp ekranın üstünden taşıyordu. En
  üstteki "Tümü" ile "Hiçbiri"ye ulaşılamıyor, liste kaydırılamıyordu. Pencere artık açıldığı yandaki yer kadar uzun;
  seçenekleri içinde kayar, "Tümü" ile "Hiçbiri" hep görünür. Kayıtlı görünümlerin penceresi de öyle.
- Hiçbir seçeneği seçili olmayan bir süzgeç listeyi boşaltıp yalnızca "Bu süzgeçlerle işlem yok" diyordu. Artık
  hangi süzgecin boş kaldığını söyler ve onun bütün seçeneklerini tek tıkla geri seçen bir düğme sunar.
- Pano'nun aylık grafiği kapanmamış her aya "eksik" diyordu. Oysa ekstrelerini bekleyen bir ayda eksik bir şey yok.
  Sütunun üstünde artık ayın durumu yazar: "bekliyor" ve kapanacağı gün ("~20.11"), "sürüyor", gerçekten bir belgesi
  yoksa "eksik". Grafiğin altında her kapanmamış ayın cümlesi var: "Ekim 2026 eksik değil: ayın son günlerini kapsayan
  2 belge bekleniyor, sonuncusu 20.11.2026 civarında gelir." Değerlendirme'nin grafikleri de aynı sözleri kullanır.
- Sıfır tutarlar işaretsiz yazılır: "Çıkan −0,00 TL" yerine "0,00 TL".

### Eklenenler

- Pano'nun hikâyesi kapanmamış ayın beklediği belgeleri tek tek sayar: hangi kartın hangi günlerinin ekstresi, kesimi
  ne zaman.
- İşlemler'de listelenen günlerden biri kapanmamış bir aydaysa listenin üstünde o ayın neyi beklediği yazar: her
  hesabın beklenen belgesi, günleri ve kesimi. Belge gelince o günlerin işlemleri listeye girer. Süren ay sürdüğünü
  söyler; ötekiler ay sonu sayfasına götürür.
- Pano'nun aylık grafiğinde bir ayın adına ya da sütunun boş yerine tıklayınca o ayın bütün işlemleri açılır. Gelen
  ya da giden çubuğundan açılan listede "Dönemin bütün işlemleri" tek tıkla ayın bütününe geçer.

## [0.10.1] — 2026-11-11 — Pano biten ayı hemen anlatır, İşlemler'de dönem süzgeci

### Düzeltilenler

- Pano, bir ayın bütün belgeleri gelene dek bir önceki ayı anlatıyordu. Kartların ayın son günlerini kapsayan
  ekstresi haftalar sonra geldiği için Kasım ortasında hâlâ Eylül görünüyordu. Artık biten ay hemen anlatılır.
  Rakamları ve hükmü "şimdilik"tir: "Şimdilik kalan", "Gelen paranın şimdilik %40'ı elinizde kaldı." Altında
  ayın son günlerini kapsayan kaç belgenin beklendiği ve sonuncusunun hangi gün geleceği yazar. Belgeler geldikçe giden
  artabilir, kalan azalabilir. "Paranız nereye gitti?" de o ay için "şimdiye kadar" der.
- Pano'da başlığın yanındaki oklarla önceki aylara gidilir; ay adreste kalır, geri düğmesi de çalışır.
- İplikçi Nedim her gün aynı sözü söylüyordu. Her söz tek bir duruma bağlıydı ve durumların yarısından çoğunun tek
  sözü vardı. Pano'nun ayı haftalarca aynı kalınca söz de değişmiyordu. Artık her durumun en az iki sözü var ve söz
  günden güne değişir; bir söz anlamına uyan birden çok durumda söylenebilir. "Başka bir söz" her sözü bir kez gösterir.
  Ayın hükmü de Pano'nunki gibi biten son aydır; ay henüz kapanmadıysa "şimdilik" der.
- Kurulum sihirbazında "Bitir" yalnızca Pano'ya götürüyordu. Sihirbaz yeniden açılınca son adımda, henüz
  kullanılamayan uzaktan erişimde, bitmemiş gibi duruyordu. Artık "Bitir" kurulumun özetini gösterir: hepsi tamamsa
  "Kurulum tamamlandı", değilse hangi adımların beklediği, her biri kendi adımına giden bir bağlantıyla. Kullanmadığınız
  isteğe bağlı adımlar ayrıca yazar. Sihirbaz gerekli adım kalmayınca bu özetle açılır.
- İşlemler'in hesap süzgeci uzun hesap adlarını kesiyordu: yalnızca son haneleri ayrı iki hesap birbirinden ayırt
  edilemiyordu. Süzgecin penceresi artık en uzun ad kadar geniş.

### Eklenenler

- İşlemler'de dönem süzgeci aramanın yanında: Tüm zamanlar, Bu ay, Geçen ay, Son 30 gün, Son 3 ay, Bu yıl, Geçen yıl
  ya da seçtiğiniz iki gün. Kaydettiğiniz bir görünümün "Bu ay"ı zamanla ilerler. Başka bir ekrandan gelen bir ayın
  günleri ayın adıyla yazılır ("Haziran 2026").
- Süzgeçler'de yön (yalnızca giren ya da yalnızca çıkan para) ve tutar (en az, en çok). Tutar Türkçe yazıldığı gibi
  girilir: "1.500" ya da "1.500,50".
- Etiket alanı satırlarınıza verdiğiniz etiketleri en çok kullanılandan başlayarak önerir; birine basınca süzülür.

## [0.10.0] — 2026-11-11 — Sürümler ve güncellemeler

### Eklenenler

- İplikçi Nedim kendini günceller. Her gün yeni bir sürüm olup olmadığına bakar; bulunca önce verilerinizin yedeğini
  alır, sonra yeni sürümü kurar ve kendiliğinden yeniden açılır. İndirilen dosya, İplikçi Nedim'in imzasıyla ve
  özetiyle doğrulanmadan kurulmaz.
- Ayarlar'da "Güncellemeler" kartı: çalışan sürüm, son denetim, yeni sürümün neler getirdiği ve "Şimdi güncelle". Yeni
  sürüm çıkınca ne olacağını siz seçersiniz: kendiliğinden kur (önerilen), önce bana sor ya da hiç denetleme.
  "Şimdi denetle" her zaman bakar. Sistem ekranı da yeni sürüm olup olmadığını söyler.
- Paketlenmemiş yüklenen tarayıcı eklentisi (0.8.0), İplikçi Nedim güncellenince kendini yeni sürümle yeniden yükler;
  eklentiler sayfasında bir şey yapmanız gerekmez.
- Eklenti Chrome Web Store'da yayımlanınca Tarayıcı eklentisi ekranı önce mağazayı gösterir; mağazadan kurulan
  eklentiyi tarayıcı kendisi günceller.
- Her sürüm GitHub'da yayımlanır: macOS, Windows ve Linux için kurulum paketleri, güncelleme dosyaları ve eklentinin
  mağaza paketi. Paketler yayımlanmadan önce açılıp denenir.

### Bilinmesi gerekenler

- Güncelleme denetimi yalnızca GitHub'daki sürüm sayfasına bakar; hesaplarınızdan ya da belgelerinizden hiçbir bilgi
  gitmez. Ayarlar'dan kapatılabilir.
- Elle kurulmuş bir kopya (ör. geliştiricinin kurduğu) kendini güncellemez; yeni sürümü haber verir.
- Kurulu kopyaların güncellemeyi indirebilmesi için sürümlerin herkese açık bir yerde durması gerekir; bu sürümde
  sürümler henüz herkese açık değil.

## [0.9.18] — 2026-11-11 — Bildirimler neyle ilgili olduğunu söyler

### Düzeltilenler

- Telegram'a ve masaüstüne giden bildirimler hangi ödemeden söz ettiğini söylemiyordu: "İptal ettiğiniz bir
  abonelikten ödeme alındı: 249,90 TL." Artık her bildirim neyle ilgili olduğunu da yazar. Ödemelerde, gelirlerde ve
  harcamalarda kategorisini ("İnternet & Telefon", "Maaş"), kart son ödemesinde, kredi taksitinde, bakiye öngörüsünde
  ve dekontlarda bankasını ("TEB") yazar. Örneğin: "İptal ettiğiniz bir abonelikten ödeme alındı (İnternet & Telefon):
  249,90 TL."
- Hesaplarınızın toplamı eksiye düşecekse bildirim bunu "hesaplarınızın toplamı" diye söyler.
- İşyerinin ya da kişinin adı ve hesap numarası bu bildirimlerde yine yazmaz, çünkü Telegram iletileri uçtan uca
  şifreli değildir. Adları da görmek isterseniz Bildirimler → Kanallar'da Telegram'ın ayrıntısını "Tam" seçin.
- Güncellemeden önce gönderilmiş bildirimler değişmez.

## [0.9.17] — 2026-11-10 — İş Bankası'nda hesaplarınız arası aktarma

### Düzeltilenler

- İş Bankası'nda bir hesabınızdan öbürüne yaptığınız aktarma ("… HESABA <adınız> Hesaplar Arası Akt") kişilere
  gönderilen para sayılıyordu. Hesap özeti bu satırda parayı alanın adını yazar; okuyucu bu adı okumuyordu. Artık ad
  okunur ve sizin adınızsa aktarma kendi hesaplarınız arası sayılır. Daha önce eklenen hesap özetleri güncellemeyle
  kendiliğinden yeniden okunur.
- Parayı alan hesabın kendi hesap özeti de gelince iki uç eşleşir ve o hesabın bakiyesi toplamlara girer.

## [0.9.16] — 2026-11-10 — Uygulamadan paylaşılan dekontlar ve TEB cüzdanı

### Eklenenler

- Vakıfbank'ın uygulamasından paylaşılan dekont (PDF) okunur. Önceden "ekstre veya hesap hareketi değil" diye arşive
  alınıyor, içindeki para hareketi okunmuyordu. Dekontu Belge ekle ekranından, gelen klasöründen ya da Telegram botuna
  göndererek ekleyin. Dekont, hesap dökümü gelmeden önce parayı gösterir; döküm gelince onun satırı sayılır. Aynı
  FAST'in e-posta bildirimi ya da aynı dekontun ikinci bir kopyası da gelirse hareket bir kez sayılır.
- TEB'in iki TEB hesabınız arasındaki havalenin dekontu ("Banka İçi Para Transfer Dekontu") okunur. Aynı yollarla
  eklenir.
- Daha önce eklenip okunmayan dekontlar güncellemeyle kendiliğinden okunur.

### Düzeltilenler

- TEB'in Dijital Hesap Cüzdanı'nda iki satıra bölünen açıklamalar okunmuyordu ("… den gelen" / "havale tutarı",
  "… no.lu Kredi Kartına Ödenen" / "Tutar"). TEB böyle bir açıklamanın bir satırını hareketin üstüne, öbürünü altına
  yazar. Okuyucu bu hareketleri atlıyor, üstteki satırı bir önceki hareketin açıklamasına ekliyordu. Bu yüzden hesaba
  gelen havaleler ve karta yapılan ödemeler eksik kalıyordu. Vadeli hesaba aktarılan para da kişilere gönderilmiş
  görünüyordu; cüzdan doğrulanmıyor, okuyucu biçim alarmı veriyordu. Artık her açıklama satırı kendi hareketine
  verilir. Daha önce eklenen cüzdanlar güncellemeyle kendiliğinden yeniden okunur.
- Faiz işleyen TEB hesabı (ör. CEPTETEB Marifetli) vadeli hesap sayılır. Türünde "Vadeli" yazmasa da cüzdanı
  bakiyenin altına yıllık brüt faiz oranını yazar; bu yeter.
- Bir hesabın türü ve adı artık, önce bir dekont gelmiş olsa da, o hesabın ekstresinden ya da dökümünden gelir.
  Önceden hesabı ilk anlatan belge geçerliydi. Örneğin cüzdandan önce gelen bir havale dekontu, vadeli hesabı
  "Vadesiz" gösterecekti.

## [0.9.15] — 2026-11-10 — Başkasının parası kendi aktarmanız sayılmaz

### Düzeltilenler

- Başka birinden gelen para, kendi hesaplarınız arası bir aktarmanın öbür ucu sayılabiliyordu. Başka bir bankadaki
  hesabınıza gönderdiğiniz para belgesi olmayan bir hesabınıza girdiyse, bir gün önce başka birinin belgeli hesabınıza
  gönderdiği aynı tutar onun karşılığı sanılabiliyordu. Böylece başkasının parası "kendi hesaplarınız arası"
  görünüyor ve gönderdiğiniz paranın nereye girdiği belli sanılıyordu.
- Artık başka birinin adını yazan satır ("… den gelen havale", başka bir ada giden FAST) kendi aktarmanızla hiçbir
  zaman eşleşmez: gelen para gelir, giden para kişilere gönderilen sayılır. Gönderdiğiniz paranın girdiği hesap
  belgelerde yoksa, o bankadaki hesabınızın bakiye notu bunu söyler.

## [0.9.14] — 2026-11-10 — Okunan iletiler ve TEB cüzdanı

### Eklenenler

- Gmail açıkken görünen banka iletileri, okunmuş olsalar da, kendiliğinden alınır (tarayıcı eklentisi 0.7.0).
  Eklenti eskiden her dakika yalnızca okunmamış iletileri alıyordu. Bir sonraki denetimden önce Gmail'de açtığınız
  ileti ancak "Gmail'de eksikleri tara" ile geliyordu. Artık Gmail'in listesinde ya da açtığınız konuşmada görünen,
  listedeki bankaların iletileri alınır. Eklenti bunun için yalnızca iletilerin kimliklerine ve göndericinin alan
  adına bakar; konu, metin ve ad okumaz, Gmail'de hiçbir şeyi değiştirmez. Eklenti güncellenince açık Gmail sekmesini
  yenilemek gerekmez.
- Gmail'in hiç göstermediği iletiler için "Gmail'de eksikleri tara" kalır. Örneğin bilgisayar kapalıyken telefonda
  okunup arşivlenen iletiler ya da bir konuşmanın ortasındaki iletiler.
- TEB'in "Dijital Hesap Cüzdanı" PDF'i okunur. Bu belge TEB'in uygulamasından bir hesabın iki gün arasındaki
  hareketleriyle indirilir. Belge ekle ekranından, gelen klasöründen ya da Telegram botuna gönderilerek eklenir; her
  satırın bakiyesi bir öncekiyle denetlenir. TEB hareketleri e-postayla bildirmediği için TEB hesaplarının güncel
  bakiyesi bu belgeyle ya da CEPTETEB'in hesap hareketleri dökümüyle gelir. Daha önce eklenip okunamayan cüzdanlar
  güncellemeyle kendiliğinden okunur.
- Bir hesabın bakiyesinin gününden sonra o hesaba gönderdiğiniz para bakiyenin notunda yazar: "… tarihinde bu hesaba
  … gönderildi (… hesabından); bakiyede henüz yok". Paranın yalnızca bankası belliyse not onu söyler: "… TEB
  hesaplarınızdan birine … gönderildi; hangisine girdiği belgelerde yok". Not, Akış'ın "Şu an" bölümünde ve
  Değerlendirme'nin varlıklarında görünür.

### Düzeltilenler

- Değerlendirme bir hesabın bakiyesini son dökümden alıyordu. Dökümden sonra gelen banka bildiriminin yazdığı bakiyeyi
  görmüyordu. Hesaplar ve öngörü gelen parayı gösterirken Değerlendirme eski bakiyeyi ve ona göre önerileri
  gösteriyordu. Artık her ekran en yeni basılı bakiyeyi alıyor. Değerlendirme'nin notu bakiyeyi yazan bildirimin
  gününü söylüyor.
- "Ek hesaplarda şu an … borç var" önerisi eski bir dökümün borcunu bugünkü gibi söylüyordu. Borcu söyleyen belge
  eskiyse öneri artık onun gününü yazıyor: "Ek hesaplarda 31.10.2026 itibarıyla … borç var".

## [0.9.13] — 2026-11-08 — Telegram'dan belge

### Eklenenler

- Belgeler Telegram'dan da eklenir. Telegram botunuz eşleştiyse, bankanın uygulamasından indirdiğiniz ekstreyi, hesap
  dökümünü ya da dekontu bota dosya olarak gönderin. İplikçi Nedim belgeyi Belge ekle ekranındaki gibi içeriğinden
  tanır, arşive alır ve belgeyi getiren iletiye ne olduğunu yazar: arşivdeki adı, ekstre ve dökümlerde satır sayısı
  ve denetimi; ya da zaten arşivde olduğu, okunamadığı, şirket belgesi olduğu için alınmadığı. Zip ve e-posta dosyası
  belge belge yanıtlanır. Belgeler ekranında bu belgelerin geliş yolu "Telegram"dır.
- Yalnızca eşleşen, botla bire bir sohbetten gelen belgeler alınır. Başka sohbetlerden gelen dosyalar hiç indirilmez
  ve yanıtlanmaz. Fotoğraf, 20 MB'den büyük dosya ve belge olmayan dosya için bot ne yapılacağını yazar.
- Bildirimler → Kanallar → Telegram kartında "Belge gönderme" bölümü: belge alımını açıp kapatan anahtar ve
  Telegram'dan geçen belgelerin gizlilik notu. Kapalıyken servis botun iletilerini okumaz. Komut satırında
  `iplikci telegram belgeler ac|kapat`; `iplikci bildirim durum` belge alımının açık olup olmadığını da yazar.
- Belge ekle ekranı bu yolu da anlatır ve Telegram kartına götürür.

### Değişenler

- Servis eşleşmiş botun iletilerini sürekli okur (her okuma Telegram'da en çok 25 saniye bekler). Eşleştirme kodu
  arayüz açık olmasa da işlenir; karşılama iletisi belge göndermeyi de anlatır.
- Telegram okumayı ya da indirmeyi belirteç yüzünden reddederse kanal, bildirim gönderiminde olduğu gibi durur.

## [0.9.12] — 2026-11-05 — Eksiye düşemeyen hesap

### Düzeltilenler

- Ek hesabı olmayan bir vadesiz hesap eksi bakiyeyle görünebiliyordu. Garanti yalnızca giden transferleri bildiriyor;
  döviz satışını ve gelen parayı bildirmiyor. Döküm 0,00 TL'yle alındıktan sonra hesaba para girip transferle
  çıkınca, bildirim bakiyeyi sıfırın altına indiriyordu; giriş ise hiçbir belgede yoktu. Bu eksi tutar ek hesap borcu
  sayılıyordu ve borç toplamını, Değerlendirme'nin "ek hesaplarda şu an … borç var" önerisini ve öngörünün
  başlangıcını bozuyordu.
- Artık böyle bir hesabın bakiyesi 0 sayılıyor ve notu, belgelerde olmayan en az ne kadar girmiş olması gerektiğini
  yazıyor. Bu tutar borca girmiyor. Toplamlardan "Belgede görünmeyen giriş" adıyla ayrı bir satırla düşülüyor:
  Hesaplar'da, Pano'nun net varlığında, Döviz'de ve Değerlendirme'nin birikiminde.
- Neden düşülüyor: para kendi hesaplarınızdan birinden geldiyse o hesap belgelerde hâlâ eski bakiyesiyle duruyor.
  Düşülmeseydi aynı para iki kez sayılır, kendi hesaplarınız arasındaki bir aktarma da net varlığı artırırdı. Net
  varlık değişmiyor; borçlarla varlıkların ayrımı düzeliyor. Yeni dökümler gelince satır kendiliğinden kalkıyor.
- Hesap sayfasının günlük bakiyesi de dökümden sonraki günlerde böyle bir hesabı sıfırın altına indirmiyor.
- İplikçi Nedim, borcu olmayan birine "borçlarınız paranızdan fazla" demiyor.

## [0.9.11] — 2026-11-05 — Havale, yazdığı bankaya

### Düzeltilenler

- Kendi hesaplarınız arasındaki bir havale, yazdığı bankadan başka bir bankadaki hesabınızın gelen parasıyla
  eşleşebiliyordu. TEB yalnızca alıcının bankasını yazıyor: aynı gün aynı tutarda biri Ziraat'e, biri Garanti'ye iki
  havale gidince, Garanti hesabınıza gelen para sırası önce gelen Ziraat havalesinin karşılığı sayılıyordu; Garanti'ye
  giden "kişilere gönderilen", Ziraat'e giden "kendi hesaplarınız arası" görünüyordu. Vakıfbank'tan aynı gün TEB'e ve
  Garanti'ye giden iki FAST da çapraz eşleşiyordu. Artık paranın gittiği bankayı yazan bir satır yalnızca o bankadaki
  bir hesabınızla eşleşiyor. Toplamlar değişmiyor; hangi satırın kime gittiği düzeliyor.
- Adında "Turizm" geçen her işyeri otobüs bileti ("Uçak, Tren & Otobüs") sayılıyordu; oysa bu kelime lokanta, market
  ve otel adlarında da geçiyor. Otobüs firmaları artık adlarıyla tanınıyor (Metro Turizm, Pamukkale Turizm, Kâmil Koç,
  Varan, Ulusoy, Nilüfer, Süha); "… Gıda Turizm" Market & Gıda'ya, başka bir şey söylemeyen "… Turizm" kategorisizlere
  düşüyor.

## [0.9.10] — 2026-11-04 — Kapanmayan ay neden anlatılmıyor

### Düzeltilenler

- Pano'nun ay hikâyesi son kapanan ayı anlatıyor, ama ondan sonra biten ve henüz kapanmayan ayı hiç anmıyordu:
  4 Kasım'da hikâye Eylül'deydi, Ekim'in neden yer almadığı hiçbir yerde yazmıyordu. Artık kapanmayan ay kendi
  cümlesiyle söyleniyor: "Ekim 2026 henüz kapanmadı: ayın son günlerini kapsayan 2 belge bekleniyor, sonuncusu
  20.11.2026 civarında gelir. Şimdiye kadar gelen belgelere göre Ekim 2026'da … harcandı; ay kapanınca bu özet o
  ayı gösterir." Yanında o ayın Ay sonu sayfasına giden bağlantı var. Belgesi eksik ya da bakılması gereken bir ay
  da kendi sözleriyle söyleniyor; gün verilemeyen durumlarda (indirilecek bir döküm, geciken bir ekstre) gün
  söylenmiyor.
- Süren ayda hiçbir belge harcama göstermiyorsa Pano "bu ayın belgeleri henüz gelmedi" diyordu, oysa hesap dökümleri
  gelmiş olabiliyor. Artık "bu aya ait harcama henüz hiçbir belgede yok; ekstreler geldikçe görünür" diyor.

## [0.9.9] — 2026-11-04 — Kalan, Ay sonu'ndaki gibi

### Değişenler

- Pano'nun ay hikâyesi artık Ay sonu ekranıyla aynı "Kalan"ı söylüyor. Gelenden yalnızca harcama değil, kişilere
  gönderilen para, ödenen kredi anaparası ve birikim de düşülüyor. "Giden" harcamayı, kişilere gönderilen parayı
  ve kredi ödemelerini içeriyor; birikim (BES, döviz, altın, yatırım) ayrı bir rakam olarak gösteriliyor ve
  cümlede de söyleniyor ("Gelen paranın %12'si birikime gitti, %16'sı elinizde kaldı"). Aylara göre çubuklarda
  birikim mavi bir çubuk; giden çubuğu o ayın harcamalarına, kişilere gönderilen paraya ve kredi ödemelerine,
  birikim çubuğu birikim satırlarına götürüyor. İplikçi Nedim'in ay hükmü de aynı hesaba göre.

### Düzeltilenler

- Garanti kartının taksitli nakit avansının faizi hiçbir yerde sayılmıyordu: ekstre yalnızca taksiti yazıyor.
  Avansın vadesiz hesaba geldiği satır bulununca her taksit artık anapara (kredi ödemesi) ve faiz (harcama) diye
  ayrılıyor, İş Bankası'nın taksitli avanslarında olduğu gibi. Hesabın satırı yoksa taksit eskisi gibi nakit
  avans kalıyor.
- Bir maaş, işverenin adında bir mağaza kategorisinin kelimesi geçtiği için o mağaza kategorisine düşüyordu. Gelir
  satırı artık yalnızca gelen parayı gelir sayan bir kategoriyi alıyor; öbür türlü "Diğer Gelirler"de kalıyor. Toplamlar değişmiyor: gelir türüyle sayılıyordu.

## [0.9.8] — 2026-11-03 — İki ödeme bir dönem yapmaz

### Düzeltilenler

- Yarım yıl arayla yapılan iki ödeme (örneğin iki bağış) "altı ayda bir" ödenen bir düzenli ödeme sayılabiliyordu.
  İkincisi daha az olunca da bir "Düzenli ödeme zammı" bildirimi gelebiliyordu. Kira, fatura ve abonelik gibi düzenli
  ödeme kategorilerinin dışındaki bir ödemenin altı ayda ya da yılda bir ödenen bir ödeme sayılması için artık aynı
  aralığın iki kez tekrarlanması (en az üç ödeme) gerekiyor. Aylık seriler de üç ay istiyor. Bu kategorilerde iki
  ödeme eskisi gibi yetiyor. Bir dükkândan yarım yıl arayla yapılan iki alışveriş de böylece düzenli ödeme
  sayılmıyor; takvim ve öngörü onları beklemiyor.
- Tutarı düşen bir düzenli ödemenin bildirimi "zam" diyordu. Başlık artık "Düzenli ödeme ucuzladı", özet
  "Bir düzenli ödeme ucuzladı" diyor; Akış'taki kart da böyle adlandırılıyor ve uyarı rengini taşımıyor. Kuralın
  adı "Düzenli ödeme tutarı değişti" oldu: hem zamları hem düşüşleri bildiriyor.

## [0.9.7] — 2026-11-03 — Tek satırın düzeltmesi, sayıldığı yerle

### Değişenler

- Bir transferin kategorisini yalnızca o satır için değiştirdiğinizde, satırın nerede sayıldığı da değişiyor.
  Önceden yalnızca etiketi değişiyordu; harcama sayılan bir satır harcama sayılmaya devam ediyordu. Örnekler:
  - Ev sahibine ödenen bir depozitoyu "Kişilere Gönderilen"e alırsanız harcamadan çıkar.
  - Kendi hesabınıza gittiğini bildiğiniz bir transferi "Hesaplar Arası Transfer"e alırsanız kendi transferiniz
    olur.
  - Kişiye gönderilmiş görünen bir muayene ücretini "Sağlık Hizmetleri"ne alırsanız harcama olur.
  Böylece tek bir satırın istisnası için kural dosyasına o satırı dışarıda bırakan özel bir desen yazmak gerekmiyor.
  Kartla yapılan alışverişler ve programın kendi transferiniz diye bildiği satırlar eskisi gibi kalıyor. İşlemler
  ekranı bunu kategori seçiminin altında söylüyor; Claude'un düzeltme planı türün nasıl değişeceğini de gösteriyor.
- Bir kural bir transferi programın tuttuğu kategorilerden birine (Hesaplar Arası Transfer, Nakit Avans & Çekim,
  Kredi & Borç Anapara, faiz ve ücretler) koyarsa, transfer artık o türü alıyor; önceden alışveriş sayılıyordu.
  Bugünkü belgelerde hiçbir satır değişmiyor.

## [0.9.6] — 2026-11-03 — Transferin karşılığı önce

### Düzeltilenler

- Yalnızca alıcı bankayı yazan bir ödeme (TEB'in "QNB BANK A.Ş." gibi satırları), aynı bankaya aynı tutarda adıyla
  yapılmış herhangi bir ödemenin türünü, tarihine bakılmadan alıyordu. Bu adım, ödemenin sizin başka bir
  hesabınızdaki birebir karşılığından önce geliyordu. Bir yakınınıza aynı tutarda ve aynı bankaya para gönderdiğinizde,
  aylar önce kendi ek hesabınıza yaptığınız ödeme de ona gitmiş sayılabiliyordu. Artık önce sizin adınızı yazan
  karşılık aranıyor; benzerlik ondan sonra geliyor. Bugünkü belgelerde hiçbir satır değişmiyor.

## [0.9.5] — 2026-11-03 — Kuralların yerinde düzeltmeler

0.9.3'ün iki düzeltmesi geçici yamalardı; ikisi de olması gereken yerde yeniden yapıldı. Biten bir düzenli gelir
artık arayüzden bitiriliyor.

### Eklenenler

- Düzenli ödemeler: her düzenli gelirin kartında, tablosunda ve panelinde "Artık gelmiyor…" var. Son gelişin ayını
  seçiyorsunuz (son maaş henüz yatmadıysa yatacağı ayı); değişiklik önizleniyor, sonra kişisel kurallarınıza
  yazılıyor. O aydan sonra takvim ve nakit akışı öngörüsü geliri beklemiyor. Bitirdiğiniz gelir listede "Artık
  gelmiyor" diye kalıyor ve "Yeniden bekle…" ile geri alınabiliyor.
- Kurallar: bir kategoriye `_hariç` yazılabiliyor. Kategorinin desenleri bir kelimenin başında tutsa da o
  kategoriye ait olmayan kelimeler buraya yazılıyor; o yerdeki eşleşme sayılmıyor, açıklamada sonra geçen bir eşleşme
  yine sayılıyor. Kendi kurallarınızdaki `_hariç`, hazır kurallardakinin üstüne ekleniyor.

### Değişenler

- Kira yeniden hazır kurallardaki "KİRA" kelimesiyle bulunuyor; kira olmayan kelimeler (KIRAATHANE, KİRALAMA,
  KİRALIK, KİRAZ) `_hariç`'te yazıyor. 0.9.3'teki ek listesi kalktı: Türkçe ekler sayılamaz, "KİRADAN" gibi bir
  kira ödemesi o listeye uymuyordu.
- "İptal ettim"de seçilen ay son ödemenin ayı demek. O ayın ödemesi henüz gelmediyse ödeme ay sonuna dek
  bekleniyor, sonrası beklenmiyor. Önceden ileri bir ay seçmek o ayın ödemesini de hemen takvimden düşürüyordu.

### Düzeltilenler

- Kendi hesaplarınız arasındaki bir transferin iki ucu da adınızı yazıyorsa artık birbirine bağlanıyor. Hesaplar'daki
  para akışı bu transferleri "belgesi olmayan hesap"a değil, gittiği hesaba çiziyor. Aynı tutarda başka birinden
  gelen para da artık kendi transferinizin yerine geçemiyor. 0.9.3'te bulgunun kendisi iki ucu eşleştiriyordu; artık
  eşleştirmeyi defter yapıyor.
- QNB'nin "ATM/Banka Kartı Para Çıkışı" bildirimi artık nakit çekim (Nakit Avans & Çekim) sayılıyor. Önceden
  karşı tarafı olmayan bir transfer gibi okunup "Kişilere Gönderilen"e düşüyordu. Bildirim ATM'yi mağazadaki kart
  okuyucusundan ayırmıyor; bir kart ödemesini biliyorsanız tek satır olarak düzeltebilirsiniz. Bildirimler yeniden
  okunuyor.

## [0.9.4] — 2026-11-03 — Grafiklerden işlemlere

Grafikler artık birer kısayol. Bir çubuğa, bir dilime, bir güne ya da bir akışa tıklayınca onu oluşturan işlemler
açılıyor. Listenin toplamı tıklanan rakamla aynı.

### Eklenenler

- Ay sonu: "Son 12 ayın gideri"nde bir aya tıklayınca o ayın giderleri (harcama, iade, faiz ve ücret) İşlemler'de
  listeleniyor. Ayın gruplarına, gereklilik düzeylerine, kategorilerine ve işyerlerine tıklayınca da o ayın giderleri
  açılıyor.
- Pano: aylar grafiğinde gelen para o ayın gelirlerini, giden para giderlerini açıyor. "Paranız nereye gitti?"de bir
  kategori o ayki işlemlerini açıyor; "Önümüzdeki 30 gün"de bir güne tıklamak o günü Takvim'de gösteriyor.
- Değerlendirme: aylık giderlerde bir ay ya da bir grup, gerekliliklerde bir düzey, kategoriler ve işyerleri, "Gelir
  ve gider"de bir ayın geliri, gideri, kişilere giden parası, borcu ve birikimi, tahminin geçmiş ayları. Hepsi ekranın
  süzgeçleriyle ve seçili dönemin günleriyle açılıyor.
- Hesaplar: para akışı diyagramında bir bant. Hesap sayfasında bakiye eğrisinin bir günü, bir ayın giren ve çıkan
  parası, faiz ve ücretlerin bir kalemi.
- Takvim: öngörü grafiğinde bir güne tıklayınca liste o güne daralıyor, "Bütün günleri göster" geri döndürüyor.
  Bildirimlerin son ödeme günleri ve düzenli ödemelerin sonraki ödemesi de artık o günü gösteriyor.
- Döviz: tek hesapta duran bir para birimi o hesabı açıyor.
- Fareyle bir tıklama yetiyor. İpucu neyin açılacağını söylüyor ve açılacak dilimi öne çıkarıyor. Dokunmatik ekranda
  ilk dokunuş değeri gösteriyor; ikinci dokunuş ya da ipucundaki "Aç" bağlantısı açıyor. Grafiğin altındaki bir satır
  neye tıklanabileceğini söylüyor; klavyeyle aynı yerlere tablo görünümündeki bağlantılarla gidiliyor.

### Düzeltilenler

- Değerlendirme'de ve Pano'da bir kategoriye ya da işyerine tıklamak, seçili dönemin değil bütün zamanların
  işlemlerini açıyordu. Bağlantı artık kartın günlerini, hesaplarını ve türlerini taşıyor.
- Hesaplar'daki para akışında bir hesaptan bir harcama grubuna giden bant, grubun değil hesabın bütün alışverişlerini
  açıyordu. Birden çok türü ya da hesabı olan bir bantta da yalnızca sonuncusu süzülüyordu.
- Bir ekranın aşağısından açılan yeni ekran, önceki ekranın kaydırıldığı yerde açılabiliyordu. Artık sayfanın
  başından açılıyor.
- İşlemler'de bir grafiğin açtığı gider türleri "Tür: 3/12" yerine "Tür: Giderler (harcama, iade, faiz ve ücret)"
  diye yazıyor.

## [0.9.3] — 2026-11-03 — Düzeltmeler

Harcamalar Claude'la kategorilere ayrılırken bulunan üç hata düzeltildi.

### Düzeltilenler

- Kıraathaneler artık kira sayılmıyor. Hazır kurallardaki "KİRA" kelimesi, kelimenin başı tuttuğu için
  "KIRAATHANESİ"ni de kiraya yazıyordu; "KİRALAMA" (araç ya da eşya kiralama), "KİRAZ" ve "KIRAÇ" da kiraya
  düşebilirdi. Kira artık yalnızca kelimenin kendisinden ve eklerinden (KİRASI, KİRAYI…) bulunuyor; kıraathaneler
  Kafe & Kahve'ye gidiyor. Kendi kurallarınıza yazdığınız ev sahibi değişmiyor.
- Bir hesabın bakiyesi artık her yerde aynı. Dökümün son günlerinde yapılan ve dökümde henüz görünmeyen bir işlem,
  ör. dökümü indirdiğiniz gün yaptığınız bir transfer, Değerlendirme'de bakiyeye ekleniyordu. Hesaplar'da, Şu an'da,
  Döviz'de, net varlıkta ve nakit akışı öngörüsünün başlangıcında ise eklenmiyordu. Artık hepsinde ekleniyor ve döküm
  gelince satırıyla eşleşip kesinleşiyor.
- Değerlendirme'deki "Ekstre gelmeden işlenen dekontlar" bulgusu, kendi hesaplarınız arasındaki bir transferin iki
  ucu da dekontla geldiğinde boş bir liste yazıyordu ("… şimdiden işlendi (…): ."). Artık transfer tek işlem
  sayılıyor ve taşınan tutarla yazılıyor: "1 işlem … kendi hesaplarınız arasında 12.500 TL".

## [0.9.2] — 2026-11-03 — İplikçi Nedim'in sözleri

İplikçi Nedim artık paranızın durumunu kendi sözleriyle söylüyor: Pano'nun en üstünde ve tarayıcı eklentisinin
penceresinde, yüzü paranın durumuna göre renk alarak.

### Eklenenler

- Pano'nun başında, sade ve ayrıntılı görünümde, İplikçi Nedim'in yüzü ve dizideki sözlerinden biri bir konuşma
  balonunda duruyor. Sözün altında hangi durum için söylendiği yazıyor, ör. "Ekim 2026'da gelen paranın %49'u elde
  kaldı."
- Söz paranın durumuna göre seçiliyor. Önce en acil durum geliyor: hesabın eksiye düşeceği öngörülüyorsa, ay eksiyle
  kapandıysa, borçlar paradan fazlaysa, bu ay her zamankinden fazla harcanıyorsa, az kaldıysa. Ardından iyi haberler
  ve öbür notlar geliyor: en iyi ay, döviz geliri, tasarruf, gelen maaş, iyi bir ay, zam, faiz ve ücretler.
- Söz her gün değişiyor. "Başka bir söz" o gün doğru olan öbür durumların sözlerini sırayla gösteriyor.
- Yüz durumun rengini alıyor: iyi giderken logonun kendisi (yeşil), dikkat isteyen durumda turuncu, kötü durumda
  kırmızı, henüz bilgi yokken gri. Belge yokken İplikçi Nedim "İsa Muhammed aşkına bilmiyorum." diyor.
- Tarayıcı eklentisinin penceresinde (eklenti 0.6.0) başlıktaki logo aynı rengi alıyor, söz altındaki balonda
  duruyor. Sözün cümlesi tutar, hesap ya da ad içermiyor. Eklenti eşleşmemişse ya da İplikçi Nedim çalışmıyorsa söz
  görünmüyor.
- Sözlerin listesi ve her birinin hangi durumda söylendiği "İplikçi Nedim'in sözleri" belgesinde.

## [0.9.1] — 2026-11-03 — Enflasyondan arındırma

Ayarlar'daki EVDS kartı artık özelliğin ne işe yaradığını bir örnekle anlatıyor, açık mı kapalı mı olduğunu söylüyor ve
anahtarın alınacağı sayfalara götürüyor. TÜFE de TÜİK'in güncel serisinden alınıyor.

### Değişenler

- Kartın adı "Enflasyondan arındırma (EVDS)" oldu. Kart şunları gösteriyor:
  - "Ne işe yarar?": fiyatlar arttığı için harcamanın artmış görünebileceğini ve Değerlendirme'nin karşılaştırmayı
    aynı ayın fiyatlarıyla nasıl yaptığını sade sözlerle, bir örnekle anlatıyor.
  - Özellik anahtar girilene kadar kapalı ("Kapalı"), anahtar kabul edilince açık ("Açık"). Açıkken Değerlendirme'ye
    bir bağlantı var.
  - "Anahtar nasıl alınır?": EVDS'nin giriş sayfasına (üye olmak için "Kayıt" sekmesi) ve kılavuzlarına giden
    bağlantılar yeni sekmede açılıyor; anahtarın kopyalanacağı yer adım adım yazıyor.
- Anahtar kaldırılınca özellik gerçekten kapanıyor: Değerlendirme saklanan TÜFE aylarını kullanmayı bırakıyor ve
  anahtarın girilebileceğini söylüyor. Aylar silinmiyor; anahtar yeniden girilince hemen geri geliyor.

### Düzeltilenler

- TÜİK, TÜFE'yi 2026'da 2025=100 bazına taşıdı. EVDS 0.9.0'ın istediği 2003=100 serisini (`TP.FG.J0`) arşive aldı ve
  bu seri Ocak 2026'da bitti; bu yüzden anahtar girilse bile 2026'nın ayları hiç gelmeyecekti. TÜFE artık TÜİK'in
  güncel genel endeksinden (`TP.TUKFIY2025.GENEL`) alınıyor. Bu seri EVDS'de Ocak 2005'ten bugüne kadar var.
- Bir seri yine durursa (en yeni ay, TÜFE'nin yayım takvimine göre çoktan gelmiş olmalıysa) Ayarlar "TÜFE'nin yeni
  ayları gelmiyor" diye uyarıyor. Bekleyen karşılaştırma sessizce eskimiyor.

## [0.9.0] — 2026-11-03 — Aşama 8: Döviz

Dövizli hesaplar, net varlık ve kur farkları artık resmî kurlarla hesaplanır: TCMB'nin her iş günü yayımladığı kurlar,
TCMB'ye ulaşılamayan günlerde ECB'nin referans kurları. İnternet yokken bankaların belgelerindeki kurlarla çalışmaya
devam eder.

### Eklenenler

- Kurlar her gün 16.30'da TCMB'den alınır. Belgelerinizin kapsadığı günlerin geçmiş kurları bir kez, kendiliğinden
  çekilir: arka planda, iki dakikalık parçalar hâlinde, servisin öteki işlerini bekletmeden. Hafta sonları hiç, kur
  yayımlanmayan tatil günleri bir kez sorulur. TCMB'ye ulaşılamayan günlerin kuru ECB'nin referans kurlarından,
  Frankfurter üzerinden alınır.
- Döviz ekranı dört bölüm oldu:
  - **Varlıklar:** net varlık TL, euro, dolar ve gram altın karşılıklarıyla; her birimin yanında kullanılan kurun
    kaynağı ve günü ("TCMB 13.11.2026 döviz satış kuruyla").
  - **Kurlar:** her para biriminin en yeni döviz alış ve satış kuru, günü ve kaynağı; son 90 günün kuru grafik ve tablo
    olarak; ayrıntılı görünümde belgelerin yazdığı bütün kurlar.
  - **Kur makası:** son 12 ayda kendi hesaplarınız arasındaki döviz alım-satımları ve yurt dışı kart harcamaları,
    her biri aynı günün TCMB kuruyla karşılaştırılarak; bankaların kurunun size toplam maliyeti ve ilgili işlemler.
  - **Döviz geliri:** döviz hesaplarınıza gelen gelirin bugünkü kurla TL karşılığı, dövizin TL'ye çevrildiği günler
    ve kurun aylık gelire etkisi ("EUR/TRY %5 düşerse aylık gelir … TL azalır"). Ortalama yalnızca tam aylardan.
- Sistem ekranında "Döviz kurları" kartı: hangi sağlayıcının hangi güne kadar kuru olduğu, kaç günün kurunun saklandığı,
  geçmişte eksik gün olup olmadığı, son deneme ve hatası; "Kurları şimdi al" ve "Eksik günlerin kurlarını al".
- İsteğe bağlı enflasyon verisi: Ayarlar'daki "Enflasyon verisi (EVDS)" kartına TCMB EVDS'den aldığınız API anahtarını
  girerseniz aylık TÜFE alınır ve Değerlendirme'deki "Harcamalar nasıl değişti" kartı harcamanızı enflasyondan
  arındırılmış olarak da gösterir: iki dönemin ortalaması aynı ayın fiyatlarıyla, hangi aylardan hesaplandığıyla.
  Anahtar yalnızca bu bilgisayarın anahtar zincirinde saklanır; EVDS'ye yalnızca TÜFE'nin seri kodu ve tarih aralığı
  gider.
- Komut satırı: `iplikci kurlar al [--gecmis]` ve `iplikci kurlar durum` (geliştiriciler için; her şeyin arayüzde de
  yolu var).

### Değişenler

- Döviz hesaplarının satırları, belgede o işlemin kendi kuru yoksa o günün TCMB döviz alış kuruyla TL'ye çevrilir
  (hafta sonu ve tatilde önceki iş gününün kuru); daha önce belgelerdeki en yakın kur kullanılıyordu. Bu yüzden
  dövizli hesabı olanların TL toplamları biraz değişebilir.
- Varlıklar döviz alış, borçlar döviz satış kuruyla değerlenir. Net varlığın euro ve dolar karşılığı satış kuruyla
  bulunur.
- Bir kurun gösterildiği her yerde kaynağı da yazar: işlemin yan panelinde, Akış'ta, hesap sayfasında ve Döviz'de
  ("TCMB'nin 13.11.2026 kuruyla", "13.11.2026 belgesindeki kurla").
- Kuru bilinmeyen bir varlık için "Kuru belgelerde yok" yerine "Kuru bilinmiyor" yazar.

### Güvenlik

- Kur sağlayıcılarına yalnızca tarih, EVDS'ye yalnızca seri kodu ve tarih aralığı gider; hepsi `egress` modülünden ve
  ADR-0009'un izin listesinden geçer. Yönlendirme izlenmez, yanıt 1 MB ile sınırlıdır; belge türü ya da varlık bildiren
  XML okunmaz.
- EVDS anahtarı yalnızca girilir: bir kez denenir, kabul edilirse anahtar zincirine yazılır ve bir daha gösterilmez.
  Anahtar girilmemiş bir veri klasörü anahtar zincirini bunun için hiç okumaz.

## [0.8.0] — 2026-11-03 — Aşama 7: MCP

Claude, paranıza dair sorularınızı İplikçi Nedim'deki verilere ve belgelere bakarak yanıtlar. Bağlantı bu bilgisayarda
kalır: Claude yalnızca bu bilgisayardaki servise bağlanır.

### Eklenenler

- "Claude bağlantısı" ekranı (Kurulum altında), Claude'u terminal açmadan bağlamak için:
  - Claude Code'a claude-SAK'ın web panelinden eklemenin üç adımı ve kopyalanacak yapılandırma. Komut satırı
    kullananlar için claude-SAK'ın ve Claude Code'un komutları da orada.
  - Claude Desktop'ın ayar dosyasına eklenecek bölüm.
  - MCP adresi ve "Göster" düğmesinin arkasında API belirteci, başka bir MCP istemcisi için.
  - Claude'a giden yanıtlarda neyin gizleneceği: hiçbir şey, hesap numaraları ya da hesap numaralarıyla birlikte kişi
    adları. Tutarlar ve tarihler her zaman görünür.
- Claude Code'un yapılandırmasında belirteç yoktur: Claude her bağlantıda onu İplikçi Nedim'in başlık yardımcısıyla
  anahtar zincirinden okur.
- Claude Desktop İplikçi Nedim'i kendisi başlatır. Servis çalışıyorsa sorular servise gider. Servis kapalıyken yalnızca
  okuyan araçlar çalışır; servis açılınca sorular yine ona gider.
- Yeni araçlar: işlemlerde ve belgelerin metninde arama; bir işlemin belgesi, belgedeki yeri, kuralı ve eşleşmeleri;
  bir belgenin bilgileri ve metni; işlenmeyen belgeler ve nedenleri; bir belgeyi yeniden okutma; anlık akış; hesap
  haritası ve türlere göre toplamlar; net varlık; belgelerdeki kurlar; bir işleme not, etiket ya da düzeltme.
- Claude'un okuyup dayanabileceği kaynaklar: belgeler (metinleriyle; PDF'lerin sayfaları resim olarak), ay
  kapanışları ve hesap sayfaları.
- Hazır istemler: Aylık değerlendirme, Abonelik denetimi, Bu ay neden fazla harcadım?, Ay kapanışı, İşlenmeyen belgeyi
  incele.
- Claude'un her araç çağrısı ve kaynak okuması denetim kaydına yazılır: neyi çağırdığı ve sonucu; verdiği değerler
  yazılmaz.

### Değişenler

- Bir şeyi değiştiren araçlar önce planı gösterir ve hiçbir şeyi değiştirmez: kural eklemek, bir ödemeyi bitti saymak,
  kural dosyasını yazmak, bildirim kuralları, bir işleme not ve bir belgeyi yeniden okutmak. Siz onaylayınca Claude aynı
  aracı planın numarasıyla çağırır; plan bir kez uygulanır, o arada değişen bir şeyin üstüne uygulanmaz.
- MCP sunucusu resmî MCP SDK'sıyla yeniden yazıldı ve servisin içinde, `/mcp` adresinde çalışır. MVP'nin 16 aracı ve
  Aşama 4–5'te gelenler aynı adlarla kalır. Her aracın Türkçe adı ve bir şeyi değiştirip değiştirmediğini söyleyen
  işaretleri var.

### Güvenlik

- Servisin talimatları ve her belge metninin başı, belgelerdeki yazının veri olduğunu, talimat olmadığını söyler.
- MCP'ye yalnızca API belirteciyle girilir; tarayıcının oturumu oraya geçmez.
- Maskeleme açıkken PDF sayfalarının resmi verilmez: resimdeki numara gizlenemez.

## [0.7.6] — 2026-11-03 — Bildirimler belgelerle denetlendi

Kutudaki bildirimler gerçek belgelerle tek tek karşılaştırıldı; yanlış çıkanların kuralları düzeltildi.

### Düzeltilenler

- Elle indirilen eski belgeler aylar önceki zamları yeni gibi bildiriyordu. Zam artık yalnızca yeni fiyatı
  kesinleştiren ödeme son 45 günün içindeyse bildirilir: aylık bir ödemede yeni fiyatın ikinci ödemesi, yıllık ya da
  altı aylık bir ödemede tek ödemesi. Eski zamlar Düzenli ödemeler ekranında yine görünür.
- Dolarla ya da avroyla faturalanan bir ödemenin TL tutarı kurla her ay oynar. Bu artık zam sayılmaz: fiyat, kart
  ekstresinin TL tutarın yanına yazdığı döviz tutarıyla karşılaştırılır.
- Ek hesap (KMH) eksiye düşünce "Hesap eksiye düşecek" uyarısı gelmez: eksi bakiye kullanılan kredidir.
- Kendi hesaplarınızdan düzenli para aktardığınız bir hesap için de bu uyarı gelmez. Öngörü bu aktarmaları saymadığından
  hesap kâğıt üzerinde eksiye iniyordu. İki durumda da öngörünün notu nedenini yazar.

### Eklenenler

- Hesaplarınızın toplamı öngörüde eksiye düşerse "Hesap eksiye düşecek" uyarısı gelir: "Hesaplarınızın toplamı: …".

### Değişenler

- "Abonelik zammı" kuralının adı "Düzenli ödeme zammı" oldu: faturalar ve kira da düzenli ödemedir. Bildirimin metni
  "Bir düzenli ödeme zamlandı" der.

## [0.7.5] — 2026-11-03 — Belge ekle ekranı

### Eklenenler

- "Belge ekle" ekranı: bankadan elle indirilen belgeler buradan, bir klasörün tamamı ya da tek tek dosyalar olarak
  eklenir. Sade görünümün menüsünde ve Pano'nun "Ne yapmalısınız?" kartında da yeri var. Ekran ne yapılacağını adım adım
  anlatır.
- Sürüklenen bir klasörün içindekilerin hepsi, alt klasörleriyle alınır; önceden tarayıcı klasörün içini vermiyordu.
  Gizli dosyalar (`.DS_Store` gibi) atlanır.

### Değişenler

- Servis dosyaları okurken bunu söyler. Sonunda kaç belgenin arşive alındığı ve kaçının zaten arşivde olduğu yazar,
  Belgeler'e ve Pano'ya giden bağlantılarla. Onay düğmesinin adı "Arşive al".

## [0.7.4] — 2026-11-03 — Belgeler içeriğinden tanınır

Bankadan elle indirilen belgeler bir klasör olarak verilebilir: dosya ve klasör adlarına bakılmadan her belge
içeriğinden tanınır, yeni olanlar arşive girer, arşivdekilerle aynı olanlar eşleşir (K24).

### Eklenenler

- Bir dosyanın türü adından ya da uzantısından değil, içeriğinden anlaşılır (PDF, Excel, HTML, XML, ZIP, e-posta).
  Uzantısı olmayan ya da yanlış olan bir indirme de alınır. Belgeler'de dosya seçerken her dosya seçilebilir.

### Düzeltilenler

- Aynı hesabın tarihleri çakışan iki hareket listesi, çakışan günlerin hareketlerini iki kez sayıyordu. Elle indirilen
  listelerde bu sık olur. Artık her gün tek listeden sayılır: o gün daha çok hareketi olandan, eşitse daha ileri tarihe
  uzanandan. Bir hareketin notları hangi listeden sayılırsa sayılsın ona bağlı kalır.

### Değişenler

- Belgeler'deki yükleme kartı, dosya ve klasör adlarının önemli olmadığını söyler.

## [0.7.3] — 2026-11-03 — Güncellemeler açık sekmeye ulaşır

### Düzeltilenler

- Arayüzün güncellemeleri açık bir sekmeye hiç ulaşmıyordu. Yeni sürüm indiriliyor, ama uygulamanın bütün sekmeleri
  kapanana dek bekliyordu; sayfayı yenilemek de yetmiyordu. 0.7.2'deki "sayfa bir kez kendiliğinden yenilenir"
  düzeltmesi de bu yüzden devreye girmedi. Yeni sürüm artık hemen devreye girer ve açık sayfa kendini bir kez yeniler.
  Sekme her öne geldiğinde de yeni bir sürüm olup olmadığına bakılır. Eski bir sürümde kalmış sekme bir kez
  yenilenince yeni sürüme geçer (gerekirse Shift'le: ⌘⇧R).

## [0.7.2] — 2026-11-03 — Pano resimlerle anlatır

Arayüz hâlâ karışık bulundu ve paranın grafiklerle okunması istendi. Sade görünümde Pano finans bilgisi
gerektirmeden, resimlerle ve bir sonraki adımla anlatır; menü sık kullanılan ekranlara indi.

### Eklenenler

- Pano'nun sade görünümü baştan yazıldı: paranızı finans bilgisi gerektirmeden, resimlerle ve yukarıdan aşağı bir
  hikâye gibi anlatır.
  - Son kapanan ayda gelen, giden ve kalan para, gelenin ne kadarının harcandığını gösteren bir çubuk ve bir cümlelik
    hüküm ("Gelen paranın %49'u elinizde kaldı. İyi gidiyor."; az kaldıysa ya da gelirden fazla harcandıysa o söylenir).
  - Hesaplardaki para, neye dayandığıyla: son belgeler, düşülen kart borçları, bakiyesi bilinmeyen hesaplar.
  - Aylara göre gelen (yeşil, çizginin üstünde) ve giden (turuncu, altında) çubuklar; eksik aylar soluk.
  - O ay paranın nereye gittiği; her harcama türü işlemlerine götürür.
  - Önümüzdeki 30 günde hesaptaki paranın tahmini çizgisi: eksiye düşecekse uyarır, yetiyorsa en düşük günü söyler;
    yanında yaklaşan ödemeler ve gelirler.
  - "Ne yapmalısınız?": açık uyarılar düzeyiyle ve Değerlendirme'nin önerdiği adımlar.
  - Her grafiğin üstünde nasıl okunacağı yazar; her grafiğin tablosu da var. Ayrıntılı görünüm kartlarıyla kaldı.

### Değişenler

- Sade görünümde menü sık kullanılan yedi ekranı gösterir: Pano, Hesaplar, İşlemler, Düzenli ödemeler, Takvim,
  Değerlendirme ve Yapılacaklar. Diğerleri "Diğer ekranlar" altındadır; açık olan ekran oradaysa bölüm kendiliğinden
  açılır. Ayrıntılı görünümde menü gruplarıyla eskisi gibi.
- Pano'nun yaklaşan ödemeler ve veri tazeliği kartları yalnızca ayrıntılı görünümde, tablolarıyla.
- Logo, depo kökündeki `iplikci_nedim_logo_transparent/` klasöründen simgeleri çizen betiğin yanına,
  `packaging/logo/`'ya taşındı; `packaging/icons.py` simgeleri oradan çizer, simgeler değişmedi.

### Düzeltilenler

- Bir güncellemeden sonraki ilk açılışta arayüz eski sürümü gösteriyordu. Artık yeni sürüm gelince sayfa bir kez
  kendiliğinden yenilenir.

## [0.7.1] — 2026-11-02 — Arayüzün sadeleşmesi

Aşama 6'nın ardından arayüz sadeleşti, hesap kitabı daha açık anlatır oldu ve bütün ekranlar demo çalışma alanında
elle yeniden denendi. Tarayıcı eklentisinin araç çubuğundaki düğmesi arayüzü tek tıkla açıyor.

### Eklenenler

- Logo her yerde: arayüzün simgeleri, eklentinin simgeleri ve kurulum paketlerinin simgeleri
  `iplikci_nedim_logo_transparent/`'tan çizilir (`packaging/icons.py`); servisin giriş sayfaları da logoyu gösterir.
- Tarayıcı eklentisinin penceresi: araç çubuğundaki düğme durumu, "İplikçi Nedim'i aç", "Şimdi denetle" ve
  "Eşleştirme ve ayarlar"ı gösterir. "İplikçi Nedim'i aç" açık bir arayüz sekmesini öne getirir; yoksa eşleşmiş
  eklenti servisten tek kullanımlık bir giriş bağlantısı alır ve arayüzü oturum açılmış olarak açar
  (`POST /api/bridge/login-link`, ADR-0019). Eklentinin ayarlar ve doğrulama sayfaları yenilendi (eklenti 0.5.0).
- Pano'nun ilk satırı dört rakamı bir bakışta gösterir: net varlık, bu ay harcanan (tipik ayla), yedi gün içinde
  ödenecek ve bekleyen işler; her biri ilgili ekrana götürür.
- Uzun ekranlar bölümlere ayrıldı, seçilen bölüm adreste (`?bolum=`): Akış (olaylar, şu an, yaklaşanlar),
  Değerlendirme (özet, harcamalar, gelir, varlık ve borç, önümüzdeki aylar, işlemler ve veriler), Bildirimler (kutu,
  kanallar, kurallar, teslim kaydı), Kurallar (işyeri kuralı, kategoriler, biten ödemeler, gereklilik, dosya) ve hesap
  sayfası (özet, düzenli ödemeler ve ücretler, işlemler).
- "Nasıl hesaplandı?": toplamların ve akışların nasıl hesaplandığı katlanır, ayrıntılı görünümde açık gelir.

### Değişenler

- Uygulama kabuğu: üst çubukta logo, bildirim zili ve görünümle temayı birlikte seçen tek menü; menü simgeli ve
  gruplu, telefonda açılır kapanır.
- Abonelikler ekranının adı "Düzenli ödemeler": kira ve faturalar da orada. Kartlarda aylık tutar en büyük rakam,
  "İptal ettim…" kartın altında sade bir düğme.
- İşlemler: süzgeçler "Süzgeçler" düğmesinin altında, arama ve hızlı seçimler hep açık; toplamlar giren, çıkan, fark
  ve harcama olarak ayrı kutularda, geçici ve ekstrede görünmeyen satırlar adıyla.
- Akış'ın sade görünümünde bir belgenin "geldi" olayı, okunmasının sonucu da listedeyse ayrıca gösterilmez; olaylar
  daha sıkı satırlarda.
- Hesaplar: bir hesap toplama girmiyorsa nedeni yazar (bakiyesi belgelerde yok ya da TL karşılığı bilinmiyor);
  "Birlikte göster" kutusu adıyla görünür; eksik aylar uyarı olarak işaretlenir.
- Belgeler: yükleme alanı geniş ekranda tek satır, belgeler tek çerçeveli bir liste.
- Çok küçük oranlar "%1'den az" diye yazılır; değerlendirmenin bütçe cümlesi önce bugünkü ayı, sonra öneriyi söyler.

### Düzeltilenler

- Kapanmamış bir geçmiş ayın (belgesi eksik, ekstresi beklenen ya da kontrol isteyen) rakamları Ay sonu listesinde
  eksik olabileceğini söyler; ay sayfasının "Son 12 ayın gideri" en yüksek ve en düşük ayı yalnızca kapanmış aylardan
  seçer, diğerlerini adıyla anar. Demo'da Temmuz, dökümünün ilk günleri eksik olduğu için "en düşük ay" görünüyordu.
- Sistem ekranı hiç kurulmamış bir e-posta hesabını "IMAP" diye göstermez, "Henüz kurulmadı" der ve Ayarlar'a
  götürür; Ayarlar hangi yolun seçileceğini söyler.
- Nakit akışı öngörüsü, bakiyeyi yazan belgenin gününden bugüne kadarki günlerde beklenenleri de sayar: dökümü 31
  Ekim'de biten bir hesapta 1 Kasım'da beklenen maaş öngörüden düşüyordu (demo'da en düşük bakiye 164.452,38 TL yerine
  204.452,11 TL). Öngörünün notu o günleri ve rakamları yazar; akışın olayları da aynı başlangıcı kullanır.
- Bekleyen bir fatura, satıcısının düzenli ödemesiyle takvimde ikinci bir ödeme olarak görünmez: fatura o ödemenin
  tutarını verir, ödeme kendi gününde kalır.
- Hiçbir belgenin henüz ulaşmadığı bir ay "hiç harcanmadı" ya da "günlerin %0'ı kapsandı" diye anlatılmaz; Pano,
  Akış ve Hesaplar belgenin henüz gelmediğini söyler.
- Faiz ve ücret uyarısı türüne göre öğüt verir: transfer ücretine "borcu zamanında ödeyin" denmez. Hesaptan ödenen
  büyük bir alışveriş kart borcu sayılmaz. Bulgular arayüzün ekranlarını adıyla anar ("Düzenli ödemeler ekranında
  İptal ettim…", "Döviz ekranındaki Varlıklar ve borçlar tablosu"); harcama eğilimi iki pencerenin ortalamasını
  adıyla yazar.
- Gereksiz sayılan bir abonelik bütçede iki kez düşülmez; bütçenin satırı "Gereksiz harcamalar (faiz, banka
  ücretleri…)" adını aldı.
- Kısmen kapsanan bir ayda görünmeyen maaş, ödeme gününün kaymasına bağlanmaz: dökümün kapsamadığı günlerde yatmış
  olabileceği yazılır. Pano'nun kapanış tablosu, kapanmamış bir ayın gelirinin neden eksik olabileceğini gösterir.
- Kural önizlemesi yalnızca gerekliliği değişen satırları "X → X" diye kategori değişimi gibi göstermez.
- Ay sonunda eksik bir döküm, MVP'nin "Gelen Belgeler" klasörüne değil, Belgeler ekranından yüklenir.
- Küçük paylar bütçede ve kategorilerde "%1'den az" yazılır; yalnızca eksik bir ayda harcanan kategorinin aylık
  ortalaması 0,00 TL değil "yalnızca eksik ayda" diye görünür.

## [0.7.0] — 2026-11-02 — Aşama 6: Arayüz

Arayüz tamamlandı: on beş ekran sırayla, açık ve koyu tema, sade ve ayrıntılı görünüm, çeviri altyapısı ve kurulabilir
uygulama (PWA). MVP raporunun bölümleri Değerlendirme'de ve yanındaki ekranlarda. macOS, Windows ve Linux için kurulum
paketleri var (imzasız, K22): uygulama ilk açılışta servisi kaydeder ve kurulum sihirbazını açar; servis Ayarlar'dan
durdurulur, yeniden başlatılır, geri yüklenir ve kaldırılır. Her ekran demo çalışma alanında, iki temada, telefon
genişliğinde ve axe denetimiyle uçtan uca sınanır.

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
- Hesaplar ekranı (`/hesaplar`): hesaplar gruplarıyla, bakiyeleri, belgelerinin ulaştığı gün ve bu ayki giriş ve
  çıkışlarıyla; hesaplar arası para akışı diyagram ve tablo olarak, bir akış bandından satırlarına gidilir. Hesap
  sayfası (`/hesaplar/:id`): durum, türüne göre ayrıntılar (kartın ekstreleri ve taksitleri, ek hesabın maliyeti,
  mevduatın getirisi, döviz ve altının değeri, portföy, kredi), belgelerin kapsamadığı günleri boş bırakan günlük
  bakiye, son 12 ay, faiz ve ücretler, hesaptan geçen düzenli ödeme ve gelirler, satırlar; hesaba kendi adınızı
  verebilirsiniz.
- Belgeler ekranı (`/belgeler`): saklanan her belge türü, hesabı, dönemi, durumu ve geliş yoluyla; tam metin arama,
  tür, geliş yolu, hesap ve banka süzgeci adreste; okunamayanlar ayrı bir sekmede, nedenleri, asılları ve yeniden
  okuma düğmesiyle. Görüntüleyici (`/belgeler/:id`): PDF sayfa sayfa, seçilen satırın kutusuyla; tablo, satırı
  işaretli; e-postanın metni, satırın sözcükleri işaretli, özgün görünümü yalnızca kum havuzlu bir çerçevede; yanında
  okunan satırlar, ekstrenin denetimleri, nasıl geldiği ve ekleri; aslını indirme, yeniden okuma ve sorulduktan sonra
  çöp kutusuna taşıma. Satır panelindeki "Belgede aç" buraya gider.
- Abonelikler ekranı (`/abonelikler`): süren aylık ödemelerin bir aya düşen toplamı, dönemsel ödemeler dönem başına
  (aya çevrilmeden), bitenler ve iptal edilenler, düzenli gelirler ve taksiti kalan kart alışverişleri; her seride
  durumu, tutarı, son ve sonraki ödemesi ve fiyat değişimi. Serinin paneli dayandığı ödemeleri satırlarına
  bağlantılarıyla listeler. "İptal ettim" ayı seçtirir, kural dosyasının farkını gösterdikten sonra `_biten`'e yazar;
  "Yeniden bekle" bunu geri alır. İptalden sonra gelen ödeme ekranın başında uyarı olur.
- Takvim ekranı (`/takvim`): önümüzdeki 60 günde beklenen ödemeler ve gelirler, her biri serisine, faturalara ya da
  hesabına giden bağlantısıyla; her TL hesabın gün gün bakiye tahmini çizgi grafik ve tablo olarak, eksiye düştüğü gün
  işaretli; varsayımlar, hiçbir hesaba düşülmeyen kalemler ve öngörüye girmeyen hesaplar. İkisi de "Tahmin" etiketli.
- Değerlendirme ekranı (`/degerlendirme`): MVP raporunun kartları, dönem seçenekleri ve İşlemler süzgeçleriyle;
  süzgeçler adreste durur. Özet kutuları ve toplama girmeyenler; öne çıkanlar satırlarıyla, aylık etkisiyle adımlar
  ve bütçe; aylık giderler grup ve gereklilik başına ısı tablosuyla; alışkanlıklar; gelir ve gider; üç aylık tahmin
  kalem kalem; kategoriler ve en çok harcanan yerler, her biri satırlarına giderek; büyük tek seferlikler ayrı tutulan
  eğilim ve olağan dışı hareketler; net varlık, ay sonu, kart borcu ile ek hesap kullanımının pencere boyunca nasıl
  değiştiği, düzenli ödemeler ve verinin kapsamı: her hesabın ekstrelerinin ve hesap dökümlerinin ay ay kapsadığı
  günler, MVP raporundaki gibi bir ızgara ve tablo olarak. Belgelerin yalnızca bir kısmını kapsadığı ay soluk çizilir,
  "eksik" yazar ve hiçbir ortalamaya girmez; rapor ve Excel dosyası başlıktan indirilir.
- Ay sonu ekranları (`/ay-sonu`, `/ay-sonu/:ay`): içinde bulunulan ay ve önceki on iki ay, durumlarıyla (sürüyor,
  eksik, kontrol gerekli, bekleniyor, kapandı) ve kapanışları bir cümleyle. Ayın sayfasında hesap başına kapanış ve
  neyin beklendiği ("19–31 Ekim ekstresi, kesim ~18.11"); iki ay da kapanmışsa önceki ve tipik ayla karşılaştırılan
  toplamlar; son on iki ayın harcaması; paranın gittiği gruplar ve en çok harcanan yerler, ayrıntılı görünümde
  gereklilik düzeyleri, bütün kategoriler ve yerler, her biri ayın satırlarına giderek; ödenen ve beklenen düzenli
  ödemeler, büyük alışverişler, geçici kayıtlar ve ekstrede görünmeyen dekontlar; ayların betiksiz sayfaları. Pano'nun
  kapanış kartı ve akışın ay olayları ayın sayfasına gider.
- Döviz ekranı (`/doviz`): net varlık TL, euro, dolar ve gram altın cinsinden, belgelerin kendi kurlarıyla; kuru
  belgelerde olmayan birim sıfır gösterilmez, nedeni yazar. Varlıkların para birimlerine dağılımı grafik ve tablo
  olarak; her varlık ve borç kendi biriminde ve TL karşılığıyla, ayrıntılı görünümde kuru, maliyeti ve kur farkıyla;
  belgelerin yazdığı kurlar, her birimin en yenisi ve hepsi.
- Bildirimler ekranı yeni düzende: sade görünümde her kart ne tuttuğunu bir cümleyle söyler (görülmemiş bildirimler,
  bildirimlerin gittiği yerler ve sessiz saat, Telegram'ın beklediği adım, açık kurallar, gidenler ve bekleyenler);
  ayrıntılı görünüm teslim kaydının tablosunu, her bildirimin olayını ve ilgili sayfasını, kanalların durumunu ve
  kuralların olay kodunu ekler. Telegram'ı kaldırmak ve kural silmek uygulamanın kendi onay penceresiyle sorulur.
- Kurallar ekranı (`/kurallar`): kategoriler gruplarının altında renkleri, gereklilik düzeyleri ve taahhüt kategorisi
  olup olmadıklarıyla; bitti denen ödemeler son ödeme aylarıyla, kullanıcının yazdığı yeniden beklenebilir;
  kategorisinden ayrı tartılan işyerleri kendi düzeyleriyle; kalıpları, kategorisi ve gerekirse kendi gerekliliğiyle
  yeni işyeri kuralı. Her değişiklik yazılmadan önce kaç satırı hangi kategoriden hangisine taşıyacağını, örnek
  satırları ve kural dosyasının farkını gösterir. Ayrıntılı görünüm kural dosyasının tamamını düzenletir ve önceki
  sürümlerini listeler.
- Yapılacaklar ekranı (`/yapilacaklar`): verinin eksiksiz ve doğru olmasını engelleyenler türlerine göre, önemleri ve
  ne anlama geldikleriyle; her madde sayıları ve penceresiyle, onu kapatacak tek tıklık adımlarla: "Kural ekle"
  Kurallar ekranını işyeriyle açar, "Belge yükle" yükleme panelini, "Yeniden oku" belgeyi yeniden okur, "Göster"
  satıra, faturaya ya da belgeye götürür, "Claude'a ver" isteği kopyalar. "Yok say" maddeyi listeden çıkarır, "Geri
  al" ile ya da yok sayılanların listesinden geri gelir. Panodaki sayı ekrana türüyle süzülmüş olarak götürür.
- Kurulum sihirbazı (`/kurulum`): veri klasöründen uzaktan erişime dokuz adım, her biri nerede durduğu ve ne
  istediğiyle; adım adreste durur (`?adim=`), sihirbaz yapılmamış ilk adımda açılır. Adlarınız ve şirket adlarınız;
  e-postanın yolu, ya tarayıcı eklentisi (klasöründen kurulup eşleştirilir) ya da uygulama şifreli IMAP hesabı (şifre
  yalnızca girilir, adres maskeli görünür); bankalar ve banka dışı göndericiler, eski belgeler, bildirim kanalları,
  servis ve uzaktan erişim. Hiçbir şey kurulmamışken (ilk açılış) arayüz Pano yerine sihirbazla açılır, oturumda bir
  kez.
- Ayarlar ekranı (`/ayarlar`): sihirbazın alanları her zaman değiştirilebilir (adlar ve şirket adları, e-postanın yolu
  ve okunmaya başlandığı gün, günlük yedeklerin kaç gün saklandığı). Şimdi yedek alınır ya da bir yedek geri yüklenir:
  önce ne olacağı söylenir, şu anki veri ayrı bir yedeğe alınır, bitince uygulama yeniden açılır. Servisin sürümü ve
  kaydı; durdurma, yeniden başlatma ve bilgisayardan kaldırma. Kaldırırken veri klasörü yalnızca istenirse çöp
  kutusuna taşınır ve uygulamanın kendisinin nasıl kaldırılacağı sisteme göre söylenir. Yeniden başlatma, geri yükleme
  ve kaldırma yalnızca bu veri klasörü için kayıtlı bir serviste açıktır.
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
- Hesapların ay ay kapsamı: her hesabın ekstrelerinin ve hesap dökümlerinin her ayın günlerinden ne kadarını
  kapsadığı (`GET /api/accounts/coverage`); dekont ve bildirimler hiçbir ayı kapsamaz.
- Ay sonu kapanışı ay ay ve bir ayın tamamı; döviz: belgelerin kendi kurları ve her birimde net varlık.
- Yapılacaklar listesi, her maddeyi kapatacak adımlarla; kategori kuralları okunur, önizlenir, değiştirilir.
- Kurulum sihirbazı ve Ayarlar API'si: adlar ve şirket adları, yedeklerin saklanma süresi, e-posta bağlayıcısı, IMAP
  hesabını tek girişle kurma ve unutma; sihirbazın adımları ve ilk açılış.
- Servisin günlüğü Sistem ekranından indirilir: kişisel olabilecek yollar, adlar, adresler, IBAN'lar ve uzun numaralar
  çıkarılmış.
- Dışa aktarımlar (rapor, CSV, Excel, ay sonu sayfaları) Sistem ekranında listelenir, indirilir ve istenince yeniden
  yazılır.
- Kurulum paketleri ([ADR-0017](docs/adr/0017-no-terminal-install.md)): macOS'ta `.dmg`, Windows'ta kurulum
  programı, Linux'ta AppImage. Pakette taşınabilir CPython 3.13 ve içine kurulmuş program vardır; derlenmiş arayüz ve
  tarayıcı eklentisi de içindedir. Kullanıcıda Python ya da uv gerekmez. Paketler bir sürüm etiketinde ya da
  istenince CI'da, her sistemin kendi makinesinde üretilir ve iki hafta saklanır; şimdilik imzasızdır (K22).
- Kurulan uygulama açılınca servisi kendi kopyası için kaydeder ve başlatır. Eski bir sürüm çalışıyorsa yeniden
  başlatır ve yeni servis yanıt verince arayüzü tek kullanımlık giriş bağlantısıyla açar; Linux'ta eski sürümlerin
  kopyalarını kaldırır. Disk görüntüsünden açılırsa önce Uygulamalar klasörüne taşınmasını ister. Sorunları sistemin
  kendi penceresinde söyler (`iplikci uygulama`).
- Servis arayüzden durdurulur, yeniden başlatılır ve bilgisayardan kaldırılır; veri klasörü yalnızca istenirse çöp
  kutusuna taşınır. Bir yedek arayüzden geri yüklenir: yedek hemen denetlenir, servis yeniden başlarken veritabanı
  açılmadan yerine konur, öncesi ayrı bir yedekte kalır. Yeniden başlatma, geri yükleme ve kaldırma yalnızca
  bilgisayarın bu veri klasörü için kaydettiği serviste yapılır: elle çalıştırılan bir servis başka bir klasörün
  kaydını silemez. API: `GET /api/service`, `POST /api/service/stop|restart|remove`, `POST /api/backups/{ad}/restore`.
- Tarayıcı eklentisi programla gelir; mağazaya çıkana dek paketlenmemiş yüklenir (K20):
  - Tarayıcı eklentisi ekranındaki "Eklenti klasörünü aç" eklentiyi veri klasörünün `extension/` klasörüne kopyalar
    ve dosya yöneticisinde gösterir.
  - Ekran klasörün yerini ve eklentiler sayfasının adresini kopyalatır, paketlenmemiş yüklemeyi adım adım anlatır.
  - Program güncellenince servis bir sonraki açılışında klasörü yeniler.
  - API: `GET /api/extension`, `POST /api/extension/folder`.
- CI: uçtan uca testler her push'ta, her ekran iki temada axe ile.

### Düzeltilenler

- Aynı anda yapılan iki ayar değişikliği birbirini silebiliyor, ayar dosyasını okunamaz bırakabiliyordu; değişiklikler
  artık kilitle sırayla yapılır.
- Bir belge, okunmaya başladığı andaki şirket adlarıyla okunup kaydedildiği andakilerle damgalanıyordu; arada eklenen
  şirket adı belgeyi hiç yeniden okutmuyordu. Analiz de okuma sürerken kaydedilen adları görmeden güncel sayılıyordu.
- Harcama kartları ortalamalara kısmen kapsanan ayları da katıyordu; artık yalnızca tam aylar sayılır, gün aralığı
  İşlemler ekranındaki gibi sayılır, tahminin düzenli ödemeleri dönem dışındaki bütün süzgeçlere uyar.
- CSV ve Excel dışa aktarımında formül gibi başlayan metin artık metin olarak yazılır.
- Kategori kurallarında aynı anda yapılan iki değişiklikten biri ötekinin eklediğini siliyordu; değişiklikler artık
  sırayla, her biri bir öncekinin bıraktığı dosyadan yapılır.
- Kurulum sihirbazının servis adımı, bilgisayarda başka bir veri klasörü için kayıtlı servisi de "tamam" sayıyordu.
- Olağan dışı hareketler `docs/domain/interpretation.md`'deki eşiklere uyar; kart aidatı için iade adımı önerilir.
- Olay akışı baştan açılınca bütün kaydı yeniden göndermez; son dakikanın olaylarını yeniden söyler.
- Bölünmüş bir satır her sayımda tek ödemedir: ay sonu, alışkanlıklar, en çok harcanan yerler, kart dönemi ve
  dekont bulgusu onu bir kez sayar; büyük alışveriş satırın bütününe bakar. Üç aylık tahmin, son ödemesi bölünmüş
  düzenli ödemeyi parçalarının paylarıyla gösterir; kategori, grup ya da gereklilik süzgeci yalnızca tuttuğu
  parçaları sayar.
- Bir kural satırın türünü bölünmeyen bir türe çevirince ya da tutar bir parçayı sıfıra indirecek kadar değişince
  bölme sessizce kayboluyordu; artık Yapılacaklar'da "Uygulanamayan bölme" çıkar, satır paneli uyarır ve bölmeyi
  kaldırma yolu sunar. Kural önizlemesi böyle satırların değişikliğini de gösterir.
- Bölünen ve sonra birleştirilen satırın panelinde kategori düzeltmesi yerine yeni bir bölmenin düzenleyicisi
  kalıyordu.
- Bölünmüş satırın kendisine verilen kategori ya da gereklilik görünmüyordu; artık reddedilir. Bir dekontun bölünmüş
  satırının parçalarına giden bağlantılar, dekontu ekstre gösterince ekstrenin aynı parçalarını açar.
- Windows'ta uygulama açılırken ve Ayarlar servisi denetlerken her seferinde bir konsol penceresi açılıp kapanıyordu.
- Türkçe kod sayfası olmayan bir Windows'ta uygulama her açılışta servisi yeniden kaydedip yeniden başlatıyordu;
  kullanıcı klasörünün adında ş, ğ, ı ya da İ varsa Ayarlar servisi bu veri klasörü için kayıtlı saymıyordu.
- Windows'ta arayüzden yeniden başlatılan ya da yedeği geri yüklenen servis bir sonraki oturum açılışına dek geri
  gelmiyordu: Görev Zamanlayıcı yalnızca başlayamayan görevi yeniden başlatır. Servis artık biterken görevi yeniden
  çalıştıracak bir yardımcı bırakır; yardımcı ve uygulamanın yeniden başlatması, biten sürecin işi bitmeden görevi
  çalıştırmaz.
- Eski bir kopya açılınca, daha yeni bir sürümün servisi çalışsa ya da veri klasörünü daha yeni bir sürüm açmış olsa
  da servisi kendine kaydediyor, Linux'ta yeni sürümün kopyasını da siliyordu. Artık yeni sürümün açılmasını ister ve
  yalnızca daha eski sürümlerin kopyalarını kaldırır; sürümler sayı olarak karşılaştırılır.
- Uygulamaya art arda iki kez tıklanınca iki açılış servisi aynı anda kaydedip başlatabiliyordu; Windows'ta ikincisi
  birincinin başlattığı servisi durduruyordu. Açılışlar artık sırayla yürür.
- Linux'ta zenity ya da kdialog olmayan bir masaüstünde, uygulamanın açılırken söylediği sorun ve tarayıcı
  açılamayınca verdiği bağlantı hiç görünmüyordu; artık kapatılana dek kalan bir bildirimle söylenir.
- Başka bir diskin Uygulamalar klasörüne konan Mac uygulaması da "önce Uygulamalar klasörüne taşıyın" diyordu.
- Linux'ta Python'u olmayan bir sürüm kopyası (yarım kalmış ya da kısmen silinmiş) AppImage'ın her açılışını sessizce
  bozuyordu; aynı anda iki açılış birbirinin kopyasını silebiliyordu. Kopya artık her açılışın kendi klasörüne yapılıp
  bitince yerine konur, Python'u olmayan kopya yeniden yapılır, kopyalanamazsa sorun masaüstünün penceresinde
  söylenir.
- Linux'ta programın kopyaları veri klasörünün içindeydi (`~/.local/share/iplikci/app`): veri klasörünü çöpe atan
  kaldırma çalışan programı da götürüyor, veri klasörünü kenara almak servisi bozuyordu. Kopyalar artık
  `~/.local/lib/iplikci/<sürüm>` klasöründedir; eski yerdekiler yeni sürüm ilk açıldığında kaldırılır.
- Windows güncellemesi, arka plan servisi durmasa da sürüyor ve çalışan programın dosyalarını değiştirmeye
  kalkışıyordu; artık durur ve nedenini söyler.
- Yapılacaklar ve Pano'nun belge uyarıları hesapları bankanın adıyla anıyordu; artık kullanıcının verdiği adla anar.
- İlk Gmail taraması sürerken akışın geçmişin bir parçasından çıkardığı uyarılar masaüstüne gidiyordu: henüz okunmamış
  gelirsiz bir tahmin "Hesap eksiye düşecek" diyordu. E-posta geçmişi baştan okunurken bildirimler artık yalnızca
  uygulamanın kutusuna düşer; eklentide ilk tarama bitene, IMAP'te geçmiş sonuna dek okunana kadar.
- Arayüz açıkken durdurulan ya da yeniden başlatılan servis, açık olay akışını beş saniye bekleyip kesiyor ve günlüğe
  hata yazıyordu; akış artık servis dururken kendisi kapanır.
- Yarıda kalan bir eklenti derlemesi programın taşıdığı eklentiyi yarım bırakabiliyor, paket yalnızca bildirgeye
  bakıp yine de üretiliyordu. Derleme artık kendi klasöründe yapılıp bütün olarak yerine konur; paket eklentinin her
  dosyasını derlemeden önce ve kurulan kopyada denetler.

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
