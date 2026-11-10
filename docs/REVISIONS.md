# Revizyonlar

İplikçi Nedim'in (İngilizce alternatif adı Money-Grubber) revizyonları: her revizyonun gereksinimleri ve kararları
kendi klasöründe, fikirler ve karar bekleyen sorular [`BRAINSTORM.md`](BRAINSTORM.md)'de.

| Revizyon | Konu | Durum | Belge |
|---|---|---|---|
| V0 | MVP `gider-analizi`: banka belgelerini okuyan, doğrulayan, yorumlayan yerel komut satırı programı, web paneli ve MCP sunucusu | 2026-10-31'de emekliye ayrıldı (K17) | Depo dışında, veri klasöründeki arşivde: `archive/mvp/CLAUDE.md` ve `README.md` |
| V1 | Tam teşekküllü kişisel finans analizi ve gelir-gider yorumlama platformu | Aşama 0–6 (v0.1.0–v0.7.0), arayüzün sadeleşmesi (v0.7.1), resimlerle anlatan Pano (v0.7.2), açık sekmeye ulaşan güncellemeler (v0.7.3), içeriğinden tanınan belgeler (v0.7.4), Belge ekle ekranı (v0.7.5), belgelerle denetlenen bildirimler (v0.7.6) ve Aşama 7 (MCP, v0.8.0), Aşama 8 (Döviz, v0.9.0), enflasyondan arındırmanın kartı (v0.9.1), İplikçi Nedim'in sözleri (v0.9.2), düzeltmeler (v0.9.3), grafiklerden işlemlere giden kısayollar (v0.9.4), kuralların yerinde düzeltmeler (v0.9.5), transferin karşılığını önce arayan defter (v0.9.6), sayıldığı yeri de değiştiren tek satırlık düzeltmeler (v0.9.7) üç ödeme isteyen dönemsel seriler (v0.9.8), Ay sonu'yla aynı Kalan (v0.9.9), kapanmayan ayı söyleyen Pano (v0.9.10), yazdığı bankaya eşleşen havaleler (v0.9.11), eksiye düşemeyen hesaplar (v0.9.12), Telegram'dan eklenen belgeler (v0.9.13) ve Gmail'de okunan iletilerle TEB'in hesap cüzdanı (v0.9.14) uygulandı; sırada sürüm 1.0'ın koşulları var | [`v1/requirements.md`](v1/requirements.md), [`v1/architecture.md`](v1/architecture.md), [`v1/features.md`](v1/features.md), [`v1/roadmap.md`](v1/roadmap.md), [`v1/migration.md`](v1/migration.md) |
| V2 | Finansal strateji uzmanları ve yapay zekâ asistanı | Gelecek (V1'den sonra) | [`v2/requirements.md`](v2/requirements.md) |

## Değişiklik kaydı

- 2026-11-10 (44) — Okunan iletiler ve TEB cüzdanı (v0.9.14):
  - [ADR-0016](adr/0016-mail-connectors.md): uygulama notu (eklenti 0.7.0). Açık Gmail sekmesinde görünen banka
    iletileri, okunmuş olsalar da alınır. İçerik betiği yalnızca ileti kimliklerine ve göndericinin alan adına bakar,
    eklenti kurulunca ya da güncellenince açık sekmelere de konur; eklentinin deposu ona kapalıdır.
  - [Özellikler](v1/features.md) F01: aynı yol ve elle taramaya kalan iletiler.
  - [Banka biçimleri](domain/bank-formats.md#teb): TEB'in dijital hesap cüzdanı PDF'i. [Mimari](v1/architecture.md)
    §10: okuyucu `teb.passbook`.
  - [Yorumlama](domain/interpretation.md#varlıklar-ve-borçlar): her ekran en yeni basılı bakiyeyi alır; bakiyenin
    gününden sonra giden para notta yazar; eski bir belgenin borcu tarihiyle söylenir.
  - [Defter](domain/ledger.md#transferler): yeri belli olmayan transfer.

- 2026-11-08 (43) — Telegram'dan belge (v0.9.13):
  - [Gereksinimler](v1/requirements.md): K28, belgeler Telegram botuyla da eklenir.
  - [ADR-0021](adr/0021-telegram-documents.md): eşleşmiş özel sohbetten bota gönderilen belgeler arşive alınır; servis
    botun iletilerini uzun yoklamayla okur; her ileti bir kez işlenir; başka sohbetlerin dosyaları indirilmez.
    ADR-0009 ve ADR-0010'a not.
  - [Özellikler](v1/features.md) F02 ve F13, [Mimari](v1/architecture.md) §6, §7, §16, §19 ve §20: Telegram'dan
    belge akışı, `PUT /api/notify/telegram/documents`, `iplikci telegram belgeler`, `[notify] telegram_documents`.

- 2026-11-05 (42) — Eksiye düşemeyen hesap (v0.9.12):
  - [Yorumlama](domain/interpretation.md#varlıklar-ve-borçlar): belgede görünmeyen giriş. Ek hesabı olmayan bir
    hesabı dekontlar sıfırın altına indiriyorsa bakiye 0'dır; tutar borç sayılmaz, toplamlardan ayrı bir satırla düşer.
  - [Banka biçimleri](domain/bank-formats.md#garanti-bbva): Garanti yalnızca giden transferleri bildirir; hesap
    dökümünün üst bloğu indirildiği anı ve kullanılabilir bakiyeyi yazar.

- 2026-11-05 (41) — Havale, yazdığı bankaya (v0.9.11):
  - [Defter](domain/ledger.md#transferler): paranın gittiği bankayı yazan satır yalnızca o bankadaki bir hesapla
    eşleşir.
  - [Kategori kuralları](domain/categorization.md#ilkeler): "TURİZM" tek başına otobüs bileti değildir.

- 2026-11-04 (40) — Kapanmayan ay neden anlatılmıyor (v0.9.10):
  - [Özellikler](v1/features.md) F06: Pano'nun hikâyesinden sonra biten ama kapanmayan ay, kaç belge beklediğini,
    sonuncusunun hangi gün geleceğini ve o aya kadar ne harcandığını bir cümleyle söyler.

- 2026-11-04 (39) — Kalan, Ay sonu'ndaki gibi (v0.9.9):
  - [Özellikler](v1/features.md) F06: Pano'nun Kalan'ı Ay sonu'nunki; Giden harcama, kişilere gönderilen para ve
    kredi anaparası, birikim ayrıca (kullanıcının isteğiyle).
  - [Yorumlama](domain/interpretation.md) "Toplamlar": Kalan'ın tanımı ve onu söyleyen yerler.
  - [Defter](domain/ledger.md#taksitli-nakit-avans) ve [banka biçimleri](domain/bank-formats.md): Garanti'nin
    taksitli nakit avansı anapara ve faize ayrılır.
  - [Kategori kuralları](domain/categorization.md): gelir satırı yalnızca gelen parayı gelir sayan bir kategoriyi
    alır.

- 2026-11-03 (38) — İki ödeme bir dönem yapmaz (v0.9.8):
  - [Yorumlama](domain/interpretation.md) "Dönemsel seriler": `_düzenli` kategorileri dışında dönemsel seri en az
    üç ödeme ister; fiyat değişiminin bildirimi zammı ve düşüşü ayrı adlandırır.
  - [Özellikler](v1/features.md) F08 ve F13, [Mimari](v1/architecture.md) §14: kuralın adı "Düzenli ödeme tutarı
    değişti".

- 2026-11-03 (37) — Tek satırın düzeltmesi, sayıldığı yerle (v0.9.7):
  - [Özellikler](v1/features.md) F04: defterin çözdüğü bir transfere verilen kategori türünü de belirler; tek bir
    satırın istisnası için desen yazılmaz.
  - [Mimari](v1/architecture.md) §7 "Kullanıcı düzeltmesi" ve [kategori kuralları](domain/categorization.md): programın
    bir tür için tuttuğu kategoriler o türdür.

- 2026-11-03 (36) — Transferin karşılığı önce (v0.9.6):
  - [Defter](domain/ledger.md#transferler): transferler en sağlam işaretten başlayarak çözülür. İki ucu da kendi
    adınızı yazan satırlar ve kendi adınızı yazan ters satırla eşleşen açık satırlar, adıyla yapılmış bir ödemeye
    benzeyen satırlardan önce gelir.

- 2026-11-03 (35) — Kuralların yerinde düzeltmeler (v0.9.5):
  - [Kategori kuralları](domain/categorization.md): `_hariç`, bir kategorinin desenleri tutsa da ona ait olmayan
    kelimeler; katmanlar arasında birleşir.
  - [Yorumlama](domain/interpretation.md): `_biten`'deki ay son ödemenin ayıdır, o ayın ödemesi gelene dek seri
    sürer; düzenli bir gelir de böyle bitirilir ve sonradan gelen para onu yeniden başlatmaz.
  - [Özellikler](v1/features.md) F08: "Artık gelmiyor".
  - [Banka biçimleri](domain/bank-formats.md): QNB'nin ATM ya da banka kartıyla para çıkışı bildirimi nakittir.

- 2026-11-03 (34) — Grafiklerden işlemlere (v0.9.4):
  - [Gereksinimler](v1/requirements.md): K27, grafikler kısayoldur. Bir parçaya tıklayınca onu toplayan işlemler
    açılır.
  - [Özellikler](v1/features.md): ortak kurallarda "İz"in açtığı listenin rakamı toplaması ve grafiklerin kısayolları
    (fare, dokunmatik ekran, klavye); yeni bir ekranın sayfanın başından açılması; F09'da adresteki gün (`?gun=`).
  - [Mimari](v1/architecture.md) §18: bağlantılar; birden çok değerli bir süzgecin değerleri liste olarak gelir.

- 2026-11-03 (33) — Düzeltmeler (v0.9.3):
  - [Yorumlama](domain/interpretation.md#v1de-eklenen-hesaplar): öngörünün başlangıç bakiyesi; döküm yalnızca
    gösterdiği satırları kapsar, son günlerinin dökümde görünmeyen dekont satırları da eklenir. Hesaplar, Şu an,
    Döviz, net varlık ve öngörü aynı bakiyeyi kullanır.

- 2026-11-03 (32) — İplikçi Nedim'in sözleri (v0.9.2):
  - [Gereksinimler](v1/requirements.md): K26, İplikçi Nedim'in sözleri paranın durumuna göre ve yüzüyle, arayüzde ve
    eklentinin penceresinde.
  - [ADR-0020](adr/0020-bridge-sayings.md) kabul edildi: eşleşmiş eklenti sözleri `GET /api/bridge/sayings` ile alır;
    yanıt tutar, hesap ya da ad taşımaz. [ADR-0007](adr/0007-api-and-auth.md)'ye ve
    [ADR-0016](adr/0016-mail-connectors.md)'ya notu.
  - [İplikçi Nedim'in sözleri](İplikçi_Nedim_Sözler.md): kullanıcının listesi, her sözün durumu, sırası ve rengi.
  - [Özellikler](v1/features.md#f06--pano): F06'nın sözü; F01'de eklentinin penceresi.
  - [Mimari](v1/architecture.md) §16: `/api/dashboard`'un `sayings` alanı ve `GET /api/bridge/sayings`; §18: sözü
    kimin seçtiği, yüzlerin nereden çizildiği.

- 2026-11-03 (31) — Enflasyondan arındırma (v0.9.1):
  - [Gereksinimler](v1/requirements.md): K25, Windows ve Linux denemeleri bekletilir.
  - [Yol haritası](v1/roadmap.md#sürüm-10): sürüm 1.0'ın süreye bağlı koşullarının neyi göstermesi gerektiği; K25'in
    eşitlik listesine etkisi; Aşama 8'in EVDS notu.
  - [Mimari](v1/architecture.md#15-döviz) §15: TÜFE serisi `TP.TUKFIY2025.GENEL` (2003=100 serisi Ocak 2026'da
    arşive alınıp bitti); Değerlendirme TÜFE'yi yalnızca anahtar varken okur; duran seri (`behind`). §16'da
    `/api/settings/evds`'nin `behind` alanı.
  - [Özellikler](v1/features.md#f12--döviz-ve-varlıklar): F12'nin V1+ maddesi, kartın anlattıkları ve özelliğin açılıp
    kapanması.

- 2026-11-03 (30) — Aşama 8: Döviz (v0.9.0):
  - [ADR-0009](adr/0009-network-egress-policy.md)'un notu: kur sağlayıcılarının ve EVDS'nin sunucuları, yalnızca GET,
    ECB'nin sertifikası yüzünden Frankfurter'in önce gelmesi; EVDS'nin izin listesine girmesi.
  - [Mimari](v1/architecture.md#15-döviz) §15: uygulananlar (sağlayıcılar, geçmişin bir kez çekilmesi, kur defteri,
    makas ve döviz geliri, TÜFE); §16'da `POST /api/fx/fetch` ve `/api/settings/evds`; §9'da `price_index`; §20'de
    `[fx] evds`.
  - [Özellikler](v1/features.md#f12--döviz-ve-varlıklar): F12'nin Aşama 8'de uygulananları, V1+ TÜFE'si dahil.
  - [Yol haritası](v1/roadmap.md#aşama-8--döviz): Aşama 8'in durumu.
  - [Alan kuralları](domain/): kur çevirisi ([defter](domain/ledger.md#kur-çevirisi)), kur makası ve döviz geliri
    ([yorumlama](domain/interpretation.md)).

- 2026-11-03 (29) — Aşama 7: MCP (v0.8.0):
  - [ADR-0011](adr/0011-mcp.md)'e uygulama notu: SDK, durumsuz `/mcp`, başlık yardımcısı, her iletide servisi ya da
    veritabanını seçen stdio köprüsü, plan → onay → uygula, maskeleme düzeyleri ve denetim kaydı.
  - [Mimari](v1/architecture.md#17-mcp) §17: 31 aracın tablosu, hangilerinin iki adımlı olduğu, sayfalama.
  - [Özellikler](v1/features.md#f16--mcp): F16'nın uygulananları ve ölçütlerin denenmesi; MVP eşitlik listesinin
    Kurallar ve MCP maddeleri işaretlendi.
  - [Yol haritası](v1/roadmap.md#aşama-7--mcp): Aşama 7'nin durumu.

- 2026-11-03 (28) — Aşama 7 başladı (`asama-7`):
  - [Gereksinimler](v1/requirements.md): K23, Claude'u claude-SAK ile terminalsiz bağlamak; bağlantı bilgisi ve
    belirteç arayüzde gösterilir ve kopyalanır.
  - [Yol haritası](v1/roadmap.md#aşama-7--mcp): Aşama 7'nin teslimlerine Claude bağlantısı ekranı, başlık yardımcısı
    ve SAK ile ekleme.

- 2026-11-03 (27) — Bildirimler belgelerle denetlendi (v0.7.6):
  - [Yorum kuralları](domain/interpretation.md): aylık serilerin fiyat değişimi kuralı yazıldı; dövizle faturalanan
    ödemeler döviz tutarıyla karşılaştırılır. Zam, yeni fiyatı kesinleştiren ödeme 45 günden eski değilse haberdir.
    KMH'nin ve kendi hesaplarından para aktarılan hesabın eksi günleri uyarı sayılmaz; hesapların toplamı izlenir.
  - [Özellikler](v1/features.md): F08'in fiyat değişimi, F09'un uyarısı, F13'ün denetimi.
  - [Mimari](v1/architecture.md) §14: "Abonelik zammı" kuralının adı "Düzenli ödeme zammı" oldu.

- 2026-11-03 (26) — Belge ekle ekranı (v0.7.5): [özellikler](v1/features.md#f02--elle-ekleme-ve-gelen-klasörü)'de
  F02'nin yolları ve klasörle ekleme, F06'nın sade menüsü.

- 2026-11-03 (25) — Belgeler içeriğinden tanınır (v0.7.4):
  - [Gereksinimler](v1/requirements.md): K24, elle indirilen belgeler her yükleme gibi alınır.
  - [Özellikler](v1/features.md#f02--elle-ekleme-ve-gelen-klasörü): türü içerikten anlaşılan dosyalar; adlar
    önemli değil.
  - [Defter](domain/ledger.md#kopyalar): aynı hesabın çakışan listelerinde her gün tek listeden sayılır.

- 2026-11-03 (24) — Arayüzün güncellemeleri açık sekmeye ulaşır (v0.7.3):
  [ADR-0008](adr/0008-frontend-pwa.md)'e not: yeni service worker beklemeden devreye girer, sayfa kendini yeniler ve
  öne gelen sekme yeni bir sürüm olup olmadığını sorar. `CHANGELOG.md`'ye 0.7.3 eklendi.

- 2026-11-03 (23) — Pano'nun sade görünümü resimlerle anlatır (`arayuz` dalı, v0.7.2); belgeler kodla uyumlu
  hâle getirildi:
  - [Özellikler](v1/features.md#f06--pano): F06 sade görünümün hikâyesini (son kapanan ay, aylar, paranın nereye
    gittiği, önümüzdeki 30 gün, ne yapmalı) ve iki görünümün menüsünü anlatır.
  - README'nin durum bölümü güncellendi; `CHANGELOG.md`'ye 0.7.2 eklendi.

- 2026-11-02 (22) — Aşama 6'nın ardından arayüz sadeleşti (`arayuz` dalı, v0.7.1); belgeler kodla uyumlu hâle
  getirildi:
  - README'nin durum bölümü güncellendi; `CHANGELOG.md`'ye 0.7.1 eklendi.
  - [ADR-0019](adr/0019-bridge-login-link.md) kabul edildi: eşleşmiş tarayıcı eklentisi arayüzü tek kullanımlık giriş
    bağlantısıyla açar; [ADR-0007](adr/0007-api-and-auth.md) ve [ADR-0016](adr/0016-mail-connectors.md)'ya notlar.
  - [Özellikler](v1/features.md#ortak-kurallar): ekranların bölümleri, "Nasıl hesaplandı?", kapanmamış ayların ve
    toplama girmeyen hesapların anlatımı, eklentinin penceresi; ekranın adı "Düzenli ödemeler".
  - [Mimari](v1/architecture.md): `POST /api/bridge/login-link` ve eklenti belirtecinin yeni kapsamı.
  - [Yorumlama](domain/interpretation.md) ve [defter](domain/ledger.md): öngörünün belgelerin henüz ulaşmadığı
    günleri sayması, bütçenin her harcamayı tek satırda sayması, bekleyen faturanın satıcının düzenli ödemesi olması.

- 2026-11-02 (21) — Aşama 7'ye hazırlık: [yol haritası](v1/roadmap.md#aşama-7--mcp)'na Aşama 7'nin başlangıçtaki
  durumu (MCP sunucusunun bugünkü hâli, 21 araç) ve ayrıntılı teslimleri, Aşama 8'in başlangıçtaki durumu yazıldı.

- 2026-11-02 (20) — Aşama 6 uygulandı (`asama-6` dalı); belgeler kodla uyumlu hâle getirildi:
  - README'nin durum bölümü ve `web/README.md` güncellendi; `CHANGELOG.md`'ye 0.7.0 eklendi.
  - [Yol haritası](v1/roadmap.md#aşama-6--arayüz): Aşama 6'nın durumu, macOS'ta temiz kurulumun sonucu ve açık
    kalanlar (Windows'ta temiz kurulum ve orada bakılacaklar, yedi günlük çalışma).
  - [ADR-0010](adr/0010-notification-channels.md) ve [F13](v1/features.md#f13--bildirimler): e-posta geçmişi baştan
    okunurken bildirimler yalnızca uygulamanın kutusuna düşer.
  - [Özellikler](v1/features.md#mvp-eşitlik-listesi): MVP eşitlik listesinde rapor bölümleri, ay sonu ve çıktılar
    işaretlendi; bilerek farklı olanlar yazıldı.
  - [Mimari](v1/architecture.md): API tablosunda hesapların ay ay kapsamı.
  - [ADR-0016](adr/0016-mail-connectors.md) ve [ADR-0017](adr/0017-no-terminal-install.md)'ye uygulama notları:
    eklentinin veri klasöründeki klasörden yüklenmesi (K20), paketlerin yapısı, güncelleme ve kaldırma.

- 2026-11-02 (19) — [ADR-0017](adr/0017-no-terminal-install.md) kabul edildi (kullanıcının sözü: "Kabul edildi, amaca
  uygun özellik."): kurulum paketleri Aşama 6'da, imzasız (K22), taşınabilir CPython ve içine kurulmuş programla.

- 2026-11-02 (18) — Kullanıcı kararı [K22](v1/requirements.md#kararlar): kurulum paketleri şimdilik imzalanmaz;
  Windows denemesini kullanıcı istediğinde yapar; macOS'ta temiz kurulum bir Mac'te, eski kurulum kaldırılarak denenir.

- 2026-11-02 (17) — Aşama 6'nın ön incelemesi: [ADR-0017](adr/0017-no-terminal-install.md)'ye "Paketleme biçimi"
  bölümü eklendi (ADR hâlâ önerildi). Okuma süreçleri ve servis kaydı `python -I -m` ile çalıştığı için paket donmuş
  değil, taşınabilir CPython ve içine kurulmuş programdır; kalıcı yer, güncelleme ve imzasız paket notları da orada.

- 2026-11-02 (16) — Aşama 5 uygulandı (`asama-5` dalı); belgeler kodla uyumlu hâle getirildi:
  - README'nin durum bölümü güncellendi; `CHANGELOG.md`'ye 0.6.0 eklendi.
  - [ADR-0010](adr/0010-notification-channels.md)'a uygulama notu: kurallar, kanallar, tekrar engeli, sessiz saat ve
    özet, yeniden deneme, duran kanal, Telegram eşleştirmesi ve `[notify]` ayarları.
  - [Yol haritası](v1/roadmap.md#aşama-5--bildirimler): Aşama 5'in durumu.
  - [Özellikler](v1/features.md#f13--bildirimler): F13'te Aşama 5'te uygulananlar.
  - [Mimari](v1/architecture.md): akış olaylarının hedefleri ve ayrıntıları, bildirimlerin uygulanışı, API tablosunda
    bildirimler, uyarı kuralları, Telegram ve olay akışının `notifications` olayı, MCP'de `alerts`, `[notify]`
    ayarları.
  - [Yorum](domain/interpretation.md#akış-olayları): akış olayları ve onları söyleyen kurallar.

- 2026-11-02 (15) — Aşama 4 uygulandı (`asama-4` dalı); belgeler kodla uyumlu hâle getirildi:
  - README'nin durum bölümü güncellendi; `CHANGELOG.md`'ye 0.5.0 eklendi.
  - Kullanıcı kararı [K21](v1/requirements.md#kararlar): banka e-postayla göndermiyorsa döküm kullanıcıdan istenmez;
    hesabın hareketleri bankanın e-postalarından kendiliğinden çıkarılır.
  - [Yol haritası](v1/roadmap.md#aşama-4--e-postanın-tamamı): Aşama 4'ün durumu, kutunun envanteri ve F01'in kapsamı.
  - [Özellikler](v1/features.md#f14--banka-dışı-e-postalar): F14'te Aşama 4'te uygulananlar.
  - [Mimari](v1/architecture.md): API tablosunda faturalar ve banka dışı göndericiler, MCP'de `invoices`, ön yüzde
    `/faturalar`.
  - [Defter](domain/ledger.md#kanıtlar-dekontlar-ve-banka-bildirimleri): banka bildirimleri kanıttır; banka dışı
    faturaların eşleştirilmesi ve kategoriye katkısı.
  - [Banka biçimleri](domain/bank-formats.md): Vakıfbank, Garanti BBVA, QNB ve İş Bankası bildirimleri, e-posta
    gövdesinin okunması, selamlamadaki şirket adı ve SGK işyeri sicil numarası.
  - [Yorum](domain/interpretation.md): dönemsel seriler, takvim, nakit akışı öngörüsü ve ay sonunda yalnızca
    e-cüzdanından bilinen hesap.
  - [Geçiş](v1/migration.md#aşama-3-e-posta-ve-geçmiş): gövdelerin okunması; e-postayla gelmeyen döküm artık
    istenmez.

- 2026-11-01 (14) — Aşama 3 uygulandı (`asama-3` dalı); belgeler kodla uyumlu hâle getirildi:
  - README'nin durum bölümü güncellendi; `CHANGELOG.md`'ye 0.4.0 eklendi.
  - Kullanıcı kararları: [K19](v1/requirements.md#kararlar), önce macOS; Aşama 3, servisin yedi günlük çalışması ve
    Windows denemesi açık koşul olarak yazılıp kapatıldı. [K20](v1/requirements.md#kararlar), eklenti şimdilik
    Chrome Web Store'da yayımlanmaz.
  - [ADR-0016](adr/0016-mail-connectors.md)'ya uygulama notları: doğrulamanın sonuçları, "Gmail'de eksikleri tara",
    geçmişin servisçe izlenmesi, alınmayan ve ekleri boş saklanan iletiler, ekler için "Orijinali indir" ve
    konuşmaların ortası için yazdırma görünümü. Ek sunucusu [ADR-0009](adr/0009-network-egress-policy.md)'a da
    eklendi.
  - [ADR-0007](adr/0007-api-and-auth.md), [ADR-0014](adr/0014-event-log-and-jobs.md) ve
    [ADR-0015](adr/0015-email-ingestion.md)'e uygulama notları; ADR-0015'e güven kuralının ana alan adı ayrıntısı.
  - [Mimari](v1/architecture.md)'de API tablosu ve güvenlik; [özellikler](v1/features.md)'de e-posta, yükleme ve
    Sistem ekranı.
  - [Geçiş](v1/migration.md#aşama-3-e-posta-ve-geçmiş): kutunun baştan okunması ve ilk gerçek taban.
  - [Yol haritası](v1/roadmap.md#aşama-3--servis): Aşama 3'ün durumu ve açık koşulları.

- 2026-11-01 (13) — Aşama 2 uygulandı (`asama-2` dalı); belgeler kodla uyumlu hâle getirildi:
  - README'nin durum bölümü ve geliştirici komutları güncellendi; `CHANGELOG.md`'ye 0.3.0 eklendi.
  - [ADR-0005](adr/0005-parser-plugins.md)'e uygulama notu: okuyucuların yeri, seçim eşiği, sürüm, kalıcı okuma süreci
    (bellek sınırı yalnızca Linux'ta), kaynak konumu, biçim alarmı, sahte belgeler ve araçlar.
  - [ADR-0014](adr/0014-event-log-and-jobs.md)'e uygulama notu: `events` tablosu biçim alarmı için Aşama 2'de açıldı.
  - [Mimari §10](v1/architecture.md#10-okuyucular): okuyucuların modülleri, kaynak konumunun biçimleri, okuma süreci ve
    alarm.
  - [Defter](domain/ledger.md#doğrulama-değişmezleri): biçim alarmı; yeniden kurma olay kaydını da taşır.
  - [Banka biçimleri](domain/bank-formats.md): sayfanın ilerisindeki şirket kartı işareti ve OCR'ın temassız simgesi.
  - [Eşitlik listesi](v1/features.md#mvp-eşitlik-listesi)'nde belge okuma işaretlendi; yol haritası ve geçiş belgesi
    Aşama 2'nin durumunu söylüyor. Tablodaki V1 durumu Aşama 1'den beri güncel değildi; düzeltildi.

- 2026-11-01 (12) — Aşama 1 uygulandı (`asama-1` dalı); belgeler kodla uyumlu hâle getirildi:
  - README'nin durum bölümü ve geliştirici komutları güncellendi; `CHANGELOG.md`'ye 0.2.0 eklendi.
  - [Mimari §9](v1/architecture.md#9-veri-klasörü): doğrulama tabanının yeri (`baseline.json`).
  - [Defter](domain/ledger.md#doğrulama-değişmezleri): taban veri klasöründe; `--arsiv` ve `--yeniden-kur` eklendi.
  - [ADR-0006](adr/0006-money-and-codes.md)'ya uygulama notu: satır tutarları `Decimal`; satırlar `Money`'yi, defter
    ve yorum hesapları kendi paketlerine taşınırken alır. Geçişte demonun tabanı değişmedi.
  - [Geçiş](v1/migration.md#aşama-1-çalışma-alanından-veri-klasörüne) belgesine Aşama 1 adımı eklendi.
  - [Eşitlik listesi](v1/features.md#mvp-eşitlik-listesi)'nde kopyalar işaretlendi.
  - Kullanıcıya görünen metinler `kategoriler.yaml` yerine kişisel kuralları anıyor.
- 2026-11-01 (11) — Kullanıcı kararı [K18](v1/requirements.md#kararlar): depo özel kalır, lisans BSD 3-Clause
  (`LICENSE.txt`, kullanıcı ekledi). CLAUDE.md, gereksinimlerdeki açık soru, README ve `pyproject.toml`'un lisans
  alanları buna göre güncellendi.
- 2026-11-01 (10) — Aşama 0 uygulandı (`asama-0` dalı); belgeler kodla uyumlu hâle getirildi:
  - README'nin durum bölümü güncellendi; geliştiriciler için komutlar eklendi. `CHANGELOG.md` başladı.
  - [Yol haritası](v1/roadmap.md)'nın ilk oturum bölümü, adımların uygulandığını söylüyor.
  - [Geçiş](v1/migration.md#aşama-0-kod-arşivden-depoya) belgesindeki Aşama 0 adımları yapılanlarla işaretlendi.
  - [Defter](domain/ledger.md#doğrulama-değişmezleri) belgesine doğrulama tabanının içeriği, `--tarih` ve `--kabul`
    eklendi.
  - [ADR-0001](adr/0001-modular-monolith-service.md)'deki servis komutu, mimarideki adıyla (`iplikci servis calistir`)
    eşlendi. Mimarinin ölçek bölümü, verinin MVP'ye ait olduğunu ve V1'e devredilmediğini söylüyor.
- 2026-11-01 (9) — İlk commit'ten önceki düzeltmeler:
  - [Kategori kuralları](domain/categorization.md)'ndaki örnek işyeri, kişisel kurallardan gelen bir ad yerine genel bir
    zincir oldu.
- 2026-10-31 (8) — Eski yapı kaldırıldı ve MVP emekliye ayrıldı ([K17](v1/requirements.md#kararlar),
  [ADR-0018](adr/0018-retire-mvp-clean-start.md)). Kullanıcı, İplikçi Nedim'in veriyi kendisi toplamasını istedi;
  sistem MVP'nin belge klasörleriyle ve taşıma kayıtlarıyla çalışmayacak.
  - MVP'nin kodu, testleri, kuralları ve ayarları veri klasörünün arşivine (`archive/mvp/`) kopyalandı. Aşama 0 kodu
    oradan alır; kişisel kurallar ve ayarlar V1'e aktarılmaz.
  - Geçiş planı yeniden yazıldı.
  - Yol haritasından `migrate-mvp` ve geçiş aşaması çıkarıldı. Gerçek belgeler gelene dek taban demo çalışma alanında
    alınır; `v1.0.0` sürüm koşulları sağlanınca atılır.
  - CLAUDE.md, gereksinimler, mimari, özellikler ve ilgili ADR'ler buna göre güncellendi.
- 2026-10-31 (7) — Son düzeltmeler; çalışma artık yalnızca depo klasöründe.
- 2026-10-31 (6) — Kullanıcı eklentinin okuma yolu olarak B'yi, yani Gmail'in web arayüzünü seçti
  ([K16](v1/requirements.md#kararlar)). Apps Script kendiliğinden kurulamıyor ve kurulumu son kullanıcıya göre değil.
  - [ADR-0016](adr/0016-mail-connectors.md) kabul edildi. Gmail'den okuma üç katmana ayrıldı: belgelenmiş gelen
    kutusu akışı, web araması ve ham ileti. Doğrulaması Aşama 3'ün ilk işi oldu.
  - Eşleştirme, kod yazmak yerine eklentide tek bir onaya indi.
- 2026-10-31 (5) — Kullanıcı Thunderbird köprüsünü reddetti, bir Chrome eklentisi önerdi ve iki ilke koydu: platformdan
  bağımsızlık ve terminalsiz kullanım ([K14, K15](v1/requirements.md#kararlar)).
  - [ADR-0016](adr/0016-mail-connectors.md) tarayıcı eklentisi köprüsü olarak yeniden yazıldı (önerildi). Okuma yolu
    (A: Apps Script, B: Gmail web) tarayıcıdaki bir denemeyle seçilecek.
  - [ADR-0017](adr/0017-no-terminal-install.md) eklendi: işletim sistemi başına kurulum paketi ve her işin arayüzde
    olması (önerildi).
  - Mimari, özellikler, yol haritası (eklenti Aşama 3'te, paketler Aşama 6'da), geçiş planı ve CLAUDE.md buna göre
    güncellendi.
- 2026-10-31 (4) — Ad düzeltmesi ve e-posta bağlantısı:
  - Ad **İplikçi Nedim** oldu ([K1](v1/requirements.md#kararlar)). Depo ve dağıtım adı `iplikci-nedim`. Python paketi, komut ve diğer teknik adlar kısa adla `iplikci` kalır.
  - Gelişmiş Koruma'daki (Advanced Protection) Gmail hesaplarında uygulama şifresi yok; MVP'nin e-posta alımı bu hesaplarda çalışmaz. E-posta bağlantısı için [ADR-0016](adr/0016-mail-connectors.md) önerildi. Önerilen yol Thunderbird
    köprüsü; kabulü kullanıcının denemesine bağlı.
- 2026-10-31 (3) — Belgeler son hâline getirildi; uygulama yeni bir oturumda Aşama 0 ile başlayacak. Eklenenler:
  - [Mimari](v1/architecture.md), [özellikler](v1/features.md) (kabul ölçütleri ve MVP eşitlik listesiyle),
    [yol haritası](v1/roadmap.md) ve [geçiş planı](v1/migration.md).
  - [ADR-0001 … ADR-0015](adr/README.md).
  - [Alan kuralları](domain/): MVP'nin `CLAUDE.md`'sindeki bilgi kişisel verilerden arındırılıp Türkçe olarak buraya
    taşındı.
  - Deponun `CLAUDE.md`'si, belge dizini ve `.gitignore`.

  Beyin fırtınası kapatıldı. Açık sorular varsayılan kararlarla kapatıldı (V1 gereksinimleri → Açık sorular).
- 2026-10-31 (2) — Kullanıcının yanıtları işlendi: ad İplikçi (`iplikci`), İngilizce alternatif Money-Grubber;
  belgeler `iplikci` deposuna taşındı ve depoya README eklendi. V1'e ürün ilkeleri, karar kaydı (K1–K13), kural
  değişiklikleri tablosu ve yeni gereksinimler eklendi: G10 anlık finansal akış, G11 hesap türlerine göre toplu ve
  ayrı akışlar, G12 kural tabanlı bildirimler (e-posta, Telegram), G13 banka dışı e-postalar. Beyin fırtınasında
  onaylanan öneriler işaretlendi; yeni bölümler §16–§20 eklendi; yol haritası §21'e, sorular §22'ye taşındı.
- 2026-10-31 (1) — V1 ve V2 gereksinimleri kullanıcının ifadesiyle kaydedildi; gereksinimlere kimlik verildi (V1-G1 …
  V1-G9, V2-G1, V2-G2) ve her birinin bugünkü durumu yazıldı. Beyin fırtınası belgesi açıldı.
