# Beyin fırtınası — V1 ve sonrası

Proje: İplikçi Nedim · Durum: **kapandı (2026-10-31)** · Gereksinimler ve kararlar: [V1](v1/requirements.md),
[V2](v2/requirements.md)

> Ad notu: bu belge yazılırken proje adı İplikçi, depo adı `iplikci` idi. Aynı gün ad **İplikçi Nedim**, depo adı
> `iplikci-nedim` oldu; teknik adlar `iplikci` kaldı ([K1](v1/requirements.md#kararlar)). Aşağıdaki eski adlar tarihçe
> olarak bırakıldı.

> Bu belge tarihçedir. Kabul edilen öneriler ve açık soruların varsayılan kararları şu belgelere işlendi; güncel kaynak
> onlardır:
>
> - [V1 gereksinimleri](v1/requirements.md)
> - [özellikler](v1/features.md)
> - [mimari](v1/architecture.md)
> - [yol haritası](v1/roadmap.md)
> - [geçiş planı](v1/migration.md)
> - [ADR'ler](adr/README.md)
>
> Aşağıdaki ayrıntılarla bu belgeler çelişirse geçerli olan bu belgelerdir.

Bu belge bir öneri listesiydi. Kullanıcının onayladıkları **[Kabul]** etiketi taşır; kararların kendisi
[V1 gereksinimlerinde](v1/requirements.md#kararlar) (K1 …) kayıtlıdır. Reddedilenler nedenleriyle §15'tedir.
`G1` … `G13` V1 gereksinimlerine karşılık gelir.

Etiketler: **[Kabul]** kullanıcı onayladı · **[V1]** V1'in çekirdeğine öneriyorum · **[V1+]** V1 mimarisi
kurulduktan sonra · **[V2]** · **[Sonra]** ileride · **[Araştır]** önce doğrulanmalı · **[Karar]** kullanıcının
seçimi gerekli

## 0. Önce: zemin

- **Depo** [Kabul: K2] — Temiz git deposu `iplikci` hazır (GitHub uzak deposu var). Önerim: MVP kodu `iplikci` adıyla
  ilk sürüm olarak depoya alınır, yeniden yapılanma onun üzerinde adım adım ilerler. Banka belgeleri, çıktılar,
  ayarlar ve kişisel kurallar depoya hiç girmez; `.gitignore` ve commit öncesi gizli veri taraması (gitleaks) bunu
  korur.
- **Kural katmanları** [V1] — `kategoriler.yaml` ikiye ayrılır: uygulamayla gelen genel işyeri kuralları (depoda) ve
  kişisel kurallarla kararlar (kira, aile, `_biten`; veri klasöründe). Bugünkü dosya kişi adları (ev sahibi, aile)
  içerebildiği için depoya doğrudan giremez.
- **Doğrulama tabanı komutu** [V1] — MVP'nin CLAUDE.md'sindeki tabanı (belge sayısı, doğrulanan ekstre ve dökümler,
  okunamayanlar, ay kapanışları, son 12 ayın gideri) üreten ve bir öncekiyle farkını gösteren bir komut
  (`iplikci dogrula --taban`).
  Taban veri klasöründe saklanır (bugün CLAUDE.md'de duran tutar da oraya taşınabilir). Arşive taşıma, eski
  klasörlerin temizliği ve her yeniden yapılanma adımı bununla ölçülür.
- **MVP'nin arka plan görevi** [V1] — Saatlik görev MVP'nin çalışma klasörünü çalıştırıyor. Yeni kod `iplikci`'de
  yazılacağı için MVP klasörü geçiş boyunca donmuş kalmalı (yalnızca hata düzeltmesi); görev yeni sistem eşitliği
  sağlayınca kapatılır. Yeni servis de geliştirme klasörünü değil, kurulu sürümü çalıştırmalı.
- **Ad değişikliği listesi** [Kabul: K1] — paket ve komut `iplikci`; MCP sunucu adı `iplikci` (araç adları
  `mcp__iplikci__…`); anahtar zinciri hizmet adı `iplikci` (e-posta şifresi bir kez taşınır ya da yeniden girilir;
  taşınmazsa e-posta alımı durur); servis etiketi ve systemd / Görev Zamanlayıcı adları; `IPLIKCI_` önekli ortam
  değişkenleri; ayar anahtarları (eski `ayarlar.toml` bir kez okunup çevrilir).

## 1. Belge arşivi — `Bankalar/` yerine (G2)

- **İçerik adresli depo** [Kabul: K3] — Her belge bir kez, sha256'sı adıyla ve değiştirilmeden saklanır
  (`vault/objects/ab/cd/<sha256>`). Aynı belge yeniden gelirse yalnızca yeni kaynağı eklenir; "sha256'sı farklı
  dosyanın üzerine yazma" kuralı yapının kendisinden gelir.
- **Belge kaydı veritabanında** [Kabul: K3] — kaynak (e-posta: gönderen, tarih, konu, Message-ID; yükleme; içe
  aktarma), banka, belge türü, hesap, dönem, okuyucu ve sürümü, doğrulama sonucu, durum (işlendi / işlenmedi /
  okunamadı). Bugünkü okunaklı ad (`2026-09-22 Garanti Bonus 4321 Ekstre.pdf`) bir alan olur, indirirken kullanılır.
- **İşlenmeyen banka belgeleri** [Kabul: K11] — Sözleşme, poliçe ve tanınmayan ekler çöpe gitmez: aslı arşivde
  "işlenmedi" durumunda ve nedeniyle kalır. Arayüzde ve MCP'de bir bağlantıyla görünür; geldiği e-postaya da bağlantı
  verilir (Gmail'de `rfc822msgid:` aramasıyla). "Claude'a ver" yolu: bir MCP aracı belgeyi, okuyucusu yazılsın ya da
  düzeltilsin diye sunar. Kredi sözleşmesindeki vade ve faiz, poliçedeki yenileme tarihi gibi bilgiler ileride
  okunabilir. Şirket belgeleri yine hiç saklanmaz.
- **Klasörde gezinme** [V1+] — Finder'da gezmek isteyene arşivden `Banka/Hesap/` ağacını sabit bağlantılarla (hard
  link) kuran salt okunur bir görünüm. Asıl gezinme arayüzdeki belge sayfasında.
- **Türetilmiş veriler** [V1] — sayfa görüntüleri, çıkarılmış metin (arama), OCR sonucu, satır konumları: belgeden
  yeniden üretilebilir, ayrı bir önbellekte durur.
- **Silme yok, iz var** [V1] — Kaldırılan belge kayıtta "kaldırıldı" olur, dosyası çöp kutusuna gider (bugünkü kural);
  CSV kayıtlarının yerini veritabanındaki denetim kaydı alır (dışa aktarılabilir).
- **Bütünlük ve yedek** [V1] — Her nesnenin sha256'sını yeniden hesaplayan bir denetim; şifreli yedek ve geri yükleme
  provası; Time Machine'in veri klasörünü kapsaması.
- **Taşıma ve temizlik** [Kabul: K2] — Yeni sistem kurulunca `Bankalar/`, `Gelen Belgeler/` ve düzenleme kayıtları
  arşive alınır; doğrulama tabanı birebir tutunca eski klasörler temizlenir (çöp kutusuna; kalıcı silme yok) ve
  çalışma yalnızca depo üzerinden sürer.
- **Uygulama düzeyinde şifreleme** [Karar] — FileVault diski zaten şifreliyor. Veritabanını ve nesneleri ayrıca
  şifrelemek (anahtarı anahtar zincirinde) ek koruma getirir ama Quick Look'u, Spotlight'ı ve hata ayıklamayı
  zorlaştırır. Veri bu bilgisayardan çıkmadığı için (K5) önerim şimdilik FileVault + şifreli yedek.

## 2. Veri katmanı ve alan modeli (G6)

- **SQLite** [Kabul: K3] — Tek kullanıcı, yerel, sunucusuz. WAL kipinde servis, CLI ve MCP aynı anda okur; FTS5 ile
  işlem ve belge metninde tam metin arama (MVP'nin Python'ında SQLite 3.53 ve FTS5 var). Şema göçleri sürümlü.
  Postgres gereksiz.
- **Dört katman veri** [V1] — (1) belgeler: asıl kaynak; (2) okunan satırlar: belgelerden türer, yeniden üretilir;
  (3) kullanıcı kararları (kurallar, düzeltmeler, notlar, etiketler, "bitti" işaretleri): birincil veri, asla
  kaybolmaz; (4) analiz ve yorum: 1–3'ten her seferinde hesaplanır. Bu ölçekte bir saniyenin altında sürer;
  artımlı olması gereken yalnızca belge okuma.
- **Kalıcı işlem kimliği** [V1] — Okuyucu güncellenip belge yeniden okununca kullanıcının işleme eklediği not ya da
  düzeltme kaybolmamalı. Kimlik: belge sha256 + satır konumu; yeniden okumada (hesap, tarih, tutar, sadeleştirilmiş
  açıklama, aynı satırlar arasındaki sıra) ile eşleşme. Aynı gün aynı tutarlı satırların hepsi gerçek olduğundan
  sıra numarası şart.
- **Para tipi** [V1] — `float` yerine `Decimal` (ya da kuruş cinsinden tamsayı) ve para birimini taşıyan bir `Money`;
  kur çevirisi ayrı bir adım, kaynağı belli (belge kuru / TCMB / ECB, tarihiyle).
- **İngilizce alan kodları** [V1] — `harcama`, `kisiye_transfer` gibi değerler İngilizce kodlara (`purchase`,
  `p2p_transfer`, …) dönüşür; arayüz etiketleri Türkçe kalır. İleride İngilizce arayüze kapı açar. Eşleme tablosu:
  [domain/ledger.md](domain/ledger.md).
- **Katmanlar** [V1] — `domain` (saf: modeller, transfer çözümü, dekont eşleştirme, yorum kuralları; G/Ç yok) ·
  `ingestion` (e-posta, yükleme, izlenen klasör) · `vault` · `parsers` (eklentiler) · `ledger` (birleştirme,
  eşleştirme, transferler, kur) · `insights` · `notify` (kurallar, kanallar) · `api` / `mcp` / `cli` (sunum). Büyük
  modüller bölünür; her bulgu yazarı ayrı bir birim olur.
- **Olaylar ve iş kuyruğu** [V1] — `DocumentReceived → DocumentParsed → LedgerUpdated → InsightsRecomputed →
  Notified`: her adım kayıtlı, yeniden denenebilir, hatası görünür. SQLite üzerinde basit bir kuyruk yeter. Aynı olay
  kaydı anlık akışı (§16) ve bildirimleri (§18) besler.

## 3. Servis ve PWA (G4)

- **Tek servis süreci** [Kabul: K5] — launchd (`KeepAlive`, `RunAtLoad`) / systemd kullanıcı servisi / Windows hizmeti
  olarak sürekli çalışan bir süreç: HTTP API + arayüz + zamanlayıcı (e-posta, kur, ay sonu, hatırlatmalar) + gelen
  klasörü izleyicisi + MCP (HTTP) + bildirim gönderici. Bugünkü tek seferlik görevin ve elle açılan panelin yerini
  alır; "panel eski kodla çalışıyor" sorunu, güncellemede servisin yeniden başlatılmasıyla biter.
- **Önce API** [V1] — Arayüz, MCP ve CLI aynı uygulama servislerini kullanır. FastAPI + pydantic (sınırda doğrulama)
  doğal seçim; OpenAPI şemasından arayüz için tip güvenli istemci üretilir.
- **CLI istemci** [V1] — Servis çalışıyorsa API'yi, çalışmıyorsa (kilitle) veri klasörünü doğrudan kullanır.
- **PWA** [Kabul: K5] — manifest + service worker (uygulama kabuğu önbelleği); masaüstüne uygulama olarak kurulur.
  Tarayıcılar `127.0.0.1`'i güvenli bağlam saydığından bu bilgisayarda HTTPS gerekmez.
- **Uzaktan erişim** [Kabul: K5] — Şimdilik PWA yalnızca bu bilgisayarda; uzaktayken bilgi bildirimlerle gelir.
  Gerektiğinde Tailscale: `tailscale serve` ile yalnızca kendi cihazlarınıza geçerli sertifikalı HTTPS, internete
  açık port yok; üstüne cihaz başına oturum (passkey). Servis internete doğrudan açılmaz.
- **Bildirim kanalları** [Kabul: K10] — e-posta ve Telegram (§18); macOS bildirimi bugün de var. Telefonda PWA
  kullanılmadığı için Web Push ve ntfy şimdilik gerekmiyor.
- **Sağlık ve gözlemlenebilirlik** [V1] — `/healthz`, yapılandırılmış (JSON) günlük, iş geçmişi, son başarılı e-posta
  alımı, hata sayaçları; arayüzde bir "Sistem" sayfası.
- **Menü çubuğu simgesi** [Sonra] — servis durumu, son e-posta kontrolü, bekleyen işler; tek tıkla arayüz.

## 4. Okuyucu (parser) eklentileri (G5)

- **Tek sözleşme** [Kabul: K6] — Her okuyucu `id` (`garanti.bonus_card`), banka, belge türü, sürüm, biçimler,
  `detect(probe) → eşleşme + güven + neden` ve `parse(doc) → ParseResult` sunar. Sıralı `if` zinciri ve `hesaplar.py`
  dalları bir kayıt defterine (registry) dönüşür; iki okuyucu aynı belgeyi isterse bu hata olarak raporlanır, sıraya
  bağlı sessiz seçim olmaz.
- **Okuyucu başına sürüm** [Kabul: K6] — Önbellek anahtarı (sha256, okuyucu, sürüm): bir bankanın okuyucusu değişince
  yalnızca onun belgeleri yeniden okunur. Arşiv bütün banka eklerini (işlenmeyenler dahil, K11) sakladığı için yeni
  bir okuyucu eski eklere posta kutusunu baştan okumadan uygulanır.
- **Biçim değişikliği alarmı** [Kabul: K6] — Okuyucu belgeyi tanıyıp doğrulamadan geçiremezse "banka biçimini
  değiştirmiş olabilir" uyarısı (bir bildirim kuralı olarak da, §18); okuyucu başına sağlık (doğrulanan / toplam,
  son başarı).
- **Sahte belge üreticisi** [Kabul: K6] — Her okuyucu için gerçekçi sahte belge (PDF, XLS, HTML, e-posta) üreten araç:
  testler, arayüz geliştirme, ekran görüntüleri ve demo için. Gerçek veri depoya girmez.
- **Geliştirme araçları** [V1] — `parser probe <dosya>` (hangi okuyucu tanıyor, neden), `parser debug <dosya>` (sayfa
  satırları ve x konumları), `parser test <okuyucu>` (sahte örnekler + yerel gerçek belgelerle doğrulama).
- **Ayrı paket olarak eklenebilme** [V1+] — Okuyucular Python entry point'leriyle ayrı bir paketten de yüklenir.
- **Yalıtılmış okuma** [V1] — Okuma ayrı bir alt süreçte, zaman ve bellek sınırıyla çalışır: bozuk ya da kötü niyetli
  bir PDF servisi kilitleyemez.

## 5. E-postadan otomatik toplama (G1)

- **E-posta gövdesi okuyucuları** [Kabul: G1] — Revizyonun çıkış noktası. Bankaların gövdede gönderdikleri: kart
  harcama bildirimi, gelen/giden FAST-EFT bildirimi, otomatik ödeme sonucu, fatura ödendi bildirimi, kredi taksidi
  hatırlatması, "ekstreniz hazır / son ödeme tarihi / asgari tutar". Yeni belge türü "bildirim"; e-postanın kendisi
  arşivde `.eml` olarak saklanır, okuyucuları aynı eklenti sözleşmesiyle yazılır.
- **Bildirimden geçici kayıt** [V1 · G10] — Kart harcama bildirimi dekont gibi geçici işlenir, ekstre gelince eşleşir
  (bugünkü dekont mekanizması); ekstrede yoksa "ekstrede görünmeyen" olur. Ay içi harcama ekstre beklemeden görünür.
- **Son ödeme tarihleri ve hatırlatmalar** [Kabul: K7] — Kart ekstrelerinden son ödeme tarihi ve asgari / toplam borç
  okunur (bugün okunmuyor); hatırlatma e-postalarıyla birlikte "Yaklaşan ödemeler" takvimi ve bildirimi ("Garanti
  kartının son ödemesi 3 gün sonra").
- **Anlık alım** [Kabul: K5] — 15 dakikalık yoklama yerine IMAP IDLE (Gmail destekliyor): e-posta gelir gelmez işlenir.
- **Banka dışı göndericiler** [Kabul: K12] — ayrıntılar §19.
- **Elle yükleme** [V1 · G1] — Elle yüklenen her belge e-postayla gelenle aynı hattan geçer ve aynı biçimde analize
  girer (panel, klasöre bırakma, MCP ile içe aktarma).
- **Birden çok posta kutusu** [V1+] — ikinci bir Gmail, iCloud ya da Outlook IMAP.
- **Gmail API (OAuth)** [Araştır] — Uygulama şifresi yerine dar kapsamlı, salt okunur yetki. Google'ın OAuth uygulama
  doğrulaması ve belirteç süresi koşulları kişisel kullanımda zahmetli olabilir; şimdilik IMAP + uygulama şifresi
  yeterli.
- **E-postayla gelmeyen dökümler** [V1] — "Elle yükleme olmasın" hedefine en yakın yollar: (a) bankanın izin verdiği
  yerde dökümlerin e-postayla gönderimini açmak (banka başına kontrol listesi), (b) bildirim ve dekontlarla hareketleri
  ekstre gelene kadar geçici tutmak, (c) İndirilenler klasörünü izleyip indirilen banka dökümlerini kendiliğinden
  almak, (d) "döküm 35 gündür yok" hatırlatması + bankanın sayfasını açan bağlantı.
- **SMS** [Sonra, Araştır] — Bankaların işlem SMS'leri iPhone Kısayollar otomasyonuyla servise iletilebilir; telefonun
  servise Tailscale üzerinden ulaşmasını gerektirir.
- **Açık bankacılık** [Sonra, Araştır] — Türkiye'de hesap bilgisi hizmeti lisanslı kuruluşlar üzerinden veriliyor;
  kişisel bir araç için doğrudan erişim bugün gerçekçi değil.

## 6. İşlemden belgeye iz (G2)

- **Her satırın kaynağı** [Kabul: K4] — işlem → belge kimliği + sayfa + satırın kutusu (pdfplumber'ın kelime
  konumlarından) ya da tablo satır numarası → belgenin geldiği e-posta (gönderen, tarih, konu) → onu alan iş. Bugün
  yalnızca dosya adı var.
- **Belge görüntüleyici** [Kabul: K4] — İşleme tıklayınca yan panelde PDF sayfası, sunucuda resme çevrilmiş
  (pypdfium2 zaten bağımlılık) ve satırı vurgulanmış; XLS/HTML dökümlerde satır tabloda vurgulu; e-postalar betiksiz
  ve uzak içeriksiz güvenli bir görünümde. Ham PDF ve HTML uygulamanın kendi kökeninde (origin) açılmaz.
- **"Neden?" açıklaması** [Kabul: K4] — hangi kural bu kategoriyi verdi, neden kendi transferi sayıldı (karşı satır
  hangisi), hangi dekontla ya da e-postayla eşleşti, hangi kurla çevrildi; kuralı düzenlemeye tek tık.
- **Akış izi** [V1] — maaş → hesap → kart ödemesi → harcamalar; bir transferin iki ucu (iki belge) yan yana; ay için
  Sankey: gelir kaynakları → hesaplar → gider grupları, birikim, kişiler.
- **Zaman çizelgeleri** [V1] — hesap başına (belgeler, kesimler, boşluklar, bakiye), abonelik başına (her çekim ve
  belgesi), belge başına (nereden geldi, ne çıktı).

## 7. Arayüz (G7)

- **Teknoloji** [V1] — React + TypeScript + Vite + Tailwind (genel kurallarınızla uyumlu); grafik kütüphanesi pakete
  gömülü (CDN yok); sıkı CSP korunur. Bugünkü grafik kuralları (sabit renk yuvaları, her grafiğe tablo görünümü, ayrı
  açık/koyu paletler, durum renginin yanında ikon ve etiket) taşınır.
- **Ekranlar** [V1]:
  - *Akış*: gelen her finansal olay anlık, durumu ve belgesiyle (§16).
  - *Pano*: net varlık, bu ay ve tipik ay, yaklaşan ödemeler, uyarılar, ay kapanışı, veri tazeliği.
  - *Hesaplar*: türe göre gruplu hesap haritası, birleşik akış ve türe özel sayfalar (§17).
  - *İşlemler*: tam metin arama, kayıtlı filtreler, toplu kategori değiştirme, bölme, not, etiket.
  - *Abonelikler ve düzenli ödemeler*: durum, sonraki çekim, fiyat değişimi, iptal akışı.
  - *Takvim*: yaklaşan ödemeler, kesim ve son ödeme tarihleri, maaş günleri, vade sonları.
  - *Bütçe ve tahmin*, *Değerlendirme ve strateji*, *Ay sonu*.
  - *Döviz ve varlıklar*.
  - *Belgeler*: arşiv gezgini, arama, görüntüleyici, işlenmeyenler ve okunamayanlar.
  - *Bildirimler*: kurallar ve gönderilenlerin geçmişi (§18).
  - *Kurallar*: canlı önizlemeli kategori kuralı düzenleyici ("bu kural 14 işlemi etkiler").
  - *Yapılacaklar*: kategorisiz işlemler, eşleşmeyen dekontlar ve e-postalar, doğrulanmayan ekstreler, eksik belgeler;
    tek tıkla çözüm.
  - *Sistem*: servis sağlığı, iş geçmişi, okuyucu sağlığı, yedek durumu.
- **Tek dosyalık rapor** [Karar] — Bugünkü kendi kendine yeten HTML rapor bir "dışa aktar" seçeneği olarak kalabilir
  (arşivlemek, paylaşmak için).
- **Takvim aboneliği (.ics)** [V1+] — Yaklaşan ödemelere Apple Takvim'den abone olmak: bildirimlere ek olarak
  hatırlatma takvimde de görünür.
- **Düz metin muhasebe dışa aktarımı** [Sonra] — hledger / beancount biçimi: verinin uygulamadan bağımsız bir kopyası.

## 8. Abonelikler, düzenli ve dönemsel ödemeler (G7, G10)

- **Yıllık ve dönemsel ödemeler** [V1] — Bugün yalnızca aylık seriler (15–50 gün arayla) tanınıyor; yıllık abonelikler,
  kasko ve sigorta yenilemesi, yılda iki taksitli MTV ve emlak vergisi, alan adı ve yazılım yenilemeleri kaçıyor.
  ~365 ve ~182 günlük dönem tespiti + "Mart'ta kasko yenilemesi var; geçen yıl X TL" uyarısı. E-postayla gelen
  fatura ve yenileme bildirimleri (§19) tespiti güçlendirir.
- **Sonraki çekim** [V1] — Her abonelik için beklenen tarih ve tutar → takvim ve tahmin.
- **Dövizli abonelikler** [V1] — USD/EUR fiyatlı aboneliklerde TL artışının kurdan mı fiyattan mı geldiğini ayırmak.
- **Deneme ve yenileme e-postaları** [V1+] — "deneme süreniz bitiyor", "aboneliğiniz yenilenecek" e-postalarından
  önceden uyarı.
- **İptal akışı** [V1] — "İptal ettim" düğmesi → `_biten` (bugünkü mekanizma) → sonrasında ödeme görünürse uyarı.
- **Çift ve unutulmuş abonelikler** [V1+] — aynı hizmete iki ödeme; aylık abonelik toplamı ve dağılımı.

## 9. Döviz, altın ve enflasyon (G8)

- **Kur sağlayıcıları** [Kabul: K8] — Ortak bir `RateProvider` arayüzü: TCMB günlük kurları (resmî, ücretsiz,
  anahtarsız XML; iş günleri öğleden sonra yayımlanır), ECB / Frankfurter (EUR bazlı, ücretsiz, TRY dahil) ve
  belgedeki kur (bankanın o işlemde uyguladığı gerçek kur; işlemin kendisi için öncelikli). Kurlar tarihçeli saklanır;
  hafta sonu ve tatilde önceki iş gününün kuru.
- **Ağ kuralı** [Kabul: K8] — Yalnızca listedeki kur adresleri, yalnızca GET, istekte kişisel veri yok (yalnızca
  tarih), TLS doğrulamalı; ağ yoksa belge kurlarıyla devam. Yeni deponun CLAUDE.md'sine ve bir ADR'ye yazılır.
- **Kur makası maliyeti** [Kabul: K8] — Döviz bozdurma ve alımlarında bankanın uyguladığı kurla o günün TCMB kuru
  arasındaki fark → "son 12 ayda kur makasına ödenen". Veriyle fiyatlanan, somut bir tasarruf adımı.
- **Çoklu para birimiyle görünüm** [Kabul: K8] — Net varlık TL, EUR, USD ve gram altın cinsinden; varlıkların döviz
  dağılımı.
- **Enflasyondan arındırma** [Kabul: K8, V1+] — Yüksek enflasyonda "harcamam mı arttı, fiyatlar mı?" sorusu için TÜFE
  ile reel seriler. Kaynak karar ister (§22).
- **Döviz geliri** [V1] — Döviz cinsinden gelirin TL karşılığı, bozdurma zamanları ve kurun bütçeye etkisi ("EUR/TRY
  %5 düşerse aylık bütçe şu kadar azalır").
- **Altın ve hisse fiyatı** [Araştır] — TCMB'nin günlük listesi döviz kurlarını verir; altın ve BIST fiyatı için
  ücretsiz ve güvenilir kaynak ayrıca doğrulanmalı. O zamana dek bugünkü yaklaşım: altın gram + maliyetle, hisse
  ekstrenin yazdığı değerle.

## 10. Yorum ve strateji

- **Nakit akışı takvimi** [Kabul: K7] — Hesap başına gün gün beklenen bakiye (maaş günü, otomatik ödemeler, kart son
  ödemeleri, taksitler) → "ayın 25'inde vadesiz hesap eksiye düşebilir, KMH faizi işler" uyarısı.
- **Borç görünümü** [V1] — kredi taksitleri, kalan taksitli alışverişler, KMH; toplam borç, bitiş takvimi, ödenen faiz.
- **Olağan dışı hareketler** [V1] — işyerinin alışılmış tutarından çok farklı çekim, aynı gün aynı tutarda olası çift
  çekim (yalnızca işaret; satırlar silinmez), yeni bir yerde büyük tutar, beklenmedik banka ücreti (aidat iadesi
  talebi adımı).
- **Kişiler arası borç-alacak** [V1+] — Kişilere giden ve kişilerden gelen para kişi başına net; "borç iadesi mi,
  destek mi" gibi sınıflama sorularını görünür kılar.
- **Nakit cüzdanı** [V1+] — ATM çekimleri nakit cüzdanına girer; hızlı nakit harcama girişi, girilmeyen kısım
  "dağılımı bilinmeyen nakit" olarak kalır. Kâğıt fiş fotoğrafının metin tanımayla okunması [Sonra].
- **Bütçe ve hedefler** [V1+] — kategori bütçeleri ve aşım uyarısı (§18); birikim hedefleri (ör. taşınma masrafı).
- **Senaryolar** [V1+, V2'nin temeli] — "kira biterse", "gelir dövize geçerse", "kur %10 oynarsa": aylık bütçeye ve
  birikime etkisi; deterministik hesap.
- **Özetler** [V1+] — haftalık / aylık "ne değişti" bildirimi; yıl sonu özeti.
- **Kural önerileri** [V1+] — Elle yapılan kategori düzeltmelerinden açıklanabilir kural önerisi (kara kutu değil).

## 11. MCP (G9)

- **Resmî MCP Python SDK'sı** [Kabul: K9] — Elle yazılmış JSON-RPC yerine: protokol sürümü anlaşması, yapılandırılmış
  çıktı (output schema), sayfalama, ilerleme bildirimi, iptal.
- **İki taşıma** [V1] — stdio (Claude Code, Claude Desktop) + servisin sunduğu Streamable HTTP (yerel, belirteçli). Her
  oturumun belgeleri kendi sürecinde yeniden yüklemesi biter; MCP servisin güncel verisini görür.
- **Kaynaklar (resources)** [Kabul: K9] — Belgeler (metin + sayfa görüntüsü), ay sonu sayfaları, hesap özetleri: model
  belgeyi görebilir ve ona atıf yapabilir.
- **Hazır istemler (prompts)** [Kabul: K9] — "Aylık değerlendirme", "Abonelik denetimi", "Bu ay neden fazla
  harcadım?", "Ay kapanışı".
- **Araçlar** [Kabul: K9] — Mevcut 16 araç korunur; eklenecekler: `search` (tam metin), `explain_transaction` (belge,
  kural, eşleşme), `get_document`, `unprocessed_documents` (K11), `feed` (anlık akış), `accounts_overview` (hesap
  türleri), `upcoming_payments`, `subscriptions`, `fx_rates`, `net_worth`, `cash_flow_forecast`, `alerts` (bildirim
  kuralları), `annotate_transaction`, `budgets`. Salt okunur ve yazan araçlar ek açıklamalarla ayrılır
  (`readOnlyHint`, `destructiveHint`); yazanlar bugünkü gibi plan → onay → uygula akışıyla.
- **Sağlamlık** [V1] — Her aracın şeması için sözleşme testleri, MCP Inspector ile otomatik deneme, çıktılarda boyut
  sınırı (önce özet, istenince ayrıntı), araç çağrılarının denetim kaydı.
- **Gizlilik düzeyi** [V1+] — Araç sonuçları modele gider: IBAN, hesap numarası ve kişi adlarını maskeleme seçeneği.
- **Prompt injection** [V1] — Belge ve e-posta metni veri olarak, ayrı alanlarda döner; hiçbir araç çıktısı
  kendiliğinden bir yazma aracını tetiklemez (bugünkü ilke).

## 12. Güvenlik ve gizlilik

- **Tehdit modeli** [V1] — Varlıklar (belgeler, veritabanı, e-posta şifresi, bot belirteci), tehditler (kötü niyetli
  belge ve e-posta, bu bilgisayardaki başka bir kullanıcı ya da uygulama, DNS rebinding ve CSRF, Tailscale üzerinden
  erişim, dışarı giden bildirimler, modele giden veri ve prompt injection) ve önlemler tek belgede. Bugünkü panel
  önlemleri (tek kullanımlık anahtar → HttpOnly çerez, Host ve Origin denetimi, özel başlık) yeni API'ye taşınır.
- **Sırlar** [V1] — Yalnızca anahtar zinciri: e-posta uygulama şifresi (bugünkü gibi), Telegram bot belirteci,
  gerekirse kur servisi anahtarı.
- **Dışarı giden veri** [V1] — Kur isteklerinde kişisel veri yok; bildirimlerde kanal başına seçilen ayrıntı (§18).
- **Bağımlılık hijyeni** [V1] — Doğrudan bağımlılıklar sabitlenir (bugün `>=`), kilit dosyası korunur; güvenlik açığı
  taraması (pip-audit / OSV) ve lisans denetimi.
- **Yedek** [V1] — Şifreli yedek ve düzenli geri yükleme provası.

## 13. Mühendislik süreci (G6)

- **ADR'ler** [V1] — `docs/adr/` altında büyük kararlar: veritabanı, belge arşivi, ağ istisnaları, ön yüz, servis
  modeli, uzaktan erişim, bildirim kanalları.
- **Araçlar** [V1] — ruff (proje kuralı: 120 karakter), pyright (yeni kod sıkı), pytest + kapsama, Vitest + Testing
  Library, Playwright ile uçtan uca testler (sahte belgelerle kurulmuş bir çalışma alanında; bugün elle yapılan
  headless Chrome kontrolleri otomatikleşir).
- **CI** [Karar] — Depo GitHub'da (K2). Önerim: GitHub Actions'ta testler, tip denetimi, lint ve gizli veri taraması;
  yalnızca sahte verilerle. Depo açık mı, özel mi? (§22)
- **Sürümleme** [V1] — SemVer + CHANGELOG; servis yalnızca etiketli sürümü çalıştırır.
- **Performans hedefleri** [V1] — Yeni belgenin gelişinden arayüzün güncellenmesine < 5 sn; API yanıtı p95 < 200 ms;
  tam yeniden okuma bugünkü ~10 sn'yi aşmaz.

## 14. Ad (G3)

- **İplikçi** [Kabul: K1] — depo, paket ve komut `iplikci`; İngilizce alternatif ad **Money-Grubber**. Ad, bir filmde
  paraları tutan karakterden gelir. Değerlendirilen adaylar (Moneytrail, Paperledger, Ledgerlens, Fiscus) seçilmedi.

## 15. Önermediklerim

- **İnternet şubesine otomatik giriş, ekran kazıma** — banka şifresini ve iki adımlı doğrulamayı saklamayı gerektirir;
  kırılgandır ve banka sözleşmelerine aykırı olabilir.
- **Banka şifresi ya da oturum bilgisi saklamak** — hiçbir koşulda.
- **Servisi internete doğrudan açmak** (port yönlendirme) — Tailscale varken gereksiz risk.
- **Ham belgeleri bulut eşitleme klasörüne koymak** (iCloud Drive, Dropbox) — arşiv yerel kalır; yedek şifreli gider.
- **Kategorilemeyi kara kutu bir modele bırakmak** — kurallar açıklanabilir ve düzeltilebilir; model yalnızca öneri
  üretebilir.
- **Mikroservis, Postgres, Kafka, Kubernetes** — tek kullanıcılı yerel bir uygulama için gereksiz karmaşıklık; tek
  süreç + SQLite yeterli.
- **Her şeyi baştan yazmak** — gerçek belgelerin tamamını doğrulayan okuyucular en değerli birikim. Yeni sözleşmeye
  sarılarak taşınmalılar; yeni yapı eskisinin yanında büyüyüp yerini almalı (strangler, ADR-0013).

## 16. Anlık finansal akış (G10)

- **Akış ekranı** [V1] — Gelen her şey zaman sırasıyla tek akışta: banka bildirimi, dekont, ekstre, döküm, banka dışı
  e-posta, elle yükleme. Her olayın durumu (geçici / kesinleşti / ekstrede yok / yalnızca bilgi) ve belgesine bağlantı.
  Servis yeni olayları arayüze anında iletir (Server-Sent Events); sayfayı yenilemek gerekmez.
- **Şu anki durum** [V1] — Hesap başına tahmini güncel bakiye: son belgenin bakiyesi + sonrasında gelen geçici olaylar
  (bugünkü dekont mantığının genişlemesi). Kart başına dönem içi harcama ve bir sonraki ekstreye tahmini borç.
- **Ay içi tempo** [V1] — "Ayın %60'ı geçti; harcama tipik ayın %75'inde" gibi bir gösterge; tipik ay yalnızca tam
  aylardan hesaplanır.
- **Güven düzeyi her rakamda** [V1] — Kesin (ekstre, döküm), geçici (bildirim, dekont), bilgi (eşleşmeyen banka dışı
  e-posta) her toplamın ve satırın yanında görünür. Ekstre gelince geçici satırlar kendiliğinden kesinleşir; akışta
  "kesinleşti" olarak işaretlenir.
- **Beklenen olaylar** [V1] — Akışın ileriye bakan kısmı: yaklaşan son ödemeler, beklenen düzenli ve dönemsel ödemeler
  (§8), beklenen maaş, vade sonları. Beklenen gelmezse bildirim kuralı tetiklenir (§18).

## 17. Hesap türleri: toplu ve ayrı görünüm (G11)

- **Hesap haritası** [V1] — Bütün hesaplar türe göre gruplu: kredi kartları, vadesiz, vadeli, KMH, döviz, altın,
  yatırım, krediler. Grup toplamı (varlık / borç), hesap kartı (bakiye, son belge, tazelik, bu ayın girişi ve
  çıkışı). Birden çok hesap seçilince birleşik akış; bir hesaba tıklayınca o hesabın sayfası. Banka, tür ve para
  birimine göre süzme.
- **Türe özel sayfalar** [V1]:
  - *Kredi kartı*: dönem borcu, son ödeme tarihi, asgari tutar, limit (ekstrede yazıyorsa), gelecek aylara yayılan
    taksit takvimi, faiz ve ücretler, ödeme geçmişi (tam / asgari / kısmi).
  - *Vadesiz*: günlük bakiye eğrisi (döküm bakiyelerinden), gelen ve giden, otomatik ödemeler, maaş.
  - *Vadeli*: anapara, faiz oranı, vade sonu (hatırlatma), net getiri.
  - *KMH*: limit, kullanılan tutar, eksi gün sayısı, faiz maliyeti, çıkış planı.
  - *Döviz ve altın*: miktar, güncel TL karşılığı, maliyet ve kur farkı.
  - *Yatırım*: portföy, nakit, temettü, komisyon, getiri.
  - *Kredi*: kalan anapara, taksit planı, ödenen faiz.
- **Hesaplar arası akış** [V1] — Kendi hesaplarınız arasındaki transferler bir akış haritasında: hangi hesaptan
  hangisine, ne kadar, ne zaman.
- **Hemen kullanılabilir para** [V1+] — Vadesiz ve nakit ile bağlı para (vadeli, yatırım) ayrı; yaklaşan ödemeler
  karşısında ne kadar boşluk olduğu.

## 18. Tetikleyiciler ve bildirimler (G12)

- **Kural: olay + koşul + kanal** [V1] — Olaylar: yeni işlem, yeni belge, son ödemeye N gün, bakiye eşiğin altında ya
  da hesap eksiye düşecek, büyük harcama, yeni işyeri, abonelik zammı, iptalden sonra ödeme, beklenen ödeme ya da maaş
  gelmedi, ay kapandı, kontrol gerekli, işlenmeyen ya da okunamayan belge, okuyucu biçim alarmı, kur eşiği (ör.
  EUR/TRY), bütçe %80 / %100, vade sonu yaklaşıyor. Koşullar: hesap, kategori, tutar, işyeri, saat aralığı.
- **Kanallar** [Kabul: K10] — e-posta ve Telegram; ayrıca macOS bildirimi ve uygulama içi bildirim kutusu.
- **Hazır kurallar** [V1] — Finanstan anlamayan kullanıcı hiçbir şey kurmadan fayda görsün: "son ödemeye 3 gün",
  "hesap eksiye düşecek", "büyük harcama", "abonelik zammı", "ay kapandı" varsayılan açık; her biri tek tıkla kapanır.
- **Gürültü denetimi** [V1] — Her haber bir kez (bugünkü ay sonu bildirimlerindeki gibi), sessiz saatler, anında ya da
  günlük / haftalık özet seçimi, kanal başına sıklık sınırı.
- **Kural tanımı** [V1] — Arayüzde form; dosyada (YAML, kategori kuralları gibi); MCP aracıyla ("son ödemeye 2 gün kala
  Telegram'a yaz").
- **E-posta kanalı** [V1] — Kullanıcının kendi adresine bildirim e-postası (SMTP, TLS). Okuma tarafı değişmez: posta
  kutusu yine salt okunur açılır.
- **Telegram kanalı** [V1] — Kullanıcının kendi botu; bot belirteci anahtar zincirinde; sohbet bir eşleştirme koduyla
  bağlanır. Telegram'a uzun yoklamayla (long polling) bağlanılır: gelen bağlantı gerekmez, servis internete
  açılmaz. İleride düğmeler ("İptal ettim", "Kategori doğru") ve V2'de asistana Telegram'dan soru.
- **İçerik ayrıntısı** [V1] — Bildirim e-posta ya da Telegram sunucularından geçer; Telegram bot iletileri uçtan uca
  şifreli değildir. Kanal başına ayrıntı düzeyi: tutar ve işyeri / yalnızca başlık / yalnızca "yeni bildirim var".
- **Bildirim geçmişi** [V1] — Gönderilen her bildirim uygulamada, ilgili işlem ve belgeye bağlantıyla.

## 19. Banka dışı e-postalar (G13)

Karar (K12): esas banka akışlarıdır; banka dışı e-postalar kanıt ve bilgi katmanıdır.

- **Göndericiler** [V1] — e-faturalar (elektrik, doğalgaz, su, telefon, internet), abonelik makbuzları (App Store,
  Google Play, Netflix, Spotify, YouTube…), e-ticaret siparişleri, e-Arşiv faturaları, sigorta, BES, vergi ve SGK
  bildirimleri. Güven kuralı bankalarla aynı: gönderici alan adı listesi + DMARC.
- **Eşleştirme** [Kabul: K12] — E-postadan tutar, tarih, para birimi, satıcı ve son ödeme tarihi okunur; banka satırıyla
  (kart harcaması, otomatik ödeme, havale) birkaç günlük bir pencerede eşleşir. Durumlar: *eşleşti* (banka satırı
  faturayla ve kalemlerle zenginleşir), *bekliyor* (son ödeme ileride: yaklaşan ödeme olur), *eşleşmedi* (yalnızca
  bilgi, toplamlara girmez).
- **Eşleşmeyenin anlamı** [Kabul: K12] — Ödemeyi başkası yapmış (ör. aileden biri faturayı ödemiş), belgesi olmayan
  bir hesaptan ya da nakit ödenmiş ya da henüz ödenmemiş olabilir; ekran bu olasılıkları söyler, rakam uydurmaz.
- **Yapısal veri** [V1] — e-Arşiv / e-Fatura e-postasında UBL-TR XML eki varsa tutar, tarih, satıcı ve kalemler
  güvenilir okunur; yoksa PDF ya da gövde okuyucusu.
- **Zenginleştirme** [V1] — "APPLE.COM/BILL" gibi bir kart satırı makbuzla eşleşince hangi abonelik olduğu görünür;
  sipariş kalemleri kategoriyi iyileştirir (bir e-ticaret siparişi giyim mi, elektronik mi).

## 20. Herkes için kullanılabilirlik (ürün ilkeleri)

- **İki düzey** [V1] — "Sade" görünüm: sade dil, ne olduğu ve ne yapılacağı ("Bu ay 3 abonelik zamlandı: aylık 180 TL
  fazla. İncele"). "Ayrıntılı" görünüm: tablolar, belgeler, kurallar, ham veri.
- **Terimler sözlüğü** [V1] — KMH, asgari ödeme, kesim tarihi, kur makası, reel / nominal gibi her terimin üzerine
  gelince kısa açıklama.
- **Kurulum sihirbazı** [V1] — İlk açılışta: e-posta hesabını bağlama, bankaları seçme, ad-soyad (kendi transferlerini
  tanımak için), eski belgeleri içe aktarma, bildirim kanalları. Başka bir kullanıcı da kendi bankalarıyla aynı verimi
  almalı.
- **Hazır varsayılanlar** [V1] — Türkiye'deki yaygın işyerleri için hazır kategori kuralları, hazır bildirim kuralları;
  kişisel kurallar ayrı katmanda.
- **Kurumsal değil** [ilke] — Tek kullanıcı (ileride hane), yerel kurulum, tek komutla başlatma; çok kiracılı yapı,
  SSO, yönetim paneli gibi kurumsal özellikler yok.
- **Erişilebilirlik ve dil** [V1] — Klavyeyle kullanım, yeterli kontrast, açık / koyu tema; arayüz Türkçe, kod
  İngilizce (ileride İngilizce arayüz).

## 21. Taslak yol haritası

Güncel ve ayrıntılı yol haritası [v1/roadmap.md](v1/roadmap.md)'dedir. Aşağıdaki taslak tarihçe olarak kalır.

Her aşamanın sonunda testler geçer, doğrulama tabanı aynı çıkar ve MVP'nin hiçbir özelliği kaybolmaz (MVP README'sindeki
özelliklerden çıkarılan bir eşitlik listesiyle). Arayüz iskeleti servisle birlikte başlar; her aşama kendi ekranını
o aşamada ekler.

| Aşama | İçerik |
|---|---|
| 0 — Zemin | README (yapıldı); MVP kodunun `iplikci` adıyla ilk sürüm olarak alınması; yeni CLAUDE.md (K1–K13 kurallarıyla); `.gitignore` ve gizli veri taraması; kural katmanları; `verify` komutu |
| 1 — Veri çekirdeği | veri klasörü, belge arşivi, SQLite şeması, kalıcı kimlikler, satır düzeyinde iz; `Bankalar/` ve `Gelen Belgeler/`'den taşıma |
| 2 — Okuyucu eklentileri | sözleşme ve kayıt defteri, okuyucu başına sürüm, mevcut okuyucuların sarılması, biçim alarmı, sahte belge üreticisi, geliştirme araçları |
| 3 — Servis | API, zamanlayıcı, IMAP IDLE, iş kuyruğu ve olay kaydı, arayüze anlık iletim, CLI istemci, launchd / systemd servisi |
| 4 — E-postanın tamamı | banka bildirimleri ve hatırlatmaları, son ödeme tarihleri, banka dışı e-postalar ve eşleştirme |
| 5 — Bildirimler | kural motoru, hazır kurallar, e-posta ve Telegram kanalları |
| 6 — Arayüz (PWA) | akış, pano, hesap haritası ve türe özel sayfalar, işlemler, belge görüntüleyici, takvim; MVP raporu eşitliğe dek yanında |
| 7 — MCP | SDK, HTTP taşıma, resources ve prompts, yeni araçlar |
| 8 — Döviz | kur sağlayıcıları, kur makası, çoklu para birimi; ardından enflasyon |
| Geçiş | doğrulama tabanı birebir tutunca MVP'nin görevi kapatılır, eski klasörler temizlenir (K2) |

Aşama 5, 7 ve 8 büyük ölçüde bağımsız; öne alınabilirler.

## 22. Karar bekleyen sorular

Yanıtlananlar (2026-10-31; ayrıntı: [kararlar](v1/requirements.md#kararlar)):

- Ad → İplikçi (`iplikci`), İngilizce alternatif Money-Grubber (K1).
- Kod deposu → `iplikci`, GitHub uzak deposuyla (K2).
- PWA → şimdilik yalnızca bu bilgisayarda; gerektiğinde Tailscale (K5).
- Ağ istisnaları → kur servisleri ve telefona bildirim onaylandı; kanallar e-posta ve Telegram (K8, K10).
- Kullanılmayan banka belgeleri → aslı arşivde, bağlantıyla; Claude'a verilebilir (K11).
- Banka dışı e-postalar → V1'de; esas banka akışları (K12).

Sonuç (2026-10-31): aşağıdaki sorular, belgeler son hâline getirilirken varsayılan kararlarla kapatıldı. Kullanıcıda
kalanlar dahil liste [V1 gereksinimleri → Açık sorular](v1/requirements.md#açık-sorular)'dadır.

O tarihte açık olanlar:

1. **Veri klasörü** — Önerim: depo dışında, sistemin uygulama verisi klasörü (macOS'ta
   `~/Library/Application Support/iplikci/`), yolu ayarlanabilir. Depo içinde olursa `git clean -xfd` bütün arşivi
   silebilir ve yanlışlıkla commit riski doğar.
2. **Şifreleme** — FileVault + şifreli yedek yeterli mi? (Önerim: şimdilik evet.)
3. **Depo görünürlüğü ve CI** — GitHub deposu açık mı, özel mi? CI yalnızca sahte verilerle çalışsın mı? (Önerim:
   evet.)
4. **MVP kodu** — `iplikci`'ye ilk sürüm olarak alınıp orada dönüştürülsün mü (önerim), yoksa yeni iskelet sıfırdan
   yazılıp okuyucular tek tek mi taşınsın?
5. **Bildirim içeriği** — Telegram ve e-postaya tutar ve işyeri gitsin mi, yalnızca başlık mı?
6. **Bildirim e-postası** — Aynı Gmail hesabından kendinize mi (uygulama şifresi SMTP için de çalışır), başka bir
   adrese mi?
7. **Enflasyon ve altın kaynağı** — TCMB EVDS için ücretsiz API anahtarı alınsın mı? Altın fiyatı için hangi kaynak?
8. **Tek dosyalık HTML rapor** — Dışa aktarma seçeneği olarak kalsın mı?
9. **V2 "uzmanlar"** — Yapay zekâ ajanları mı, insan uzmanla (mali müşavir, danışman) paylaşım mı, ikisi mi?
