# ADR-0017: Terminalsiz kurulum ve kullanım

Durum: **Kabul edildi** (2026-11-02) · Tarih: 2026-10-31 · Dayanak: K14, K22, G4, ürün ilkeleri

Kullanıcı 2026-11-02'de kabul etti: "Kabul edildi, amaca uygun özellik." Paketler şimdilik imzasızdır (K22).

## Bağlam

Kullanıcı 2026-10-31'de şöyle dedi: "Kullanıcı odaklı düşünmelisin, terminalden bile iş yapmaya gerek kalmamalı" (K14).
Ürün, finanstan ve bilgisayardan anlamayan kullanıcıya da hitap etmeli.

Bugünkü tasarımda kurulum ve bazı işler terminal ister (mimari §19): `uv tool install`, `iplikci servis kur`,
`iplikci eposta kur`, `iplikci telegram kur`. MVP'de de her şey terminaldendir.

## Karar

**Kurulum paketi**

- CI her işletim sistemi için bir paket üretir:
  - macOS: `.dmg` içinde uygulama,
  - Windows: kurulum programı,
  - Linux: AppImage.
- Python yorumlayıcısı ve bağımlılıklar pakettedir; kullanıcıda Python ya da uv gerekmez.
- Paket donmuş (frozen) bir program değildir: uv'nin de kurduğu taşınabilir CPython (python-build-standalone),
  içine kurulmuş `iplikci` paketi ve bağımlılıkları pakete girer. Program, `uv tool install` ile kurulu hâliyle aynı çalışır. Gerekçe, ölçüler ve kalıcı yer aşağıda, "Paketleme biçimi"
  bölümündedir.

**İlk açılış ve günlük kullanım**

- Uygulama ilk açılışta arka plan servisini kullanıcı için kaydeder:
  - macOS'ta oturum ajanı,
  - Windows'ta oturum açılışında başlayan görev,
  - Linux'ta kullanıcı systemd birimi.
- Ardından tarayıcıda kurulum sihirbazını açar. Kullanıcı hiçbir komut yazmaz.
- Sonraki açılışlarda uygulamaya çift tıklamak, servisin çalıştığını denetler ve arayüzü tek kullanımlık giriş
  bağlantısıyla açar.

**Her iş arayüzde**

- Arayüzde yapılan işler: kurulum, e-posta bağlantısı (eklenti eşleştirmesi ya da uygulama şifresi), Telegram
  eşleştirmesi, servisi durdurma ve başlatma, yedek alma ve geri yükleme, dışa aktarma, belge ekleme ve kaldırma.
- Sırlar yalnızca arayüzde girilir; sohbete, dosyaya, komut satırı argümanına ya da günlüğe asla yazılmaz.
- Komut satırı geliştiriciler ve isteyen kullanıcılar için kalır. Her kullanıcı komutu arayüzdeki bir işin karşılığıdır;
  ikisi aynı `app` kullanım durumunu çağırır.
- Kullanıcıya yazılan yönergeler (README, yardım, bildirimler) terminal komutu içermez.

**Güncelleme ve kaldırma**

- **Güncelleme:** yeni paket indirilip açılır; servis yeni sürümle yeniden başlar ve veri klasörü yerinde kalır.
  Uygulama kendi kendine güncelleme denetimi yapmaz (ADR-0009); istenirse yeni bir ADR ile eklenir.
- **Eklenti:** Chrome Web Store'dan kurulur ve tarayıcı tarafından güncellenir (ADR-0016). Mağaza yayını şimdilik
  yok (K20). O güne dek eklenti programla gelir ve paketlenmemiş yüklenir:
  - Servis eklentiyi veri klasörüne kopyalar ve klasörü dosya yöneticisinde gösterir.
  - Arayüz tarayıcıdaki adımları anlatır.
  - Program güncellenince klasördeki eklenti de yenilenir.
- **Kaldırma:** Ayarlar'daki "Kaldır" servisi siler. Veri klasörü, kullanıcı ayrıca isterse çöp kutusuna taşınır.

**İmzalama**

- macOS'ta Apple onayı (notarization) ve Windows'ta kod imzalama ücretlidir. İmzasız paket ilk açılışta uyarı verir.
- Kurulum rehberi uyarının arayüzden nasıl geçileceğini gösterir: macOS'ta Sistem Ayarları → Gizlilik ve Güvenlik →
  "Yine de aç"; Windows'ta "Ek bilgi" → "Yine de çalıştır".
- İmzalama için ödeme yapılıp yapılmayacağı kullanıcının kararıdır. Karar (K22, 2026-11-02): paketler şimdilik
  imzalanmaz.

**Zamanlama**

- Eklenti Aşama 3'te gelir (ADR-0016).
- Kurulum paketleri ve sihirbazın tamamı Aşama 6'da gelir.
- O zamana dek geliştirme `uv run` ile sürer. MVP 2026-10-31'de emekliye ayrıldı
  ([ADR-0018](0018-retire-mvp-clean-start.md)).

## Paketleme biçimi

Aşama 6'nın ön incelemesi (2026-11-02). Bu bölüm ADR kabul edilmeden önce eklendi ve kabul edilen kararın
parçasıdır.

- Program gerçek bir Python yorumlayıcısına dayanır:
  - Okuma ve görüntüleme süreçleri `python -I -m iplikci.parsers.worker` ve `python -I -m iplikci.viewer.worker`
    olarak başlar ([ADR-0005](0005-parser-plugins.md)). `-I`, belgenin yanındaki hiçbir dosyanın içe
    aktarılamamasını sağlar.
  - Servis kaydı `python -I -X utf8 -m iplikci servis calistir --ev <veri klasörü>` komutunu çalıştırır.
- PyInstaller ve Briefcase programı dondurur: `sys.executable` uygulamanın kendi ikili dosyası olur ve `-I -m`
  çalışmaz. Okuma süreçleri ve servis kaydı yeniden tasarlanmak zorunda kalır, yalıtım da zayıflar.
- Bu yüzden paket şunlardan oluşur:
  - taşınabilir CPython 3.13 (python-build-standalone),
  - içine kurulmuş `iplikci` ve bağımlılıkları, derlenmiş arayüz dahil,
  - arayüzü açan küçük bir başlatıcı.

  macOS'ta Vision (OCR) bağı pyobjc tekerlekleriyle aynen gelir.
- Ölçü: bir Mac'te (Apple Silicon), sıkıştırılmadan, CPython 3.13.18 72 MB, kurulu program ve
  bağımlılıkları 102 MB tutuyor.
- **Kalıcı yer:** servis kaydı yeri değişmeyen bir yolu göstermelidir.
  - macOS: uygulama Uygulamalar klasöründen çalışır. Disk görüntüsünden açılırsa önce taşınmasını ister.
  - Windows: kurulum programı kullanıcının kendi klasörüne kurar (`%LOCALAPPDATA%\Programs`); yönetici izni
    gerekmez.
  - Linux: AppImage her açılışta başka bir yere bağlanır. İlk açılışta çalışma ortamını
    `~/.local/share/iplikci/app/<sürüm>` klasörüne kurar ve servisi oradan kaydeder.
- **Güncelleme:** yeni sürüm eskisinin yanına kurulur, servis yeni yoldan yeniden kaydedilip başlatılır, sonra eski
  sürümün klasörü kaldırılır. Veri klasörüne dokunulmaz.
- **İmzasız paket:** macOS indirilen uygulamayı karantinaya alır. "Yine de aç"tan sonra paketteki yorumlayıcının da
  çalıştığı temiz kurulum denemesinde doğrulanır.
- **Üretim:** paketler CI'da her işletim sisteminin kendi makinesinde üretilir.

## Uygulama notu (Aşama 6, 2026-11-02)

- **Paket** (`packaging/build.py`, CI'da "Paketler" iş akışı: bir sürüm etiketinde ya da istenince):
  - Yorumlayıcı `.python-version`'ın sabitlediği CPython'dur; uv onu indirir ve doğrular. Yorumlayıcı yalnızca bu
    programın olduğundan, paket kurucularını dışarıda tutan `EXTERNALLY-MANAGED` işareti kaldırılır.
  - Bağımlılıklar kilit dosyasından hash'leriyle kurulur, sonra programın tekerleği. Derlenmiş arayüz ve tarayıcı
    eklentisi tekerleğin içindedir; ikisinden biri yoksa paket üretilmez.
  - Programın kullanmadığı parçalar çıkarılır: paket kurucusu, test takımları, Tk, IDLE, C başlıkları.
  - macOS: `İplikçi Nedim.app` (`com.iplikci.app`), ad-hoc imzalı ve Apple onaysız (K22); `.dmg` içinde Uygulamalar
    bağlantısıyla.
    - macOS imzasız uygulamayı bir kez sorar ("Yine de aç"). Kullanıcı uygulamayı açınca uygulamanın kendi betiği,
      indirmenin karantina işaretini uygulamanın kendi dosyalarından kaldırır. İşaret kalsaydı macOS paketteki
      Python'u ve kütüphanelerini dosya dosya reddederdi.
    - Disk görüntüsünden ya da indirildiği yerden açılan uygulama, Python çalışmadan önce taşınmasını ister.
  - Windows: Inno Setup kurulum programı, `%LOCALAPPDATA%\Programs\İplikçi Nedim` klasörüne, yönetici izni
    olmadan; Başlat menüsü uygulamayı `pythonw` ile açar.
  - Linux: AppImage. AppRun, Python'u sürüm başına bir kez `~/.local/share/iplikci/app/<sürüm>` klasörüne kopyalar.
- **Açılış** (`iplikci uygulama`, `service/launcher`):
  - Kayıt bu kopyanın ve bu veri klasörünün değilse servis yeniden kaydedilir ve başlatılır.
  - Servis çalışmıyorsa ya da eski bir sürümse yeniden başlatılır.
  - Eski bir kopya, daha yeni bir sürümün servisi çalışırken ya da veri klasörünü daha yeni bir sürüm açmışken servisi
    kaydetmez; yeni sürümün açılmasını ister. Sürümler sayı olarak karşılaştırılır (0.10, 0.9'dan yenidir).
  - Aynı anda iki açılış sırayla yürür (`run/uygulama.kilit`): ikincisi birincinin servisi kaydedip başlatmasını
    bekler, sonra servisi hazır bulur.
  - Giriş bağlantısı ancak yeni servis yanıt verince alınır: biten eski servisin verdiği bağlantı onunla ölürdü.
  - Disk görüntüsünden ya da macOS'un geçici yerinden açılan uygulama önce taşınmasını ister.
  - Geliştirme kopyası servisi hiçbir zaman kaydetmez. Sorunlar sistemin kendi penceresinde söylenir; Linux'ta
    zenity ya da kdialog olmayan bir masaüstünde kapatılana dek kalan bir bildirimle (notify-send).
  - Windows'ta görevin hangi Python'u hangi veri klasörü için çalıştırdığı uygulamanın kendi dosyasında da tutulur
    (`%LOCALAPPDATA%\iplikci-servis\gorev.json`). schtasks görevi konsolun kod sayfasıyla yazar: İngilizce bir
    Windows'ta "İplikçi"nin İ'si ya da kullanıcı klasörünün adındaki ş başka bir harfe döner. Görev dosyaya uydukça
    yollar dosyadan okunur; uymazsa (dosyayı tutmayan bir kopya kaydettiyse) görevin kendi yazdığı geçerlidir.
- **Güncelleme** her sistemde şöyle yürür; veri klasörüne dokunulmaz:
  - macOS: yeni uygulama eskisinin yerine sürüklenir. Çalışan servis eski dosyalarla sürer; uygulama açılınca yeni
    sürümle yeniden başlar.
  - Windows: kurulum programı önce servisi kaldırır ve sürecin bitmesini bekler, Python'u bütünüyle değiştirir,
    sonra uygulamayı açar; uygulama servisi yeniden kaydeder.
  - Linux: yeni sürümün kopyası eskisinin yanına kurulur; yeni servis yanıt verince yalnızca daha eski sürümlerin
    kopyaları kaldırılır.
- **Her iş arayüzde:** servis arayüzden durdurulur, yeniden başlatılır ve bilgisayardan kaldırılır; bir yedek
  arayüzden geri yüklenir.
  - Servis kendi sürecini bitirir: temiz çıkış (0) durmadır. 75 çıkış kodunu launchd ve systemd servisi yeniden
    başlatarak karşılar. Görev Zamanlayıcı yalnızca başlayamayan görevi yeniden başlatır: Windows'ta servis biterken
    görevin dışında bir yardımcı bırakır, yardımcı süreç bitince görevi yeniden çalıştırır.
  - Veritabanı kapalıyken yapılacak işler `run/`'da bekler: geri yüklenecek yedek bir sonraki açılışta, veritabanı
    açılmadan yerine konur. Kaldırma istediyse veri klasörü çalışmanın sonunda çöp kutusuna taşınır.
- **Eklenti** (K20): program derlenmiş eklentiyi taşır. Servis istenince onu veri klasörünün `extension/`
  klasörüne kopyalar ve klasörü dosya yöneticisinde gösterir; açılırken klasörü programla aynı tutar.
- **Açık:** temiz kurulum denemeleri (macOS ve Windows), imzasız paketin
  "Yine de aç" yolu ve Linux ile Windows paketlerinin CI'daki ilk üretimi.

## Sonuçlar

- Olumlu:
  - Bilgisayardan anlamayan kullanıcı da kurabilir; destek yükü azalır.
  - Üç platform aynı yoldan kurulur.
- Olumsuz:
  - CI'da üç platform için paket üretimi ve testi gerekir.
  - İmzasız paketler uyarı verir.
  - Paket büyüktür: yorumlayıcı ve bağımlılıklarla onlarca MB.

## Değerlendirilen seçenekler

- **`uv tool install` ya da pipx:** terminal ister.
- **PyInstaller ya da Briefcase ile donmuş paket:** okuma süreçleri ve servis kaydı `python -I -m` ile çalıştığından
  yeniden tasarım ister ve yalıtım zayıflar (yukarıda, "Paketleme biçimi").
- **Electron ya da Tauri kabuğu:** Electron ağırdır, Tauri yeni bir araç zinciri (Rust) ister. Arayüz zaten tarayıcıda
  çalıştığı için gereksizdir.
- **Docker:** terminal ister; anahtar zincirine ve OCR'ye erişim zordur.
