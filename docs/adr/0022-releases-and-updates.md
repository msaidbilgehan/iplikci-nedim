# ADR-0022: Sürümler GitHub'da yayımlanır; uygulama imzalı bildirgeyle kendini, eklentiyi mağaza günceller

Durum: Kabul edildi · Tarih: 2026-11-10 · Dayanak: K29, K14, K22 · [ADR-0009](0009-network-egress-policy.md)'un
"güncelleme denetimi yoktur" maddesini, [ADR-0017](0017-no-terminal-install.md)'nin güncelleme bölümünü ve
[ADR-0016](0016-mail-connectors.md)'nın K20 notunu değiştirir

## Bağlam

- Kullanıcı 2026-11-10'da uygulamanın ve tarayıcı eklentisinin GitHub'da derlenip kendiliğinden güncellenmesini
  istedi; eklentiyi Chrome Web Store'da yayımlayacak (K29).
- Kurulum paketleri her sürüm etiketinde CI'da üç sistem için derleniyordu, ama yalnızca iş akışının iki hafta duran
  çıktısı oluyordu. Yeni bir sürüm, paketi yeniden indirip açmakla kuruluyordu (ADR-0017). ADR-0009 güncelleme
  denetimini dışarıda bırakmıştı.
- Paketler imzasızdır (K22): işletim sistemi bir güncellemenin kimden geldiğini denetlemez. İndirilen program,
  kullanıcının bütün banka verisini okuyan servisin yerine geçer. Neyin kurulacağına uygulamanın kendisi karar vermeli.
- Depo özeldir (K18). Özel bir deponun sürüm dosyaları ancak giriş yapmış bir hesapla indirilir.
- Chrome, mağaza dışından eklenti kurdurmaz (Windows ve macOS'ta kurumsal ilke olmadan). Mağazadaki eklentiyi tarayıcı
  kendisi günceller. Mağazanın API'si (v2) yeni bir sürümü yükleyip incelemeye gönderir; yeni bir öğeyi oluşturmaz.

## Karar

### Yayın

- Bir sürüm etiketi (`vX.Y.Z`) "Paketler" iş akışını başlatır. Etiket `pyproject.toml`'un sürümüyle aynı olmalıdır.
- Her sistem kendi makinesinde derlenir: kurulum paketi (macOS `.dmg`, Windows kurulum programı, Linux AppImage) ve
  güncelleme dosyası (macOS'ta `ditto` ile sıkıştırılmış `.app`, Linux'ta Python klasörünün `.tar.gz`'si, Windows'ta
  kurulum programının kendisi). Paket, kurulu Python'uyla servisi boş bir veri klasöründe başlatıp yanıt aldıktan
  sonra çıkar: açılamayan bir sürüm yayımlanmaz.
- Eklentinin mağaza paketi (`iplikci-kopru-<sürüm>.zip`) derlenir, testleri geçer.
- Sürüm işi bunları bir GitHub sürümüne koyar. Notu `CHANGELOG.md`'nin o sürümün bölümüdür.
- Sürümle birlikte bir bildirge yayımlanır: `iplikci-nedim-surum.json`. Bildirge ürünü, sürümü, etiketi, günü, notu,
  her sistemin güncelleme dosyasının ve kurulum paketinin adını, boyutunu ve SHA-256'sını, eklentinin sürümünü ve
  paketini yazar.
- Bildirge Ed25519 ile imzalanır (`iplikci-nedim-surum.json.sig`: anahtarın adı ve imza).
  - Gizli anahtar yalnızca GitHub Actions'ın sırrında (`UPDATE_SIGNING_KEY`) ve sahibinin anahtar zincirinde durur.
    Depoya, günlüğe ya da bir dosyaya yazılmaz.
  - Açık anahtar programın içindedir (`update/keys.py`). Sürüm işi imzayı yayımlamadan önce bu anahtarla doğrular:
    sır programın güvendiği anahtar değilse sürüm yayımlanmaz.
  - Anahtar değişirken yeni anahtar önce bir sürümle programa eklenir, eski anahtarla imzalanan son sürümden sonra
    çıkarılır.
- Sürümün hangi depoya konacağı iş akışının değişkenidir (`RELEASE_REPO`; yoksa bu depo). Başka bir depo için sırrı
  `RELEASE_TOKEN` olur. Programın sorduğu depo programın içindedir (`update/source.py`).
- **Görünürlük:** kurulu kopyalar sürümü kimlik bilgisi olmadan indirir; bu yüzden sürümlerin durduğu depo herkese
  açık olmalıdır. Kod deposu özel kalabilir (K18): o zaman sürümler herkese açık ayrı bir depoya konur. Hangisinin
  seçileceği kullanıcının kararıdır. Karar verilene dek sürümler bu depoya konur ve programın denetimi "güncelleme
  kaynağına ulaşılamadı" der.

### Uygulamanın güncellenmesi

- **Ayar:** `[updates] mode`:
  - `auto` (varsayılan): günde bir denetler, yeni sürümü kendiliğinden kurar;
  - `ask`: denetler ve haber verir, kullanıcı "Şimdi güncelle" deyince kurar;
  - `off`: GitHub'a hiç sormaz; kullanıcı "Şimdi denetle" derse bir kez sorar.

  Demo veri klasörü `off` ile kurulur.
- **Denetim** (`update.check` işi, her gün 05:00'ten sonraki ilk fırsatta):
  - Bildirge ve imzası indirilir. İmza programın bildiği bir anahtarla doğrulanmazsa hiçbir şey kurulmaz; Sistem ve
    Ayarlar sorunu söyler.
  - Ürün adı tutmalı, sürüm çalışandan yeni olmalıdır: eski bir bildirge geri döndüremez.
  - Bu sistemin güncelleme dosyası yoksa (ör. Intel Mac) "bu sistem için güncelleme dosyası yok" denir.
- **Kurulum** (`update.install` işi):
  - Bildirge yeniden indirilip doğrulanır. Dosya akışla indirilir; boyutu ve SHA-256'sı bildirgeyle aynı olmalıdır.
  - Önce bir yedek alınır (neden: güncelleme).
  - Yeni program yerine konmadan önce kendi Python'uyla açılır ve sürümünü söyler.
  - Ardından sisteme göre:
    - **macOS:** paket `.app`'in içine açılır, `Contents` klasörü yenisiyle tek adımda yer değiştirir
      (`renamex_np` ile; olmazsa iki ad değiştirme). Uygulamanın yolu değişmez; servis kaydı aynı kalır.
    - **Linux:** Python klasörü `~/.local/lib/iplikci/<sürüm>`'e açılır (AppRun'un kopyaladığı yer); systemd birimi
      yeni Python'u başlatacak biçimde yeniden yazılır. Eski AppImage açılırsa en yeni kopyayı çalıştırır.
    - **Windows:** kurulum programı sessiz çalıştırılır (`/VERYSILENT`). Servisi kendisi durdurur, dosyaları
      değiştirir, sonra uygulamayı tarayıcı açmadan çalıştırır; uygulama servisi yeniden kaydeder.
  - macOS ve Linux'ta servis 75 koduyla biter, servis yöneticisi onu yeni sürümle başlatır.
- **Bitiş:** yeni sürüm açılırken sonucu yazar (hangi sürümden hangisine, ne zaman). Eski programın dosyalarını
  kaldırır: macOS'ta eski `Contents`, Linux'ta eski kopyalar. Bunlar belge değildir. Kurulan sürüm açılmadıysa sonuç
  hata olarak kalır; aynı sürüm kendiliğinden ikinci kez denenmez.
- **Elle kurulan kopya** (`uv tool install`, geliştirme kopyası) güncellenmez; yeni sürüm yalnızca haber verilir.
- **Ağ:** yalnızca GET. `github.com`'dan başlar; yalnızca `github.com`, `release-assets.githubusercontent.com` ve
  `objects.githubusercontent.com`'a giden yönlendirmeler izlenir. Giden veri yalnızca isteğin kendisidir: hesap,
  belirteç, sürüm dışında bilgi yoktur.

### Eklentinin güncellenmesi

- Mağazadan kurulan eklentiyi Chrome günceller.
- İlk yayın kullanıcının elle yaptığıdır: geliştirici kaydı, mağaza sayfası ve listelenmemiş görünürlük. Sonra sürüm
  iş akışı, değişkenler (`CWS_PUBLISHER_ID`, `CWS_ITEM_ID`) ve servis hesabının anahtarı (`CWS_SERVICE_ACCOUNT_KEY`)
  tanımlıysa eklentinin yeni sürümünü mağazaya yükler ve incelemeye gönderir. Sürümü mağazadakinden yeni değilse
  yüklemez. Tanımlı değilse bu adım atlanır.
- Eklentinin mağaza kimliği bilinince programa yazılır (`app/extension.STORE_URL`); arayüz önce mağazayı gösterir.
- Paketlenmemiş yüklenen eklenti, servisin taşıdığı sürüm kendininkinden yeniyse kendini bir kez yeniden yükler
  (`chrome.runtime.reload`). Veri klasöründeki kopya program güncellenince yenilendiği için yeni sürüm yüklenir.
  Yeni sürüm gelmezse bu sürüm için bir daha denenmez.

## Sonuçlar

- Olumlu:
  - Kullanıcı hiçbir şey yapmadan güncel kalır; güncellemeden önce verisinin yedeği vardır.
  - Kurulan her bayt, programın içindeki anahtarla imzalanmış bildirgede yazılıdır. GitHub hesabına sızan bir belirteç
    sürüme dosya koysa da kurulmaz.
  - Açılamayan bir paket yayımlanmaz.
- Olumsuz:
  - GitHub'a günde bir istek gider: kullanıcının IP adresi GitHub'a görünür. Ayarlar'dan kapatılır.
  - Sürümlerin herkese açık bir yerde durması gerekir.
  - İmza anahtarı kaybolursa kurulu kopyalar yeni sürümü kabul etmez; paket yeniden elle kurulur. Anahtarın yedeği
    sahibinin anahtar zincirindedir.
  - Windows ve Linux'taki güncelleme yolu, o sistemlerin denemesiyle birlikte denenecektir (K25).

## Değerlendirilen seçenekler

- **Bildirgesiz, yalnızca HTTPS ve GitHub:** GitHub'a sızan bir belirteç sürüme istediği dosyayı koyabilirdi.
- **Sigstore ya da GitHub'ın kanıtları (attestation):** doğrulama ağda başka sunucular ve büyük kütüphaneler ister.
- **Kod imzalama:** ücretlidir (K22) ve güncellemenin kendisini denetlemez.
- **Programın tekerleğini kurulu Python'a pip ile kurmak:** bağımlılıklar ve derlenmiş parçalar sistemden sisteme
  değişir; yarım kalan bir kurulum programı bozar. Bütün çalışma ortamını değiştirmek kurulum paketinin yaptığıdır.
- **Eklentiyi kendi sunucumuzdan güncellemek (`update_url`):** Chrome mağaza dışındaki eklentiyi kurdurmaz.

## Not (2026-11-14, K31)

Sürümlerin yeri seçildi: kod deposu özel kalır, sürümler herkese açık `msaidbilgehan/iplikci-nedim-surumler`
deposunda yayımlanır. `update/source.REPO` v0.11.1'den beri onu gösterir; iş akışı `RELEASE_REPO` ve `RELEASE_TOKEN`
ile oraya yayımlar. Depo, paketlenmiş uygulama kullanıcının Mac'inde denendikten sonra açılır.
