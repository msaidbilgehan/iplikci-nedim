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

**Kart ekstresinin ödeme bilgileri** (`Statement.due_date`, `minimum_payment`, `credit_limit`, `next_cut`)

- Kesim tarihi ve dönem borcu gibi, ilk sayfanın metnindeki etiketlerinden okunur.
- Son ödeme tarihi bu ekstrenin son ödeme tarihidir. "Bir Sonraki Son Ödeme Tarihi" ve "son ödemeniz …" gelecek
  ekstrenindir; alınmaz.
- Sonraki kesim (`next_cut`), ekstrenin gelecek ekstre için yazdığı "bir sonraki hesap kesim tarihi"dir. Dört
  bankanın kart ekstresi de bunu yazar. Kesim günü aydan aya birkaç gün oynar (hafta sonu, bankanın takvimi): aynı
  günün bir ay sonrası çoğu ay tutmaz. Kendi kesiminden sonra olmayan bir tarih alınmaz (`common.next_cut`).
- Program sonraki kesimi tek yerden bilir (`Statement.cut_after`): ekstrenin yazdığı gün, yazmıyorsa aynı günün bir
  ay sonrası. Tahmin edilen gün arayüzde "~" ile yazılır. Ay sonu, Hesaplar, Şu an ve taksitlerin kesim günleri bunu
  kullanır.
- Kart ekstresi takvim ayını değil, iki kesim arasını kapsar: ayın kesimden sonraki günleri bir sonraki ayın
  kesimiyle gelen ekstrededir ("21–31 Ekim, 21 Ekim–19 Kasım ekstresinde").
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
- "EKSTRE ÖZETİ" cümlesi gelecek ekstreyi anlatır: "Bir sonraki hesap kesiminiz 4 Eylül 2026 Cuma ve son ödemeniz
  14 Eylül 2026 Pazartesi 'dir." Kesim tarihi sonraki kesim olarak alınır, son ödeme tarihi alınmaz. Cümle
  satırlardan sonra gelir: satırlar ilk sayfayı doldurunca sonraki sayfadadır, bu yüzden bütün sayfalarda aranır.
- Kart limiti "Kart Limiti" satırıdır; üstündeki "Müşteri Limiti", altındaki "Nakit Avans Limiti" ve cümledeki
  "kullanılabilir limitiniz" değildir.
- Asgari ödeme tutarı özette dönem borcunun altındadır: "Min. Ödeme Tutarı 1.553,96 TL". Satırlardan sonraki tablonun
  "Min. Ödeme Tutarınız" sütunu tutarı bir alt satıra yazar; alınmaz. (Okuyucunun 4. sürümüne dek ilk sayfada asgari
  tutar yazmadığı sanılıyordu; gerçek ekstrelerin hepsinde yazar.)

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
- Özetteki "Bir Sonraki Hesap Kesim Tarihi" ve "Bir Sonraki Son Ödeme Tarihi" gelecek ekstrenindir; ilki sonraki
  kesim olarak alınır. Bazı ekstreler kelimeleri bitişik basar ("BirSonrakiHesapKesimTarihi: 07.01.2025").
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
- Bankadaki iki hesap arası aktarma (`İşlem Tipi` "Para Transferi") gittiği hesabı ve sahibini yazar: "1234/0123456
  HESABA <AD SOYAD> Hesaplar Arası Akt". Karşı taraf, `HESABA` ile "Hesaplar Arası" arasındaki addır. Ad
  kullanıcınınsa öbür hesabın belgesi gelmemiş olsa da aktarma kendi hesaplar arasıdır (v0.9.17'ye dek ad okunmuyor,
  aktarma kişilere gönderilen sayılıyordu).
- Hareketsiz bir dönemin özeti tabloya satır basmaz: başlığın altında birkaç boş satır, sonra dipnot ("(*) Çekilen
  tutar '-' ile gösterilmiştir."). Bakiyeyi yalnızca tablonun üstündeki "Mevcut Bakiye" yazar; o, özetin hazırlandığı
  andaki bakiyedir ("Belge Düzenleme Tarihi: 31.10.2026 - 10:30:00"). Dönem o güne kadar sürüyorsa liste o bakiyeyle
  açılıp kapanır; daha önce bitiyorsa bakiyesi bilinmez. Böyle bir liste boştur (`empty`) ve doğrulanmış sayılır;
  tabloda okunamayan bir satır varsa boş sayılmaz (v1.0.8'e dek hareketsiz özet "doğrulanamadı" kalıyordu).
- Günlük faizli hesap faizi her gün brüt yazar ("BRÜT FAİZ %30.00 ÜZERİNDEN 1 GÜN"; hafta sonu birikip "3 GÜN") ve
  vergisini ayrı bir satırla keser ("BRÜT FAİZDEN %17.50 GELİR VERGİSİ STOPAJI"). İkisi de faiz gelirine girer; vergi
  onu düşürür.
- Başlıktaki "Ürün-Döviz Tipi" hesabın ürünüdür: "Vadesiz Hesap", "Vadesiz YP Hesap" (döviz) ya da "Vadeli Hesap".
  Banka günlük faizli hesabı ("Günlük Kazandıran") da "Vadeli Hesap" diye yazar. Vadeli hesap mevduattır
  (`deposit`): birikimi tutar, ayın harcandığı hesap değildir; adı "İş Bankası Vadeli TL …" olur. v1.0.10'a dek ürün
  okunmuyor, günlük faizli hesap vadesiz sayılıyordu.

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
- **OCR'ın önbellek tuzağı (2026-11-15):** macOS, metin tanımanın derlenmiş modelini sürecin adına göre önbellekte
  tutar (`~/Library/Caches/<süreç adı>/com.apple.e5rt.e5bundlecache`). Bu önbellek bozulursa Vision aynı sayfadan
  bazı uzun satırları hiç döndürmez; o süreç adıyla okunan ekstre birden doğrulanmaz olur. Görülen örnekte `python`
  adlı süreçler (uv'nin sanal ortamı, uv tool kopyası) yabancı para tutarlı dört satırı kaybetti, aynı Python'un
  `python3` adıyla çalışan kopyası hepsini okudu. Önbellek Çöp'e taşınınca macOS onu yeniden kurar ve satırlar geri
  gelir. Doğrulanmış bir OCR ekstresi kod değişmeden doğrulanmaz olursa önce buna bakılır.
- `(9/8. Taksit)` "9 taksitten 8'incisi" demektir.
- `(Yurt dışı işlem tutarı EUR.25,75)` orijinal tutardır. Sayfa resmi olarak gelen ekstre bunu bitişik yazar
  ("Yurtdışı").
- Bir ekstrede birden çok kart bölümü olabilir.
- OCR, temassız ikonunu `)))`, `»))`, `»)` ya da `1))` olarak okur (Ekim 2026'nın ekstresinden beri çoğu kez
  `»`lı). Okuyucu metnin sonundaki, harf taşımayan ve metnin açmadığı bir parantezi kapatan son kelimeyi ikon sayıp
  atar; metni bitiren kapama parantezi (`(9/8. Taksit)` gibi) kalır. v1.0.3'e dek `»`lı ikon açıklamada kalıyordu: aynı
  işyeri ikonun okunuşuna göre iki işyeri görünüyordu ("ÖRNEK CAFE »)" ve "ÖRNEK CAFE »))").
- OCR, bir tutarın arkasındaki lekeyi nokta okuyabilir ("TL.950,40."). Okuyucu tutar hücresinin sonundaki bir nokta ya
  da virgülü yok sayar. v1.0.3'e dek böyle bir satır hiç okunmuyor, ekstre farkla doğrulanmıyordu (biçim alarmı).
- Vision "ş" yerine benzeri olan Romence "ș"yi (virgüllü s) verebilir: "Yurtdıșı". Türkçede bu harf olmadığından OCR
  okunanı "ş" yazar (`parsers.pdf.recognized`). v1.0.3'e dek böyle bir satırın orijinal tutarı açıklamada kalıyordu.
- Metin katmanlı ekstre, ödeme bilgilerinden son ödeme tarihini ve gelecek ekstrenin tarihlerini yazar: "Son Ödeme
  Tarihi: 15/10/2026", "Bir Sonraki Hesap Kesim Tarihi: 04/11/2026", "Bir Sonraki Son Ödeme Tarihi: 14/11/2026".
  Kelimeler çoğu kez bitişiktir ("BirSonrakiHesapKesimTarihi :04/11/2026"). "Sonraki" ile başlayan son ödeme
  tarihi gelecek ekstrenindir; sonraki kesim alınır. Bazı ekstrelerin altındaki açıklama ("… bir sonraki hesap kesim
  tarihi ve bir sonraki son ödeme tarihi ile ilgili bilgi …") tarih yazmaz; alınmaz.
- Sayfa resmi olarak gelen ekstrede (OCR) aynı kutu okunur: her etiket ve tarihi ayrı bir hücredir, kutunun satırları
  sağdaki başlık ve adresle aynı satırdadır. OCR "Son Ödeme Tarihi"nin Ö'sünü O okuyabilir; başlık son ödeme tarihini
  bir kez daha yazar ("SON ÖDEME TARİHİ: 15/10/2026").
- Aynı kutu asgari tutarı ve kart limitini yazar, çoğu kez küsuratsız: "Minimum Ödeme Tutarı :TL.1.887,-", "Kart Limiti
  :TL.60.000,-". Altındaki "Nakit Avans Limiti" kartın limiti değildir. OCR'da her biri ayrı bir hücredir; nakit avans
  limiti bir faiz oranıyla aynı satırdadır. (MVP'nin bildiği düzende bunlar yoktu; gerçek ekstrelerin hepsinde
  yazar, okuyucunun 6. sürümünden beri okunur.)

**Kart ödeme dekontu PDF'i:** `ekstresiz_kart` (`card_payment_no_statement`) türündedir; ekstresi olmayan bir karta
yapılan ödemedir.

**Hesap dökümü:** `.xls` adıyla kaydedilmiş bir HTML'dir; 7 sütunlu satırlar en yeniden eskiye sıralıdır.

- Önce `Hesap Sahibi` alanı şirket işaretleri için denetlenir.
- Eksiye düşen TL hesabı KMH'dir.
- `GR` altın hesabıdır.
- Giden transferler yalnızca alıcı bankayı yazar ("TÜRKIYE GARANTI BANKASI A.Ş.").
- "… no.lu hesaba gönderilmiştir", alıcı tarafta bile kendi hesabını adlandırır.
- "Müşteriye TL karşılığı Altın satışı", kullanıcının altın almasıdır.

**Dijital hesap cüzdanı PDF'i** (`teb.passbook`): TEB'in uygulamalarının istek üzerine verdiği, bir hesabın iki gün
arasındaki hareketleri. Kullanıcı onu çoğunlukla Telegram botuna gönderir; TEB hesap hareketlerini e-postayla
göndermez.

- 1. sayfada "Etiket: değer" satırları vardır: `Hesap Numarası`, `IBAN`, `Hesap Türü`, `Para Kodu`, `Bakiye`,
  `Raporlama Tarihi` ve `Hesap Hareketi Tarih Aralığı`. Altında hareketler eskiden yeniye sıralanır: `Sıra No |
  Tarih | Açıklama | İşlem Tutarı | Bakiye`. Son sayfa mevduat koşullarıdır.
- KMH hesabının türü burada da "Vadesiz" yazar. CEPTETEB dökümündeki gibi eksiye düşen TL hesabı KMH sayılır; hesap
  numarası iki belgede aynıdır (`teb-<numara>`).
- `Bakiye` raporlama günündeki bakiyedir. Aralık o günden önce bitiyorsa son satırın bakiyesiyle tutmayabilir.
- Faiz işleyen hesap, bakiyenin altına yıllık brüt faiz oranını yazar (`Brüt Faiz Oranı (Yıllık)`). Vadeli hesap da
  CEPTETEB Marifetli de bu satırı taşır; Marifetli'nin türü "CEPTETEB Marifetli" yazar, "Vadeli" yazmaz. Vadesiz ve
  KMH hesapları bu satırı yazmaz. Bu satırı taşıyan hesap vadeli hesap sayılır.
- Bir satırın hücreleri satırın yüksekliğine ortalanır. Sütuna sığmayan açıklama kendi sütununda kaydırılır. İki
  satırlık bir açıklamanın ilk satırı numaranın, tarihin ve tutarların yazdığı satırın üstünde, ikincisi altındadır.
  O satırda açıklamadan hiç kelime kalmaz ("<Ad Soyad> den gelen" / "havale tutarı", "<kart> no.lu Kredi Kartına
  Ödenen" / "Tutar"). Okuyucu, açıklama sütunundaki her satırı en yakın hareketin açıklamasına verir.
  - v0.9.14'ün okuyucusu yalnızca alta süren açıklamayı biliyordu. Kelimesi kalmayan satırları atlıyor, üstteki
    satırı bir önceki hareketin açıklamasına ekliyordu. Bu yüzden cüzdan doğrulanmıyor, biçim alarmı veriyordu
    (v0.9.16'da düzeldi).
- İlk satırın öncesinde bakiye yazmaz. Bu yüzden on satırda dokuz bakiye denetlenir. Hesap cüzdanın ilk günü
  açıldıysa (`Hesap Açılış Tarihi`) sıfırdan başlar; ilk satır da denetlenir.
- CEPTETEB Marifetli faizini her iş günü, vergisi düşülmüş olarak yatırır: "CEPTETEB Marifetli Hesap net faiz geliri
  %<oran>". Hesaba giren ve iade ya da iptal olmayan faiz gelirdir (`movements.classify`, bütün hesap dökümleri);
  v1.0.3'e dek "Ek Hesap (KMH) Faizi" sayılıyordu, gideri azaltıyordu. Yeni müşteriye verilen oran bir süre sonra
  biter ve satırdaki oran düşer ("%45" → "%15"). Öngörü oranı satırdaki yazıdan değil, tutarların bakiyeye oranından
  okur ve en yeni oranı sürdürür (v1.1.1).
- TEB, iki TEB hesabı arasındaki aktarmada alıcı hesabın numarasını iki tarafa da yazar: "222333444 no.lu hesaba
  gönderilmiştir." Gönderen tarafın karşılığı yalnızca o numaralı hesaptadır (`analysis._goes_to`, v1.1.1).
- Hesaptan alınan fon, pay sayısı ve adıyla yazar: "<pay> Pay <kod>-<kurucu> PORTFÖY PARA PİYASASI (TL) FO alış
  bedeli," (açıklama kaydırılır, kesilir). Genel kurallardaki "Yatırım Fonu" onu birikim sayar; v1.0.3'e dek kişiye
  gönderilen para sayılıyordu. Fonun kendisini gösteren bir belge yoktur; değeri varlıklara girmez.

**Banka içi havale dekontu PDF'i** (`teb.transfer_receipt`, "BANKA İÇİ PARA TRANSFER DEKONTU"): CEPTETEB'in
uygulamasının paylaştığı, iki TEB hesabı arasındaki aktarmanın dekontu.

- Hücreler "Etiket:değer" biçimindedir ("Hesap Sahibi:…"); bir satırın hücreleri birbirinden uzaktır.
- Dekont tek bir hesabı numarası ve para birimiyle yazar: `Hesap Numarası:123456789-TL`. Hareketi şu satır söyler:
  "<hareketin metni>: Valör:<gün> TL <tutar><işaret>" ("vadeli para yatırma: Valör:02/11/26 TL 2.500,00+"). `+`
  hesaba giren paradır.
- Öbür hesabın numarası yazmaz; yalnızca sahibi (`Borçlu Hesap Sahibi`, parayı gönderen) ve şubesi yazar.
- Dekont hesabın türünü (vadeli mi, KMH mi) söylemez. Hesabın türü cüzdanından ya da dökümünden gelir: analiz,
  önce gelen dekontun hesabının yerine listenin hesabını koyar.
- Dekont anahtarı hesap numarası ile `İşlem No`'dur. Böylece bir aktarmanın iki ucunun dekontları iki ayrı dekont
  sayılır.
- Şimdiye dek yalnızca parayı alan hesabın dekontu görüldü.

## Vakıfbank

**Hesap XLSX'i** (`VB MUSTERI NO`)

- Satırlar eskiden yeniye sıralıdır.
- `RUMUZ` etikette görünen takma addır.
- Maaş satırları işvereni `(<kod>_<kod>_<AD>)` olarak taşır.
- Karşı taraf, banka adından sonraki addır ("… A.Ş. <Ad Soyad> hesabına/hesabından").
- Döviz satırları `İşlem Kuru` yazar.

**e-cüzdan PDF'i** (`vakifbank.passbook`): mevduat koşulları 1. sayfada, hesap (`Cüzdan Seri No`, satırlar
`NO tarih tutar bakiye metin`) sonraki sayfalarda.

**Dekont PDF'i** (`vakifbank.receipt`): Vakıfbank'ın uygulamasının paylaştığı transfer dekontu.

- "İŞLEM BİLGİLERİ" başlığının altında her satırda iki etiket-değer çifti vardır: `İŞLEM TÜRÜ` ("FAST Giden Anlık
  Ödeme") ve `İŞLEM TARİHİ`, `ALICI BANKA` ve `SORGU NO`, `İŞLEM TUTARI` ve `MASRAF TUTARI`, gönderenin ve alıcının
  adı, alıcının IBAN'ı ve `İŞLEM NO`. Kullanıcının yazdığı açıklama `İŞLEM AÇIKLAMASI` başlığının altındadır.
- Hücrenin metni kendi sütununda kaydırılır: "GÖNDEREN AD SOYAD /" + "UNVAN", uzun adlar ve IBAN iki satırdır. Bir
  satırın hücreleri satırın yüksekliğine ortalanır. Bir etiketin değeri, sağındaki, ortası onunkiyle aynı hizada olan
  hücredir. Boş değerin hücresi yoktur (masrafsız FAST'te `MASRAF TUTARI`).
- Dekont gönderenin hesabını yazmaz. Satır, Vakıfbank'ın o para birimindeki tek banka hesabına geçer
  (`analysis.resolve_masked`).
- Aynı FAST'in e-posta bildirimi de gelirse hareket bir kez sayılır: dekontun satırı kalır, bildirimin bakiyesini
  alır.
- Dekont anahtarı `İŞLEM NO`'dur. Aynı dekontun iki kopyası (Telegram'dan ve Belge ekle'den) bir kez sayılır.
- Şimdiye dek yalnızca giden FAST'in dekontu görüldü. "Gelen" yazan bir dekont aynı tabloyla okunur. Yönü
  yazmayan bir dekont okunmaz ve biçim alarmı verir.

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
- Kart PDF'i son ödeme tarihini kart numarasının yanında ay adıyla yazar: "Son Ödeme Tarihi: 15 Ağustos 2026,
  Cumartesi". Yazı tipi "Ö"yü ve ayın Türkçe harflerini düşürür; her biri bir `(cid:N)` olur ("A(cid:6)ustos",
  "Eyl(cid:6)l"). Bu yüzden tarih ham metinden okunur ve ay, düşen her harfin yerine bir harf kabul edilerek
  tanınır. Ödenecek borcu olmayan ekstre son ödeme tarihi yazmaz. (MVP'nin varsaydığı "15/10/2026" biçimi gerçek
  ekstrelerde yoktur; o yüzden son ödeme tarihleri hiç okunmuyordu.)
- Son sayfadaki not gelecek ekstreyi anlatır: "* Bir sonraki hesap kesim tarihiniz 04/11/2026, bir sonraki son ödeme
  tarihiniz 14/11/2026". İlki sonraki kesim olarak alınır.
- Özet asgari tutarı ve kart limitini ABD biçimiyle yazar: "Asgari Ödeme Tutarı : 1,036.36 TL" (Ö'sü yazı tipine
  düşer), "Kredi Kartı Limiti : 120,000.00 TL". Ödenecek borcu olmayan ekstre asgari tutarı 0.00 yazar. Yanındaki
  "Asgari Ödeme Oranı", altındaki "Nakit Avans Limiti" ve "Kullanılabilir Limit" ile satırların altındaki yasal not
  ("… asgari ödeme tutarını belirtilen son ödeme tarihine …") bunlar değildir. Okuyucunun 4. sürümünden beri okunur.

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
