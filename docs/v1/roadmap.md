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
| Sürüm 1.0 | v1.0.0 | Eşitlik listesi tamam, bir ay kapanmış, servis iki hafta kesintisiz ([aşağıda](#sürüm-10)) |

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
belgeleri hazır; demoya katılmaları altın tabanı değiştireceği için kullanıcının onayını bekler.

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
  Mağaza metinleri `extension/store/`'da hazır.

**Teslimler**

- `api`: FastAPI; kimlik doğrulama, Host ve Origin denetimi, SSE (ADR-0007).
- `jobs`, `feed`: kuyruk, zamanlayıcı, olay kaydı, anlık görüntü farkı (ADR-0014).
- İlk iş: [ADR-0016](../adr/0016-mail-connectors.md)'nın doğrulama denemesi (gelen kutusu akışı, ham ileti, tam
  tarama).
- `ingest`: e-posta bağlayıcıları (IMAP IDLE ve tarayıcı eklentisinin alım ucu), güven kuralı, `.eml` saklama
  (ADR-0015); gelen klasörü izleyicisi; yükleme ve plan/uygula.
- `extension/`: Chromium eklentisi (Manifest V3; ADR-0016). Eşleştirme, Gmail bağdaştırıcısı (üç katman), teslim ve
  sağlık; Chrome Web Store'da listelenmemiş yayın.
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

**Teslimler**

- Resmî SDK; servis üzerinden HTTP ve stdio köprüsü (ADR-0011).
- MVP'nin 16 aracı ve yeni araçlar; kaynaklar; istemler.
- Şema anlık görüntü testleri; maskeleme.
- Deponun `.mcp.json`'u; belirteç ortam değişkeninden okunur.

**Çıkış koşulu:** F16 ölçütleri sağlanır.

## Aşama 8 — Döviz

**Teslimler**

- Kur sağlayıcıları (TCMB, ECB ya da Frankfurter) ve geçmiş kurların bir kez çekilmesi.
- Kur seçim politikası; kur makası; çoklu para birimi.
- İsteğe bağlı EVDS ile enflasyondan arındırma (V1+).

**Çıkış koşulu**

- F12 ölçütleri sağlanır.
- Ağ yokken belgelerdeki kurlarla çalışır (test).

## Sürüm 1.0

MVP 2026-10-31'de emekliye ayrıldı, bu yüzden ayrı bir geçiş aşaması yok
([ADR-0018](../adr/0018-retire-mvp-clean-start.md)). `v1.0.0` şu koşullar sağlanınca atılır:

- [MVP eşitlik listesi](features.md#mvp-eşitlik-listesi)'nin tamamı işaretlidir.
- En az bir ay İplikçi Nedim'de kapanmıştır.
- Servis iki hafta kesintisiz çalışmış, yedek alınmış ve geri yükleme provası geçmiştir.
- `iplikci dogrula --arsiv` hatasız biter ve gerçek belgelerin tabanı gerilememiştir.

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
