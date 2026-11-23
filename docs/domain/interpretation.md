# Yorum ve ay sonu kuralları

Kaynak: MVP'nin `CLAUDE.md` dosyası (2026-10-31), kişisel bilgilerden arındırılmış ve V1 eklemeleriyle
genişletilmiştir. Kod adları MVP'dekilerdir (`insights.py`, `month_end.py`).

## İlke

Kullanıcı yalnızca toplamları değil, yorumu ve stratejiyi istiyor. Kullanıcı bir yorumun yanlış olduğunu söylerse
("X bitti", "Y sürekli değil") şöyle davranılır:

1. Belgelerin ne gösterdiğine bakılır ve kullanıcıya söylenir.
2. Kural genel olarak düzeltilir.
3. Yalnızca kullanıcının bilebileceği bilgi kişisel kurallara yazılır.

## Harcamayı ileriye taşımak

- Düzensiz harcama yıllığa çevrilmez, ileriye taşınmaz ("× 12" yok).
- Yalnızca süren alışkanlıkların aylık bir maliyeti vardır.
- Ara sıra olan harcamalar pencereye yayılır.
- Tek seferlik harcamalar ve durmuş alışkanlıklar bundan sonrası için hiçbir şeye mal olmaz.

## Düzenli ödemeler

**Seri tanımı**

- Yaklaşık bir ay arayla yapılan ödemeler bir seri oluşturur: 15–50 gün; tutar değişmediyse 70 güne kadar.
- `_düzenli` kategorilerinde:
  - Ayda bir ödeme alan bir ödeme alanı, tutar ne olursa olsun tek bir seridir (faturalar mevsime göre değişir).
  - 100 günlük bir aradan sonra seri bölünür.
  - Aynı ödeme alanının birden çok aboneliği tutarlarından ayırt edilir.
  - Serinin her zamanki gününde yeni bir tutarla gelen ödeme seriyi yeni fiyatla sürdürebilir. Ama aynı dönem içinde
    (15 günden kısa bir sürede) ödeme alanının eski fiyattan bir ödemesi daha gelirse yeni tutarlı ödeme başka bir
    çekimdir (ikinci bir plan, ek kullanım): seri eski fiyatıyla sürer (v1.0.5'e dek seri yeni tutara geçiyor, zam
    sanılıyordu).
- 200 güne kadar bir aradan sonra gelen ve kendi başına seri olamayacak kadar az ödeme, ödeme alanının en yeni serisini
  sürdürür. Ödeme alanı tutara göre zincirleniyorsa benzer tutardaki seri sürer. Bu, faturanın arada belgesi olmayan bir
  hesaptan ödendiği, bitmediği anlamına gelir. Serinin son ödemesinden 15 günden kısa süre sonra gelen ödeme bu yolla
  seriye katılmaz: o, serinin geri gelişi değil, aynı dönemin başka bir çekimidir.
- Diğer kategorilerde yalnızca aydan aya %10 içinde kalan bir tutar seri oluşturur.
- Ayda 5'ten fazla ödeme alan bir ödeme alanı abonelik değil, alışveriş yeridir.

**Durumlar**

| MVP | V1 kodu | Kural |
|---|---|---|
| `bitti` | `ended` | Hesaplarının ekstreleri beklenen ödemeyi ve payını ödeme olmadan geçti, ya da beklenen tarihten bu yana 90 gün geçti. |
| `iptal` | `cancelled` | `_biten`'de yazıyor ve o ayın ödemesi yapıldı (ya da beklenen ödeme o aydan sonraya düşüyor, ya da hiç gelmedi). |
| `iptal_sonrasi` | `paid_after_cancel` | O aydan sonra bir ödeme göründü; kullanıcı uyarılır. Gelirde olmaz. |
| `devam` | `active` | Diğer durumlar. |

- `_biten`'deki ay son ödemenin ayıdır: o ayın ödemesi henüz gelmediyse seri o ayın sonuna dek sürer ve takvim, öngörü
  onu yalnızca o aya dek bekler. Kullanıcı ayı ileriye yazmışsa (son maaş gelecek ay yatacaksa) o ödeme sayılır.
- Düzenli bir gelir de `_biten`'e yazılarak bitirilir ("Artık gelmiyor"). O aydan sonra gelen para geliri yeniden
  başlatmaz ve uyarı değildir; gecikmiş gelir haberi de verilmez.

**Bildirilen gelir** (`_düzenli_gelir`, v1.0.12)

- Bir gelirin seri olması için üç ayrı ayda gelmesi gerekir; yeni bir işin maaşı aylarca hiçbir yerde sayılmaz.
  Kullanıcı onun her ay geldiğini, tutarını, para birimini ve gününü bildirirse ödeyenin gelir satırları ilk ödemeden
  itibaren tek bir seri olur, belgelerin kurduğu serinin yerine.
- Beklenen tutar bildirilen tutardır. Döviz ise bugünkü TCMB alış kuruyla TL'ye çevrilir; kur yoksa belgelerin en
  yeni kuruyla, o da yoksa son üç gelişin medyanıyla.
- Takvimdeki günü bildirilen gündür (kısa aylarda ayın son günü). Sayım, bildirilen tutarın en az yarısını getiren en
  yeni ödemeden başlar: sonraki gün ondan en az 15 gün sonradır. Parça parça gelen bir maaşın küçük parçası ayı
  ilerletmez.
- Seri, öteki gelirler gibi `_biten` ile biter. Belgeleri bildirilen günü ve 10 günlük payı ödemesiz geçerse gecikmiş
  gelir haberi verilir; listede her zaman görünür.

Biten bir "Gerekli" fatura "Belgelerde yok" diye gösterilir: belgesi olmayan bir hesaptan ödeniyor olabilir.

**Fiyat değişimi**

- Son fiyat en az iki ödemedir sürüyorsa ve kendinden önceki üç ödemenin medyanından %5'ten fazla farklıysa yeni
  fiyattır. Birbirinden %2 içinde kalan tutarlar aynı fiyat sayılır. Değişimin günü yeni fiyatın ilk ödemesidir.
- Eski fiyat da en az iki kez ödenmiş olmalıdır. Serinin ilk ödemesi ayın bir parçası (kıst dönem) ya da bir
  kampanya olabilir; ardından gelen planın kendi fiyatı zam değildir (v1.0.5'e dek yeni açılan bir aboneliğin ilk
  faturası zam bildirimi doğuruyordu).
- Yurt dışından dövizle faturalanan bir ödeme (kart ekstresi TL tutarın yanında döviz tutarını da yazar: "4,00 USD")
  döviz tutarıyla karşılaştırılır. Aylık 4 dolarlık bir planın TL tutarı her ay kurla oynar; bu zam değildir. Yalnızca
  son ödemeyle aynı dövizde yazılı son ödemelere bakılır. Gösterilen eski ve yeni fiyat yine TL'dir.

**Dönemsel seriler (V1 taslak kuralı)**

- Aynı ödeme alanına ~182 gün (160–200) ya da ~365 gün (330–400) arayla ödemeler: `_düzenli` kategorilerinde en az
  iki, diğerlerinde en az üç.
- `_düzenli` kategorilerinde tutar serbesttir; diğerlerinde ±%50.
- Diğer kategorilerde iki ödeme yetmez (v0.9.8, gerçek veriyle): yarım yıl arayla yapılan iki bağış, bir dükkândan
  yarım yıl arayla yapılan iki alışveriş tesadüfen bir dönem aralıklı olabilir. Dönem bir kez daha gelmeden seri
  sayılmaz; aylık seri de üç ay ister. Kategorinin `_düzenli`'de olması ödemelerin bir taahhüt olduğunu söyler.
  Böyle iki ödeme seri sayılsaydı, ikincisinin farklı tutarı yanlış bir zam bildirimi doğururdu.
- Durum kuralları aynıdır; beklenen tarih dönem uzunluğuyla hesaplanır.
- Eşikler gerçek veriyle ayarlanır.
- Uygulama (Aşama 4, `insights.periodic_payments`):
  - Yalnızca aylık serilerin almadığı ödemelere bakılır; aylık seriler ve onlardan beslenen bulgular değişmez.
  - `_düzenli` kategorilerinde her dönem bir kez ödeme alan bir ödeme alanı, tutar ne olursa olsun tek seridir.
  - Diğer durumlarda bir ödeme, kendinden önceki en yeni benzer ödemeden (fark büyük tutarın yarısını geçmez) bir
    dönem sonra geliyorsa seriyi sürdürür; arada benzer tutarlar ödenen bir işyeri dönemsel ödeme değildir. Böyle
    bir zincir `_düzenli` kategorilerinde iki, diğerlerinde üç ödemeyle seri olur (`insights._PERIODIC_LEAST`).
  - Ayda 5'ten fazla ödeme alan bir ödeme alanı burada da alışveriş yeridir.
  - Dönem uzunluğu aralıkların medyanıdır; beklenen tarih son ödemeden bir dönem sonradır. Payı bandın sonuna
    kadardır: ödeme son ödemeden 200 (altı ayda bir) ya da 400 (yılda bir) gün sonrasına kadar gecikebilir, beklenen
    tarihten en az 10 gün.
  - Beklenen tutar son ödemedir: dönemsel bir fiyat bir dönem boyunca değişmez. Fiyat değişimi son ödemeyi bir
    öncekiyle karşılaştırır ve fark %5'i geçerse gösterilir. Dövizle faturalanan iki ödeme döviz tutarlarıyla
    karşılaştırılır.

## Alışkanlıklar

Kaçınılabilir maliyetler kategori başına, isteğe bağlı harcamalar işyeri başına izlenir.

| MVP | V1 kodu | Kural |
|---|---|---|
| `duzenli` | `regular` | Penceredeki ayların en az %75'inde. |
| `yeni` | `new` | İlk alışveriş pencerenin içinde, en az 3 ay ve o zamandan beri ayların en az %75'inde. |
| `ara_sira` | `occasional` | Ara sıra. |
| `durdu` | `stopped` | Ekstreler sürerken max(60 gün, işyerinin olağan aralığının 2 katı) süresince sessiz, ya da `_biten`'de yazıyor. |
| `tek` | `one_off` | Tek seferlik. |

## Tahmin

Önümüzdeki aylar için tahmin üç kalemin toplamıdır:

1. Süren düzenli ödemeler: son tutar; tutarlar oynuyorsa son üç tutarın medyanı.
2. Kalan taksitler.
3. Gereklilik düzeyi başına son altı tam ayın medyanı. Bu medyana seri ödemeleri, taksitler ve `_biten` işyerleri
   girmez.

İşyeri başına asla tahmin yapılmaz. Büyük tek seferlik alışverişler (≥ max(5.000 TL, ortalama ayın %10'u)) eğilimin
nedenleri arasında sayılmaz.

## Varlıklar ve borçlar

- **Hesaplar:** bakiyeyi yazan en yeni belge: hesap listesinin kapanış bakiyesi ya da listeden sonraki bir banka
  bildiriminin bakiyesi (`analysis.start_of`). Hesaplar, Şu an, Döviz, net varlık, öngörü ve Değerlendirme aynı
  bakiyeyi kullanır.
- **Bakiyeden sonra giden para** (`analysis.sent_after`)
  - Bir hesabın bakiyesi belgesinin gününe aittir. O günden sonra başka bir hesabın belgesi bu hesaba ya da bu hesabın
    bankasına kendi transferinizle para gittiğini söylüyorsa, ama karşı tarafı hiçbir belgede yoksa, bakiye onu henüz
    içermez.
  - Hesabın notu her birini günü, tutarı ve çıktığı hesapla yazar. Satır hesabı adlandırıyorsa ("12345678 no.lu
    hesaba gönderilmiştir") "bu hesaba", yalnızca bankayı yazıyorsa "<banka> hesaplarınızdan birine" der ve hangisine
    girdiğinin belgelerde olmadığını ekler.
  - Değerlendirme'nin "Faiz ödemeyi bırakın" adımı, ek hesap borcunu yazan belge en yeni belgeden eskiyse borcu
    "şu an" diye değil, o günün tarihiyle söyler: borç sonradan ödenmiş olabilir.
- **Kartlar:** ekstre borcundan kesimden sonra yapılan ödemeler düşülür.
- **Döviz** (V1, [mimari §15](../v1/architecture.md#15-döviz))
  - Kur sağlayıcısının en yeni kuruyla (TCMB; ulaşılamadığı günlerde ECB): varlık döviz alış, borç (eksi bakiye) döviz
    satış kuruyla. Banka da dövizinizi alış kuruyla alır, borcunuzu satış kuruyla kapatır. Kurun günü ve kaynağı
    yazılır.
  - Kur sağlayıcısının o para birimi için kuru yoksa belgelerdeki en yeni kurla, tarihi yazılarak (MVP kuralı).
  - Net varlık EUR ve USD'ye en yeni döviz satış kuruyla çevrilir: o parayla döviz almak satış kuruna mal olur.
- **Altın:** gram ve ödenen TL ile gösterilir; belgeler altın fiyatı taşımaz.
- **Hisseler:** en yeni yatırım ekstresinin piyasa değeriyle, tarihi yazılarak.
- **Eski belge:** en yeni belgesi en yeni ekstreden 180 günden eski olan bir bakiye TL değeri olmadan gösterilir ve
  hiçbir toplama girmez. Örnek: yalnızca açılış cüzdanından bilinen bir vadeli hesap.
- **Geçici dekontlar**
  - Bir listenin son gününden sonra gelen geçici dekontlar o listenin bakiyesini değiştirir; not, listenin bakiyesini
    ve değişikliği ayrıca yazar.
  - Geçici kart ödemeleri kartın borcunu düşürür.
- **Belgede görünmeyen giriş** (`analysis.untold_in`)
  - Banka bir hesaptan, içindekinden fazlasını ödemez. Ek hesap (KMH), kart ya da kredi olmayan ve hiçbir belgesinde
    sıfırın altında görünmeyen bir hesap eksiye düşmez. Görünmesi, dökümün açılış, kapanış ve ay sonu bakiyelerinde,
    gün sonlarında ya da bir bildirimin yazdığı bakiyede olur: öyle bir hesabın ek hesabı vardır ve kullanılıyordur.
  - Dekont ve bildirimler bakiyeyi böyle bir hesapta sıfırın altına indiriyorsa, arada hiçbir belgede olmayan para
    girmiştir. Bildirimler hareketlerin yalnızca bir kısmını anlatır: Garanti belli bir tutarın üstündeki giden
    havaleleri bildirir; döviz satışını ve gelen parayı bildirmez. Örnek: döküm 0,00 TL ile alınmış, sonra
    12.750 TL giden bir bildirim gelmiş. Bakiye o zaman 0 sayılır (geçici), not da en az ne kadar girmiş olması
    gerektiğini yazar.
  - Bu tutar borç değildir: ek hesap borcuna, KMH önerisine ve borç toplamına girmez.
  - Toplamlar onu ayrı bir satırla düşer: Hesaplar'ın, net varlığın ve Değerlendirme'nin birikimi. Para kendi
    hesaplarınızdan birinden geldiyse o hesap belgelerde hâlâ eski bakiyesiyle durur. Düşülmezse aynı para iki kez
    sayılır ve kendi hesaplarınız arasındaki bir aktarma net varlığı artırır.
  - İplikçi Nedim'in "borçlarınız paranızdan fazla" sözü bu düşüşle borçlardan fazla eksiye inmez: borcu olmayanı
    borçlu saymaz.
  - Öngörü hesabı 0'dan başlatır. Hesap sayfasının günlük bakiyesi de dökümden sonraki günlerde sıfırın altına inmez;
    notu nedenini yazar.

## Bulgular ve adımlar

- Her bulgu penceresini ve rakamlarını verir.
- Bir adım aylık TL etkisini yalnızca veri onu fiyatlıyorsa taşır.
- Bütçenin son satırı, gelirden diğer satırların düşülmesine eşittir.
- Bütçede her harcama tek satırda sayılır. Gereksiz saydığınız bir düzenli ödeme sürdükçe sabit ödemelerdedir, bitince
  hiçbir satıra girmez; "Gereksiz harcamalar" satırında faiz ve ücretler (kendi serileri de) ile gereksiz saydığınız
  öteki harcamalar vardır.
- Sayılardan ve yıllardan sonraki Türkçe ekler `pct`, `since`, `months_in` ve `year_suffix` ile kurulur; `'i` ya da
  `'da` elle yazılmaz.
- Yeni bir bulgu `_Context` ile beslenen bir yazar olarak eklenir. Rakamları tam aylardan gelir, testi yazılır;
  arayüzde, MCP'de ve Excel'in Değerlendirme sayfasında görünür.

## V1'de eklenen hesaplar

- **Son ödemeler:** kart ekstresinden son ödeme tarihi, dönem borcu ve asgari tutar okunur; takvime ve
  `payment.due_soon` olayına girer.
- **Nakit akışı öngörüsü** (hesap başına, 60 gün)
  - Başlangıç tahmini güncel bakiyedir: son belge artı geçici olaylar.
    - Son belge, bakiyeyi yazan en yeni belgedir: hesap dökümünün kapanış bakiyesi ya da bir banka bildiriminin
      satırdan sonraki bakiyesi (Vakıfbank'ın FAST bildirimleri ile QNB'nin hareket bildirimleri yazar). İkisi aynı
      günse döküm esas alınır. Sonraki günlerin henüz ekstreye girmemiş dekont ve bildirim satırları eklenir.
    - Döküm yalnızca gösterdiği satırları kapsar: son günlerinin dökümde görünmeyen dekont satırları da eklenir
      (banka onları döküm alındıktan sonra işlemiş olabilir; defter onları geçici sayar). Bildirimin bakiyesi ise
      kendi gününün ve önceki günlerin satırlarını zaten içerir. Hesaplar, Şu an, Döviz, net varlık ve öngörü aynı
      bakiyeyi kullanır.
    - Dekont ve bildirimler eksiye düşemeyen bir hesabı sıfırın altına indiriyorsa başlangıç 0'dır; arada belgelerde
      olmayan bir giriş vardır (yukarıda, "Belgede görünmeyen giriş").
    - Bakiyesi hiçbir belgede yazmayan, bakiyesi en yeni belgeden 180 günden eski olan ve döviz ya da altın olan
      hesaplar öngörüye girmez; nedenleri yazılır.
    - Döviz, altın ve yatırım hesapları bugünkü TL değerleriyle (net varlıktaki kurla; altının fiyatı belgede yoksa
      değersiz) öngörünün yanında verilir. Öngörü onlar olmadan TL'nin ne zaman biteceğini söyler; Pano isteyene
      onları bugünkü değerleriyle, değişmez sayarak çizgiye ekler. Uyarılar TL hesapları sayar.
    - Bu hesaplara beklenen düzenli gelir (dövizle gelen maaş) de TL çizgisine girmez: kullanıcı onu ihtiyaç oldukça
      bozdurur. Öngörünün notu kaç gelir beklendiğini ve bugünkü kurla toplamını yazar. Pano'nun "Döviz ve
      yatırımlarla" çizgisi onları geldikleri günden itibaren ekler; TL toplamının uyarısı en düşük güne kadar
      gelecek olanı "karşılıyor" hesabına katar.
    - Bakiyeyi yazan belgenin gününden bugüne kadarki günler de sayılır: döküm 31'inde bitip bugün ayın 2'siyse,
      1'inde beklenen maaş bugünkü bakiyededir; belge aksini gösterene dek beklenen sayılır. O günlerin beklenen
      kalemleri ve seri dışı çıkışların o günlere düşen payı bugünden önce işlenir; öngörünün notu günleri ve
      rakamları yazar. Sonraki dekont ve bildirimler yalnızca anlattıkları hareketleri gösterir: bir serinin ödemesini
      anlatan dekont serinin sonraki gününü zaten ileri taşır. Takvim yine bugünden ileriye bakar.
    - Bakiye bugünden 60 günden (öngörünün ileri baktığı kadar) eskiyse aradaki günler tahmin edilmez: öngörü o
      bakiyeden başlar ve not bunu söyler.
  - Üstüne beklenen olaylar eklenir:
    - maaş (serinin günü; son üç tutarın medyanı),
    - düzenli ve dönemsel ödemeler (en son hangi hesaptan ödendiyse oradan),
    - kart son ödemeleri (kullanıcının geçmiş ödeme davranışına göre tam ya da kısmi),
    - taksitler.
  - Takvim (`upcoming.py`) ve öngörü (`forecast.py`) bu olayları şöyle kurar:
    - Aylık bir ödeme, son dört ödemesine göre ayın olağan gününe düşer. Ay dönümünde ödenenlerde günler ayın 1'ine
      göre sayılır (ayın son günü, sonraki ayın 1'inden bir gün öncedir); böylece 30'unda ya da 1'inde yatan maaş
      ayın ortasına kaymaz. Sonraki ödeme sonuncudan en az 15 gün sonradır. Dönemsel ödeme son ödemeden bir dönem
      sonradır.
    - Kart son ödemesi, kredi kartının en yeni TL ekstresinden gelir: son ödeme tarihi, dönem borcu ve asgari tutar.
      Kesimden sonra karta yapılan ödemeler borçtan da asgari tutardan da düşülür: hesapların bakiyesi onları zaten
      saymıştır. Borcu kapanmış ya da son ödeme tarihini yazmayan ekstre takvime girmez.
    - Kart son ödemesi, kartı en son ödeyen hesaptan çıkar. Son altı ekstrede ödenen payın medyanı en az %99 ise
      tamamı sayılır; değilse o pay sayılır, asgari ödemeden az olmamak üzere. Ödeme geçmişi yoksa tamamı sayılır.
    - Kart taksitleri (n/m etiketinden, sonraki kesim günlerinde) ve kartla ödenen düzenli ödemeler kartın ekstresine
      girer; hesaptan kart ödemesiyle çıktıkları için öngörüde ayrıca düşülmez.
    - Kredi taksiti dekontlardan gelir: son taksidin tamamı (anapara, faiz ve vergiler), dekontlar sürdükçe; kalan
      taksit sayısını dekontlar yazmaz. Taksit, bankanın öngörüdeki tek TL hesabından ödenmiş sayılır; böyle bir
      hesap yoksa ya da birden çoksa hiçbir hesaba düşülmez, ayrıca gösterilir. Taksitleri hesap dökümünde süren bir
      seri olan bankanın kredisi o seriyle gelir, ikinci kez eklenmez.
  - Seri dışı çıkışlar, son altı tam ayın aylık medyanıyla günlere yayılır.
    - Yalnızca hesabın belgelerinin tamamen kapsadığı aylar sayılır; kendi hesaplar arası transferler ve `_biten`
      işyerleri girmez.
    - Kart ödemeleri ayrı bir medyandır; hesabın o aylarda ödediği kartların en yeni ekstrelerinin son ödeme
      günlerinin en geçinden sonrasına yayılır, o güne kadar onları bu ekstreler karşılar. Son ödemeyi hangi hesap
      üstlenirse üstlensin böyledir: kartı aylarca ek hesaptan, son kez vadesizden ödeyen kullanıcının ekstresi
      vadesizden düşülür, ek hesabın kart ödemeleri o güne dek sayılmaz (v1.0.5'e dek yalnızca son ödemeyi üstlenen
      hesapta böyleydi; aynı borç iki kez sayılıyor, toplam erken eksiye düşüyordu). Ekstre son ödeme gününden önce
      ödenince de böyledir: ödeme ödeyen hesabın bakiyesindedir, kart ödemeleri yine son ödeme gününden sonra başlar
      (v1.0.6'ya dek ödenen ekstre takvimden düşünce kart ödemeleri bugünden başlıyordu; zamanında ödenen ekstre
      toplamın eksiye düştüğü günü öne çekiyordu). Başka bir kartın son ödemesi bir hesabın kart ödemelerini ertelemez.
    - Seri dışı girişler öngörülmez: düzensiz gelir ileriye taşınmaz. Öngörünün notu son 90 günde gelip yeniden
      beklenmeyen gelirleri ödeyene göre, tutarlarıyla yazar (bitenleri "bitti" diye). İlk üçünü adıyla, gerisini
      sayıyla söyler. Her ay geldiği bilinen bir gelir Düzenli ödemeler ekranında bildirilebilir.
  - Vadeli hesabın faizi günlere eklenir.
    - Oran, hesabın belgelerindeki faiz satırlarından çıkar: son 30 günün net faizi (kesilen vergi düşülmüş), onu
      kazandıran gün sonu bakiyelerinin toplamına bölünür. Bir günün faizi bir önceki günün bakiyesinindir; bakiyeler
      belgenin yazdığı bakiyeden geriye, satırlarla bulunur.
    - Öngörü her gün o günün bakiyesine bu oranla faiz ekler. Bakiye değişince faiz de değişir: karta ödeme için
      çekilen para artık faiz getirmez. Bu yüzden ortalama günlük tutar ileriye taşınmaz.
    - En az 3 günlük faiz satırı gerekir. Hesabın notu günleri, net faizi ve yıllık net getiriyi yazar.
    - TL toplamının uyarısı "Öngörü TL hesaplarınıza vadeli hesap faizi dışında düzenli bir gelir beklemiyor" der.
  - KMH faizi yalnızca belgede yazan aylık oranla hesaplanır; oran yoksa faiz tahmin edilmez (oranı okuyan bir okuyucu
    henüz yok).
  - Öngörü her zaman "tahmin" diye işaretlenir. Eksiye düştüğü gün uyarı sayılıyorsa `balance.forecast_negative`
    olayı üretilir (aşağıda, Akış olayları).
- **Olağan dışı hareketler** (yalnızca işaret, satır silinmez; son 90 günün hareketleri)
  - Geçmişte en az 3 ödemesi olan bir işyerinde, medyanının 3 katından büyük ve medyanından en az 500 TL fazla bir
    çekim. Kafede birkaç lira fazlası haber değildir.
  - Aynı gün, aynı işyerinde, aynı tutarlı birden çok satır: olası çift çekim.
  - İlk kez görülen bir işyerinde büyük harcama eşiğini geçen tutar. Satırlar en az üç ay geriye gitmelidir: ilk
    haftalarda her işyeri yenidir.
  - Son 12 ayda görülmemiş, en az 50 TL tutarında bir banka ücreti ya da kart aidatı. Hesabın satırları en az üç ay
    geriye gitmelidir. Kart aidatı için iade talebi adımı önerilir; yıllık aidat her yıl yeniden işaretlenir.
  - Bölünmüş bir satır tek ödemedir: işyeri ve tutar karşılaştırmaları satırın bütününe bakar.
- **Kur makası** (`exchange.spread`)
  - Kendi hesapları arasındaki her döviz alım ve satımında, bankanın kuru ile aynı günün yönüne uygun TCMB kuru
    arasındaki fark döviz tutarıyla çarpılır. Bu, TL cinsinden makas maliyetidir.
    - Alımda (TL hesaptan TL çıkar) TCMB'nin döviz satış kuru: (banka − TCMB satış) × tutar.
    - Satışta (TL hesaba TL girer) TCMB'nin döviz alış kuru: (TCMB alış − banka) × tutar.
    - Bankanın kuru, TL hesabının satırının yazdığı kurdur (`EUR: 36,50`, Vakıfbank'ın `İşlem Kuru`). Döviz tutarı
      Vakıfbank'ta yazılıdır; yazmayan satırda TL tutarı kura bölünür.
  - Yurt dışı kart harcamaları ikinci bir gruptur: TL ekstrede döviz tutarı TL tutarının yanında yazar ("19,99 USD").
    Kartın kuru TL ÷ döviz tutarıdır; harcama gününün TCMB döviz satış kuruyla karşılaştırılır. Taksitli bir harcamanın
    taksidi bütünün bir parçasıdır, kur söylemez.
  - Yalnızca TCMB'nin kuruyla karşılaştırılır: ECB'nin günde tek referans kuru alış ve satışı ayırmaz. Hafta sonu ve
    tatilde önceki iş gününün bülteni geçerlidir (en çok bir hafta geriye). O gün için TCMB kuru olmayan satırlar
    toplama girmez; sayıları yazılır.
  - Son 12 ayın (bugünden geriye bir yılın) toplamı, pencerenin tarihleri ve işlem listesi gösterilir: her satırın
    parmak izi, günü, tutarı, bankanın kuru, TCMB kuru ve farkı. Eksi bir fark bankanın kurunun TCMB'ninkinden iyi
    olduğunu söyler.
- **Döviz geliri** (`exchange.foreign_income`): döviz hesaplarına giren gelir, para birimi başına.
  - Son 12 ayın gelir satırları döviz tutarlarıyla, defterin o günün kuruyla saydığı TL ve güncel kurla (kur
    sağlayıcısının en yeni döviz alış kuru; yoksa belgelerin en yeni kuru) TL karşılıklarıyla gösterilir.
  - Bozdurma zamanları: aynı pencerede dövizin TL'ye çevrildiği satırlar, günü, döviz ve TL tutarı ve bankanın
    kuruyla.
  - Kur duyarlılığı: aylık ortalama döviz geliri yalnızca tam aylardan hesaplanır (değerlendirmenin penceresindeki
    tam aylar; içinde bulunulan ay sayılmaz) ve cümle hangi aylardan, kaç tam aydan hesaplandığını söyler. Ortalama
    güncel kurla TL'ye çevrilir ve %5'i verilir: "EUR/TRY %5 düşerse aylık gelir X TL azalır".
  - Döviz geliri yoksa hiçbir şey hesaplanmaz; not bunu söyler. Kur yoksa TL karşılığı ve duyarlılık verilmez.
- **Borç görünümü**
  - Kart borçları; kalan taksitler (n/m etiketinden kalan × tutar); KMH (eksi bakiye) gösterilir.
  - Krediler, e-dekontlardaki taksit bilgisinden gösterilir; kalan anapara bilinmiyorsa "bilinmiyor" yazar.
- **Çoklu para birimi:** varlıklar aynı günün kurlarıyla EUR, USD ve gram altın cinsinden de gösterilir. EUR ve USD
  karşılığı kur sağlayıcısının en yeni döviz satış kuruyla hesaplanır (yukarıda, Varlıklar ve borçlar); gram altın,
  ücretsiz ve güvenilir bir fiyat kaynağı doğrulanana dek gram ve maliyetiyle kalır.
- **Enflasyondan arındırma** (V1+, `inflation.real_trend`): kullanıcı EVDS anahtarı girdiyse harcama eğiliminin iki
  dönemi (değerlendirmenin tam ayları, eğilimin seçtiği gibi) en yeni TÜFE'li ayın fiyatlarına taşınır:
  reel = harcama × TÜFE(taban ay) ÷ TÜFE(ay).
  - Yalnızca tam aylar. TÜFE'si henüz çıkmamış bir ay (TÜFE sonraki ayın başında yayımlanır) iki taraftan da çıkar ve
    adıyla yazılır; bir tarafta TÜFE'li ay kalmazsa karşılaştırma yapılmaz, not nedenini söyler.
  - Cümle iki dönemin aylarını, fiyatların (TÜFE ortalamalarının) ne kadar değiştiğini, harcamanın TL'deki ve taban
    ayın fiyatlarıyla değişimini söyler. TÜFE analizin parçası değildir; toplamları değiştirmez.

## Akış olayları

Her analizden sonra akış, bildirim kurallarının eşleştiği olayları üretir (mimari §13; `feed/news.py`). Her olay bir
kez söylenir; ilk analiz yalnızca not eder. Önümüzdeki haftanın ödemeleri bunun dışındadır: geçmiş değil, önümüzdeki
günlerdir. Boş başlayan bir veri klasörü onları belgeler geldikçe zaten söyler; ilk analizini belgeleriyle yapan bir
klasör (demonunki gibi) de yakın son ödemeyi o an söyler (v1.0.2).

- **Yaklaşan ödeme** (`payment.due_soon`)
  - Takvimin kullanıcının ilgilenmesi gereken kalemleri: kart son ödemesi, banka dışı fatura, kredi taksidi ve bir
    hesaptan yapılan düzenli ya da dönemsel ödeme (kira gibi).
  - Kart taksidi kartın ekstresiyle ödenir. Kartın kendiliğinden çekildiği ödeme (abonelik) kullanıcıdan bir şey
    istemez; her ay söylemek gürültü olurdu. Gelir hiçbir zaman söylenmez.
  - Gününe 7, 3, 1 ve 0 gün kala söylenir; her eşik bir kez. Kalan günün girdiği en dar eşik söylenir: servis kapalı
    kaldıysa atlanan eşikler sonradan söylenmez.
- **Eksiye düşen hesap** (`balance.forecast_negative`)
  - Nakit akışı öngörüsünde bir TL hesabın eksiye düştüğü ilk gün. İki hesabınki uyarı sayılmaz; öngörü grafiği
    onların eksi günlerini yine gösterir, öngörünün notu nedenini yazar:
    - Ek hesap (KMH): eksi bakiyesi kullanılan kredidir.
    - Kendi hesaplarından düzenli para aktarılan hesap: öngörünün seri dışı çıkışları yaydığı tam aylarda kendi
      hesaplardan gelen para, hesaptan çıkanın en az yarısıdır. Öngörü bu aktarmaları saymaz (kendi hesaplar arası
      transferler öngörüye girmez); hesap, kartı ödediği ve aktarmalar gelmediği için eksiye iner.
  - TL hesapların toplamı da izlenir ("TL hesaplarınızın toplamı"): toplam bugün eksi değilken öngörüde eksiye düşerse
    söylenir. Kendi hesaplar arasındaki aktarmalar toplamda birbirini götürür, KMH'nin kullanılan kredisi borç olarak
    sayılır. Toplamın ilk eksi günü bir hesabın uyarısıyla aynı gün ve tutarsa (tek hesap) ikinci kez söylenmez.
    - Toplamın uyarısı nedenini ve neyin karşıladığını da söyler. Öngörü TL hesaplara hiçbir gelir beklemiyorsa bunu
      yazar. Toplamın öngörü günleri içindeki en düşük hâlini günüyle verir. Öngörünün dışında kalan döviz ve
      yatırımların bugünkü değerini de yazar: altın fiyatsız sayılmaz, borçlar sayılmaz.
    - Bu değer en düşük hâli karşılıyorsa uyarı "eksiye düşmeden önce bir kısmını TL'ye çevirmeniz yeter" der. Pano'da
      kritik değil, uyarıdır; İplikçi Nedim'in sözü de uyarıdır.
    - Karşılamıyorsa "hepsini karşılamıyor" der. Hafta içindeyse kritiktir.
    - Neden (2026-11-23): geliri başka bir para biriminde gelip gerektikçe TL'ye çevrilince TL hesaplar her gün iner.
      Uyarı yalnızca ilk eksi günü söylediği için kullanıcı parasının bittiğini sanmıştı.
  - Hesap önceki analizde eksiye düşmüyorduysa ya da gün öne geldiyse söylenir.
  - Gün yalnızca ileri kaydıysa yeni haber değildir. Bakiye bugün zaten eksideyse ilk eksi gün her gün bugündür;
    bakiyesi 60 günden eski bir hesabın öngörüsü her gün aynı bakiyeden başlar, günlere yayılan çıkışların
    belirlediği gün her gün bir ileri kayar.
- **Gelmeyen ödeme ve gecikmiş gelir** (`expected_payment.missing`, `income.late`)
  - Serinin son iki ödemesinin görüldüğü hesapların belgeleri, beklenen günü ve serinin payını ödemesiz geçmiştir:
    payın son gününde ya da sonra biten bir döküm ya da ekstre, ya da daha sonraki bir günün dekontu ya da bildirimi
    vardır.
  - Beklenen gün, takvimin ve Düzenli ödemeler ekranının gösterdiği gündür; pay, serinin durum kuralındaki paydır
    (`Series.grace`).
  - Belgeler o günleri geçmedikçe söylenmez. Kartla ya da aylık dökümü olan bir hesaptan yapılan ödeme yapılmış
    olabilir: ekstresi ya da dökümü henüz gelmemiştir. Belgeler payı geçince seri `bitti` olur; olay yine söylenir.
  - İptal edilmiş seri beklenmez.
  - Payı 60 günden (takvimin ileri baktığı kadar) önce bitmiş bir ödeme geçmiştir, haber değildir: eski belgeler
    sonradan gelse de söylenmez.
- **Zam ve iptalden sonra ödeme**
  - `subscription.price_changed`: süren bir serinin yeni fiyatı (fiyat değişimi kuralı yukarıda), yeni fiyatın ilk
    ödemesinin günüyle. Fiyat artmış da olabilir, düşmüş de: bildirimin başlığı "Düzenli ödeme zammı" ya da
    "Düzenli ödeme ucuzladı" der, özeti "zamlandı" ya da "ucuzladı" (`notify.content.title`); Akış'ın kartı da
    böyle adlandırılır. Kuralın adı "Düzenli ödeme tutarı değişti"dir (v0.9.8'e dek "Düzenli ödeme zammı",
    2026-11-03'e dek "Abonelik zammı"): faturalar ve kira da seridir, düşen bir fiyat da haberdir.
    - Yeni fiyatı kesinleştiren ödeme analiz gününden en çok 45 gün önceyse söylenir: aylık seride yeni fiyatın
      ikinci ödemesi, dönemsel seride tek ödemesi. Bir kart ekstresi bir ödemeyi bir aya kadar sonra gösterir ve
      kesimden günler sonra gelir.
    - Daha eskisi geçmiştir: geçen yılın belgelerini getiren bir içe aktarma geçen yılın zamlarını söylemez. Fiyat
      değişimi Düzenli ödemeler ekranında yine görünür.
  - `subscription.paid_after_cancel`: iptal edilmiş serinin iptal ayından sonraki en son ödemesi; daha yeni bir ödeme
    yeniden söylenir.
- **Gelen gelir** (`income.received`): bir gelir serisinin yeni satırı. Büyük harcama gibi yalnızca analiz gününden en
  çok 7 gün önceki satırlar haberdir.
- **Büyük harcama** (`transaction.large`)
  - Seri dışındaki tek bir alışveriş, büyük alışveriş eşiğinden büyük ya da eşitse: ≥ max(5.000 TL, ortalama ayın
    %10'u) ("Tahmin"; `insights.large_purchase_threshold`).
  - Yalnızca analiz gününden en çok 7 gün önceki satırlar haberdir. Daha eski bir satırı getiren ekstre ya da içe
    aktarma bildirim yağdırmaz.
- Dekontu ya da bildirimi zaten bilinen bir hareketi doğrulayan ekstre satırı yeni bir gelir ya da büyük harcama
  değildir: aynı para ikinci kez söylenmez.

## Ay sonu kapanışı

Kullanıcı her ayın ekstreleriyle kapanmasını ve her ay için bir rapor istiyor. Dekontlardan bilinen transferler
ekstre gelmeden sayılır.

**Hesap ve ay başına kapanış** (`AccountClose`)

- Ekstreleri o aya ulaşan her hesap kapanışa katılır. Belgeleri en yeni ekstreden `ACTIVE_DAYS` öncesinde bitmiş hesap
  dışarıda kalır.
- Hesabın durumu şöyle belirlenir:
  - En yeni kapsanan gününden önceki kapsanmamış günler `eksik`tir; bu günlerin belgesi indirilmelidir.
  - En yeni kapsanan gününden sonraki günler `bekleniyor`dur.
  - Kendi kontrolünden geçmeyen bir ekstre ya da `eslesmedi` bir dekont, hesabı `kontrol` yapar.
  - Bunların dışında hesap `kapandi`dır.
- Kontrol edilecek bir şeyi olmayan bir belge ayı asla açık tutmaz. Örnekler: hareketsiz bir liste, toplamı yazmayan
  bir ekstre. Bu belgeler `_fails` ile ayrılır ve `statement_check` bunları "–" olarak gösterir.
- İçinde bulunulan ay yalnızca bugüne kadarki günleri ister. Ay içinde sıfır bakiyeyle açılan hesap, yalnızca açıldığı
  günden sonrasını ister.

**Ayın durumu**

- Ay sürerken `suruyor` (`running`).
- Sonra, ayı kapanmaktan alıkoyan hesaplar üzerinden şu öncelikle belirlenir: `eksik` (`missing`) > `kontrol`
  (`check`) > `bekleniyor` (`waiting`) > `kapandi` (`closed`).
- Yatırım hesabı ayı asla bekletmez; ay sonundan 10 gün sonra "gecikti" olur.

**Beklenen belgeler**

- Kart ve yatırım ekstreleri e-postayla gelir (`mailed`).
- Hesap listelerini kullanıcı indirir; notları indirmeyi ister.
- V1: banka e-postayla göndermiyorsa döküm elle istenmez; hesabın hareketleri bankanın e-postalarından çıkarılır (K21).
  - E-cüzdan, hesap açılınca bir kez gönderilir (`Statement.one_off`); ardından aylık döküm gelmez. Yalnızca e-cüzdanı
    olan bir hesabın sonraki günleri beklenmez; ay sayfası bunu yazar. Hesabın sonradan bir dökümü gelirse ondan
    sonraki günler yine beklenir.
- Kartın açık günleri bir sonraki kesimi bekler: son ekstrenin yazdığı "bir sonraki hesap kesim tarihi", yazmıyorsa
  son kesimin bir ay sonrası, aynı gün (`Statement.cut_after`; tahmin "~" ile yazılır). Bankalar kesim gününü aydan
  aya birkaç gün oynattığı için tahmin çoğu ay tutmaz. Açık günler o kesimi de aşıyorsa sonraki ekstre de beklenir.
  Beklenen ilk ekstrenin kesiminden 5 günden fazla geçerse "gecikti" olur.

**Toplamlar**

- Toplamlar takvim ayı başınadır.
- Gelir yalnızca bir banka listesi (kart ya da yatırım değil) ayın en az yarısını kapsıyorsa gösterilir. İçinde
  bulunulan ayda bu, bugüne kadarki günlerin yarısıdır.
- Kalan, gelenden harcamanın, kişilere gönderilen paranın, ödenen kredi anaparasının ve birikimin düşülmesiyle bulunur
  (`month_end.Totals.left`). Pano'nun hikâyesi, aylara göre çubukları ve İplikçi Nedim'in ay hükmü aynı Kalan'ı
  söyler (v0.9.9'a dek Pano yalnızca harcamayı düşüyordu). Pano'da "Giden" harcama, kişilere gönderilen para ve kredi
  anaparasıdır; birikim ayrıca gösterilir. Nakit avans ve çekim, kart ödemeleri ve kendi hesaplar arası transferler
  hiçbirine girmez; taksitli nakit avansın taksitleri anapara ve faiz diye ayrılınca anaparası kredi ödemesi, faizi
  harcama olur ([defter](ledger.md)).
- **Birikim**, ayda birikime net giden paradır (`insights.saving_of`, `savings`); Pano, Ay sonu, Değerlendirme'nin
  "Gelir ve gider" tablosu, Excel dışa aktarımı, MCP `month_end` ve İplikçi Nedim aynısını sayar:
  - BES ve yatırım ödemeleri (`investment` türü: BES, fon, hisse, sermaye), birikim hesabı olmayan bir hesaptan
    ödendiyse; fon satışı gibi geri gelen para eksi yazar.
  - Döviz ve altın alım-satımı ("Döviz & Altın Alım-Satımı" kategorisindeki kendi hesaplar arası transfer): alışta
    ödenen TL birikime girer, satışta gelen TL birikimden çıkar. Okuyucular işlemin döviz tarafını satır yapmaz
    (`parsers.movements.classify`), onun yerini TL tarafı tutar.
  - Birikim hesapları (döviz, altın, vadeli, yatırım hesabı; `insights.SAVINGS_ACCOUNTS`): hesaba giren her para
    (gelir, faiz, vadesizden aktarılan) birikime girer, çıkan her para (vadesize geri dönen, oradan ödenen kart borcu,
    harcama) birikimden çıkar. Dövizle gelen gelir, döviz hesabında kaldıkça birikimdir; bozdurulunca birikimden çıkar.
  - Birikimin içinde kalan para hiçbir şey eklemez: vadeli hesabın parasıyla alınan fon, mevduatla alınan döviz, iki
    birikim hesabı arasındaki transfer.
  - Eksi birikim "birikimden kullanılan"dır: bozdurulan döviz ya da altın, vadeliden çekilen para. Kalan onu da içerir;
    ama ay hükmü gelirin bıraktığını onsuz söyler (`app.sayings._kept`), Pano "birikimden X kullanıldı" der.
  - Birikimin parçaları (her yatırım kategorisi; döviz, altın, vadeli hesap, yatırım hesabı) kendi satırlarına götürür:
    İşlemler'in `saving` süzgeci bir ayın birikim satırlarını tutar, toplamlardaki `saving` onların birikime kattığıdır.
  - v1.0.10'a dek birikim yalnızca `investment` türüydü: TL ile alınan döviz ve altın, döviz hesabında kalan gelir ve
    vadeli hesaba giden para ne birikimde ne gidende sayılıyordu, hepsi Kalan'a düşüyordu. Pano'nun "BES, döviz, altın
    ve diğer yatırımlara ayrılan para" yazısı tutmuyordu.
- Giden para gelenden fazlaysa ay eksiyle biter (kritik). Gelir gideni karşıladığı hâlde birikim gelirin bıraktığını
  aşıyorsa (döviz ya da altın önceki aylardan kalan parayla alındıysa) bu eksiyle bitiş değildir: hüküm uyarıdır, "gelen
  paranın hepsi harcandı ya da birikime ayrıldı" der.
- Maaş serisi ayda hiç ödeme yapmadıysa ya da iki kez ödediyse, not bunu söyler (`insights.salary_timing`).
- Maaşı önceki ayın son günü yatan bir ay gelir 0 ve eksi "kalan" gösterir. Bu beklenen bir durumdur; sayfa ve dizin
  nedenini söyler.
- Yalnızca kapanmış aylar birbiriyle karşılaştırılır: açık bir ayda, ekstrelerin henüz ulaşmadığı günler eksiktir.
- Pano'nun hikâyesi ve İplikçi Nedim'in ay hükmü gelirin bilindiği, biten en yeni ayı anlatır; ay kapanmamışsa
  rakamları ve hükmü "şimdilik"tir ve neyi beklediği yazar (v0.10.1). Tek bir ayın kendi hükmü bir karşılaştırma
  değildir; o ayı başka aylarla kıyaslayan "en iyi ay" yalnızca kapanmış bir ay için söylenir.
- Kapanmamış bir ay eksik diye adlandırılmaz, neyi beklediği söylenir: ekstrelerini bekleyen ay "bekliyor" ve
  kapanacağı gün (son beklenen kartın kesimi), belgesi gerçekten olmayan ay "eksik". Beklenen belgeler hesap hesap,
  günleri ve kesimiyle sayılır; İşlemler listelenen günler için aynısını söyler (v0.10.2).

**Sayfalar**

- İçinde bulunulan ay ve önceki on iki ay için birer sayfa, artı bir dizin üretilir. Daha eski bir ay istenince
  üretilir.
- Sayfalar Python'da üretilir:
  - Her metin `html.escape`'ten geçer; betik yoktur.
  - CSP: `default-src 'none'; style-src 'unsafe-inline'; img-src data:`.
  - Aylar arasındaki bağlantılar görelidir.
- Durum etiketinin yanında her yerde `MonthEnd.summary` durur ve etiketi tekrarlamaz.
- Raporun kapanış kartı son 7 ayı gösterir ve hiçbir süzgeçten etkilenmez.
- Excel'de `Ay Sonu` ve `Kapanış` sayfaları vardır. CSV'de ve işlemler sayfasında geçici satırlar `Durum` sütununda
  işaretlenir.
- V1'de aynı sayfalar uygulama içinde de gösterilir. Durum değişince `month.ended`, `month.closed` ve
  `month.needs_check` olayları her ay için bir kez üretilir.
- Kapanmış bir ay yeni belge gelmeden yeniden açılırsa bu bir gerilemedir.
