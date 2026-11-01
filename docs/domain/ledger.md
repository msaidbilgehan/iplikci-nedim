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
  - V1'de ayrıca son ödeme tarihi, asgari ödeme ve (yazıyorsa) limit okunur.
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
- `iplikci dogrula --yeniden-kur`: birincil verileri (belgelerin adları ve gelişleri, düzeltmeler, denetim kaydı) dışa
  aktarır, yanında yeni bir veritabanı kurar, her belgeyi arşivden yeniden okur ve iki analizin aynı çıktığını denetler.

## Kopyalar

- Bir ekstrenin içindeki satırlar asla tekilleştirilmez. Aynı gün aynı tutarlı satırlar gerçek alışverişlerdir.
- Kopya yalnızca aynı ekstrenin birden çok dosya olarak gelmesinden doğar. Böyle kopyalar (hesap, kesim tarihi, para
  birimi, başlangıç) üzerinden birleştirilir; satırı çok olan kopya kalır.

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
3. Yalnızca alıcı bankayı yazan bir satır, aynı bankaya aynı tutarda adıyla yapılmış ödemenin türünü alır. Örnek:
   TEB'den ödenen kira.
4. Başka bir kendi hesabında −1…+4 gün içinde aynı tutarda ters bir satır varsa → `own_transfer`. Yalnızca kart
   ekstresinde görünen kart ödemeleri de eşleşir.
5. Kullanıcının hesabı olan bir bankaya, o bankanın hiçbir listesinin kapsamadığı bir tarihte yapılmış ve yalnızca
   bankayı yazan ödeme → kendi transferi.
6. Kalan giden para → `p2p_transfer`; kalan gelen para → `income`.

Kart ödemeleri ve kart tarafındaki alacakları birbirini götürür; asla harcama sayılmaz.

## Kur çevirisi

- MVP'de dövizli satırlar belgelerde bulunan en yakın kurla çevrilir: açıklamalardaki `USD:` / `EUR:` ya da
  Vakıfbank'ın `İşlem Kuru`.
- V1'de bunlara kur servisleri eklenir:
  - Belgedeki kur o işlem için her zaman önce gelir.
  - Belgede kur yoksa TCMB ya da ECB kuru kullanılır ([mimari §15](../v1/architecture.md#15-döviz)).
  - Kurun kaynağı ve tarihi satırda saklanır.
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

## Banka dışı faturalar (V1)

Banka dışı e-postalardan okunan fatura, makbuz ve siparişler sayılmaz. Esas olan banka akışlarıdır (K12). Bunlar
yalnızca banka satırlarıyla eşleştirilir:

| Durum | Kural |
|---|---|
| `matched` (eşleşti) | Aynı tutarda (dövizliyse kur farkı payıyla) bir banka satırı var. Faturada pencere fatura tarihinden son ödeme tarihine (+3 gün) kadardır; makbuzda −1…+3 gündür. Satıcı adı işyeriyle benzeşmelidir. Banka satırı faturayla ve kalemlerle zenginleşir. |
| `pending` (bekliyor) | Son ödeme tarihi gelmedi; takvimde yaklaşan ödeme olur. |
| `unmatched` (eşleşmedi) | Pencere geçti, satır yok. Bilgi olarak görünür, toplamlara girmez. Olası nedenler: başkası ödemiş, belgesi olmayan bir hesaptan ya da nakit ödenmiş, ya da hiç ödenmemiş. |
