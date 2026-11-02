# ADR-0017: Terminalsiz kurulum ve kullanım

Durum: **Önerildi** · Tarih: 2026-10-31 · Dayanak: K14, G4, ürün ilkeleri

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
- **Eklenti:** Chrome Web Store'dan kurulur ve tarayıcı tarafından güncellenir (ADR-0016).
- **Kaldırma:** Ayarlar'daki "Kaldır" servisi siler. Veri klasörü, kullanıcı ayrıca isterse çöp kutusuna taşınır.

**İmzalama**

- macOS'ta Apple onayı (notarization) ve Windows'ta kod imzalama ücretlidir. İmzasız paket ilk açılışta uyarı verir.
- Kurulum rehberi uyarının arayüzden nasıl geçileceğini gösterir: macOS'ta Sistem Ayarları → Gizlilik ve Güvenlik →
  "Yine de aç"; Windows'ta "Ek bilgi" → "Yine de çalıştır".
- İmzalama için ödeme yapılıp yapılmayacağı kullanıcının kararıdır (açık soru).

**Zamanlama**

- Eklenti Aşama 3'te gelir (ADR-0016).
- Kurulum paketleri ve sihirbazın tamamı Aşama 6'da gelir.
- O zamana dek geliştirme `uv run` ile sürer. MVP 2026-10-31'de emekliye ayrıldı
  ([ADR-0018](0018-retire-mvp-clean-start.md)).

## Paketleme biçimi

Aşama 6'nın ön incelemesi (2026-11-02). Bu bölüm ADR kabul edilmeden önce eklendi ve kararın parçasıdır.

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
