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
- Konuda para hareketi ya da borç geçiyorsa ileti tanınmamış kalır: ekstre, hesap özeti, dekont, transfer, para
  çıkışı, tahsilat, prim, SGK, borç, fatura, vade tarihi, dönem ücreti, bakiye, maaş, havale, EFT, FAST. Henüz
  okuyucusu olmayan bir bildirim olabilir; okuyucusu yazılana dek gözden kaybolmaz.
- `bilgi.` alt alan adından gelen ileti duyurudur. Kampanya kelimeleri (fırsat, davet, bonus, indirim, taksit…) ve duyuru
  kelimeleri (tatil, işlem saatleri, halka arz, ücret, tarife…) en son denenir.
- Hiçbir şey söylemeyen bir konu ("BİLGİLENDİRME") için gövdenin ilk cümlesine bakılır. Bir ücret değişikliği
  duyuruyorsa ileti duyurudur.
- Kampanya, duyuru, güvenlik ve kart bildirimleri "para hareketi yok" diye bilerek sınıflanır. F01'in kapsam ölçütü
  bunları sayar. Kurallar değişince okuyucusu olmayan iletiler yeniden sınıflanır (`messages.VERSION`).
- İmza sirküleri ve genel kurul, şirketin belgeleridir: konusunda bunları anan ileti şirket belgesi sayılır.

## V1'de eklenecek bilgiler

E-posta gövdesi okuyucuları (banka bildirimleri) ve banka dışı göndericiler yazıldıkça biçimleri ve tuzakları burada,
bankanın başlığı altında belgelenir. Örnek gerçek belgeler depoya girmez; okuyucunun sahte belge üreticisi bu bilgiyle
yazılır.
