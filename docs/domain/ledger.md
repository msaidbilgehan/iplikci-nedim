# Defter kuralları

Kaynak: MVP'nin `CLAUDE.md` dosyası (2026-10-31), kişisel bilgilerden arındırılmış ve V1 eklemeleriyle
genişletilmiştir. Kod MVP'deki adlarla anılır; V1'deki karşılıklar
[mimari §6](../v1/architecture.md#6-bileşenler)'dadır.

## İşaret kuralı

Her türde aynıdır: `tutar > 0` paranın kullanıcıdan çıkması, `tutar < 0` kullanıcıya girmesi demektir.

## İşlem türleri

| MVP kodu | V1 kodu | Etiket | Gider mi? |
|---|---|---|---|
| `harcama` | `purchase` | Harcama | evet |
| `iade` | `refund` | İade / indirim | evet (eksi) |
| `faiz_ucret` | `interest_fee` | Faiz & banka ücreti | evet |
| `kisiye_transfer` | `p2p_transfer` | Kişilere gönderilen para | hayır |
| `kredi_anapara` | `loan_principal` | Kredi & borç anapara ödemesi | hayır |
| `nakit_avans` | `cash_advance` | Nakit avans / çekim | hayır |
| `yatirim` | `investment` | Birikim & yatırım (döviz, altın, BES) | hayır |
| `gelir` | `income` | Gelir | hayır |
| `ekstresiz_kart` | `card_payment_no_statement` | Ekstresi olmayan kart ödemesi | hayır |
| `kart_odemesi` | `card_payment` | Kredi kartı borç ödemesi | hayır |
| `transfer` | `own_transfer` | Kendi hesaplarım arası transfer | hayır |

Varsayılan gider türleri yalnızca `purchase`, `refund` ve `interest_fee`'dir. Diğerleri ayrı tutulur; gidere eklenirse
aynı para iki kez sayılır.

## Gereklilik

| MVP | V1 kodu | Not |
|---|---|---|
| Gerekli | `required` | |
| İsteğe bağlı | `optional` | |
| Gereksiz | `unnecessary` | Faiz ve ücretler varsayılan olarak buradadır. |
| Belirsiz | `unknown` | Hiçbir kural tutmadığında. |

## Hesap türleri

| MVP | V1 kodu |
|---|---|
| Kredi kartı | `credit_card` |
| Banka kartı | `debit_card` |
| Vadesiz hesap | `current` |
| Vadeli hesap | `deposit` |
| Ek hesap (KMH) | `overdraft` |
| Döviz hesabı | `fx` |
| Altın hesabı | `gold` |
| Yatırım hesabı | `brokerage` |
| Kredi | `loan` |

Yatırım hesabı (`brokerage`) hangi ayların tam olduğuna ve bir ayın gelirinin bilinip bilinmediğine asla karar vermez;
o hesaptan fatura ödenmez, maaş yatmaz (`insights.NOT_BANK_ACCOUNTS`).

## Ekstreler ve dökümler

`Statement` kayıtlarının türleri:

- **Kart ekstresi** (`start` boş)
  - `previous` artı satırların toplamı `total`'e eşittir.
  - Paracard'da yalnızca toplam vardır (`total_is_sum`).
  - V1'de ayrıca son ödeme tarihi (`due_date`), asgari ödeme (`minimum_payment`) ve kartın toplam limiti
    (`credit_limit`) okunur; ekstre yazmıyorsa boş kalır ([bank-formats.md](bank-formats.md)).
- **Hesap hareketleri listesi** (`start` dolu)
  - `previous` ve `total` açılış ve kapanış bakiyesidir.
  - `balances` ay sonu bakiyeleridir.
  - `checks_ok` ve `checks_total`, satır satır bakiye kontrollerinin sonucudur.
- **Yatırım ekstresi:** hesabın nakdinin listesi ve `securities` (kod, adet, ekstre tarihindeki TL piyasa değeri).

Okumanın üç sonucu vardır:

- bir sonuç,
- `Skipped`: ekstre değil; şirket belgesiyse `business=True`,
- `Unreadable`: olduğu gibi okunamayan bir banka belgesi. Örnekler: şifreli PDF, şifreli ya da bozuk zip, OCR olmayan
  bir sistemde sayfa resmi PDF. Bu belgeler "okunamadı" durumunda saklanır, elle bakılır ve asla "kullanılmayan"
  olarak ayrılmaz.

## Doğrulama değişmezleri

| Belge | Kural |
|---|---|
| Kart ekstresi | Önceki bakiye artı satırlar, bankanın yazdığı toplama eşittir (V1'de en çok 1 kuruş fark). |
| Hesap listesi | Her satırda yazan bakiye, bir önceki bakiye artı tutara eşittir. |
| Yatırım ekstresi | Nakit bakiyeleri satır satır tutar. Yazılan kapanış nakdi, hisse toplamı ve portföy toplamı (hisseler + nakit) de tutar. |

Bir değişiklikten sonra daha az doğrulanan ekstre ya da yeni bir "okunamadı" belgesi çıkıyorsa bu bir gerilemedir ve
önce o düzeltilir. Gerçek belgelerdeki taban, veri klasöründe saklanır ve `iplikci dogrula --taban` ile karşılaştırılır.

Bir okuyucu belgesini tanıyıp okuyamazsa ya da okuduğu ekstre doğrulanmazsa banka biçimini değiştirmiş olabilir: okuma
işi olay kaydına `parser.format_alarm` yazar (ADR-0005). Bakiyesini denetleyecek kadar satırı olmayan hesap dökümü
alarm vermez.

Taban şunları kaydeder:

- belge sayıları, durumları ve okunamayan belgeler,
- doğrulanan ve toplam kart ekstreleri ile hesap dökümleri (hesap türlerine göre) ve doğrulanamayan ekstreler,
- dekont satırlarının durumları,
- ayların kapanış durumları,
- son 12 ayın gideri.

Aylar `--tarih` ile verilen güne göre kapanır (varsayılan: bugün). Gerileme bulunursa komut 1 ile biter ve kayıtlı taban
değişmez; bilinçli bir değişiklik `--kabul` ile kaydedilir. Taban veri klasöründe `baseline.json` olarak durur.

Taban sonuçlara bakar; arşivin kendisini iki komut daha denetler:

- `iplikci dogrula --arsiv`: arşivdeki her nesneyi yeniden özetler ve veritabanını arşivle karşılaştırır. Nesnesi
  kaybolmuş belge, hiçbir belgenin anmadığı nesne, SQLite'ın kendi denetimleri ve arama dizini buna dahildir. Bozulma ya
  da kayıp 1 ile biter.
- `iplikci dogrula --yeniden-kur`: birincil verileri (belgelerin adları ve gelişleri, düzeltmeler, denetim ve olay
  kayıtları) dışa aktarır, yanında yeni bir veritabanı kurar, her belgeyi arşivden yeniden okur ve iki analizin aynı
  çıktığını denetler.

## Kopyalar

- Bir ekstrenin içindeki satırlar asla tekilleştirilmez. Aynı gün aynı tutarlı satırlar gerçek alışverişlerdir.
- Kopya yalnızca aynı ekstrenin birden çok dosya olarak gelmesinden doğar. Böyle kopyalar (hesap, kesim tarihi, para
  birimi, başlangıç) üzerinden birleştirilir; satırı çok olan kopya kalır.
- Aynı hesabın iki hareket listesi aynı günleri kapsayabilir: kullanıcı listeleri istediği tarihlerle indirir (K24).
  Böyle bir günün satırları tek listeden sayılır (`analysis.one_list_per_day`):
  - o gün daha çok satırı olan liste (gün içinde alınmış bir liste günün sonraki hareketlerini göstermez),
  - eşitse daha ileri tarihe uzanan liste,
  - o da eşitse belge kimliği önce gelen.
- Listeler kendi satırlarını ve denetimlerini korur. Bir satırın parmak izi hangi listeden sayılırsa sayılsın aynıdır;
  kullanıcının notları ona bağlı kalır.

## Kanıtlar: dekontlar ve banka bildirimleri

Dekontlar (ve V1'de e-posta gövdesindeki banka bildirimleri), gün gün hesabın ekstreleriyle uzlaştırılır
(`analysis.settle_receipts`).

| MVP | V1 | Kural |
|---|---|---|
| `eslesti` | `matched` | Aynı hesapta aynı tutarlı bir ekstre satırı var ve tarihi kanıtın −1…+3 günü içinde (`POSTING_DAYS`). Kart ödemesi, kartın alacağıyla ya da ödeyen listedeki `kart_odemesi` satırıyla eşleşir. Sayılan ekstre satırıdır; kanıt yalnızca dayanaktır. Bir kanıtın bir satırı eşleşirse, ekstrenin farklı yazdığı diğer satırları (ücretler) da eşleşmiş sayılır. |
| `gecici` | `provisional` | Eşleşme yok ve kanıtın günleri hesabın en yeni ekstresinin ötesine uzanıyor (sonraki ekstre gösterebilir). Satır sayılır ve geçici olarak işaretlenir. |
| `eslesmedi` | `unmatched` | Ekstreler kanıtın bütün günlerini kapsıyor ama böyle bir satır yok. Satır hiçbir toplama girmez; bulgu olarak işaretlenir (ay kapanışında "kontrol"). |
| `ekstresiz` | `no_statement` | O günleri kapsayan ekstre yok. Sebebi ekstrenin hiç olmaması, ilk ekstreden önce kalması, bir boşluk ya da belgeleri en yeni ekstreden `ACTIVE_DAYS` = 180 günden eski olan bir hesap olabilir. Satır sayılır. |

- Ekstresi olmayan bir kart için ödeme dekontu (`ekstresiz_kart`), kartın ekstreleri dekont tarihinde ya da daha önce
  başlıyorsa `kart_odemesi` olur; ekstreler ödediği alışverişleri zaten gösterir.
- Kanıttaki transfer satırları adaydır (`aday`) ve liste satırlarıyla birlikte çözülür.
- Maskeli bir hesap numarası ("1234/****567"), o bankada ve o para biriminde, gösterilen hanelerle biten tek hesaba
  bağlanır (`analysis.resolve_masked`).
- Kart harcama bildirimi (V1) bir kart kanıtıdır: kart ekstresindeki aynı tutarlı satırla aynı pencerede eşleşir.

## Transferler

Para hareketi taşıyan hesap satırları, bütün hesaplar okunana kadar aday kalır. Sonra sırayla çözülür:

1. Kendi adı (belge sahipleri ya da `identity.names`, ad-soyad ve baş harf biçimleri dahil) ya da kendi hesap
   numarası metinde geçiyorsa → `own_transfer`.
2. Bir kategori kuralı karşı tarafı adlandırıyorsa → o kategori. Türü kuralın `_tür`'ü belirler:
   - `gelir` → `income`,
   - `kişi` → `p2p_transfer` ya da `income`,
   - `borç` → `loan_principal`,
   - `yatırım` → `investment`.
3. Başka birinin adını yazan satır ("Deniz Yılmazer den gelen havale tutarı", "… hesabından … hesabına" FAST'ında
   başka bir ad) o kişiden gelen ya da ona giden paradır: tutarı ve günü kendi aktarmanızın öbür ucuna ne kadar
   uysa da onunla eşleşmez, 8. adıma kalır. v0.9.14'e dek eşleşebiliyordu: bir hesaba bir gün önce başkasından
   gelen para, aynı bankadaki başka bir hesabınıza gönderdiğiniz paranın yerini alabiliyordu.
4. Eşleştirme, en sağlam işaretten başlar (`TRANSFER_DAYS`, −1…+4 gün):
   - İki ucu da kendi adınızı yazan satırlar birbirine bağlanır (`Reason.pair`).
   - Açık bir satır, başka bir kendi hesabında aynı tutarda ters ve kendi adınızı yazan bir satırla eşleşirse →
     `own_transfer`. Bu, 5. adımdan önce gelir: aynı tutarda adıyla yapılmış bir ödemeye benzemek, hesabınızdaki
     birebir karşılıktan zayıf bir işarettir.
5. Yalnızca alıcı bankayı yazan bir satır, aynı bankaya aynı tutarda adıyla yapılmış ödemenin türünü alır. Örnek:
   TEB'den ödenen kira.
6. Kalan açık satırlar, başka bir kendi hesabındaki aynı tutarda ters bir açık satırla → `own_transfer`. Yalnızca kart
   ekstresinde görünen kart ödemeleri de eşleşir.
7. Kullanıcının hesabı olan bir bankaya, o bankanın hiçbir listesinin kapsamadığı bir tarihte yapılmış ve yalnızca
   bankayı yazan ödeme → kendi transferi.
8. Kalan giden para → `p2p_transfer`; kalan gelen para → `income`.

Giden satır paranın gittiği bankayı yazıyorsa (TEB'in "TÜRKIYE GARANTI BANKASI A.Ş." satırı, Vakıfbank'ın "…
hesabından Türkiye Garanti Bankası A.Ş. … hesabına" FAST'ı), 4. ve 6. adımlar onu yalnızca o bankadaki bir hesabın
gelen parasıyla eşleştirir (`analysis._bank_fits`). Aynı gün aynı tutarda biri Ziraat'e, biri Garanti'ye iki havale
gittiyse Garanti hesabına gelen para Ziraat'e gidenin karşılığı olamaz; v0.9.11'e dek sırası önce gelen onu alıyordu.
Banka, programın banka adları tablosunda yoksa adlarının "Türkiye", "Bankası", "A.Ş." gibi kelimeleri atılınca kalan
kısmıyla karşılaştırılır.

Kart ödemeleri ve kart tarafındaki alacakları birbirini götürür; asla harcama sayılmaz.

**Yeri belli olmayan transfer** (`analysis.sent_after`): kendi transferinizin karşı tarafı hiçbir belgede yoksa ve
satır alıcı hesabı ya da yalnızca bankayı adlandırıyorsa, o hesabın (ya da o bankadaki hesapların) bakiyesi bu parayı
belgesinin gününden sonra henüz içermez. Defter bakiyeyi değiştirmez; notlar bunu söyler
([yorumlama](interpretation.md#varlıklar-ve-borçlar)).

## Taksitli nakit avans

- Kartın verdiği nakit avans bir borçtur: alındığı gün kendi hesabınıza gelir (kendi transferi), taksitlerle geri
  ödenir. Taksitlerin toplamının avanstan fazlası faiz ve vergidir.
- İş Bankası her taksidin faizini yazar (`FZ:… VR/FN:…`); okuyucu taksiti anaparaya (`loan_principal`) ve faize
  (`interest_fee`) ayırır.
- Garanti yalnızca taksiti yazar ("Alo Taksitli Nakit Avans 740,00x3=2.220,00"). Defter, avansın alındığı gün
  vadesiz hesaba gelen ve kartın son dört hanesini yazan satırı bulur (`analysis.split_card_advances`). n. taksit
  avanstan n − 1 ay sonra, en çok 3 gün kayarak yazılır. Her taksit avansın eşit bir payını anapara olarak öder (son
  taksit yuvarlamadan kalanı); geri kalanı faiz ve vergidir. Örnek: 2.000 TL'lik avans 3 taksitte 2.220 TL
  ödendiyse taksit başına 666,67 TL anapara (son taksitte 666,66 TL) ve 73,33 TL faizdir; toplam faiz 220 TL.
- Parçalar taksidin belgedeki yerini taşır ve kendi parmak izlerini alır; ekstrenin toplamı değişmez. Hesabın satırı
  yoksa taksit nakit avans kalır (v0.9.9'a dek hep öyleydi: faizi gider sayılmıyordu).
- Anapara Ay sonu'nun Kalan'ından "kredi ödemesi" olarak düşülür; faiz harcamadır.

## Kur çevirisi

- MVP'de dövizli satırlar belgelerde bulunan en yakın kurla çevrilir: açıklamalardaki `USD:` / `EUR:` ya da
  Vakıfbank'ın `İşlem Kuru`.
- V1'de bunlara kur servisleri eklenir ([mimari §15](../v1/architecture.md#15-döviz)). Döviz hesabının bir satırı
  şu sırayla seçilen kurla TL'ye çevrilir (`analysis.row_rate`):
  1. Satırın kendi kuru: açıklaması hesabın para biriminde bir kur yazıyorsa, bankanın o işlem için uyguladığı kur.
     Belgedeki kur o işlem için her zaman önce gelir.
  2. Yoksa kur sağlayıcısının o günkü kuru, **döviz alış** tarafıyla: dövizin o gün sahibine değeri buydu ve döviz
     hesabı bir varlıktır. Gün, o günün bülteni ya da en fazla bir hafta önceki son bülten demektir: cumartesinin
     satırı cumanın kurunu alır. Aynı gün TCMB'nin kuru ECB'ninkinden önce gelir; ECB'nin tek referans kuru iki taraf
     için de geçer.
  3. Yoksa belgelerin o güne en yakın kuru: ağ yokken yalnızca belgelerdeki kurlar bilinir.
  4. Hiçbiri yoksa satır dışarıda bırakılır ve uyarı yazılır.
- Kurun kendisi, günü (kuru yazan satırın ya da bültenin günü) ve kaynağı (belge, TCMB, ECB, Frankfurter) satırda
  saklanır; satırın kendi para birimindeki tutarı da. Satırın özgün tutarı kuruyla birlikte yazılır: "100,00 EUR ×
  36,4521" (sağlayıcının kuru TCMB'nin yazdığı gibi dört haneyle, belgenin kuru belgelerin hep gösterildiği gibi).
- Kur sağlayıcılarından hiç kur alınmamışsa sonuç MVP'deki gibidir: her satır belgelerin en yakın kuruyla çevrilir.
- Kendi hesapları arasındaki döviz hareketleri gidere girmez.

## Kapsama ve tam aylar

- **Kapsama:** her ayın bir hesabın belgelerince kapsanan payıdır.
  - İki kart ekstresi arasındaki boşluk, sonraki ekstre öncekinin toplamından başlıyorsa kapsanmış sayılır.
  - Kart ekstreleri kesim tarihinde biter; bu yüzden en yeni ay eksik kalır.
- **Tam aylar:** ortalama, eğilim ve tahmin yalnızca tam aylardan hesaplanır (`insights.complete_months`). Bir hesabın
  ilk ayı, hesap sıfır bakiyeyle başladıysa tam sayılır.
- **Gelir**
  - Gelir yalnızca hesap hareketi listesi olan aylarda bilinir; yalnızca kart belgesi olan aylarda tahmin edilmez.
  - Maaş ay sonlarına düşer; bir takvim ayında 0 ya da 2 maaş olabilir. Gelir takvim toplamlarından değil maaş
    serisinden alınır.

## Bölünmüş satırlar (F04)

Kullanıcı bir satırı birden çok kategoriye bölebilir: bir market fişinin bir kısmı ev eşyası, bir faturanın bir kısmı
cihaz taksiti olabilir.

- Yalnızca harcama, kişiye gönderilen para ve gelir bölünür. Kendi hesapları arası transfer, kart ödemesi, borç ve
  yatırım bölünmez: bunları türleri belirler.
- Parçalar satırın türünü, gününü, hesabını, belgesini ve notunu korur; yalnızca kategorileri, gereklilikleri ve
  tutarları kendilerinindir. Bir parçayı başka türde saymanın yolu bir kuraldır.
- Parçaların toplamı satırın tutarına kuruşu kuruşuna eşittir. Kur değişip satırın TL tutarı oynarsa parçalar aynı
  oranla paylaştırılır; yuvarlamadan kalanı son parça alır.
- Toplamlarda satırın yerini parçaları alır; her biri kendi kategorisinde sayılır. Ödeme düzeyindeki işler (düzenli
  ödeme serileri, büyük harcama, olağan dışı hareket, işlem sayıları) satırın bütününe bakar: bölünmüş bir satır tek
  ödemedir.
- Değerlendirme'nin üç aylık tahmininde son ödemesi bölünmüş düzenli bir ödeme parçalarıyla görünür: her parça
  kendi kategorisinde, aylık tutardan kendi payıyla. Kategori, grup ya da gereklilik süzgeci yalnızca tuttuğu
  parçaları sayar.
- Bölünmüş satırın kategorisi ve gerekliliği parçalarındadır; satırın kendisine ayrıca verilmez.
- Bir kural değişikliği satırın türünü bölünmeyen bir türe çevirirse ya da tutarı bir parçayı sıfıra indirecek kadar
  değişirse satır yeniden bütün sayılır. Parçalar düzeltmede saklanır, Yapılacaklar'da "Uygulanamayan bölme" çıkar.
- Bir dekontun bölünmüş satırını ekstre gösterince bölme ekstrenin satırına geçer; parçaların eski adresleri ekstrenin
  aynı parçalarını açar.

## Banka dışı faturalar (V1)

Banka dışı e-postalardan okunan fatura, makbuz ve siparişler sayılmaz. Esas olan banka akışlarıdır (K12). Bunlar
yalnızca banka satırlarıyla eşleştirilir:

| Durum | Kural |
|---|---|
| `matched` (eşleşti) | Aynı tutarda (dövizliyse kur farkı payıyla) bir banka satırı var. Faturada pencere fatura tarihinden son ödeme tarihine (+3 gün) kadardır; makbuzda −1…+3 gündür. Satıcı adı işyeriyle benzeşmelidir. Banka satırı faturayla ve kalemlerle zenginleşir. |
| `pending` (bekliyor) | Son ödeme tarihi gelmedi; takvimde yaklaşan ödeme olur. |
| `unmatched` (eşleşmedi) | Pencere geçti, satır yok. Bilgi olarak görünür, toplamlara girmez. Olası nedenler: başkası ödemiş, belgesi olmayan bir hesaptan ya da nakit ödenmiş, ya da hiç ödenmemiş. |

Uygulama (`invoices.py`):

- Tutar TL'de kuruşu kuruşuna aynıdır. Dövizli bir belgede satırın yazdığı döviz tutarı ("19,99 USD") aranır; TL
  tutarı bankanın kuruyla değişir.
- Son ödeme tarihini yazmayan faturanın penceresi tarihinden 30 gün sonrasına (artı 3 gün) kadardır.
- Satıcı adının kim olduğunu söyleyen bir kelimesi (dört harf ve üstü; hukuki biçim, iş kolu ve yer adı değil:
  "TURKCELL İLETİŞİM HİZMETLERİ A.Ş." → TURKCELL) satırın metninde bitişik ya da ayrı geçmelidir. Tutar ve tarih tek
  başına yetmez.
- Bir satır yalnızca bir belgeyi öder; eski belge önce seçer. Birden çok satır uyarsa faturada son ödeme tarihine,
  makbuzda belgenin tarihine en yakın olan alınır.
- Belgenin penceresi, hâlâ gelen hesapların belgelerinin ulaştığı son günden sonra bitiyorsa belge bekler: o günleri
  kapsayacak ekstre henüz gelmemiştir. Belgeleri en yenisinden 62 günden çok önce biten hesap sayılmaz.
- Aynı satıcı, numara, tarih ve tutarla iki kez gelen belge tek belgedir.
- Bekleyen bir TL faturası, son ödeme tarihi takvime düşer; satıcının bir önceki faturasını ödeyen hesaptan çıkar.
  Yabancı para birimindeki fatura takvime ve öngörüye girmez: TL tutarı banka çekince belli olur.
- Satıcının süren bir düzenli ya da dönemsel ödemesi varsa (ödeme alanı satıcıya eşleşmedeki gibi benziyorsa) bekleyen
  fatura o ödemenin kendisidir: faturanın günlerine düşen ilk beklenen ödeme faturanın tutarını alır, dayanağında
  faturanın numarası ve son ödeme tarihi yazar; fatura ayrıca takvime ve öngörüye girmez. Ödemenin günü, hesabı ve
  türü serininkidir: banka satıcıya şimdiye dek o gün ödedi, kartın çektiği bir ödeme de kartındır. Böylece aynı ödeme
  iki kez düşülmez.
- Hiçbir kuralın adlandırmadığı ("Diğer Harcamalar") eşleşmiş satır, kategorisini satıcının tam adından alır: kurallar
  "ÖRNEK ECZANESİ"ni tanır, bankanın yazdığı "IYZICO \*ORNEK"i tanımaz. Kategori satırı başka türlü sayacaksa (yatırım,
  borç) alınmaz; satırın türü ve tutarı değişmez. Kullanıcının düzeltmesi bundan sonra uygulanır.
