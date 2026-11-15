# Geliştirici rehberi

Deponun [README](../README.md)'si İplikçi Nedim'i kullanacak kişiye anlatır. Bu belge kodla çalışanlar içindir:
ilkeler, komutlar, kurulum paketlerinin her sistemde açılışı ve belgelerin yeri. Ajanların kuralları
[`CLAUDE.md`](../CLAUDE.md)'dedir; sürümlerin hikâyesi [CHANGELOG](../CHANGELOG.md)'da ve
[revizyonlarda](REVISIONS.md).

## İlkeler

- Banka akışları esastır: her para hareketi bir banka belgesine dayanır; diğer e-postalar kanıt ve bilgi katmanıdır.
- Yerel öncelik: belgeler ve veriler bu bilgisayarda, deponun dışındaki veri klasöründe durur. Ağa yalnızca e-posta
  okumak, döviz kurlarını (ve anahtar girildiyse TÜFE'yi) almak, bildirim göndermek ve GitHub'da yeni sürüm olup
  olmadığına bakmak için çıkılır.
- Yalnızca kişisel para hareketleri; şirket belgeleri kapsam dışıdır.
- Hiçbir belge kalıcı silinmez.
- Son kullanıcı terminal kullanmaz: her işin arayüzde bir yolu vardır.
- Finanstan anlayan da anlamayan da kullanmak istemeli.
- Kişisel ihtiyaçlar için yapılan bir hobi projesi, kurumsal bir ürün değil; yine de her kullanıcıya azami verim
  sağlamalı.

## Gerekenler

[uv](https://docs.astral.sh/uv/), [gitleaks](https://github.com/gitleaks/gitleaks), arayüzle eklenti için
[Node.js](https://nodejs.org/) 24 (CI'ın sürümü). README'nin görselleri için ayrıca ffmpeg ve ImageMagick.

## Komutlar

```bash
uv sync                                          # Python 3.13 ve kilitli bağımlılıklar
uv run pre-commit install                        # her commit'ten önce ruff ve gitleaks; yalnızca ana klasörde
uv run pytest -q                                 # testler; demo çalışma alanının altın tabanı dahil
uv run ruff check && uv run ruff format --check  # biçim ve kod denetimi
uv run pyright                                   # yeni paketlerde katı tip denetimi
uv run iplikci dev demo /tmp/iplikci-demo        # sahte belgelerle demo veri klasörü (boş ya da yeni klasör)
IPLIKCI_HOME=/tmp/iplikci-demo uv run iplikci dogrula --taban --tarih 2026-11-15   # demonun doğrulama tabanı
IPLIKCI_HOME=/tmp/iplikci-demo uv run iplikci dogrula --arsiv                      # arşiv ve veritabanı tutarlı mı
IPLIKCI_HOME=/tmp/iplikci-demo uv run iplikci dogrula --yeniden-kur                # arşivden aynen kurulur mu
IPLIKCI_HOME=/tmp/iplikci-demo uv run iplikci islem ara MIGROS                     # işlemler, parmak izleriyle
uv run iplikci dev parser probe belge.pdf        # okuyucular belgeyi tanıyor mu, neden
uv run iplikci dev parser debug belge.pdf        # okuyan okuyucu ne okuyor: satır satır, yerleriyle
uv run iplikci dev parser test                   # okuyucular sahte belgelerini doğru okuyor mu
uv run iplikci dev eposta-envanteri [--csv]      # saklanan e-postalar, gönderen ve konu kalıbına göre
```

Servis, arayüz ve tarayıcı eklentisi:

```bash
(cd web && npm ci && npm run build)              # arayüz; çıktı pakete girer (src/iplikci/api/ui)
(cd e2e && npm ci && npx playwright test)        # uçtan uca: demo veri klasöründe, iki temada, axe ile
uv run iplikci dev api-tipleri web/src/api/schema.ts   # API'nin modelleri değişince arayüzün tipleri
uv run iplikci servis calistir                   # servis ön planda: http://127.0.0.1:8643
uv run iplikci ac                                # arayüzü tek kullanımlık giriş bağlantısıyla açar
uv run iplikci servis durum                      # servis çalışıyor mu; kuyruk, e-posta ve kapsamı, yedek ve disk
uv run iplikci yedek al | liste | geri-yukle | prova
uv run iplikci eposta kur | durum | kaldir | al  # IMAP hesabı; şifre yalnızca anahtar zincirinde
uv run iplikci kurlar al [--gecmis] | durum      # döviz kurları: şimdi çek (servis çalışıyorsa ona sorar), durumu
uv run iplikci mcp                               # MCP'nin stdio köprüsü: servis çalışıyorsa ona, değilse salt okunur
uv run iplikci mcp baslik                        # Claude Code'un başlık yardımcısı: belirteçli Authorization başlığı
uv run iplikci guncelleme durum | denetle | kur  # yeni sürüm: durum, şimdi denetle (servise sorar), şimdi kur
uv run iplikci guncelleme mod otomatik | sor | kapali   # yeni sürüm çıkınca ne olacağı
(cd extension && npm ci && npm test && npm run build)   # eklenti; extension/dist ve pakete giren kopyası
(cd extension && npm run package)                # eklentinin mağaza paketi: iplikci-kopru-<sürüm>.zip
uv run python packaging/build.py                 # bu sistemin kurulum paketi ve güncelleme dosyası dist/paket/'e
uv run python packaging/release.py --tag vX.Y.Z --files dist/surum --notes dist/notlar.md   # imzalı sürüm bildirgesi
uv run python packaging/chrome_store.py iplikci-kopru-X.Y.Z.zip --deneme   # mağazaya ne yükleneceği, göndermeden
```

- `packaging/build.py`'den önce `web/` ve `extension/` derlenir; paket yapılmadan önce kurulan programla servis
  açılıp denenir. Bir sürümün yayını, imza anahtarı, iş akışının sırları ve Chrome Web Store adımları
  [sürüm yayını](yayin.md) belgesindedir.
- `iplikci servis kur | kaldir | yeniden-baslat` servisi sistemin servis yöneticisine kaydeder (macOS'ta launchd,
  Linux'ta systemd, Windows'ta Görev Zamanlayıcı). `kur` geliştirme klasöründen çalışmaz: servis, `uv tool install`
  ile kurulmuş sabit bir kopyayı çalıştırır. Böylece bir dal değişince ya da bir dosya yarım kalınca o kod gerçek
  veriyle çalışmaz.
- Eklentinin geliştirme ve doğrulama adımları [`extension/README.md`](../extension/README.md)'dedir. Deponun
  `.mcp.json`'u bu klasörde açılan Claude Code'u servisin `/mcp` adresine bağlar; belirteci `IPLIKCI_API_TOKEN` ortam
  değişkeninden okur.
- Veri klasörü macOS'ta `~/Library/Application Support/iplikci/`'dir; `IPLIKCI_HOME` onu değiştirir. Gerçek belgeler
  depoya hiç girmez: testler ve demo, kodla üretilen sahte belgelerle ve kendi klasörlerinde çalışır.

## Kurulum paketleri

Her sürümde "Paketler" iş akışı üç sistemin paketini yapar ve [sürüm sayfasında](https://github.com/msaidbilgehan/iplikci-nedim/releases/latest)
yayımlar. Son sürümün paketi, adında sürüm numarası olmadan hep aynı adrestedir:
[macOS (Apple Silicon)](https://github.com/msaidbilgehan/iplikci-nedim/releases/latest/download/iplikci-nedim-macos-aarch64.dmg),
[Windows](https://github.com/msaidbilgehan/iplikci-nedim/releases/latest/download/iplikci-nedim-windows-x86_64.exe),
[Linux](https://github.com/msaidbilgehan/iplikci-nedim/releases/latest/download/iplikci-nedim-linux-x86_64.AppImage).
Paketler imzasızdır (K22). 1.0 yalnızca macOS içindir; Windows ve Linux paketleri yapılır ama o sistemlerdeki
denemeler bekliyor (K25, K31).

- **macOS:** `.dmg` açılır, İplikçi Nedim "Applications" klasörüne sürüklenir. İlk açılışta macOS "“İplikçi Nedim”
  Açılmadı" der, çünkü uygulama Apple'a onaylatılmadı: "Bitti", sonra Sistem Ayarları → Gizlilik ve Güvenlik →
  "Yine de Aç" ve parola. Çöp kutusuna sürüklenen uygulama arka plan servisini de götürür: iki dakika içinde kaydını
  siler ve kapanır, veriler yerinde kalır.
- **Windows:** kurulum programı çalıştırılır. "Windows bilgisayarınızı korudu" uyarısında "Ek bilgi", sonra "Yine de
  çalıştır". Program yönetici izni istemeden kullanıcının klasörüne kurulur ve Başlat menüsünden açılır; Ayarlar →
  Uygulamalar'dan kaldırılır.
- **Linux:** AppImage dosyasının özelliklerinden program olarak çalıştırılmasına izin verilir ve dosyaya çift
  tıklanır. AppImage uygulama menüsüne kendisi girer.

Uygulama arka plan servisini bilgisayara kaydeder ve tarayıcıda kurulum sihirbazını açar; servis her oturum açılışında
kendiliğinden başlar. Ayarlar'daki "Kaldır" servisi bilgisayardan kaldırır; veri klasörü yalnızca istenirse çöp
kutusuna taşınır.

## README'nin görselleri

README'deki ekran görüntüleri ve hareketli görseller `docs/gorseller/`'dedir ve yalnızca demo veri klasöründen
çekilir: kodla üretilen sahte belgeler, gerçek veri yok. Arayüz değişince hepsi tek komutla yeniden üretilir:

```bash
(cd web && npm ci && npm run build) && (cd e2e && npm ci && npm run gorseller)
```

- Uçtan uca testlerin düzeni demo veri klasörünü kurar ve servisi kendi portunda çalıştırır (`e2e/global-setup.ts`);
  `e2e/gorseller/readme.spec.ts` her görselin hangi ekrandan, nasıl çekildiğini söyler. `npx playwright test` bu
  klasörü okumaz.
- Hareketli görseller Chrome'un ekran kaydıyla kare kare alınır ve ffmpeg ile GIF'e çevrilir; tıklayan iki görsel
  fare imlecini kendisi çizer. PNG'ler yalnızca piksellerini taşır (metin, saat, EXIF yok).
- Kurulum sihirbazının görseli boş bir veri klasöründe kendi servisiyle çekilir (`e2e/ownService.ts`). Bildirimler'in
  görseli demonun kurallarını değiştirdiği için en son çekilir.
- `yuzler.png` İplikçi Nedim'in dört yüzünü (`web/public/logo.png` ve `face-*.png`) yan yana koyar.
- Telefondan erişim henüz yok (Tailscale'li uzaktan erişim sonraki bir sürümde); README telefon görseli taşımaz.

## Belgeler

- [Belge dizini ve okuma sırası](README.md)
- [V1 gereksinimleri ve kararlar](v1/requirements.md)
- [Mimari](v1/architecture.md) · [Özellikler](v1/features.md) · [Yol haritası](v1/roadmap.md) ·
  [MVP'den geçiş](v1/migration.md)
- [Mimari karar kayıtları](adr/README.md)
- [Sürüm yayını ve güncellemeler](yayin.md)
- Geliştiriciler ve ajanlar için kurallar: [`CLAUDE.md`](../CLAUDE.md)
