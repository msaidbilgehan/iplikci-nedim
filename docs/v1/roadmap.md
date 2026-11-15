# V1 yol haritası

Proje: İplikçi Nedim · Durum: son hâli, uygulamaya hazır · Tarih: 2026-10-31 · İlgili belgeler:
[mimari](architecture.md), [özellikler](features.md), [geçiş](migration.md), [ADR-0013](../adr/0013-mvp-migration.md),
[ADR-0018](../adr/0018-retire-mvp-clean-start.md)

## Kurallar

- Aşamalar sırayla yürür. Aşama 5, 7 ve 8, Aşama 3'ten sonra birbirinden bağımsızdır; öne alınabilir.
- Arayüz iskeleti Aşama 3'te başlar; her aşama kendi ekranını o aşamada ekler. Aşama 6 arayüzü tamamlar.
- Her aşama şu koşullarla biter:
  - `uv run pytest` geçer ve CI yeşildir. Testler demo çalışma alanının altın tabanını da korur (Aşama 0).
  - Arşivde gerçek belge varsa `iplikci dogrula --taban` onların tabanını korur.
    - Gerçek belgeler V1'in kendi topladıklarıdır ve Aşama 3'te gelmeye başlar
      ([ADR-0018](../adr/0018-retire-mvp-clean-start.md)).
    - Bu doğrulama yerelde yapılır, CI'da yapılmaz.
  - README, CLAUDE.md ve gerekiyorsa bir ADR güncellenir.
  - Sürüm etiketi atılır: `v0.N.0`; sürüm 1.0'da `v1.0.0`.
- Her aşama ayrı bir dalda yürür ve kullanıcının onayıyla birleştirilir. Commit ve push yalnızca kullanıcı isteyince
  yapılır.

| Aşama | Sürüm | Hedef |
|---|---|---|
| 0 — Zemin | v0.1.0 | MVP kodu depoda, kişisel izlerden temizlenmiş, aynı davranışla; geliştirme altyapısı |
| 1 — Veri çekirdeği | v0.2.0 | Veri klasörü, belge arşivi, SQLite, `Money`, kalıcı kimlikler |
| 2 — Okuyucu eklentileri | v0.3.0 | Sözleşme, okuyucu başına sürüm, alt süreçte okuma, satır düzeyinde iz |
| 3 — Servis | v0.4.0 | API, kuyruk, olaylar, e-posta bağlayıcısı (ADR-0015, ADR-0016), launchd servisi, yedek; arayüz iskeleti; kutunun baştan okunması ve ilk gerçek taban |
| 4 — E-postanın tamamı | v0.5.0 | Banka bildirimleri, son ödemeler, dönemsel seriler, banka dışı e-postalar |
| 5 — Bildirimler | v0.6.0 | Kural motoru, e-posta ve Telegram kanalları |
| 6 — Arayüz | v0.7.0 | Bütün ekranlar, PWA, MVP raporuyla eşitlik, kurulum paketleri (terminalsiz kurulum) |
| 7 — MCP | v0.8.0 | Resmî SDK, HTTP ve stdio, yeni araçlar, kaynaklar, istemler |
| 8 — Döviz | v0.9.0 | Kur sağlayıcıları, kur makası, çoklu para birimi |
| Ara — Sürümler ve güncellemeler | v0.10.0 | GitHub'da sürüm, kendini güncelleyen program, mağazaya giden eklenti (K29, [aşağıda](#ara-sürüm--sürümler-ve-güncellemeler)) |
| Sürüm 1.0 | v1.0.0 | Eşitlik listesi tamam, bir ay kapanmış, yedek ve geri yükleme provası; yalnızca macOS (K31) ([aşağıda](#sürüm-10)) |

## Aşama 0 — Zemin

**Teslimler**

1. **Depo hijyeni:** `.gitignore` gözden geçirilir. `pre-commit` kurulur (ruff, gitleaks). `pyproject.toml` hazırlanır:
   - dağıtım adı `iplikci-nedim`, paket ve komut `iplikci` ([mimari §1](architecture.md#1-özet)), Python 3.13,
   - doğrudan bağımlılıklar `==` ile sabit, `uv.lock` ile birlikte,
   - ruff'ta satır uzunluğu 120.
2. **Kod aktarımı:** kaynak, veri klasöründeki arşivdir: `~/Library/Application Support/iplikci/archive/mvp/`
   ([geçiş](migration.md#mvpnin-arşivi)). Oradaki `src/gider_analizi` klasörü `src/iplikci` olur; `tests/` ve
   şablonlar da gelir. Arşive yazılmaz. Yalnızca adlar değişir:

   | Ne | Yeni değer |
   |---|---|
   | Dağıtım adı (`pyproject.toml`) | `iplikci-nedim` |
   | Komut | `iplikci` (MVP'nin alt komutları şimdilik aynı) |
   | Varsayılan panel portu | 8643 |
   | Anahtar zinciri hizmeti | `iplikci` |
   | Servis etiketi | `com.iplikci.*` (bu aşamada kurulmaz) |
   | MCP sunucu adı | `iplikci` |
   | E-posta şifresi ortam değişkeni | `IPLIKCI_MAIL_PASSWORD` |
   | Veri yolu | `IPLIKCI_HOME` |

3. **Kişisel izlerin temizliği:** [geçiş, Aşama 0](migration.md#aşama-0-kod-arşivden-depoya). Şirket adı
   `identity.business_names` ayarına taşınır; testlerde sahte bir ad kullanılır.
4. **`iplikci dogrula --taban`:** belgeleri salt okunur okur ve önbelleği `IPLIKCI_HOME` altında tutar.
   - Tabanı JSON olarak yazar ve bir öncekiyle farkını gösterir. Taban şunlardan oluşur:
     - belge sayıları ve durumları,
     - doğrulanan / toplam ekstreler ve dökümler,
     - dekont durumları,
     - ay kapanış durumları,
     - son 12 ayın gideri.
   - Henüz gerçek belge yok (K17). İlk taban, `iplikci dev demo`'nun sahte belgelerle kurduğu çalışma alanında alınır.
     Altın dosya olarak testlere girer ve sonraki aşamalar onu korur.
   - `iplikci dev demo`'nun ilk hâli bu aşamada yazılır. Sahte belgeleri MVP testlerindeki üreticilerle kurar
     (`conftest.text_pdf` ve benzerleri).
   - Gerçek belgelerin tabanı, V1 onları kendisi topladığında alınır (Aşama 3).
5. **Varsayılan kurallar:** arşivdeki `kategoriler.yaml`'ın genel kısmı ayıklanıp `src/iplikci/rules/default.yaml`
   olur. Hangi kısmın genel sayıldığı [geçiş](migration.md#aşama-0-kod-arşivden-depoya)'te yazılıdır. Kişisel kısım
   V1'e aktarılmaz.
6. **CI (GitHub Actions):** Linux'ta ruff, pytest ve gitleaks çalışır. OCR testleri macOS işine bırakılır.
7. **Belgeler:** README'deki komutlar gerçek hâle gelir; CLAUDE.md'deki komutlar güncellenir; `CHANGELOG.md` başlar.

**Çıkış koşulu:** MVP'nin bütün testleri (199 test işlevi) geçer; demo çalışma alanının altın tabanı testlerdedir;
temizlik taraması temizdir; CI yeşildir.

## Aşama 1 — Veri çekirdeği

Durum: 2026-11-01'de `asama-1` dalında uygulandı, `v0.2.0` ([değişiklik günlüğü](../../CHANGELOG.md)). Satırlar
şimdilik `Decimal` tutar taşır; defter ve yorum hesapları kendi paketlerine taşınırken `Money`'ye geçerler
([ADR-0006, uygulama notu](../adr/0006-money-and-codes.md#uygulama-notu-aşama-1-2026-11-01)).

**Teslimler**

- `settings`: veri klasörü, `settings.toml`, anahtar zinciri.
- `storage`: SQLite, göçler, depo modülleri, FTS.
- `vault`: nesneler, `staging`, türetilmiş veriler, çöp kutusuna taşıma, bütünlük denetimi.
- `domain`:
  - `Money` ve `Quantity`,
  - İngilizce kodlar ve Türkçe etiket eşlemesi ([domain/ledger.md](../domain/ledger.md)),
  - MVP modellerinden geçiş.
- Okunan satırlar veritabanına yazılır, analiz veritabanından beslenir. Defter ve yorum hesapları MVP'deki gibi bellekte
  kalır.
- Parmak izi ve `annotations` tablosu. Bu aşamada arayüzü yoktur; CLI ve testlerle kullanılır.
- Kural katmanları: varsayılan ve kişisel.
- Komutlar:
  - `iplikci dogrula --arsiv`,
  - `iplikci dogrula --yeniden-kur`.

**Çıkış koşulu**

- Demo çalışma alanının belgeleri arşive girer, okunur ve veritabanına yazılır; taban altın dosyayla aynıdır.
- Bir not yeniden okumadan sonra korunur (test).
- Veritabanı arşivden yeniden kurulunca aynı sonuç çıkar.

## Aşama 2 — Okuyucu eklentileri

Durum: 2026-11-01'de `asama-2` dalında uygulandı, `v0.3.0` ([değişiklik günlüğü](../../CHANGELOG.md)). Okuma tek bir
kalıcı alt süreçte yapılır; bellek sınırını yalnızca Linux uygular. Biçim alarmı için `events` tablosu bu aşamada açıldı
([ADR-0005, uygulama notu](../adr/0005-parser-plugins.md#uygulama-notu-aşama-2-2026-11-01)). Kart ekstrelerinin sahte
belgeleri hazırdı; gerçeklerin düzenine uydukları denetlenince kullanıcının onayıyla 2026-11-15'te demoya katıldılar
(dört kart, 18 ekstre; altın taban yeniden yazıldı).

**Teslimler**

- Sözleşme, kayıt defteri, tespit çakışmasının hata olarak raporlanması (ADR-0005).
- Okuyucu başına sürüm; okumanın alt süreçte, süre ve bellek sınırıyla yapılması.
- Bütün MVP okuyucularının eklentiye dönüşmesi ([mimari §10](architecture.md#10-okuyucular)).
- Her satırda `SourceRef`: PDF'de sayfa ve kutu, tabloda sayfa adı ve satır numarası.
- Her okuyucu için sahte belge üreticisi; temeli MVP'deki `conftest.text_pdf` (şimdi `iplikci.fakes`).
- `iplikci dev parser probe | debug | test`; biçim değişikliği alarmı.

**Çıkış koşulu**

- Taban aynı kalır.
- İşlemlerin %100'ünde kaynak konumu vardır.
- Bir okuyucunun sürümü artınca yalnızca onun belgeleri yeniden okunur (test).
- Her okuyucunun sahte belge testi vardır.

## Aşama 3 — Servis

Durum: 2026-11-01'de `asama-3` dalında uygulandı, `v0.4.0` ([değişiklik günlüğü](../../CHANGELOG.md)). Kullanıcı aşamayı
iki koşulu açık bırakarak kapattı ([K19](requirements.md#kararlar)).

- Hazır olanlar:
  - API, kuyruk ve olaylar;
  - e-posta alımı (IMAP ve eklentinin alım ucu, güven kuralı), gelen klasörü ve yükleme;
  - egress, servis yöneticisi ve yedek;
  - servisin istemcisi olan CLI ve arayüz iskeleti.
- Eklenti eşleşir, yeni banka iletilerini 1. ve 3. katmanla teslim eder ve geçmişi "Gmail'de eksikleri tara" ile okur
  ([ADR-0016, uygulama notu](../adr/0016-mail-connectors.md#uygulama-notu-aşama-3-2026-11-01)). Tam tarama (2. katman)
  doğrulamada tutmadı.
- Kutu baştan okundu ve ilk gerçek taban alındı ([geçiş, Aşama 3](migration.md#aşama-3-e-posta-ve-geçmiş)).
- Açık kalanlar:
  - servisin yedi gün kendi başına çalışması: servis 2026-11-01'de kuruldu, en erken 2026-11-08'de tamamlanır;
  - eklentinin Windows'ta denenmesi: önce macOS (K19);
  - yeni bir banka iletisinin akışa düşme süresi, ilk yeni iletide ölçülecek. Eklenti gelen kutusuna dakikada bir bakar.
- Eklenti şimdilik Chrome Web Store'da yayımlanmıyor, paketlenmemiş yükleniyor ([K20](requirements.md#kararlar)).
  Mağaza metinleri `extension/store/`'da hazır. (2026-11-15: eklenti mağazada yayımlandı, [K29](requirements.md#kararlar);
  v1.0.1 önce mağazayı gösterir.)

**Teslimler**

- `api`: FastAPI; kimlik doğrulama, Host ve Origin denetimi, SSE (ADR-0007).
- `jobs`, `feed`: kuyruk, zamanlayıcı, olay kaydı, anlık görüntü farkı (ADR-0014).
- İlk iş: [ADR-0016](../adr/0016-mail-connectors.md)'nın doğrulama denemesi (gelen kutusu akışı, ham ileti, tam
  tarama).
- `ingest`: e-posta bağlayıcıları (IMAP IDLE ve tarayıcı eklentisinin alım ucu), güven kuralı, `.eml` saklama
  (ADR-0015); gelen klasörü izleyicisi; yükleme ve plan/uygula.
- `extension/`: Chromium eklentisi (Manifest V3; ADR-0016). Eşleştirme, Gmail bağdaştırıcısı (üç katman), teslim ve
  sağlık; Chrome Web Store'da listelenmemiş yayın (2026-11-14: herkese açık listelenir,
  [ADR-0024](../adr/0024-extension-leads-to-download.md)).
- `egress`: dış bağlantı izin listesi (ADR-0009).
- `service`: launchd, systemd ve Görev Zamanlayıcı entegrasyonu; tek kopya kilidi; uyku sonrası tamamlama.
- Günlük yedek ve geri yükleme.
- CLI'nın servis istemcisine dönüşmesi; `/api/system`, `/healthz`.
- Arayüz iskeleti (`web/`): giriş, Sistem ekranı, Belgeler listesi, eklenti eşleştirmesi.
- E-posta kurulumu ve kutunun baştan okunması; V1'in geçmişi böyle kurulur
  ([geçiş, Aşama 3](migration.md#aşama-3-e-posta-ve-geçmiş)).

**Çıkış koşulu**

- Servis yedi gün kendi başına çalışır.
- Yeni banka iletisi ≤ 10 sn içinde (eklenti köprüsünde, tarayıcı açıkken ≤ 5 dk içinde) akışa düşer.
- Eklenti macOS ve Windows'ta Chrome'da kurulur, eşleşir ve iletileri teslim eder; hiçbir adım terminal istemez.
- Yeniden başlatmada iş kaybolmaz.
- Yedek alınır ve geri yükleme provası geçer.
- Host, Origin ve çerez testleri geçer.
- İlk gerçek taban alınır. Doğrulanamayan her ekstre ve okunamayan her belge nedeniyle listelenir.

## Aşama 4 — E-postanın tamamı

Durum: 2026-11-02'de `asama-4` dalında uygulandı, `v0.5.0` ([değişiklik günlüğü](../../CHANGELOG.md)).

- Kutunun envanteri çıkarıldı: 15 banka alan adından 1114 ileti, 617 konu kalıbı (`iplikci dev eposta-envanteri`).
  Okuyucu öncelikleri bu listeye göre belirlendi.
- Banka bildirimi okuyucuları: Vakıfbank, Garanti BBVA ve QNB'nin transfer bildirimleri, İş Bankası'nın kart borcu
  tahsilatı. Bildirimler dekontlar gibi ekstrelerle uzlaştırılır.
- F01: banka iletilerinin kapsamı Sistem ekranında ve `servis durum`'da görünür: bildirim okuyucularının okudukları,
  ekleriyle okunanlar, para hareketi taşımayanlar, şirket belgeleri ve tanınmayanlar.
- Kart ekstrelerinde son ödeme tarihi, asgari ödeme ve limit okunur. Dönemsel seriler, takvim ve nakit akışı
  öngörüsü Abonelikler ve Takvim ekranlarındadır.
- F14: banka dışı faturalar ve makbuzlar saklanır ve banka satırlarıyla eşleştirilir; bilgi satırlarının toplamları
  değiştirmediği test edilir. Eşleşen belge, hiçbir kuralın adlandırmadığı satırın kategorisini satıcının adından
  bulur. İlk okuyucu e-Fatura ve e-Arşiv faturasıdır (UBL-TR XML). Banka dışı göndericiler Sistem ekranından eklenir;
  Faturalar ekranı onların belgelerini listeler. Öteki aday okuyucular (uygulama mağazası makbuzları, abonelikler,
  telefon ve enerji faturaları, sipariş özetleri) bu göndericilerin iletileri geldikçe envantere göre seçilir.

**Teslimler**

- Kutu taranır; gönderici ve ileti türleri listelenir. Okuyucu öncelikleri bu listeye göre belirlenir.
- Banka bildirimi okuyucuları; bildirimler kanıt uzlaştırmasına girer.
- Kart ekstrelerinde son ödeme tarihi, asgari tutar ve limit okunur.
- Dönemsel seriler; yaklaşan ödemeler; nakit akışı öngörüsü.
- Banka dışı gönderici okuyucuları ve fatura eşleştirmesi.

**Çıkış koşulu**

- F01 kapsam ölçütü sağlanır: banka iletilerinin en az %90'ı işlenir ya da bilerek sınıflanır.
- F14 ölçütleri sağlanır.
- Taban gerilemez; bilgi satırları toplamları değiştirmez.

## Aşama 5 — Bildirimler

Durum: 2026-11-02'de `asama-5` dalında uygulandı, `v0.6.0` ([değişiklik günlüğü](../../CHANGELOG.md)).

- Kural motoru ve `rules/alerts.yaml`: kullanıcının kural dosyası yoksa uygulamayla gelen 16 kural geçerlidir. Bir
  kural bir olaya bakar; gün, tutar ve metin koşulu, kanalları, ayrıntı düzeyi ve sessiz saate uyup uymadığı
  seçilir. Kurallar Bildirimler ekranında düzenlenir ve son 30 güne göre önizlenir; MCP'nin `alerts` aracı da kural
  ekler, kapatır ve açar.
- Akış, kuralların baktığı yeni olayları kaydeder: yaklaşan son ödemeler (7, 3, 1 ve 0 gün kala), eksiye düşecek
  bakiye, gelmeyen beklenen ödeme ve geciken gelir, abonelik zammı, iptalden sonra ödeme, gelen gelir ve büyük
  harcama.
- Kanallar:
  - uygulama içi kutu, her zaman açık;
  - masaüstü: macOS'ta bildirim merkezi, Linux'ta `notify-send`; Windows'ta Windows denemesiyle (K19) gelecek;
  - Telegram: kullanıcının BotFather'da oluşturduğu bot; belirteç anahtar zincirinde durur, sohbet kodla eşleşir;
  - e-posta: yalnızca uygulama şifresiyle bağlı bir hesapla, kullanıcının kendi adresine.

  Gelişmiş Koruma'daki hesapta varsayılan kanallar masaüstü ve Telegram'dır.
- Her uyarı kanal başına bir kez gider. Sessiz saatte bekleyenler ve saatlik sınırı aşanlar sonra tek bir özetle
  gider. Başarısız gönderim artan aralıklarla yeniden denenir; reddeden kanal, kullanıcı yeniden açana dek durur.
  Teslim kaydı Bildirimler ekranında ve `iplikci bildirim gecmis`'te görünür, yedeğe de girer.
- Telegram kanalı, kullanıcı botunu oluşturup belirtecini girdiğinde gerçek bir sohbetle denenecek. Testler ağa
  çıkmaz, kanalları sahte nesnelerle sınar.

**Teslimler**

- Kural motoru ve `rules/alerts.yaml`; hazır kurallar.
- Kanallar: SMTP (uygulama şifresine izin veren gönderici hesapla), Telegram (eşleştirmeyle), masaüstü, uygulama içi.
- Ayrıntı düzeyleri, sessiz saat, özet, teslim kaydı (ADR-0010).

**Çıkış koşulu:** F13 ölçütleri sağlanır.

## Aşama 6 — Arayüz

Durum: 2026-11-02'de `asama-6` dalında uygulandı, `v0.7.0` ([değişiklik günlüğü](../../CHANGELOG.md)).

- On beş ekran sırayla geldi; Faturalar, Sistem ve Tarayıcı eklentisi ekranları da aynı düzene getirildi. Her ekranın
  metinleri kendi çeviri dosyasında, sade görünümü bir cümle ve sonraki adımla, ayrıntılı görünümü tablolarla.
- MVP raporunun bölümleri Değerlendirme'de, varlık tablosu Döviz'de, hesap türlerinin toplamları Hesaplar'da; ayların
  sayfaları `/ay-sonu/:ay`'da. MVP'nin kapsam ızgarası da geri geldi (`GET /api/accounts/coverage`).
  [Özellikler](features.md#mvp-eşitlik-listesi)'deki rapor maddeleri işaretlendi; bilerek farklı olanlar orada yazılı.
- Kurulum paketleri [ADR-0017](../adr/0017-no-terminal-install.md)'deki gibi: taşınabilir CPython 3.13 ve içine
  kurulmuş program, derlenmiş arayüz ve tarayıcı eklentisiyle; imzasız (K22). Paketler sürüm etiketinde ya da istenince
  CI'ın "Paketler" iş akışında, her sistemin kendi makinesinde üretilir.
- Uygulama açılınca servisi kendi kopyası için kaydeder, eski sürümü yeniden başlatır ve arayüzü açar; hiçbir şey
  kurulmamışsa arayüz kurulum sihirbazıyla açılır. Servis Ayarlar'dan durdurulur, yeniden başlatılır, geri yüklenir ve
  kaldırılır; yeniden başlatma, geri yükleme ve kaldırma yalnızca bilgisayarın bu veri klasörü için kaydettiği serviste
  yapılır.
- Uçtan uca testler demo çalışma alanında, her ekran açık ve koyu temada, telefon genişliğinde ve axe ile; ilk açılış
  boş bir veri klasöründe ayrıca sınanır.
- macOS'ta temiz kurulum 2026-11-02'de yapıldı; veri klasörü yanına taşındı, sonra geri kondu:
  - `.dmg`'den Uygulamalar'a kopyalanan uygulama açılınca servisi beş saniyede kaydetti ve sihirbazı açtı.
  - Sihirbazda şirket adları ve okumaya başlama günü girildi. Eklenti sihirbazın hazırladığı klasörden yüklendi,
    kodla eşleşti ve Gmail taramasını kendisi başlattı; bulunan iletilerin hepsi teslim edildi, hiçbir iş başarısız
    olmadı.
  - Pano ve Değerlendirme ilk raporu bütün bölümleriyle gösterdi. Ayarlar'dan yeniden başlatma bir saniyede döndü;
    veri klasörüyle kaldırma kaydı sildi ve klasörü çöp kutusuna taşıdı.
  - Bulunan iki hata düzeltildi: ilk taramanın ortasında geçmişin bir parçasından çıkan uyarılar masaüstüne
    gidiyordu (artık ilk okuma bitene dek yalnızca uygulamanın kutusuna düşer, F13), servis dururken açık olay akışı
    kesilip günlüğe hata yazılıyordu.
  - Denenmeyen: indirilmiş paketin Gatekeeper uyarısı (paket aynı bilgisayarda üretildi, indirme işareti taşımıyordu).
    Programın anahtar zincirindeki API belirteci denemeden önce silindi: başka bir Python'un yazdığı kaydı okumak
    macOS'ta parola sorar; temiz bir bilgisayarda böyle bir kayıt yoktur.
- Açık kalanlar:
  - Windows'ta temiz kurulum (kullanıcı yapacak). O denemede bakılacaklar:
    - Ayarlar'dan "Yeniden başlat": servis yaklaşık 20 saniyede geri gelmeli. Servisi yeniden çalıştıran yardımcı,
      görevin işi bittikten sonra da yaşamalı; Windows buna izin vermezse yeniden başlatma sessizce kalır.
    - Görev Zamanlayıcı'nın "çalışıyor" bilgisi (`schtasks /Query /V /FO CSV /NH`'nin yedinci alanı, çalışırken
      267009) okunuyor mu; okunmazsa yeniden başlatma 15 saniye bekleyip yine sürer.
    - `schtasks` pencere açmadan da OEM kod sayfasında yanıt veriyor mu; buna yalnızca görev kaydının XML yedeği
      dayanır.
  - macOS'ta çöp kutusuna atılan uygulama (K31, ADR-0017'nin 2026-11-15 notu). Testler launchd'ye ulaşmaz;
    paketlenmiş uygulama kuruluyken gerçek bir Mac'te bakılacaklar:
    - Uygulama çöp kutusuna sürüklenince servis iki dakika içinde durmalı. `com.iplikci.service.plist`
      `~/Library/LaunchAgents`'tan gitmeli; servisin günlüğü nedenini yazmalı; veri klasörü yerinde kalmalı. Çöp
      kutusu sonra boşaltılabilmeli.
    - Servis durdurulmuşken uygulama çöp kutusuna atılıp oturum yeniden açılınca ajan kendini kaldırmalı:
      `launchctl print gui/$(id -u)/com.iplikci.service` işi bulamamalı, sistem günlüğünde `iplikci-servis` satırı
      olmalı (`log show --last 10m --predicate 'process == "logger"'`).
    - Kendiliğinden güncelleme ve yeni sürümün eskisinin üstüne sürüklenmesi kaydı korumalı.
    - Önceki sürümün yazdığı ajan, yeni sürümün ilk açılışından sonra `/bin/sh` korumasıyla yazılmış olmalı.
    - Sistem Ayarları → Genel → Giriş Öğeleri'nde öğe "İplikçi Nedim" adıyla mı görünüyor
      (`AssociatedBundleIdentifiers`)? "sh" görünüyorsa ve bu kullanıcıyı tedirgin ediyorsa ajanın başka bir biçimi
      düşünülmeli.
  - Linux'ta uygulama menüsü (K31, ADR-0017'nin 2026-11-15 notu), Linux denemesiyle (K25). Testler geçici bir
    `$XDG_DATA_HOME`'a yazar; gerçek bir masaüstünde bakılacaklar:
    - AppImage ilk açılışta uygulama menüsüne "İplikçi Nedim" adıyla ve simgesiyle girmeli (GNOME ve KDE); menüden
      açılınca tarayıcıda arayüz açılmalı.
    - AppImage taşınıp ya da silinip menüden açılınca uygulama yine açılmalı: giriş `~/.local/lib/iplikci/<sürüm>`'deki
      kopyayı açar.
    - Kendiliğinden güncellemeden sonra giriş yeni sürümün kopyasını açmalı; eski kopya silinince menüden düşmemeli.
    - Ayarlar'daki "Kaldır" girişi ve simgeleri silmeli; menü girişi kalmamalı.
  - Aşama 3'ten kalan yedi günlük çalışma (K19).
  - Uzak erişim (Tailscale, ADR-0012) sihirbazda "sonra gelecek" diye yazılıdır.

**Teslimler**

- Ekranlar, bu sırayla:
  1. Akış
  2. Pano
  3. Hesaplar
  4. İşlemler ve iz
  5. Belgeler ve görüntüleyici
  6. Abonelikler
  7. Takvim
  8. Değerlendirme
  9. Ay sonu
  10. Döviz
  11. Bildirimler
  12. Kurallar
  13. Yapılacaklar
  14. Kurulum sihirbazı
  15. Ayarlar
- PWA; çeviri altyapısı; açık ve koyu tema; sade ve ayrıntılı görünüm.
- Kurulum paketleri: macOS `.dmg`, Windows kurulum programı, Linux AppImage. İlk açılışta servis kaydı ve sihirbaz
  (ADR-0017).
- Playwright testleri demo çalışma alanında; axe ile erişilebilirlik denetimi.

**Çıkış koşulu**

- [MVP eşitlik listesi](features.md#mvp-eşitlik-listesi)'ndeki rapor maddeleri sağlanır.
- Uçtan uca testler iki temada geçer.
- Temiz bir macOS ve Windows kurulumunda, terminal açmadan kurulum, eklenti eşleştirmesi ve ilk rapor tamamlanır.

## Aşama 7 — MCP

Durum: 2026-11-03'te `asama-7` dalında uygulandı, `v0.8.0` ([değişiklik günlüğü](../../CHANGELOG.md)).

- MCP sunucusu resmî SDK'yla (`mcp==2.3.0`) `src/iplikci/mcp/` paketinde. Servis MCP'yi `/mcp`'de sunar: durumsuz,
  JSON yanıtlı, kapının arkasında yalnızca API belirteciyle. `iplikci mcp` stdio köprüsüdür. Her iletiyi servise
  iletir; servis yanıt vermiyorsa iletiyi, veritabanını salt okunur açan yerel sunucu yanıtlar ve yazan araçlar
  reddedilir. Bu seçim her ileti için yeniden yapılır.
- 31 araç: MVP'nin 16'sı aynı adlarla, Aşama 4–5'in 5'i ve ADR-0011'in 10 yenisi. Yazanlar önce planı gösterir;
  plan, aynı araç `plan_id`'yle çağrılınca bir kez uygulanır. Uzun çıktılar sayfa sayfa gelir.
- Kaynaklar (belgeler metinleri ve PDF sayfalarıyla, ay kapanışları, hesaplar) ve beş hazır istem.
- Maskeleme `[privacy] mcp_masking`; her çağrı denetim kaydında; talimatlar ve belge metinleri belgenin veri olduğunu
  söyler.
- Arayüzde Claude bağlantısı ekranı (`/kurulum/claude`), Ayarlar'dan da açılır. Başlık yardımcısı
  `iplikci mcp baslik`; deponun `.mcp.json`'u.
- Uçtan uca denemeler ([F16](features.md#f16--mcp)):
  - Claude Code demo servisine HTTP ile bağlandı. Araç listesi, bir okuma ve bir plan → uygula akışı çalıştı.
  - Köprü servis dururken veritabanıyla, servis açılınca yine servisle yanıt verdi.
  - İplikçi Nedim claude-SAK ile kullanıcının Claude'una eklendi ve gerçek veride okundu.
- Kurulu servis 0.8.0'a güncellendi; gerçek belgelerin tabanı kayıtlı olanla aynı.

**Başlangıçtaki durum (2026-11-02)**

- MCP sunucusu MVP'nin düz düzeninde, `src/iplikci/mcp_server.py`'dadır. JSON-RPC elle yazılmıştır; yalnızca stdio
  (`iplikci mcp`) ve yalnızca araçlar vardır, kaynak ve hazır istem yoktur.
- 21 araç vardır: MVP'nin 16'sı (`status`, `import_documents`, `fetch_email`, `plan_inbox`, `apply_inbox`,
  `build_report`, `insights`, `transactions`, `regular_payments`, `habits`, `accounts`, `month_end`, `read_rules`,
  `add_rule`, `mark_ended`, `write_rules`) ve Aşama 4–5'te gelen `subscriptions`, `upcoming_payments`,
  `cash_flow_forecast`, `invoices`, `alerts`.
- Araçlar servise değil, kendi süreçlerinde veri klasörüne bağlanır. Ekranların her biri için `app`'te bir kullanım
  durumu vardır; MCP de aynı kullanım durumlarını kullanmalıdır.
- Depoda `.mcp.json` yoktur; resmî MCP SDK'sı bağımlılıklarda yoktur.

**Teslimler**

- `mcp/` paketi (MVP modüllerinin hedefleri tablosu) ve resmî Python SDK'sı (ADR-0011):
  - Asıl taşıma, servisin `/mcp` adresindeki Streamable HTTP'dir; ADR-0007'nin kapısının arkasındadır (Host ve Origin
    denetimi, API belirteci).
  - `iplikci mcp` stdio köprüsüdür: servis çalışıyorsa istekleri ona iletir. Çalışmıyorsa veritabanını salt okunur
    açar; yazan araçlar o sırada reddedilir.
- Araçlar:
  - MVP'nin 16 aracı aynı adlarla kalır; Aşama 4–5'tekiler de kalır.
  - ADR-0011'in yeni araçları eklenir: `search`, `explain_transaction`, `get_document`, `unprocessed_documents`,
    `reparse_document`, `feed`, `accounts_overview`, `net_worth`, `fx_rates`, `annotate_transaction`.
  - Aynı soruya ekranla MCP aynı cevabı verir: araçlar `app`'in kullanım durumlarını çağırır.
- Her araçta ek açıklamalar (`readOnlyHint`, `destructiveHint`, `idempotentHint`) vardır. Yazan araçlar plan → onay →
  uygula akışını izler. Büyük çıktı önce özet döner; ayrıntı istenince ve sayfa sayfa gelir.
- Kaynaklar ve hazır istemler ADR-0011'deki gibidir.
- Gizlilik:
  - Türkçe sunucu talimatları belge metninin veri olduğunu, talimat olmadığını söyler.
  - Ayarlardaki maskeleme seçeneği hesap numaralarını, IBAN'ları ve kişi adlarını gizler.
  - Her araç çağrısı denetim kaydına yazılır.
- Testler: araç listesinin, şemaların ve ek açıklamaların anlık görüntüsü; maskeleme; salt okunur köprü.
- Deponun `.mcp.json`'u: belirteç ortam değişkeninden okunur, depoya yazılmaz.
- Claude bağlantısı (K23, K14): arayüzde, Claude'u terminal açmadan bağlamak için:
  - MCP adresi, "Göster" düğmesinin arkasında API belirteci, kopyala düğmeleri ve hazır yapılandırma. Yapılandırma
    claude-SAK'ın "MCP JSON" içe aktarmasına, Claude Code'a ve Claude Desktop'a uyar.
  - claude-SAK ile ekleme adımları, sade sözcüklerle. Claude'un ayar dosyasını İplikçi Nedim yazmaz.
  - Belirteci Claude'un ayar dosyasına yazdırmayan bir başlık yardımcısı (`iplikci mcp baslik`) belirteci anahtar
    zincirinden okur. Komutun yolu çalışan kopyadan yazılır: uv aracı ya da kurulum paketinin Python'u.
- Aşama sonunda İplikçi Nedim claude-SAK üzerinden kullanıcının Claude'una eklenir ve gerçek veride bir okuma
  denenir (K23).

**Çıkış koşulu**

- F16 ölçütleri sağlanır.
- MVP eşitlik listesinin MCP ve kurallar maddeleri işaretlenir.

## Aşama 8 — Döviz

Durum: 2026-11-03'te `asama-8` dalında uygulandı, `v0.9.0` ([değişiklik günlüğü](../../CHANGELOG.md)).

- `fx` paketi: TCMB'nin günlük bülteni, ECB'nin referans kurları (günlük, 90 günlük ve bütün geçmiş) ve Frankfurter'in
  JSON'u; EVDS'den TÜFE. Hepsi `egress.https_get` ile ve ADR-0009'un izin listesiyle, yalnızca GET.
- Kurlar `fx_rates`'te tarihçeli; sorulan günler `fx_days`'te. Geçmiş, verinin kapsadığı ilk günden bir kez çekilir
  (çalıştırma başına en çok 400 istek ve iki dakika, aralarında yarım saniye; servisin öteki işleri araya girer); günün
  bülteni her gün 16:30'da. TCMB'ye ulaşılamayan günler ECB'nin referans kurlarıyla dolar; varsayılan sıra `document`,
  `tcmb`, `frankfurter`, `ecb` (ECB'nin sertifikası macOS'taki Python'da doğrulanmadığı için Frankfurter önce;
  ADR-0009'un notu).
- Kur politikası (mimari §15): satırın kendi kuru > o günün (ya da en fazla bir hafta önceki son bültenin) döviz alış
  kuru > belgelerin en yakın kuru; varlıklar alış, borçlar satış kuruyla; aynı gün TCMB ECB'den önce.
- Kur makası (`exchange.spread`) ve döviz geliri (`exchange.foreign_income`), Döviz ekranında kendi bölümlerinde ve
  MCP'nin `fx_rates` aracında.
- EVDS (V1+): kullanıcının anahtarı Ayarlar'da bir kez denenip anahtar zincirine yazılır; TÜFE her gün 10:30'da
  `price_index`'e çekilir ve Değerlendirme'deki harcama eğilimi aynı ayın fiyatlarıyla da söylenir (`inflation`).
  v0.9.1'de:
  - Kart özelliği bir örnekle anlatır, açık mı kapalı mı olduğunu söyler ve EVDS'nin giriş sayfasına ve
    kılavuzlarına bağlantı verir.
  - TÜFE, TÜİK'in 2025=100 serisinden alınır. 2003=100 serisi Ocak 2026'da arşive alınıp bitmişti.
  - Duran bir seri Ayarlar'da söylenir.
- Ağ yokken belgelerdeki kurlarla çalışır; testler bunu sağlayıcı kuru olmadan ve sağlayıcılara ulaşılamazken dener.
  Demo kendi sahte TCMB bültenlerini taşır ve ağa çıkmaz; altın tabanı değişmedi.

**Başlangıçtaki durum (2026-11-02):** kur sağlayıcısı yoktur. Döviz ekranı ve net varlık belgelerin kendi kurlarıyla
çalışır (Aşama 6); kuru belgelerde olmayan birim toplama girmez ve ekranda adıyla yazar. `fx` paketi yoktur. Kur
sağlayıcılarının adresleri ADR-0009'da listelidir; `egress` onları ancak bu özellik gelince kabul eder.

**Teslimler**

- Kur sağlayıcıları (TCMB, ECB ya da Frankfurter) ve geçmiş kurların bir kez çekilmesi.
- Kur seçim politikası; kur makası; çoklu para birimi.
- İsteğe bağlı EVDS ile enflasyondan arındırma (V1+).

**Çıkış koşulu**

- F12 ölçütleri sağlanır.
- Ağ yokken belgelerdeki kurlarla çalışır (test).

## Ara sürüm — Sürümler ve güncellemeler

v0.10.0 · [K29](requirements.md#kararlar) · [ADR-0022](../adr/0022-releases-and-updates.md) ·
[F21](features.md#f21--güncellemeler)

Kullanıcının isteği (2026-11-10): uygulama ve tarayıcı eklentisi GitHub'da derlenip kendiliğinden güncellenmeli;
eklentiyi kullanıcı Chrome Web Store'da yayımlayacak.

**Teslimler**

- "Paketler" iş akışı sürüm etiketinde paketleri, güncelleme dosyalarını, eklentinin mağaza paketini ve imzalı
  bildirgeyi bir GitHub sürümüne koyar; mağaza ayarları varsa eklentiyi mağazaya yükler.
- Paketler yayımlanmadan önce kurulan programla servisi başlatıp denenir.
- Servis günde bir yeni sürüme bakar; ayara göre kurar ya da haber verir. Ayarlar'da Güncellemeler kartı, Sistem'de
  durum, `iplikci guncelleme`.
- Eklenti 0.8.0: paketlenmemiş eklenti programın taşıdığı daha yeni sürüm için kendini yeniden yükler; mağaza
  kimliği bilinince arayüz mağazayı gösterir.

**Kullanıcıda kalanlar**

- Sürümlerin herkese açık nerede duracağı: kod deposunu açmak ya da ayrı bir sürüm deposu. Karar verilene dek kurulu
  kopyalar yeni sürümü indiremez.
- Chrome Web Store'daki ilk yayın ve iş akışının mağazaya yüklemesi için servis hesabı ([sürüm yayını](../yayin.md)).
- Windows ve Linux'ta güncellemenin denenmesi, o sistemlerin denemeleriyle (K25).

## Sürüm 1.0

MVP 2026-10-31'de emekliye ayrıldı, bu yüzden ayrı bir geçiş aşaması yok
([ADR-0018](../adr/0018-retire-mvp-clean-start.md)). `v1.0.0` şu koşullar sağlanınca atılır:

- [MVP eşitlik listesi](features.md#mvp-eşitlik-listesi)'nin tamamı işaretlidir. 1.0 yalnızca macOS'la çıkar
  ([K31](requirements.md#kararlar)); Windows ve Linux denemeleri sonra yapılır (K25), "Diğer sistemler" maddesi onlara
  kadar açık kalır.
- En az bir ay İplikçi Nedim'de kapanmıştır.
- Yedek alınmış ve geri yükleme provası geçmiştir.
- `iplikci dogrula --arsiv` hatasız biter ve gerçek belgelerin tabanı gerilememiştir.
- Paketlenmiş uygulama kullanıcının Mac'inde kurulmuş ve denenmiştir; sürümler herkese açık kod deposunun sürüm
  sayfasındadır ([K32](requirements.md#kararlar)).

**Durum (2026-11-15):** `v1.0.0` atıldı. Koşullar: eşitlik listesinin "Diğer sistemler" dışındaki maddeleri işaretli;
2025-12'den 2026-09'a dek on ay kapandı; 2026-11-14'teki yedeğin geri yükleme provası geçti; `dogrula --arsiv` hatasız
bitti; 1.0.0'ın kodu gerçek veri klasörünün bir kopyasında bütün belgeleri yeniden okudu ve tabanı kayıtlı tabanla aynı
çıktı (62/62 kart ekstresi, 61/61 hesap dökümü doğrulandı); paketlenmiş uygulama 2026-11-14'te kullanıcının Mac'inde
kuruldu ve denendi; sürümler herkese açık kod deposundadır (K32).

Servisin iki hafta kesintisiz çalışması 1.0'ı beklemez (K31, 2026-11-14): ilk günlerde kullanıcı olmayacak, mağaza
incelemesi de zaman alacak. Aşağıdaki süreye bağlı koşullar yine zamanı gelince denetlenir; bir sorun çıkarsa 1.0.x
ile düzeltilir.

**Süreye bağlı koşullar neyi gösterir (2026-11-03).** Kullanıcının isteğiyle süre dolunca denetlenirler. Sürenin
kendisi bir şey kanıtlamaz. Denetlenen, o sürede kendiliğinden yaşanması gerekenlerdir. Testler bunları sahte saatle
dener; gerçek bilgisayarda ise ancak zamanı gelince görülürler:

- **Takvimli işler gerçekten çalışır:**
  - her gece yedek, ayda bir geri yükleme provası;
  - her gün 16:30'da kurlar, anahtar varsa 10:30'da TÜFE;
  - e-postanın ve tarayıcı eklentisinin günlük teslimleri.
- **Bilgisayarın olaylarından sonra servis kendiliğinden kalkar ve kaçırdığı işi yapar:** uyku ve uyanma, yeniden
  başlatma, macOS güncellemesi.
- **Zamanla büyüyenler sınırlarında kalır:** disk, günlükler ve veritabanı.
- **Gerçek bir ay baştan sona kapanır:** ekstreleri gelir, ay kapanır, bildirimi gider. Ekim 2026'nın ekstreleri Kasım
  ortasına kadar beklenir.

Denetim `iplikci servis durum`, servisin günlüğü ve Sistem ekranıyla yapılır. Bu olaylar en az bir kez yaşanmış ve
kesinti ya da hata yoksa koşul sağlanmıştır.

## MVP modüllerinin hedefleri

| MVP modülü | Hedef | Aşama |
|---|---|---|
| `models.py` | `domain/` (modeller, `Money`, kodlar) | 1 |
| `textutil.py`, `pdfutil.py`, `tables.py` | `parsers/text.py`, `parsers/pdf.py` (OCR dahil), `parsers/sheet.py` | 2 |
| `parsers/*.py` | `parsers/<banka>/<belge>.py` eklentileri; `common.py` ve `hesap.py` ortak yardımcılara | 2 |
| `sources.py` | `ingest/archives.py` (zip, mbox) | 3 |
| `pipeline.py` | `jobs` (okuma işi) ve `storage` (önbellek yerine tablolar) | 1–3 |
| `analysis.py` | `ledger/` (birleştirme, uzlaştırma, transferler, kur, kapsama) | 1–2 |
| `categorize.py`, `rulefile.py` | `categorize/` | 1 |
| `insights.py` | `insights/` (her bulgu yazarı ayrı modülde) | 1–4 |
| `month_end.py` | `month_end/`; sayfalar `export/` | 1, 6 |
| `report.py`, `templates/` | `export/` (tek dosyalık rapor, XLSX, CSV); yeni arayüz `web/` | 6 |
| `duzenle.py` | `vault/` (görünen ad, çöp kutusu); plan/uygula `app/` | 1–3 |
| `workspace.py` | `settings/`, `service/`, `app/` | 1–3 |
| `email_fetch.py` | `ingest/mail/` | 3 |
| `automation.py` | `service/` (servis yöneticileri); `notify/` (masaüstü kanalı) | 3, 5 |
| `panel.py` | `api/` | 3 |
| `mcp_server.py` | `mcp/` | 7 |
| `cli.py` | `cli/` | 0–3 |

## İlk oturum (Aşama 0) için başlangıç

Bu adımlar 2026-11-01'de `asama-0` dalında uygulandı ([revizyon 10](../REVISIONS.md#değişiklik-kaydı)). Aşağıdaki
"henüz commit yok" gibi notlar o günün durumunu anlatır.

1. **Oturumu nerede açmalı:** depoda.
   Sırayla okunacaklar: `CLAUDE.md`, `docs/README.md`, bu belge, [geçiş](migration.md) (MVP'nin arşivi ve Aşama 0).
2. **MVP emekliye ayrıldı (2026-10-31):** arka plan görevi ve e-posta kaydı kaldırıldı. MVP'nin kodu, testleri ve
   kuralları yalnızca veri klasöründeki arşivde durur: `archive/mvp/` ([geçiş](migration.md#mvpnin-arşivi)).
   - Arşivden yalnızca kopyalanır; arşive yazılmaz.
   - Kişisel dosyalar depoya girmez: `kategoriler.yaml`'ın kişisel kısmı, `ayarlar.toml` ve `CLAUDE.md`.
   - Arşiv depo klasörünün dışındadır; dosyalarına tam yoluyla erişilir.
3. **Git**
   - Git kullanıcı adı ve e-postası tanımlı değilse ilk commit'ten önce kullanıcıya sorulur.
   - Depoda henüz commit yok. İlk commit README ve `docs/` olur (kullanıcı onayıyla).
   - Aşama 0'ın işleri `asama-0` dalında yapılır.
4. **Sıra**
   1. Kodu arşivden kopyala ve adları değiştir.
   2. Testler geçsin.
   3. Kişisel izleri temizle ve tara.
   4. `dogrula --taban`'ı ve `dev demo`'nun ilk hâlini yaz; demo tabanını altın dosya yap.
   5. Varsayılan kuralları ayıkla.
   6. CI'ı kur.
   7. Belgeleri güncelle.
   8. Kullanıcıya özet ver ve birleştirme onayı iste.
