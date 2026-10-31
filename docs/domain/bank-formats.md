# Banka belgeleri: biçimler ve tuzaklar

Kaynak: MVP'nin `CLAUDE.md` dosyası (2026-10-31), kişisel bilgilerden arındırılmıştır. Okuyucu yazarken ya da
düzeltirken önce buraya bakılır; yeni bir tuzak bulununca buraya eklenir.

## Genel

**Tutar biçimleri**

- Tutarlar Türkçe biçimdedir: `1.234,56`, `+123,45`, `1.234,00+`, `TL.1.500,-`.
- İstisnalar QNB'nin belgeleri ve Garanti BBVA Yatırım'dır: ikisi de ABD biçimini kullanır (`1,234.56`).

**Metin eşleştirme**

- PDF'ler boşlukları ve Türkçe harfleri düşürebilir. Metin bu yüzden `textutil.fold()` (ASCII büyük harf) ve
  `squash()` (boşluksuz) üzerinden eşleştirilir.
- `fold()` boşlukları birleştirir ve birleşik işaretleri atar; bu yüzden metnin uzunluğunu korumaz.
  - Katlanmış metinde bulunan bir konumla özgün metin asla kesilmez.
  - Bunun yerine kelime kelime katlanır ve özgün kelimeler tutulur (örnek: `qnb._other_side`).

**Kart PDF'leri:** sütun konumuyla okunur (`pdfutil.page_lines`, `find_header`, `take_amount`). Düz metin üzerinde
düzenli ifadeyle okunmaz.

**Şirket belgesi işaretleri**

- İşaretler yalnızca dosya adlarında, belge başlıklarında ve hesap sahibi alanında aranır. Kişisel ekstreler işlem
  satırlarında şirketin adını geçirebilir (ör. `GOOGLE*GSUITE <şirket alan adı>`); bu satırlar belgeyi şirket belgesi
  yapmaz.
- Genel işaretler:
  - ŞİRKET KREDİ KARTI
  - GİRİŞİMCİ KREDİ KART
  - KREDİLİ TİCARİ MEVDUAT
  - ÜCRET BORDROSU
  - AYLIK ÖZET RAPORU
- Kullanıcının şirket adları ayarlardan gelir (`identity.business_names`); koda yazılmaz.

**Arşivler**

- Zip, mbox ve e-posta ekleri bellekte okunur, diske çıkarılmaz.
- UTF-8 bayrağı olmayan zip üye adları cp437 olarak çözülür.
- 50 MB'tan büyük üyeler atlanır.
- Şifreli ya da bozuk bir zip, tek bir "okunamadı" belgesi olarak bütün hâlinde kalır; asla içi boşaltılmış bir arşiv
  olarak kalmaz.

**HTML kodlaması:** HTML belgeler UTF-16 olabilir ve bayt sırası işaretiyle (BOM) başlayabilir. Örneğin TEB'in yıllık
stopaj mektubu böyledir; şirkete gönderildiği için şirket belgesidir.

**İşlenmeyen belgeler:** hiçbir okuyucunun almadığı bir belge, ilk sayfasındaki en erken işarete göre adlandırılır
(`common.not_a_statement`): sigorta poliçesi, kredi sözleşmesi ya da formu, talimat formu, sözleşme. Bu belgeler para
hareketi taşımaz. V1'de çöpe gitmez; "işlenmedi" durumunda saklanır (K11).

**E-posta göndericileri:** ekstre e-postaları şu alan adlarından geldi; hepsi Gmail'de DMARC'tan geçiyor:

- `garantibbva.com.tr`
- `ileti.isbank.com.tr`
- `email.qnb.com.tr`
- `email.qnbfinansbank.com`
- `teb.com.tr`

## Garanti BBVA

**Bonus kredi kartı PDF'i** (`BONUS` + `DONEMBORCUNUZ`)

- `DEVİR` satırı önceki bakiyedir.
- Tarihsiz dönem kalemleri (DÖNEM FAİZİ, KKDF + BSMV) kesim tarihini alır.
- Alışverişlerin üstündeki başlık, genel bir başlık değilse bankanın kategorisidir.
- "NAKİT AVANS BİLGİLERİ" ve "NAKİT ÇEKİM" altındaki satırlar ATM'den nakit çekimdir; yalnızca makinenin yerini
  yazar.
- "ERTELENEN EKSTRE TUTARI" harcama değil, ertelemedir: `transfer` türündedir ve eşleşen ödeme satırıyla birlikte
  gelir.
- Taksitler `250,00x12=… 8.Taksit` biçiminde yazar (8/12).
- Görünmez `bosluk` kelimeleri atılır.

**Paracard banka kartı PDF'i:** bakiye yoktur; toplam, alışverişler ile nakit çekimlerin toplamıdır.

**Hesap XLS'i**

- Başlık satırı `Tarih | Açıklama | Etiket` biçimindedir.
- `Hesap` alanı `şube - numara PARA` biçimindedir.
- Şirket hesabında `Ad Soyad` yerine `Şirket Ünvanı` yazar.
- `Etiket = Para Transferi` satırları karşı tarafı taşır.
- Döviz satırları kuru yazar (`EUR:54.44500`).

**Dekont PDF'i** (`garanti_dekont`: "Dekont" + `HESAP NUMARASI` + `SIRA NO`)

- Sol sütun `ETİKET : değer` biçimindedir.
- Müşterinin adı ve adresi, üst blokta x 300'ün sağındadır.
- Başlık `ŞUBE ADI`'nın üstündedir: "HESAPTAN FAST", "HESAPTAN HESABA HAVALE", "GELEN FON TRANSFERİ".
- Tutar `SIRA NO` satırındadır ("TUTAR : - 500,00 TL").
- Ücret (`KOMİSYON/MASRAF TOPLAMI`) `KOMİSYON/MASRAF HESABI`'ndan alınır.
- Gelen transfer dekontları hesap numarasını ve adı maskeler.

**Garanti BBVA Yatırım** (`garanti_yatirim`, ABD sayı biçimi)

- Aylık hisse ekstresi emanet hesabı başınadır (`<emanet no>-100`, `-101`). Son iş günü tarihlidir ama bütün takvim
  ayını kapsar.
- 1. sayfa ("Hesap Durumu"):
  - Nakit "Mevcudu" satırındadır.
  - Hisseler `HS` satırlarındadır; değer sütunu x 400–480 aralığındadır.
  - "Hisse toplamı" ve "Portföy toplamı(TL)" yazar. Portföy toplamının değeri daha aşağıda, x ≥ 500'dedir ve çoğu
    zaman bir alt bilgi satırının içine düşer.
- "Hesap Ekstresi" sayfası nakit hareketlerini taşır:

  | Satır | Anlamı |
  |---|---|
  | `Devir` | açılış bakiyesi |
  | `HS <fiyat>x<adet> KOD` satışı | `yatirim` (investment) |
  | `Komisyon`, MKK ücretleri | `faiz_ucret` (interest_fee) |
  | `<KOD>.E Temettü` girişi | `gelir` (income) |
  | aktarılan temettü ya da satış geliri, "Nolu Hesabın Banka …" | aday transfer; karşı taraf hesap sahibi, yani kendi transferi |
- "İŞLEM SONUÇ FORMU" (Türkçe biçim, üç ondalık) işlemlerin ve ücretlerin dekontudur.

## İş Bankası

**Maximum kart PDF'i** (`KREDIKARTIHESAPOZETI` + `MAXIPUAN`)

- Başta `+` olan satır alacaktır.
- `*** ÖNCEKİ…` önceki bakiyedir.
- Taksitli nakit avanslar `FZ:… VR/FN:…` yazar (bazen bir sonraki satırda). Bu satırlar anaparaya (`kredi_anapara`) ve
  faize (`faiz_ucret`) bölünür.
- "HESAP ÖZETİNE AKTARILAN" döviz bakiyesini TL ekstresine taşır (`transfer`).
- Sol kenardaki `-` işaretleri katlama izidir, eksi işareti değildir.

**Hesap XLS'i**

- Başlık `Tarih/Saat` ile başlar.
- IBAN şube (4) ve hesap (7) haneleriyle biter.
- Para birimi `Mevcut Bakiye`'den gelir.
- FAST, EFT ve havale açıklamaları `AD*` ile başlar.

**FAST/EFT dekont PDF'i** (`isbank_dekont`)

- İki sütun `Etiket : değer` vardır: gönderen ve tutarlar solda, alıcı x 290'ın sağında.
- Hesap sahibi ilk satırı açar.
- "FAST Ücreti ve Vergi" ücrettir.

**e-cüzdan** (`isbank_cuzdan`; 31 günlük vadeli gibi yeni bir hesabın cüzdanı)

- 1. sayfa: sağ sütunda `Etiket: değer`.
- 2. sayfa: satırlar en yeniden eskiye sıralıdır: `#` en yeniden sayar, sonra tarih-saat, `Tutar`, `Kalan`.
- Açılış günü başlayan cüzdan sıfırdan başlar.
- "HESAP AÇMA İŞLEMİ a -> b" kendi transferidir.

## TEB

**Bonus kart PDF'i** (`KREDIKARTEKSTREOZETI`)

- Bazıları sayfa resmi olarak gelir; macOS Vision OCR ile okunur (`pdfutil.ocr_page_lines`, tr-TR).
- `(9/8. Taksit)` "9 taksitten 8'incisi" demektir.
- `(Yurt dışı işlem tutarı EUR.25,75)` orijinal tutardır.
- Bir ekstrede birden çok kart bölümü olabilir.
- OCR, temassız ikonunu `)))` olarak okur.

**Kart ödeme dekontu PDF'i:** `ekstresiz_kart` (`card_payment_no_statement`) türündedir; ekstresi olmayan bir karta
yapılan ödemedir.

**Hesap dökümü:** `.xls` adıyla kaydedilmiş bir HTML'dir; 7 sütunlu satırlar en yeniden eskiye sıralıdır.

- Önce `Hesap Sahibi` alanı şirket işaretleri için denetlenir.
- Eksiye düşen TL hesabı KMH'dir.
- `GR` altın hesabıdır.
- Giden transferler yalnızca alıcı bankayı yazar ("TÜRKIYE GARANTI BANKASI A.Ş.").
- "… no.lu hesaba gönderilmiştir", alıcı tarafta bile kendi hesabını adlandırır.
- "Müşteriye TL karşılığı Altın satışı", kullanıcının altın almasıdır.

## Vakıfbank

**Hesap XLSX'i** (`VB MUSTERI NO`)

- Satırlar eskiden yeniye sıralıdır.
- `RUMUZ` etikette görünen takma addır.
- Maaş satırları işvereni `(<kod>_<kod>_<AD>)` olarak taşır.
- Karşı taraf, banka adından sonraki addır ("… A.Ş. <Ad Soyad> hesabına/hesabından").
- Döviz satırları `İşlem Kuru` yazar.

**e-cüzdan PDF'i** (`vakifbank_cuzdan`): mevduat koşulları 1. sayfada, hesap (`Cüzdan Seri No`, satırlar
`NO tarih tutar bakiye metin`) sonraki sayfalarda.

## QNB

**Kart ve hesap PDF'leri**

- Kart PDF'i `QNB Kredi Kart` ve `Kredi Kartı Numarası` ile tanınır; hesap PDF'i `Hesap Hareketleri` ve QNB IBAN'ı ile.
- Yazı tiplerinde Türkçe glifler yoktur: `(cid:N)` görünür ve harfler düşer. Sınıflama için gereken etiketler
  `qnb_pdf._REPAIRS` içinde onarılır.
- Hesap listesi `DEVREDEN BAKİYE` ile açılır.
- `Transfer İşlemleri - Alıcı/Gönderen :` başlıkları sonraki satırlara taşar.

**e-dekont** (HTML; utf-8 ya da windows-1254; ya da PDF)

- Türleri:
  - kredi taksidi (anapara ile faiz, KKDF ve BSMV),
  - ekstresi olmayan bir karta ödeme,
  - transferler (aday).
- Karşı taraf, gelende `GÖNDEREN`'den, gidende `ALICI`'dan sonraki addır; bir sonraki etikete kadar sürer.
- Dekont anahtarı `FİŞ NO`'dur.
- Bazı gelen transfer bildirimlerinde tutar satırı hiç yoktur; bunlar "dekontta tutar yazmıyor" nedeniyle atlanır.

## V1'de eklenecek bilgiler

E-posta gövdesi okuyucuları (banka bildirimleri) ve banka dışı göndericiler yazıldıkça biçimleri ve tuzakları burada,
bankanın başlığı altında belgelenir. Örnek gerçek belgeler depoya girmez; okuyucunun sahte belge üreticisi bu bilgiyle
yazılır.
