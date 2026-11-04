# Banka belgeleri: biçimler ve tuzaklar

Kaynak: MVP'nin `CLAUDE.md` dosyası (2026-10-31), kişisel bilgilerden arındırılmıştır. Okuyucu yazarken ya da
düzeltirken önce buraya bakılır; yeni bir tuzak bulununca buraya eklenir.

## Genel

**Tutar biçimleri**

- Tutarlar Türkçe biçimdedir: `1.234,56`, `+123,45`, `1.234,00+`, `TL.1.500,-`.
- İstisnalar QNB'nin belgeleri ve Garanti BBVA Yatırım'dır: ikisi de ABD biçimini kullanır (`1,234.56`).

**Metin eşleştirme**

- PDF'ler boşlukları ve Türkçe harfleri düşürebilir. Metin bu yüzden `domain.text.fold()` (ASCII büyük harf) ve
  `parsers.text.squash()` (boşluksuz) üzerinden eşleştirilir.
- `fold()` boşlukları birleştirir ve birleşik işaretleri atar; bu yüzden metnin uzunluğunu korumaz.
  - Katlanmış metinde bulunan bir konumla özgün metin asla kesilmez.
  - Bunun yerine kelime kelime katlanır ve özgün kelimeler tutulur (örnek: `parsers/qnb/edekont.py` içindeki
    `_other_side`).

**Kart PDF'leri:** sütun konumuyla okunur (`parsers.pdf.page_lines`, `find_header`, `take_amount`). Düz metin üzerinde
düzenli ifadeyle okunmaz.

**Kart ekstresinin ödeme bilgileri** (`Statement.due_date`, `minimum_payment`, `credit_limit`)

- Kesim tarihi ve dönem borcu gibi, ilk sayfanın metnindeki etiketlerinden okunur.
- Son ödeme tarihi bu ekstrenin son ödeme tarihidir. "Bir Sonraki Son Ödeme Tarihi" ve "son ödemeniz …" gelecek
  ekstrenindir; alınmaz.
- Limit, kartın toplam limitidir; müşteri limiti, kullanılabilir limit ve nakit limiti değildir.
- Ekstrenin yazmadığı ya da bozuk yazdığı bilgi boş kalır; tahmin edilmez ve ekstre yine okunur.
- Bir bilgi birden çok kez yazıyorsa hepsi aynı olmalıdır; ayrışırsa bilgi boş kalır (`common.agreed`).

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
- Seçim, PDF'lerde işaretleri ilk sayfanın ilk 600 karakterinde arar. Girişimci ve şirket kartı işareti sayfanın
  ilerisinde de çıkabilir; TEB Bonus ve İş Bankası Maximum okuyucuları bütün ilk sayfaya bakar ve belgeyi şirket belgesi
  olarak bildirir.

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
- Taksitli nakit avans ("Alo Taksitli Nakit Avans 740,00x3=2.220,00 3.Taksit") de bu başlığın altındadır. Ekstre
  yalnızca taksiti yazar; faizi ayrı yazmaz, avansın kendisini de yazmaz. Avans, alındığı gün vadesiz hesaba gelir:
  hesabın satırı kartın son dört hanesini yazar ("**** ****1234 CC-03 Taksitli Nakit Avans İşlemi"). Defter
  taksitleri bu satırla anapara ve faize ayırır ([defter](ledger.md#taksitli-nakit-avans)).
- "ERTELENEN EKSTRE TUTARI" harcama değil, ertelemedir: `transfer` türündedir ve eşleşen ödeme satırıyla birlikte
  gelir.
- Taksitler `250,00x12=… 8.Taksit` biçiminde yazar (8/12).
- Görünmez `bosluk` kelimeleri atılır.
- Tarihler ay adıyla yazar ("5 Temmuz 2026"); ay adı katlanarak (`TEMMUZ`, `AGUSTOS`) sayıya çevrilir.
- Özet soldadır, adres sağda. Sayfanın metni adresin son satırlarını özetin satırlarına ekler: "Nakit Avans Limiti
  18.000,00 TL KAT:3 D:5", "Hesap Kesim Tarihi 5 Temmuz 2026 34000 <İLÇE> <İL>". Yıldan sonraki beş haneli sayı
  posta kodudur, tarihin parçası değildir.
- Son ödeme tarihi iki kez yazar: ilk satırdaki başlıkta ("… Bilgileriniz Son Ödeme Tarihi: 15 Ağustos 2026") ve
  özette ("Son Ödeme Tarihi 15 Ağustos 2026").
- "EKSTRE ÖZETİ" cümlesi gelecek ekstreyi anlatır: "Bir sonraki hesap kesiminiz … ve son ödemeniz 15 Eylül 2026
  Pazartesi 'dir." Bu tarih alınmaz.
- Kart limiti "Kart Limiti" satırıdır; üstündeki "Müşteri Limiti", altındaki "Nakit Avans Limiti" ve cümledeki
  "kullanılabilir limitiniz" değildir.
- İlk iki sayfada asgari ödeme tutarı yazmaz; boş kalır.

**Paracard banka kartı PDF'i:** bakiye yoktur; toplam, alışverişler ile nakit çekimlerin toplamıdır. Ödeme bilgisi
de yoktur.

**Hesap XLS'i**

- Başlık satırı `Tarih | Açıklama | Etiket` biçimindedir.
- `Hesap` alanı `şube - numara PARA` biçimindedir.
- Şirket hesabında `Ad Soyad` yerine `Şirket Ünvanı` yazar.
- `Etiket = Para Transferi` satırları karşı tarafı taşır.
- Döviz satırları kuru yazar (`EUR:54.44500`).
- Üst blok indirildiği anı (`İndirme Tarihi | 30/10/2026 09:41`), bakiyeyi ve kullanılabilir bakiyeyi yazar. Son
  gününü o saate kadar kapsar: aynı gün sonra yapılan bir transferin bildirimi dökümde görünmez, geçici kalır.
  Okuyucu bu alanları henüz okumuyor.

**Dekont PDF'i** (`garanti.receipt`: "Dekont" + `HESAP NUMARASI` + `SIRA NO`)

- Sol sütun `ETİKET : değer` biçimindedir.
- Müşterinin adı ve adresi, üst blokta x 300'ün sağındadır.
- Başlık `ŞUBE ADI`'nın üstündedir: "HESAPTAN FAST", "HESAPTAN HESABA HAVALE", "GELEN FON TRANSFERİ".
- Tutar `SIRA NO` satırındadır ("TUTAR : - 500,00 TL").
- Ücret (`KOMİSYON/MASRAF TOPLAMI`) `KOMİSYON/MASRAF HESABI`'ndan alınır.
- Gelen transfer dekontları hesap numarasını ve adı maskeler.

**Garanti BBVA Yatırım** (`garanti.brokerage`, ABD sayı biçimi)

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

**Para transferi bildirimleri** (`garanti.notice.transfer`, e-posta gövdesi, "Para Transferi Bilgilendirmesi")

- Belirli bir tutarın üzerindeki giden transferler için gelir. İki yerleşim vardır:
  - Eski yerleşim (`info.garantibbva.com.tr`, 2024): müşteriyi adıyla selamlar ("Sayın …,"). Türü ilk cümlede yazar:
    "Havale Para transferi …", "Başka Banka Para transferi …", "EFT Emri Para transferi emriniz işleme alınmıştır".
  - Yeni yerleşim (`garantibbva.com.tr`, 2025'ten beri): "Giden PT Bilgilendirmesi - 'Havale' işlem tipi için email …
    Başka Bankaya Transfer" diye açılır. Başlık her türe "Havale" der; tür alt başlıktan okunur.
- İkisi de şunları yazar:
  - gönderenin bloğu: ad, şube ("MERKEZ - 106"), hesap numarası;
  - alıcının bloğu: ad ve IBAN; yeni yerleşimde bankanın adı da; Garanti içindeki bir alıcıda "/ şube - kod hesap";
  - `Tutar:`, `İşlem Tarihi: gg.aa.yyyy ss:dd` ve `Açıklama:` (gönderenin notu).
- 2026'dan beri adlar her kelimenin ilk harfleri dışında, hesap numarası son üç hane dışında maskelidir ("****567").
  Önceden ikisi de tam yazılırdı. Maskeli hesap, aynı bankada son üç hanesi tutan hesaba geçer.
- Selam, e-postanın kime yazıldığını; gönderenin bloğu ise hesabın kimin olduğunu söyler. Şirket denetimi ikisine de
  bakar.
- Referans numarası yoktur. Bildirim hesabıyla, dakikasıyla ve tutarıyla tanınır.
- Garanti aynı transferlerin bazıları için dekont da gönderir. Analiz böyle bir hareketi bir kez sayar: aynı hesap, gün
  ve tutar, birbirini tutan adlar. Dekontun satırı kalır, bildirimin satırı düşer.
- Yalnızca giden transferler bildirilir. Döviz satışı, gelen havale ya da karttan nakit avans için bildirim gelmez.
  Hesaba önce para girip sonra transferle çıktıysa (ör. döküm 0,00 TL'yle alınmış, sonra döviz bozulup
  gönderilmiş), bildirim bakiyeyi sıfırın altına indirir. Ek hesabı olmayan bir hesap için bu, belgede görünmeyen bir
  giriştir: bakiye 0 sayılır ([yorumlama](interpretation.md#varlıklar-ve-borçlar)).

**HGS ekstresi iletisi** ("HGS EKSTRE BİLGİLENDİRME") hiç veri taşımaz. Geçişlerin ve yüklemelerin İnternet/Mobil
Şube'den görülebileceğini söyler. Tutar içermediği için "ayrıntısı internet şubesinde" diye sınıflanır.

## İş Bankası

**Maximum kart PDF'i** (`KREDIKARTIHESAPOZETI` + `MAXIPUAN`)

- Başta `+` olan satır alacaktır.
- `*** ÖNCEKİ…` önceki bakiyedir.
- Taksitli nakit avanslar `FZ:… VR/FN:…` yazar (bazen bir sonraki satırda). Bu satırlar anaparaya (`kredi_anapara`) ve
  faize (`faiz_ucret`) bölünür.
- "HESAP ÖZETİNE AKTARILAN" döviz bakiyesini TL ekstresine taşır (`transfer`).
- Sol kenardaki `-` işaretleri katlama izidir, eksi işareti değildir.
- Özet tarihleri noktayla yazar: "Hesap Kesim Tarihi: 05.10.2026", "Son Ödeme Tarihi: 15.10.2026".
- Asgari tutar sabit genişlikte basılır, boş haneleri yıldızdır: "Ödenmesi Gereken Asgari Tutar: *1.258,21 TL", bin
  liranın altında "*.597,67 TL". Tutar yıldızlardan ve öndeki noktadan sonra okunur.
- Özetteki "Bir Sonraki Hesap Kesim Tarihi" ve "Bir Sonraki Son Ödeme Tarihi" gelecek ekstrenindir.
- Son ödeme tarihi aşağıda, limit kutusunun üstünde bir kez daha, eğik çizgiyle yazar: "Son Ödeme Tarihi:
  15/10/2026".
- Limit ve faiz kutusu iki sütundur; sayfanın metni iki sütunu tek satırda birleştirir ("Toplam Kart Limiti:
  60.000,00 TL Asgari Ödeme Oranı: %40,00").
  - Kart limiti "Toplam Kart Limiti"dir; "Müşteri Limiti", "Toplam Kullanılabilir Kart Limiti" ve "Nakit Çekme
    Limiti" değildir.
  - "Asgari Ödeme Oranı" bir orandır, asgari tutar değildir.

**Hesap XLS'i**

- Başlık `Tarih/Saat` ile başlar.
- IBAN şube (4) ve hesap (7) haneleriyle biter.
- Para birimi `Mevcut Bakiye`'den gelir.
- FAST, EFT ve havale açıklamaları `AD*` ile başlar.

**FAST/EFT dekont PDF'i** (`isbank.receipt`)

- İki sütun `Etiket : değer` vardır: gönderen ve tutarlar solda, alıcı x 290'ın sağında.
- Hesap sahibi ilk satırı açar.
- "FAST Ücreti ve Vergi" ücrettir.

**e-cüzdan** (`isbank.passbook`; 31 günlük vadeli gibi yeni bir hesabın cüzdanı)

- 1. sayfa: sağ sütunda `Etiket: değer`.
- 2. sayfa: satırlar en yeniden eskiye sıralıdır: `#` en yeniden sayar, sonra tarih-saat, `Tutar`, `Kalan`.
- Açılış günü başlayan cüzdan sıfırdan başlar.
- "HESAP AÇMA İŞLEMİ a -> b" kendi transferidir.

**Gecikmiş kart borcu tahsilatı bildirimi** (`isbank.notice.collection`; "Hesabınızdan Gecikmedeki Kredi Kartı
Borcunuzun Tahsilatı")

- Tek cümledir: "1234 no ile biten kredi kartınıza ait son ödeme tarihinde ödenmeyen 1.258,21 TL'lik borç tutarı,
  1234-123456 no'lu hesabınızdan takas yoluyla tahsil edilmiştir."
- Gün yazmaz: gün, iletinin Türkiye saatine göre tarihidir.
- Hesap numarası yedi hanesinin baştaki sıfırını yazmaz (listelerde 1234-0123456).
- Satır, bir kart ödeme dekontu gibi karta yazılır: sonraki ekstre gösterir, o gelene dek kart borcunu düşürür.
  Hesap tarafı hesabın listesindeki satırdır.

## TEB

**Bonus kart PDF'i** (`KREDIKARTEKSTREOZETI`)

- Bazıları sayfa resmi olarak gelir; macOS Vision OCR ile okunur (`parsers.pdf.ocr_page_lines`, tr-TR).
- `(9/8. Taksit)` "9 taksitten 8'incisi" demektir.
- `(Yurt dışı işlem tutarı EUR.25,75)` orijinal tutardır.
- Bir ekstrede birden çok kart bölümü olabilir.
- OCR, temassız ikonunu `)))` olarak okur. Okuyucu bunu satırın sonundan atar; metni bitiren kapama parantezi
  (`(9/8. Taksit)` gibi) kalır.
- MVP'nin bildiği düzen, ödeme bilgilerinden yalnızca son ödeme tarihini yazar: "Son Ödeme Tarihi: 15/10/2026".
  "Sonraki" ile başlayan tarih gelecek ekstrenindir. Asgari tutar ve limit boş kalır; gerçek bir ekstre gelince
  denetlenmeli.
- Sayfa resmi olarak gelen ekstrede (OCR) ödeme bilgileri okunmaz.

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

**e-cüzdan PDF'i** (`vakifbank.passbook`): mevduat koşulları 1. sayfada, hesap (`Cüzdan Seri No`, satırlar
`NO tarih tutar bakiye metin`) sonraki sayfalarda.

**Transfer bildirimleri** (`vakifbank.notice.transfer`, e-posta gövdesi, `vakifbank.com.tr`)

- Vakıfbank hesap dökümünü e-postayla göndermez. Hesap hakkında kutuda bulunan, bu bildirimlerdir (K21).
- İki tür vardır:
  - "VAKIFBANK - FAST Anlık Ödeme Bilgilendirmesi": gelen ya da giden FAST.
  - "Bilgilendirme: Mevduat Hesabı Para Çıkışları": hesaptan EFT ile çıkan para.
- Gövde tek bir HTML parçasıdır (UTF-8, base64). Tablonun her satırı `etiket`, `:` ve `değer` hücreleridir. Para
  çıkışı bildiriminde iki nokta değerin hücresindedir; `Alıcı IBAN : …` tek hücrededir.
- Paranın yönünü tablonun üstündeki cümle söyler:
  - "Hesabınıza FAST Anlık Ödeme gelmiştir." gelen paradır.
  - "Bankamızdan gönderdiğiniz FAST Anlık Ödeme işleminiz …" ve "Mevduat hesabınızdan gerçekleşen para çıkış
    detayları …" çıkan paradır.
- Hesap numarası son dört hane dışında maskelidir: FAST'te `*************1234`, para çıkışında `00158********1234`.
  Hesap bu dört haneyle `vakifbank-****1234` olarak açılır. Aynı bankanın, aynı para birimindeki ve aynı dört haneyle
  biten bir hesabının dökümü gelirse satırlar o hesaba geçer (`analysis.resolve_masked`).
- Adlar her kelimenin ilk iki harfi dışında maskelidir. Müşterinin adı ("Sayın Ör**** Ku******") bilinmez sayılır. Karşı
  tarafın adı ancak kullanıcının adlarından biriyle aynı sayıda kelimeden oluşuyorsa ve her kelime gösterilen harflerle
  başlıyorsa kullanıcının sayılır. O zaman transfer kendi hesaplar arasıdır.
- Tutarlar, kuruş sıfırsa ondalıksız yazılır: `2.000 TL`, `12.345,67 TL`, `0 TL`.
- FAST bildirimi işlemden sonraki bakiyeyi de yazar (`Güncel Bakiye`); para çıkışı bildirimi yazmaz. Bakiye satırla
  birlikte saklanır.
- Dekont anahtarı işlem günü ile `Sorgu Numarası`dır.
- Tanımadığı bir etiket bir değerin içine taşarsa okuyucu belgeyi okumaz ve biçim alarmı verir: bir ad ya da tutar
  yanlış okunabilir.
- Vakıfbank'ın para hareketi taşımayan iletileri (kampanya, kart teslimi, adres ve e-posta doğrulama) bu okuyucuya
  girmez.

## QNB

**Kart ve hesap PDF'leri**

- Kart PDF'i `QNB Kredi Kart` ve `Kredi Kartı Numarası` ile tanınır; hesap PDF'i `Hesap Hareketleri` ve QNB IBAN'ı ile.
- Yazı tiplerinde Türkçe glifler yoktur: `(cid:N)` görünür ve harfler düşer. Sınıflama için gereken etiketler
  `parsers/qnb/card_pdf.py` içindeki `_REPAIRS` ile onarılır.
- Hesap listesi `DEVREDEN BAKİYE` ile açılır.
- `Transfer İşlemleri - Alıcı/Gönderen :` başlıkları sonraki satırlara taşar.
- MVP'nin bildiği kart PDF'i, ödeme bilgilerinden yalnızca son ödeme tarihini yazar: "Son Ödeme Tarihi : 15/10/2026".
  "Ö" harfi yazı tipinde düşebilir ("Önceki"nin düştüğü gibi); etiket `Son …deme Tarihi` olarak aranır. Asgari tutar
  ve limit boş kalır; gerçek bir ekstre gelince denetlenmeli.

**e-dekont** (HTML; utf-8 ya da windows-1254; ya da PDF)

- Türleri:
  - kredi taksidi (anapara ile faiz, KKDF ve BSMV),
  - ekstresi olmayan bir karta ödeme,
  - transferler (aday).
- Karşı taraf, gelende `GÖNDEREN`'den, gidende `ALICI`'dan sonraki addır; bir sonraki etikete kadar sürer.
- Dekont anahtarı `FİŞ NO`'dur.
- Bazı gelen transfer bildirimlerinde tutar satırı hiç yoktur; bunlar "dekontta tutar yazmıyor" nedeniyle atlanır.

**Hareket bildirimleri** (`qnb.notice.transfer`; 2024'e dek email.qnbfinansbank.com'dan, sonra email.qnb.com.tr'den)

- Konuları: "QNB - Fast Para transferi bildiriminiz", "QNB - Para transferi bildiriminiz", "QNB FINANSBANK -
  ATM/Banka Kartı Para Çıkışı Bildiriminiz".
- Selamlamadan sonra tek cümle hareketi anlatır, ardından bakiye gelir:
  - giden FAST: "KADIKÖY şubesindeki hesabınızdan … isimli alıcıya 1,234.56 TL'lik FAST işleminiz
    gerçekleştirilmiştir.";
  - gelen FAST: "… hesabınıza … tarafından FAST aracılığı ile 1,234.56 TL gönderilmiştir.";
  - hesap numarasını yazan havale, EFT ve para çıkışı: "… 12345678 no'lu hesabınıza … tarafından 1.234,56 TL
    gönderilmiştir.", "… no'lu hesabınızdan … adına …", "… no'lu hesabınızdan 1.234,56 TL para çıkışı olmuştur.";
  - "Hesabınızın bakiyesi saat 14:05 itibarıyla -1,234.56 TL tutarındadır." Ek hesabın bakiyesi sıfırın altındadır.
- Tuzaklar:
  - FAST bildirimleri tutarı ABD biçiminde yazar ("1,234.56", "1234.56"), ötekiler Türk biçiminde ("1.234,56",
    "99,99"): son iki haneden önceki ayraç ondalıktır.
  - Kelimeler bazen Türkçe harfsiz gelir ("subesindeki", "hesabinizdan"). En yeni bildirimler şubeyi "Kadıköy
    Şubesi'ndeki" diye yazar ve selamlamadaki adı maskeler ("Sayın Örnek K***").
  - Hiçbir bildirim günü yazmaz: gün, iletinin Türkiye saatine göre tarihidir. Bakiyenin saati iletinin gönderildiği
    saatten sonraysa hareket bir önceki gündür (23.58'deki hareket 00.01'de gelir).
  - FAST bildirimi hesap numarası yazmaz: satır, öteki belgelerin bildiği tek QNB banka hesabına (kart ya da kredi
    değil) gider. Birden çok banka hesabı varsa tahmin edilmez. Numarayı yazan bildirim de hesabın türünü bilmez:
    e-dekontun ya da listenin dediği (ek hesap ya da değil) geçerlidir.
  - QNB bazı FAST bildirimlerine e-dekontu ekler. Hareket bir kez sayılır: dekontun satırı kalır, bildirimin yazdığı
    bakiyeyi alır.
  - ATM ya da banka kartıyla para çıkışı ne işyeri ne karşı taraf yazar. Bu bir transfer değildir (deftere transfer
    adayı olarak girseydi "kişilere gönderilen" sayılırdı); ATM'nin verdiği gibi nakittir (Nakit Avans & Çekim).
    Bildirim ATM'yi işyerindeki kart okuyucusundan ayırmaz: kullanıcı bildiği bir kart ödemesini tek satır olarak
    düzeltir (okuyucu sürüm 2).
- Dekont numarası yazmaz: bildirim, günü ve dakikası, tutarı ve sonraki bakiyesiyle tanınır.

## Okuyucusu olmayan e-postalar

Bankalar para hareketi bildirimlerinden çok daha fazlasını gönderir. Gövdesini hiçbir okuyucunun okumadığı bir ileti,
gönderenin alan adına ve konusuna göre adlandırılır (`parsers/messages.py`). Kurallar kutunun envanterinden çıkarıldı
(`iplikci dev eposta-envanteri`).

- Belge taşıyan ileti (PDF, tablo, zip) ekleriyle okunur. Logo ve imza resmi belge sayılmaz. "Orijinali göster"in
  içeriğini boş bıraktığı ek de sayılmaz.
- `kampanya.` alt alan adından gelen her ileti, bankanın kendi "Kampanya:" ya da "Tanıtım:" etiketini taşıyan konu da
  kampanyadır.
- Konu şifre, cihaz, e-posta doğrulama, adres ya da tercih anıyorsa güvenlik ve hesap ayarı bildirimidir. Kart teslimi,
  başvuru ya da limit artışı anıyorsa kart bildirimidir. Ücret, oran ya da koşul değişikliği anıyorsa duyurudur.
- Konu yaklaşan bir ödemeyi hatırlatıyorsa (İş Bankası'nın haftalık kart ödemeleri, kredinin vade tarihi
  bilgilendirmesi, "hatırlatma") ödeme hatırlatmasıdır. Ödeme yapılınca hesabın kendi hareketlerinde görünür.
- Konuda para hareketi ya da borç geçiyorsa ileti tanınmamış kalır: ekstre, hesap özeti, dekont, transfer, para
  çıkışı, tahsilat, prim, SGK, borç, fatura, vade tarihi, dönem ücreti, bakiye, maaş, havale, EFT, FAST. Henüz
  okuyucusu olmayan bir bildirim olabilir; okuyucusu yazılana dek gözden kaybolmaz.
- `bilgi.` alt alan adından gelen ileti duyurudur. Kampanya kelimeleri (fırsat, davet, bonus, indirim, taksit…) ve
  duyuru kelimeleri (tatil, işlem saatleri, halka arz, ücret, tarife…) en son denenir.
- Hiçbir şey söylemeyen bir konu ("BİLGİLENDİRME") için gövdenin ilk cümlesine bakılır. Bir ücret değişikliği
  duyuruyorsa ileti duyurudur. Tutar içermeyen bir gövde ücret değişikliğiyle ya da bir kredinin ilerleyişiyle
  ("ödemelerinizin yarısından fazlasını tamamladınız") açılıyorsa, konusu para hareketi anlatsa da ileti duyurudur
  ("Dijital Teminat Mektubu Dönem Ücreti"). Tutar içermeyen ve bankanın "gönderilen e-postalar sadece bilgilendirme
  amaçlıdır" altbilgisinden başka metni olmayan gövdenin iletisi bir resimdir: duyuru sayılır.
- Kampanya, duyuru, güvenlik ve kart bildirimleri ile ödeme hatırlatmaları "para hareketi yok" diye bilerek sınıflanır.
  F01'in kapsam ölçütü bunları sayar. Kurallar değişince okuyucusu olmayan iletiler yeniden sınıflanır
  (`messages.VERSION`).
- İmza sirküleri ve genel kurul, şirketin belgeleridir: konusunda bunları anan ileti şirket belgesi sayılır.
- Okuyucusu olmayan iletinin gövdesinde şirket için yalnızca selamlamaya bakılır. "Sayın …," ya da "Merhaba …," bir
  şirketi anıyorsa ileti o şirketin belgesidir. Daha aşağıda geçen bir şirket adı, kişisel bir hesabın hareketinde
  karşı taraf olabilir. Selamlama virgülde, satırın sonunda ya da ilk küçük harfli kelimede biter, cümleye uzanmaz.
  Bildirim okuyucuları hesap sahibini bankanın yazdığı yerde arar.
- SGK işyeri sicil numarası (26 hane) altında ödenen prim işverenindir, yani bir bordronun parçasıdır. SGK'yı ve böyle
  bir numarayı anan ileti şirket belgesi sayılır. Kişinin kendi primi kimlik numarası altında ödenir. Ev hizmetlerinde
  birini çalıştıran hanenin de işyeri numarası vardır: böyle bir ileti de ayrılır, kendisi para hareketi taşımaz.

## Banka dışı belgeler

**e-Fatura ve e-Arşiv faturası** (`invoice.ubl_tr`; UBL-TR 1.2 XML eki ya da yüklenen dosya)

- Kök öğe `Invoice` (`urn:oasis:names:specification:ubl:schema:xsd:Invoice-2`); `CustomizationID` TR1.2 ve
  `ProfileID` GİB profillerinden biri (TEMELFATURA, TICARIFATURA, EARSIVFATURA…).
- Satıcı `AccountingSupplierParty`, alıcı `AccountingCustomerParty`; numara `ID`, tarih `IssueDate`; ödenecek tutar
  `LegalMonetaryTotal/PayableAmount` (`currencyID` para birimi); kalemler `InvoiceLine` (kalem adı, miktar, vergisiz
  tutar ve satırın vergileri; kalemin tutarı vergileriyle birliktedir).
- Son ödeme tarihi (`PaymentMeans/PaymentDueDate`) yazan belge faturadır; yazmayan, hemen ödenmiş bir alışverişin
  makbuzudur. İade faturası (`InvoiceTypeCode` IADE) parayı geri verir: tutarı eksidir.
- Şirket belgeleri kapsam dışıdır: şirkete kesilen fatura alıcıyı vergi numarasıyla (VKN, on hane) yazar, kişiye
  kesilen kimlik numarasıyla (TCKN, on bir hane). Kullanıcının şirket adları alıcıda ve satıcıda aranır.
- XML güvenilmez girdidir: belge türü tanımı (DTD) olan belge okunmaz (UBL-TR'de olmaz; XML bombası varlıklarla
  kurulur). XSLT görünümü ve gömülü dosyalar (`AdditionalDocumentReference`) okunmaz.
- Aynı faturanın ikinci kopyası (sıkıştırılmış XML'i, yeniden gönderilen e-posta) satıcının vergi numarası ve fatura
  numarasıyla tanınır.

## V1'de eklenecek bilgiler

E-posta gövdesi okuyucuları (banka bildirimleri) ve banka dışı göndericiler yazıldıkça biçimleri ve tuzakları burada,
bankanın başlığı altında belgelenir. Örnek gerçek belgeler depoya girmez; okuyucunun sahte belge üreticisi bu bilgiyle
yazılır.
