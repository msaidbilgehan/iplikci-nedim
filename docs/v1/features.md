# V1 özellikleri

Proje: İplikçi Nedim · Durum: son hâli, uygulamaya hazır · Tarih: 2026-10-31 · İlgili belgeler:
[gereksinimler](requirements.md), [mimari](architecture.md), [yol haritası](roadmap.md)

Her özelliğin amacı, kabul ölçütleri (test edilebilir cümleler), önceliği ve karşıladığı gereksinim (G…) yazılıdır.

Öncelikler:

- **Çekirdek:** sürüm 1.0'dan (`v1.0.0`) önce bitmeli.
- **V1+:** V1 mimarisiyle, sürüm 1.0'dan sonra.
- **Sonra:** ileride.

## Ortak kurallar

Bütün ekranlar için geçerlidir:

- **Dil ve biçim**
  - Arayüz Türkçedir. Tutarlar `1.234,56 TL`, tarihler `31.10.2026` biçimindedir.
  - Sayılardan ve yıllardan sonraki ekler yardımcı işlevlerle kurulur; `'i`, `'da` gibi ekler elle yazılmaz.
- **Kesinlik**
  - Her işlemde ve toplamda kesinlik görünür: geçici, ekstrede yok, yalnızca bilgi.
  - Kesin olmayan bir rakam kesin gibi sunulmaz. Kapanmamış bir geçmiş ayın rakamları eksik olabileceğini söyler;
    ayların en yükseği ve en düşüğü yalnızca kapanmış aylardan seçilir. Bir hesap toplama girmiyorsa neden girmediği
    (bakiyesi belgelerde yok ya da TL karşılığı bilinmiyor) yazılır.
- **Ortalamalar ve tahmin**
  - Ortalama, eğilim ve tahmin yalnızca tam aylardan hesaplanır; içinde bulunulan ay eksik sayılır.
  - Düzensiz harcama yıllığa çevrilmez, 12 ile çarpılmaz.
- **İz:** her rakamdan dayandığı işlemlere, her işlemden belgesine ve belgenin geldiği e-postaya gidilir.
- **Grafikler** (MVP kuralları):
  - Her grup ve gereklilik düzeyinin süzgeçlerle değişmeyen sabit bir renk yuvası vardır. İlk 8 ana grup renklidir,
    "Diğer" gridir.
  - Yığılmış dilimler arasında 2 px boşluk bırakılır; veri uçları 4 px yuvarlaktır.
  - Her grafiğin bir tablo görünümü vardır.
  - Açık ve koyu paletler ayrı seçilir.
  - Durum renkleri (iyi, uyarı, kritik) her zaman ikon ve etiketle birlikte kullanılır.
- **Süzgeçlerin kapsamı** (MVP kuralı):
  - Genel değerlendirme, varlıklar, ay kapanışı ve alışkanlıklar hiçbir süzgeçten etkilenmez.
  - Düzenli ödemeler ve tahmin yalnızca dönem süzgecinden etkilenmez.
  - Diğer kartlar bütün süzgeçlere uyar.
- **Görünüm**
  - "Sade" görünüm her kartta bir cümlelik yorum ve bir sonraki adımı gösterir. "Ayrıntılı" görünüm tabloları ve ham
    veriyi gösterir.
  - Terimler sözlüğü vardır: KMH, asgari ödeme, kesim tarihi, kur makası gibi terimlerin üzerine gelince kısa açıklama
    çıkar.
  - Uzun ekranlar bölümlere ayrılır: bir seferde bir bölüm görünür ve yalnızca o yüklenir; seçilen bölüm adreste durur
    (`?bolum=`), geri düğmesi ona döner. Akış, Değerlendirme, Bildirimler, Kurallar ve hesap sayfası böyledir.
  - Bir toplamın nasıl hesaplandığı "Nasıl hesaplandı?" altında katlanır; ayrıntılı görünümde açık gelir. Bir
    ortalamanın ya da tahminin hangi aylardan hesaplandığını söyleyen cümle katlanmaz.
- **Durumlar ve erişilebilirlik**
  - Her veri ekranının boş, yükleniyor ve hata durumu vardır. Hata durumunda yeniden deneme düğmesi bulunur.
  - Klavyeyle kullanılabilir; WCAG AA kontrastı; görünür odak.

## F01 — E-postadan otomatik alım

G1, G10, G13 · Çekirdek

- **Kurulum:** bağlayıcı kurulum sihirbazında seçilir ([ADR-0016](../adr/0016-mail-connectors.md)); terminal
  gerekmez. Başlangıç günü her bağlayıcıda girilir.
  - `browser_bridge`: sihirbaz eklentinin mağaza sayfasını açar. Kullanıcı eklentiyi kurar ve eklentinin ayarlar
    sayfasında eşleştirir; şifre istenmez. Gelişmiş Koruma'daki Gmail hesapları için yol budur: uygulama şifresi
    sayfası "kullanılamıyor" diyorsa sihirbaz bu yolu önerir.
    - Eklenti mağazada olmadığı sürece ([K20](requirements.md#kararlar)) sihirbaz ve Tarayıcı eklentisi ekranı
      eklentinin klasörünü hazırlatır ve dosya yöneticisinde açtırır.
    - Klasörün yeri ve eklentiler sayfasının adresi kopyalanabilir; paketlenmemiş yükleme adım adım anlatılır.
    - Program güncellenince servis klasördeki eklentiyi yeniler (test edilir).
  - `imap`: adres ve uygulama şifresi girilir; şifre anahtar zincirine yazılır.
  - Bağlantı denenir ve sonucu gösterilir. Giriş reddedilirse yeniden denemeden durur.
  - Uygulama hesabın kendi şifresini hiçbir zaman istemez.
- **Eklenti** ([ADR-0016](../adr/0016-mail-connectors.md))
  - Chrome, Edge ve Brave'de; Windows, macOS ve Linux'ta aynı biçimde çalışır.
  - Kurulum sayfası eklentiyi bulur ve eşleştirmeyi başlatır; kullanıcı eklentide bir kez onaylar. Kod yazmak yalnızca
    sayfa eklentiye ulaşamazsa gerekir.
  - İzinleri yalnızca `mail.google.com` ve 127.0.0.1'dir; mağaza sayfası ve eklentinin ayarlar sayfası bunu söyler.
  - Araç çubuğundaki düğme eklentinin penceresini açar: durum, "İplikçi Nedim'i aç", "Şimdi denetle" ve "Eşleştirme ve
    ayarlar". "İplikçi Nedim'i aç" açık bir arayüz sekmesini öne getirir; yoksa eşleşmiş eklentinin servisten aldığı
    tek kullanımlık giriş bağlantısını açar ([ADR-0019](../adr/0019-bridge-login-link.md)).
  - Gmail'i üç katmanla okur. Yeni iletiler gelen kutusu akışından, okunmuş ve arşivlenmiş iletilerle geçmiş tam
    taramadan, iletinin kendisi "Orijinali göster"den alınır. İndirilen ileti okunmamış kalır (test edilir).
  - Tam tarama bozulursa yeni okunmamış iletiler alınmaya devam eder ve kullanıcıya bir kez bildirilir (test edilir).
  - Tam tarama doğrulamada tutmadı (2026-11-01). Bu yüzden geçmiş ve kaçan iletiler "Gmail'de eksikleri tara" ile
    alınır. Tarama eşleşince kendiliğinden başlar; başlangıç günü ya da gönderici listesi değişince yeniden istenir
    (test edilir).
  - Eşleştirme arayüzden iptal edilir; iptal edilen belirteçle gelen istek reddedilir (test edilir).
  - Sistem ekranında eklentinin son görülme zamanı görünür; tarayıcı bir günden uzun kapalıysa bir kez bildirilir.
- **Salt okunur kutu:** hiçbir ileti okundu işaretlenmez, taşınmaz ya da silinmez. IMAP sahte bir sunucuyla, eklenti
  kayıtlı sahte yanıtlarla test edilir.
- **Güven:** yalnızca listedeki alan adlarından (alt alan adları dahil) gelen ve DMARC'tan geçen iletiler alınır.
  Diğerleri hiç saklanmaz.
- **Hız:** IDLE bağlıyken yeni bir banka iletisi ≤ 10 sn içinde arşive ve akışa düşer; eklenti köprüsünde, tarayıcı
  açıkken ≤ 5 dakikada.
- **İlk okuma:** kutu, başlangıç gününden itibaren partilerle okunur. Kesilirse kaldığı yerden sürer; ilerleme arayüzde
  görünür.
- **Banka iletisinin gövdesi** okunur. Okunan türler:
  - kart harcama bildirimi,
  - gelen ve giden transfer bildirimi,
  - otomatik ödeme sonucu,
  - fatura ödendi bildirimi,
  - kredi taksidi hatırlatması,
  - "ekstreniz hazır / son ödeme tarihi / asgari tutar" iletileri.

  Tanınmayan gövde "işlenmedi" olarak saklanır.
- **Ekler:** zip içleri dahil her ek ayrı bir belgedir; aynı içerik ikinci kez saklanmaz.
- **Şirket içeriği:** şirket içeriği taşıyan ileti saklanmaz; özette "şirket belgesi" olarak sayılır.
- **Giriş reddi:** alım durur, `mail.auth_failed` bir kez bildirilir, Sistem ekranında ne yapılacağı yazar.
- **Durum:** son başarılı alım ile okunan, saklanan, işlenen ve işlenmeyen ileti sayıları görünür.
- **Kapsam ölçütü:** kullanıcının kutusundaki banka iletilerinin en az %90'ı ya işlenir ya da bilerek "para hareketi
  yok" diye sınıflanır. Oran Sistem ekranında görünür.

## F02 — Elle ekleme ve gelen klasörü

G1 · Çekirdek

- **Yollar:** arayüzde "Belge ekle" ekranı (`/belge-ekle`, sade görünümün menüsünde de) ve Belgeler ekranının üstü:
  sürükle-bırak, dosya seç ve klasör seç; MCP'de `import_documents`; komut satırında `iplikci ekle`.
- **Klasör:** seçilen ya da sürüklenen bir klasörün içindeki bütün dosyalar, alt klasörleriyle gönderilir; gizli
  dosyalar (`.DS_Store` gibi) atlanır. Servis dosyaları okurken bunu söyler; sonunda kaç belgenin arşive alındığını
  ve kaçının zaten arşivde olduğunu yazar.
- **Türler:** PDF, XLS, XLSX, HTML, XML, ZIP, MBOX ve EML. Bir dosyanın türü içeriğinden anlaşılır: uzantısı olmayan
  ya da yanlış olan bir indirme de alınır. Belge olmayanlar reddedilir ve nedeni söylenir.
- **Adlar önemli değil (K24):** bir belgenin hangi bankanın hangi belgesi olduğu, hesabı ve dönemi içeriğinden okunur.
  Dosya ve klasör adları yalnızca gösterilir.
- **Sınır:** bir içe aktarım en çok 2.000 dosya ve 2 GB olabilir.
- **Plan:** her dosya için ne olacağı gösterilir: belge türü, hesap, dönem, doğrulama sonucu ya da kopya, şirket
  belgesi, işlenmedi, okunamadı.
- **Uygulama:** onaylanınca tam olarak gösterilen plan uygulanır. Plandan sonra bir dosya değiştiyse uygulama reddedilir
  ve plan yenilenir.
- **Gelen klasörü:** klasör 20 sn sessiz kalınca içindeki dosyalar onaysız alınır. Dosyalar arşive taşınır; sonuç
  bildirimle söylenir.
- **Kopya:** aynı içerik ikinci kez gelirse yalnızca yeni kaynak eklenir; aynı ekstrenin başka bir dosyası defterde
  birleştirilir. Aynı hesabın tarihleri çakışan listelerinde her gün bir kez sayılır.

## F03 — Belge arşivi ve görüntüleyici

G2, K3, K4, K11 · Çekirdek

- **Liste:** tür, banka, hesap, dönem, durum, kaynak ve geliş tarihi sütunları; tam metin arama; süzgeçler.
- **Ayrıntı**
  - Kaynaklar: e-posta (gönderen, tarih, konu, "Gmail'de aç" bağlantısı), yükleme, klasör ya da taşıma.
  - Okuyucu ve sürümü; doğrulama sonucu (ekstre toplamı, satır kontrolleri).
  - Belgeden çıkan işlemler ve sayfalar.
- **Görüntüleyici**
  - PDF sayfaları resim olarak gösterilir. Bir işlem seçilince ilgili sayfa açılır ve satır vurgulanır.
  - Tablo dökümlerinde satır tabloda vurgulanır.
  - E-posta metin olarak gösterilir; isteğe bağlı olarak güvenli özgün görünümde açılır.
- **İşlenmeyenler ve okunamayanlar** (ayrı sekme)
  - Her belgenin nedeni yazılır.
  - Seçenekler: "Aslını indir", "Yeniden dene", "Claude'a ver". Sonuncusu MCP'deki `unprocessed_documents` ve kaynak
    bağlantısı üzerinden çalışır.
  - Okuyucusu yazılınca belge kendiliğinden yeniden okunur.
- **Kaldırma:** onay ister. Dosya sistemin çöp kutusuna gider ve denetim kaydına yazılır; kalıcı silme yoktur.
- **İndirme:** inen dosyanın adı okunaklı addır.
- **Ölçüt:** her işlemin (kesin ya da geçici) belgesi ve kaynak konumu vardır (%100). Her belgenin en az bir kaynağı
  vardır.

## F04 — İşlemler ve iz

G2, K4 · Çekirdek

- **Tablo**
  - Sıralama ve sayfalama; tam metin arama.
  - Süzgeçler: dönem, hesap, tür, kategori, gereklilik, kesinlik, etiket.
  - Kayıtlı görünümler; CSV indirme.
- **Satır ayrıntısı**
  - Belge önizlemesi, satırı vurgulanmış.
  - "Neden?" bölümü:
    - kategori kuralı ve hangi katmandan geldiği,
    - transfer çözümünün adımı ve eşi,
    - eşleşen dekont, bildirim ya da fatura,
    - kur ve kaynağı.
  - Kesinlik.
- **Düzeltmeler**
  - Kategori ya da gereklilik değiştirilebilir; yalnızca bu işlem için ya da kural olarak.
  - Not, etiket ve bölme (bir satırı birden çok kategoriye ayırma) eklenebilir.
  - Düzeltmeler yeniden okumada korunur (parmak izi). Eşi bulunamayan düzeltme Yapılacaklar'a düşer.
- **Toplu işlem:** seçili işlemlere kategori ya da etiket verilebilir.

## F05 — Anlık akış

G10 · Çekirdek

- **Olay kartları:** zaman sırasıyla. Kart türleri: yeni işlem, kesinleşti, ekstre geldi, belge işlenmedi, fatura
  eşleşti ya da eşleşmedi, ay kapandı, uyarılar. Her kart ilgili belgeye ya da işleme gider.
- **Canlı güncelleme:** akış SSE ile sayfa yenilenmeden güncellenir. Bağlantı koparsa yeniden bağlanır ve kaçırılan
  olayları son olay kimliğinden itibaren çeker.
- **"Şu an" bölümü**
  - Hesap başına tahmini güncel bakiye: son belgenin bakiyesi ile sonrasında gelen geçici olaylar, notuyla.
  - Kart başına dönem içi harcama.
  - Ay içi tempo, tipik aya göre.
- **"Yaklaşanlar" bölümü:** 14 gün içindeki son ödemeler, beklenen düzenli ve dönemsel ödemeler, maaş, vade sonları.
- **Süzgeç:** hesap, olay türü, kesinlik.

## F06 — Pano

G7 · Çekirdek

- **Sade görünüm:** finans bilgisi olmayan biri için resimlerle, yukarıdan aşağı okunan bir hikâye.
  - Son kapanan ayın gelen, giden ve kalan parası; gelenin harcanan ve kalan payını gösteren bir çubuk ve bir cümlelik
    hüküm: iyi gidiyor, az kaldı (kalan gelenin %10'undan az) ya da gelirden fazla harcandı. Süren ay ayrıca söylenir.
  - Son belgelere göre hesaplardaki para, neye dayandığıyla: kart borçları düşülünce, bakiyesi bilinmeyen hesaplar.
  - Aylara göre gelen (yeşil, çizginin üstünde) ve giden (turuncu, altında) çubuklar; kapanmamış aylar soluk.
  - O ay paranın nereye gittiği: harcama türleri tek renkte yatay çubuklarla, her tür işlemlerine götürür.
  - Önümüzdeki 30 gün: hesaptaki paranın günlük tahmini, eksiye düştüğü ilk gün ya da en düşük gün, yaklaşan ödemeler ve
    gelirler. Çizginin son belgelerdeki bakiyeden bugüne nasıl geldiği söylenir.
  - "Ne yapmalısınız?": açık uyarılar düzeyi sözle yazılarak, ardından Değerlendirme'nin önerilen adımları (en çok
    dört); bekleyen işlerin sayısı Yapılacaklar'a götürür.
  - Her grafiğin üstünde nasıl okunacağını anlatan bir cümle vardır; her grafiğin tablo görünümü de vardır.
- **Ayrıntılı görünüm:** ilk satırda dört rakam (net varlık, bu ay harcanan, 7 gün içinde ödenecek, bekleyen işler),
  ardından tablolarıyla kartlar:
  - net varlık (TL ve seçilen para birimleri),
  - bu ay ile tipik ay (tipik ay yalnızca tam aylardan),
  - 7 gün içinde yaklaşan ödemeler,
  - açık uyarılar,
  - son 7 ayın kapanış durumu,
  - veri tazeliği (hesap başına son belge ve gecikenler),
  - yapılacakların sayısı.
- Her kart ve her grafik ilgili ekrana gider.
- **Menü:** sade görünümde sık kullanılan ekranlar (Pano, Hesaplar, İşlemler, Düzenli ödemeler, Takvim, Değerlendirme,
  Yapılacaklar, Belge ekle) tek listede, diğerleri "Diğer ekranlar" altında; açık ekran oradaysa bölüm açık gelir.
  Ayrıntılı görünümde bütün ekranlar gruplarıyla.

## F07 — Hesaplar

G11 · Çekirdek

- **Hesap haritası**
  - Gruplar: Kredi kartları, Vadesiz, Vadeli, KMH, Döviz, Altın, Yatırım, Krediler.
  - Her grubun toplamı vardır; varlık ve borç ayrı gösterilir.
  - Her hesap kartında: bakiye ve tarihi, son belge, tazelik, bu ayın girişi ve çıkışı.
- **Birleşik akış:** birden çok hesap seçilince işlemleri ve bakiyeleri birlikte gösterilir, toplam giriş ve çıkışla.
- **Türe özel sayfalar**

  | Tür | Gösterilenler |
  |---|---|
  | Kredi kartı | dönem borcu, son ödeme tarihi, asgari tutar, limit (ekstrede yazıyorsa), gelecek aylara yayılan taksit takvimi, faiz ve ücretler, ödeme geçmişi (tam / asgari / kısmi), ekstre zaman çizelgesi |
  | Vadesiz | günlük bakiye eğrisi, gelen ve giden, otomatik ödemeler, maaş |
  | Vadeli | anapara, faiz oranı, vade sonu, net getiri |
  | KMH | limit, kullanılan tutar, eksi gün sayısı, faiz maliyeti, çıkış planı |
  | Döviz, altın | miktar, güncel TL karşılığı, maliyet ve kur farkı |
  | Yatırım | portföy (ekstrenin değeriyle), nakit, temettü, komisyon |
  | Kredi | kalan anapara, taksit planı, ödenen faiz |
- **Hesaplar arası akış:** Sankey diyagramı ve tablo görünümü.
- **Takma ad:** kullanıcı hesaba takma ad verebilir.
- **Kapanmış hesaplar:** belgeleri en yeni belgeden 180 günden eski olan hesaplar ayrı gösterilir ve toplamlara girmez.

## F08 — Abonelikler, düzenli ve dönemsel ödemeler

G7, G10 · Çekirdek

Ekranın adı "Düzenli ödemeler"dir (`/abonelikler`; 2026-11-02'ye dek "Abonelikler"): kira ve fatura gibi her ay
ödenenler de buradadır.

- **Aylık seriler** ve durumları MVP kurallarıyla tespit edilir
  ([domain/interpretation.md](../domain/interpretation.md)).
- **Dönemsel seriler** (V1 taslak kuralı; gerçek veriyle ayarlanır):
  - Aynı ödeme alanına ~182 gün (160–200) ya da ~365 gün (330–400) arayla en az iki ödeme.
  - `_düzenli` kategorilerinde tutar serbesttir; diğerlerinde ±%50 (yıllık fiyat artışı payı).
- **Her serinin gösterdikleri**
  - durum,
  - aylık karşılık (yalnızca süren serilerde; dönemselde dönem başına tutar),
  - son ödeme ve beklenen sonraki ödeme (tarih ve tutar),
  - fiyat değişimi (dövizle faturalanan serilerde döviz tutarıyla karşılaştırılır: kurun etkisi zam sayılmaz),
  - belgeleri.
- **"İptal ettim":** `_biten`'e ay yazılır. Sonra ödeme görünürse uyarı verilir.
- **Taksitli alışverişler:** kalan taksit sayısı ve tutarı, bitiş ayı.
- **V1+:** deneme süresi ve yenileme e-postalarından önceden uyarı; çift abonelik tespiti.

## F09 — Takvim ve nakit akışı öngörüsü

G10, K7 · Çekirdek

- **Takvimdekiler**
  - kart son ödemeleri (dönem borcu, asgari tutar),
  - beklenen düzenli ve dönemsel ödemeler,
  - bekleyen faturalar,
  - kredi taksitleri,
  - vade sonları,
  - beklenen maaş.
- **Öngörü**
  - Önümüzdeki 60 gün için hesap başına gün gün bakiye.
  - Varsayımlar görünür; örneğin hangi ödemenin hangi hesaptan çıkacağı geçmiş ödemelerden çıkarılır.
  - Hesabın eksiye düştüğü gün ve tutar.
  - Uyarı: ek hesabın (KMH) ve kendi hesaplarından düzenli para aktarılan hesabın eksi günleri uyarı sayılmaz; notları
    nedenini yazar. Hesapların toplamı eksiye düşerse uyarılır
    ([domain/interpretation.md](../domain/interpretation.md#akış-olayları)).
  - KMH faizi tahmini, oran belgede yazıyorsa.
- **Etiket:** öngörü her zaman "tahmin" etiketi taşır.
- **V1+:** takvim aboneliği (`.ics`).

## F10 — Değerlendirme, bütçe ve tahmin

G7 · Çekirdek (işaretliler V1+)

- **MVP eşitliği**
  - öne çıkanlar,
  - aylık etkisiyle önerilen adımlar,
  - aylık bütçe (bugünkü tipik ay ile önerilen ay),
  - gereklilik dağılımı,
  - alışkanlıklar ve tasarruf fırsatları,
  - gelir ve gider,
  - 3 aylık tahmin,
  - kategoriler ve en çok harcanan yerler,
  - büyük tek seferlik harcamaların ayrılması.
- **Yeni**
  - Borç görünümü.
  - Olağan dışı hareketler (yalnızca işaret; satır silinmez):
    - işyerinin alışılmış tutarından çok farklı bir çekim,
    - aynı gün aynı tutarda olası çift çekim,
    - yeni bir yerde büyük tutar,
    - beklenmedik ücret ya da aidat.
  - Kur makası maliyeti; döviz gelirinin etkisi.
- **V1+**
  - bütçe hedefleri ve aşım uyarısı,
  - senaryolar,
  - kişiler arası borç-alacak,
  - nakit cüzdanı,
  - enflasyondan arındırılmış eğilimler,
  - haftalık ve aylık "ne değişti" özetleri, yıl sonu özeti.
- **Bulgu kuralı:** her bulgu penceresini, rakamlarını ve ilgili işlemleri gösterir. Bir adım aylık TL etkisini
  yalnızca veri onu fiyatlıyorsa taşır.

## F11 — Ay sonu kapanışı

MVP eşitliği · Çekirdek

- **Durumlar:** sürüyor, eksik, kontrol gerekli, bekleniyor, kapandı.
- **Ayrıntılar**
  - hesap başına kapanış,
  - neyin beklendiği (örnek: "TEB Bonus •4321: 19–31 Ekim ekstresi, kesim ~18.11"),
  - geçici kayıtlar,
  - ekstrede görünmeyen kanıtlar.
- **Ay sayfası:** uygulamanın içinde (`/ay-sonu/:ay`) ve dışa aktarılabilir, betiksiz HTML olarak (MVP sayfası).
- **Bildirimler:** ay bitti, ay kapandı, kontrol gerekli; her biri bir kez.
- **Ölçüt:** kapanmış bir ay yeni belge gelmeden yeniden açılırsa bu bir gerilemedir ve testte yakalanır.

## F12 — Döviz ve varlıklar

G8 · Çekirdek (enflasyon V1+)

- **Kurlar:** TCMB ya da ECB tarihçesi; son kurun tarihi görünür; ağ yoksa belgedeki kurlar kullanılır.
- **Varlıklar ve borçlar**
  - MVP kuralları geçerlidir.
  - Net varlık TL, EUR, USD ve gram altın cinsinden gösterilir.
  - Döviz dağılımı ve dövizli varlıkların maliyet ile kur farkı gösterilir.
- **Kur makası:** son 12 ayda ödenen fark ve ilgili işlemler.
- **Döviz geliri:** TL karşılığı, bozdurma zamanları, kur duyarlılığı (örnek: "EUR/TRY %5 düşerse").
- **V1+:** enflasyondan arındırılmış karşılaştırma (EVDS anahtarıyla).

## F13 — Bildirimler

G12, K10 · Çekirdek

- **Kural düzenleyici:** olay, koşul, kanallar, ayrıntı düzeyi ve sessiz saat seçilir. Önizleme, kuralın son 30 günde
  kaç kez tetikleneceğini gösterir.
- **Hazır kurallar** ([mimari §14](architecture.md#14-bildirimler)) varsayılan olarak açıktır.
- **Kanallar:** kendine e-posta, Telegram (bot ve eşleştirme kodu), masaüstü, uygulama içi. E-posta kanalı, uygulama
  şifresine izin veren bir gönderici hesap ister. Gelişmiş Koruma'daki hesapta varsayılan kanallar Telegram ve
  masaüstüdür (ADR-0016).
- **Ayrıntı düzeyleri:** tam, özet, asgari. Varsayılanlar ADR-0010'dadır.
- **Tekrar engeli:** aynı olay için tek bildirim gider; yeniden başlatmadan sonra da.
- **Sıklık:** sessiz saatlerde gelenler özete eklenir; her kanalın bir sıklık sınırı vardır.
- **Geçmiş:** gönderilen her bildirim kanalıyla, durumuyla ve ilgili işlem ya da belgeyle birlikte listelenir.
- **Ölçüt:** başarısız teslim yeniden denenir; başarılı teslim tekrarlanmaz (test edilir).
- **Aşama 5'te uygulanan (2026-11-02)**
  - Kurallar `rules/alerts.yaml`'dadır. 16 hazır kural açıktır: mimari §14'tekiler, ay bitti ve eklentinin iki
    uyarısı.
  - Kural düzenleyici Bildirimler ekranındadır (`/bildirimler`); MCP'de `alerts`, komut satırında `iplikci bildirim`.
    Her kural sessiz saate uyup uymayacağını seçer.
  - Telegram, kullanıcının BotFather'da oluşturduğu botla çalışır. Belirteç Bildirimler ekranına ya da
    `iplikci telegram kur`'un gizli istemine girilir. Bota on dakika içinde `/start <kod>` gönderen sohbet eşleşir.
  - E-posta kanalı yalnızca IMAP bağlayıcısının uygulama şifresiyle çalışır. Tarayıcı eklentisiyle bağlı hesapta ekran
    nedenini söyler.
  - Tekrar engeli kural, olay ve kanal başınadır; bir son ödemenin 7, 3, 1 ve 0 gün eşikleri aynı kurala ikinci kez
    bildirim doğurmaz.
  - Sessiz saatte ve sıklık sınırının üstünde gelenler kanal başına saatte en çok bir özetle gider.
  - Reddedilen giriş ya da belirteç kanalı durdurur; kanal yeniden açılana dek denenmez.
- **İlk okuma (Aşama 6, 2026-11-02):** e-posta geçmişi baştan okunurken bildirimler yalnızca uygulamanın kutusuna
  düşer: eklentide ilk tarama bitene, IMAP'te geçmiş sonuna dek okunana kadar. Geçmişin bir parçasından çıkan uyarılar
  masaüstüne, Telegram'a ve e-postaya gitmez (test edilir). Taramanın ortasında doğan geçici bir "Hesap eksiye düşecek" uyarısı, tarama bitince geçersiz kalabilir.
- **Gerçek veriyle denetim (v0.7.6, 2026-11-03):** uygulamanın kutusundaki bildirimler belgelerle tek tek karşılaştırıldı ve kurallar düzeltildi:
  - Elle indirilen eski belgeler aylar önceki zamları yeni gibi bildirebiliyordu. Artık yeni fiyatı kesinleştiren ödeme
    45 günden eskiyse zam söylenmez.
  - Dolarla faturalanan bir planın kur yükseldikçe artan TL tutarı zam sanılabiliyordu. Artık döviz tutarıyla
    karşılaştırılır.
  - Ek hesapların (KMH) ve kendi hesaplarından para aktarılan hesapların eksi günleri, hesapların toplamı eksiye düşmese de "Hesap eksiye düşecek" diye bildirilebiliyordu. Artık bu hesaplar uyarmaz; toplam izlenir.
  - Kural "Abonelik zammı" adıyla faturaları ve kirayı da kapsıyordu; adı "Düzenli ödeme zammı" oldu.

## F14 — Banka dışı e-postalar

G13, K12 · Çekirdek

- **Gönderici listesi:** DMARC kuralıyla birlikte.
- **İlk okuyucu seti:** Aşama 4'te kullanıcının kutusu taranır; en sık görülen banka dışı göndericilerden seçilir.
  Adaylar:
  - e-Arşiv ve e-Fatura (UBL-TR XML eki),
  - App Store ve Google Play makbuzları,
  - yaygın abonelikler,
  - telefon, internet ve enerji faturaları,
  - e-ticaret sipariş özetleri.
- **Eşleştirme:** e-postadaki tutar, tarih penceresi ve satıcı adının işyeriyle benzerliği birlikte kullanılır.
  - Faturada pencere son ödeme tarihine kadardır.
  - Makbuzda pencere −1…+3 gündür.
- **Durumlar**
  - *Eşleşti:* banka satırına fatura bağlantısı ve kalemler eklenir; kategori iyileşir.
  - *Bekliyor:* takvimde yaklaşan ödeme olarak görünür.
  - *Eşleşmedi:* bilgi satırı olarak görünür, toplamlara girmez. Olası açıklamalar yazılır: "başkası ödemiş olabilir",
    "belgesi olmayan bir hesaptan ödenmiş olabilir", "henüz ödenmemiş olabilir".
- **Ölçüt:** bilgi satırları hiçbir toplamı değiştirmez (test edilir).
- **Aşama 4'te uygulanan (2026-11-02)**
  - İlk okuyucu e-Fatura ve e-Arşiv faturasıdır (UBL-TR XML eki ya da yüklenen XML). Son ödeme tarihi yazan belge
    fatura, yazmayan makbuzdur. Öteki adaylar, kullanıcının eklediği göndericilerin iletileri geldikçe envantere göre
    (`iplikci dev eposta-envanteri`) seçilir.
  - Gönderici listesi Sistem ekranındaki "Banka dışı göndericiler" kartından düzenlenir. Bankanın alan adı listeye
    girmez; liste değişince geçmiş yeniden okunur.
  - Faturada pencere son ödeme tarihinden üç gün sonrasına uzanır (son ödeme tarihi yoksa belge tarihinden 30 gün).
    Tutar kuruşu kuruşuna tutmalıdır; yabancı para birimindeki belge, satırın yazdığı döviz tutarıyla eşleşir. Bir satır
    tek bir belgeyi öder; eski belge önce seçer.
  - Belgenin günleri, hâlâ gönderilen bütün hesapların belgeleri o günleri kapsamadan geçmiş sayılmaz: o zamana dek belge
    bekler.
  - Eşleşen belge, hiçbir kuralın adlandırmadığı satıra satıcının tam adından kategori bulur. Kategori satırı başka türlü
    sayacaksa (yatırım gibi) alınmaz.
  - Takvime yalnızca TL faturaları düşer; yabancı para birimindeki faturanın TL tutarı, banka çekene dek bilinmez.
  - Faturalar ekranı `/faturalar`; API `GET /api/invoices`, MCP aracı `invoices`.

## F15 — Kategori kuralları

MVP eşitliği ve arayüz · Çekirdek

- **Katmanlar:** uygulamayla gelen varsayılan kurallar ve kişisel kurallar. Kişisel kurallar önce denenir. Yapı ve
  eşleştirme sırası [domain/categorization.md](../domain/categorization.md)'dedir.
- **Düzenleyici**
  - İşyeri ya da desen eklenir; kategori ve gereklilik seçilir; `_biten` ve `_düzenli` düzenlenir.
  - Canlı önizleme etkilenen işlemleri gösterir.
  - Kaydetmeden önce doğrulanır: kurallar kurulamıyorsa kayıt yapılmaz.
  - Önceki sürüm `history/` altına alınır.
- **İşlem ekranından:** "bu işyerini her zaman X say" seçeneği kural oluşturur.
- **MCP:** `add_rule`, `mark_ended` ve `write_rules` aynı yoldan geçer; fark ve etkilenen işlemler döner.
- **V1+:** kullanıcının düzeltmelerinden kural önerisi.

## F16 — MCP

G9, K9 · Çekirdek

- **Kapsam:** araçlar ([mimari §17](architecture.md#17-mcp)), kaynaklar ve hazır istemler (ADR-0011).
- **Yazan araçlar:** plan → onay → uygula akışını izler; ek açıklamalar taşır.
- **Gizlilik ve denetim:** maskeleme seçeneği vardır; her çağrı denetim kaydına yazılır.
- **Ölçütler**
  - Claude Code HTTP ile bağlanır; araç listesi, bir okuma ve bir plan → uygula akışı uçtan uca çalışır.
  - Servis kapalıyken stdio köprüsü salt okunur çalışır.
  - Servis talimatları belge metninin veri olduğunu söyler.

## F17 — Kurulum sihirbazı ve ayarlar

Ürün ilkeleri · Çekirdek

- **Sihirbaz adımları**
  1. Veri klasörü (bilgi).
  2. Ad-soyad ve varyantları.
  3. Şirket adları (isteğe bağlı).
  4. E-posta: bağlayıcı seçimi (tarayıcı eklentisi ya da uygulama şifresi), eklentinin kurulumu ve eşleştirilmesi,
     başlangıç günü.
  5. Bankalar ve göndericiler.
  6. Eski belgeleri içe aktarma: klasör, mbox ya da zip.
  7. Bildirim kanalları: Telegram bot yönergesi ve eşleştirme; e-posta (gönderici hesap varsa).
  8. Servisin durumu (servisi kurulum paketi kurar; ADR-0017).
  9. Uzaktan erişim yönergesi (Tailscale; isteğe bağlı).
- **Terminal yok:** kurulumun hiçbir adımı terminal istemez; yardım metinlerinde terminal komutu yoktur (K14).
- **Ayarlar ekranı:** aynı alanlar. Sırlar yalnızca girilir, asla gösterilmez.
- **Ölçüt:** yeni bir kullanıcı sihirbazdan sonra hiçbir dosyayı elle düzenlemeden ilk değerlendirmesini görür.

## F18 — Sistem ve sağlık

Çekirdek

- Servisin durumu ve sürümü; veri klasörünün yolu.
- Son e-posta alımı ve hatası; iş kuyruğu.
- Okuyucu sağlığı tablosu: okuyucu, sürüm, belge sayısı, doğrulanan / toplam, son başarı, alarm.
- Son yedek ve bir sonraki yedek; disk kullanımı.
- Kişisel değer içermeyen günlüğün indirilmesi.

## F19 — Yapılacaklar

Veri kalitesi · Çekirdek

- **Liste**
  - kategorisiz ("Belirsiz") işlemler; sık görülen işyerleri önce,
  - eşleşmeyen kanıtlar ve faturalar,
  - doğrulanmayan ekstreler,
  - eksik belgeler (hangi hesap, hangi dönem; bankanın indirme sayfasına bağlantı),
  - işlenmeyen belgeler,
  - eşi bulunamayan düzeltmeler,
  - okuyucu alarmları.
- **Çözüm:** her madde için tek tıkla bir yol vardır: kural ekle, belge yükle, yok say, Claude'a ver.
- **Panoda:** yapılacakların sayısı görünür.

## F20 — Dışa aktarım ve yedek

Çekirdek (işaretliler V1+)

- **Dışa aktarımlar**
  - CSV: `;` ayraçlı, ondalık ayracı virgül; Türkçe Excel'de doğrudan açılır.
  - XLSX: MVP sayfaları ve yeni bir kesinlik sütunu. Sayfalar: Değerlendirme, Düzenli ödemeler, Alışkanlıklar, Ay
    Sonu, Kapanış, İşlemler, Aylık özet, Gereklilik, Gelir-gider, Belge kontrolü.
  - Tek dosyalık HTML rapor: MVP raporu, CSP `default-src 'none'`.
  - Ay sonu sayfaları.
- **Yedek:** her gün kendiliğinden alınır ve 14 gün saklanır; elle de alınıp geri yüklenebilir.
- **V1+:** uygulama düzeyinde şifreli, taşınabilir yedek. **Sonra:** düz metin muhasebe dışa aktarımı (hledger,
  beancount).

## MVP eşitlik listesi

Sürüm 1.0'dan önce bunların hepsi İplikçi Nedim'de çalışmalıdır. MVP 2026-10-31'de emekliye ayrıldı; bu liste onun
yaptığı her şeyin V1'de de olmasını güvenceye alır.

- [x] **Belge okuma:** MVP'nin bütün okuyucuları ve doğrulama kuralları; macOS'ta OCR; şifreli PDF ve bozuk zip
  "okunamadı" olur; şirket belgesi tanınır. (Aşama 2: 17 okuyucu eklentidir; her birinin sahte belgeleri ve testi
  vardır.)
- [x] **Kopyalar:** aynı sha256 ve aynı ekstre anahtarı kopya olarak tanınır; gelen kutusu planı ve uygulaması
  çalışır. (Aşama 1: aynı baytlar belgenin yeni bir gelişi olur; aynı ekstrenin başka bir dosyası kopyası olarak
  saklanır ve defterde birleşir.)
- [x] **E-posta:** kutu salt okunur; DMARC; okuma konumu; partiler. (Aşama 3: IMAP `EXAMINE` ve `BODY.PEEK[]` ile;
  konum veritabanında; bir alım en çok 300 ileti. Tarayıcı eklentisi de aynı güven kuralından geçer.)
- [x] **Otomatik çalışma:** e-posta, gelen klasörü ve bildirim (artık servisin içinde). (Aşama 3: e-posta ve gelen
  klasörü servisin içinde. Aşama 5: bildirimler de servisin işi; her yenilemeden sonra ve beş dakikada bir gider.)
- [x] **Rapor bölümleri**
  - süzgeçler; özet kutuları;
  - değerlendirme ve strateji (öne çıkanlar, adımlar, bütçe);
  - varlıklar ve borçlar; ay sonu kartı;
  - aylık giderler (tablo görünümü ısı haritası); gereklilik; alışkanlıklar;
  - gelir ve gider; tahmin; kategoriler; en çok harcanan yerler;
  - düzenli ödemeler ve taksitler;
  - işlemler tablosu ve CSV; veri kaynakları ve kapsam;
  - açık ve koyu tema.

  (Aşama 6: Değerlendirme ekranı raporun kartlarını İşlemler süzgeçleriyle taşır; varlık tablosu Döviz'de, hesap
  türlerinin toplamları Hesaplar'da, işlemler aynı süzgeçlerle İşlemler'de ve CSV olarak. Bilerek farklı olanlar:
  bir kategori ya da işyeri adı ekranı süzmez, satırlarını İşlemler'de açar (ekranı süzgeç çubuğu süzer); düzenli
  ödemeler kartı süzgeçlerden bağımsızdır, tamamı Düzenli ödemeler ekranındadır; ortalama kutusunda 24 aylık küçük
  çizgi yoktur, aylar aylık giderler kartındadır. Ekran raporun tek uzun sayfası yerine beş bölümdür: Özet,
  Harcamalar, Gelir, varlık ve borç, Önümüzdeki aylar, İşlemler ve veriler.)
- [x] **Ay sonu:** durumlar, sayfalar, bildirimler; tek bir ayın ayrıntısı. (Aşama 6: `/ay-sonu` ve `/ay-sonu/:ay`,
  ayların betiksiz sayfaları dışa aktarılır; "Ay bitti", "Ay kapandı" ve "Ay kontrol gerektiriyor" bildirimleri
  Aşama 5'te geldi.)
- [x] **Çıktılar:** CSV, XLSX sayfaları, tek dosyalık HTML. (Aşama 3 ve 6: rapor, CSV, Excel ve ay sonu sayfaları
  Sistem ekranında indirilir; İşlemler ve Değerlendirme süzdüklerini CSV olarak verir.)
- [ ] **Kurallar:** `kategoriler.yaml` yapısı ve bölümleri; MCP ile düzenleme, yedek, fark ve etkilenen işlemler.
- [ ] **MCP:** MVP'nin 16 aracı.
- [x] **Güvenlik:** CSP; çerez akışı; Host ve Origin denetimleri; salt okunur e-posta; şifre yalnızca anahtar
  zincirinde. (Aşama 3: servisin kapısı ADR-0007'deki gibi; testleri var.)
- [ ] **Diğer sistemler:** Linux ve Windows'ta çalışma (OCR hariç); çöp kutusu davranışı.
- [ ] **Doğrulama tabanı:** MVP'nin ölçütleriyle çalışır. Demo çalışma alanının altın tabanı tutar; gerçek belgelerin
  tabanı gerilemez (bkz. [yol haritası](roadmap.md#kurallar)).

## Kapsam dışı ve sonraya kalanlar

| Konu | Durum |
|---|---|
| Şirket belgeleri | Kapsam dışı (kalıcı kural). |
| İnternet şubesine otomatik giriş, ekran kazıma | Önerilmiyor. |
| Açık bankacılık | Kapsam dışı. |
| SMS | Sonra (araştırılacak). |
| Hane ya da birden çok kullanıcı | Sonra. |
| Birden çok posta kutusu | V1+. |
| Gmail API (OAuth) | Araştırılacak. |
| Menü çubuğu simgesi | Sonra. |
| Web Push | Şimdilik gerekmiyor (K5). |
| Yapay zekâ asistanı, strateji uzmanları | V2. |
