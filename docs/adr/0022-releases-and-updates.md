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
  - `auto` (varsayılan): üç saatte bir denetler, yeni sürümü bulunca hemen kendiliğinden kurar;
  - `ask`: üç saatte bir denetler, yeni sürümü her ekranın üstünde sorar; kullanıcı "Şimdi güncelle" deyince kurar;
  - `off`: GitHub'a hiç sormaz; kullanıcı "Şimdi denetle" derse bir kez sorar.

  Demo veri klasörü `off` ile kurulur.
- **Denetim** (`update.check` işi, gece yarısından sayılan üç saatlik dilimlerin her birinde bir kez; bilgisayar
  uyurken kaçan dilim uyanınca bir kez; v1.0.11'den önce her gün 05:00'ten sonraki ilk fırsatta):
  - Bildirge ve imzası indirilir. İmza programın bildiği bir anahtarla doğrulanmazsa hiçbir şey kurulmaz; Sistem ve
    Ayarlar sorunu söyler.
  - Ürün adı tutmalı, sürüm çalışandan yeni olmalıdır: eski bir bildirge geri döndüremez.
  - Bu sistemin güncelleme dosyası yoksa (ör. Intel Mac) "bu sistem için güncelleme dosyası yok" denir.
- **Kurulum** (`update.install` işi; aynı anda bir tane):
  - Kuyruğa girdiği andan bitene dek ekranlar sürümü "kuruluyor" diye gösterir. Bir kurulum kuyruktayken ya da
    sürerken ikinci bir istek (denetimin ya da kullanıcının) yeni iş eklemez.
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
  - macOS ve Linux'ta servis 75 koduyla biter, servis yöneticisi onu yeni sürümle başlatır. Bu sırada iş kuyruğundan
    başka iş alınmaz: kuyrukta kalanı yeni sürüm yapar.
- **Bitiş:** yeni sürüm açılırken sonucu yazar (hangi sürümden hangisine, ne zaman). Eski programın dosyalarını
  kaldırır: macOS'ta eski `Contents`, Linux'ta eski kopyalar. Bunlar belge değildir. Kurulan sürüm açılmadıysa sonuç
  hata olarak kalır; aynı sürüm kendiliğinden ikinci kez denenmez.
- **Elle kurulan kopya** (`uv tool install`, geliştirme kopyası) güncellenmez; yeni sürüm yalnızca haber verilir.
- **Ağ:** yalnızca GET. `github.com`'dan başlar; yalnızca `github.com`, `release-assets.githubusercontent.com` ve
  `objects.githubusercontent.com`'a giden yönlendirmeler izlenir. Giden veri yalnızca isteğin kendisidir: hesap,
  belirteç, sürüm dışında bilgi yoktur.

### Eklentinin güncellenmesi

- Mağazadan kurulan eklentiyi Chrome günceller.
- İlk yayın kullanıcının elle yaptığıdır: geliştirici kaydı, mağaza sayfası ve herkese açık görünürlük (kullanıcının
  2026-11-14 kararı; önce listelenmemiş düşünülmüştü, [ADR-0024](0024-extension-leads-to-download.md)). Sonra sürüm
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
  - GitHub'a üç saatte bir istek gider (günde en çok sekiz): kullanıcının IP adresi GitHub'a görünür. Ayarlar'dan
    kapatılır.
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
deposunda yayımlanır. `update/source.REPO` v0.11.1'de onu gösterir; iş akışı `RELEASE_REPO` ve `RELEASE_TOKEN` ile
oraya yayımlar. Depo, paketlenmiş uygulama kullanıcının Mac'inde denendikten sonra açılır. (Ertesi gün K32 bunu
değiştirdi; aşağıdaki nota bakın.)

## Not (2026-11-14, ADR-0024)

- Sürüm işi kurulum paketlerini yayımlamadan önce sürüm numarası olmayan adlarla yeniden adlandırır
  (`iplikci-nedim-macos-aarch64.dmg`, `iplikci-nedim-linux-x86_64.AppImage`, `iplikci-nedim-windows-x86_64.exe`).
  Böylece `releases/latest/download/<ad>` her zaman son sürümün paketidir. Programı bulamayan eklenti kullanıcıyı
  oraya götürür ([ADR-0024](0024-extension-leads-to-download.md)).
- Bildirge kurulum paketlerini bu adlarla yazar. Windows'un kurulum programı güncelleme dosyası da olduğundan
  güncelleme girişi de onu bu adla yazar; macOS'un ve Linux'un güncelleme dosyaları sürümlü adlarını korur. Kurulu
  kopyalar dosyayı sürümün etiketli adresinden, bildirgenin yazdığı adla indirir; adlar onlar için bir şey değiştirmez.
- Eklentinin sunduğu sistemlerden birinin paketi eksikse sürüm yapılmaz. Yayımlandıktan sonra iş akışı her kararlı
  adresi hesapsız indirmeyi dener; olmazsa uyarı yazar.

## Not (2026-11-15, K32)

Kullanıcı ayrı bir sürüm deposu istemedi: sürümler kod deposu `msaidbilgehan/iplikci-nedim`'in sürüm sayfasında
yayımlanır. Kod deposu 2026-11-12'de, geçmişi temizlenip yeniden kurulduğunda herkese açık oluşturulmuştu; özel
sanılması (K18) ayrı depoya yol açmıştı. `update/source.REPO` kod deposudur; iş akışı `RELEASE_REPO` ve
`RELEASE_TOKEN` olmadan kendi deposuna yayımlar (değişkenler başka bir depo için durur). 2026-11-15'te bütün geçmiş
veri klasöründeki değerlerle, genel kişisel veri kalıplarıyla ve gitleaks'le yeniden tarandı; kişisel veri çıkmadı.
v0.10.0–v0.11.0 güncellemeyi zaten kod deposunda arar. v0.11.1'i kuran tek Mac'in uygulaması 1.0.0'ı bir kez de
`iplikci-nedim-surumler`'den alır; kendini güncellemesi böylece gerçek bir Mac'te denenir. Sonra o depo kaldırılır.

## Not (2026-11-15, mağazaya yükleme)

Eklentinin yeni sürümlerini iş akışı yükler. Google Cloud'da yalnızca bunun için açılan bir projede rolü olmayan bir
servis hesabı vardır; yetkisini geliştirici panosunun Settings → Service account bölümü verir (yayıncı başına bir
servis hesabı). Anahtarı eklentinin kullanıcılarına bir sürüm gönderebilir. Bu yüzden anahtar ve yayıncı kimliği
deponun değil, yalnızca `v*` etiketlerinin girebildiği `chrome-web-store` ortamının sırlarıdır. Herkese açık deponun
günlüklerinde yayıncı kimliği de görünmez. Eklentinin mağaza kimliği (`CWS_ITEM_ID`) herkese açıktır ve depo
değişkenidir: işin koşulu onu ortamdan önce okur. Eski bir sürüm incelemedeyken yeni sürüm yüklenmez. İş bunu söyleyip
başarısız olur; inceleme bitince iş yeniden çalıştırılır. İncelemedeki sürümü geri çekmek incelemeyi baştan başlatır,
iş akışı bunu hiç yapmaz.

## Not (2026-11-23, güncellemenin akışı)

1.0.10'un gelişinde kullanıcı iki şey gördü. "Önce bana sor"dayken öğleden sonra yayımlanan sürüm ne Ayarlar'da ne
Pano'da göründü: servis günde bir, 05:00'te bakıyordu. "Kendiliğinden kur"a geçip "Şimdi denetle"ye basınca
Ayarlar yine "Şimdi güncelle" düğmesini gösterdi. Kurulum kuyruktaydı ama iş başlayana dek ekran onu bilmiyordu.
Düğmeye basılınca aynı sürüm için ikinci bir kurulum kuyruğa girdi. İlk kurulum servisi yeniden başlatırken iş
kuyruğu ikinciyi de aldı; sürüm ikinci kez kuruldu.

O günden beri:

- Servis üç saatte bir bakar.
- Kuyruktaki ya da süren kurulum "kuruluyor" sayılır ve ikinci bir kurulum eklenmez.
- Kurulum servisi yeniden başlatınca iş kuyruğundan başka iş alınmaz.
- "Önce bana sor"da yeni sürüm, Ayarlar dışında her ekranın üstünde bir şeritle sorulur.

Gün içinde kendiliğinden kurulan bir sürüm servisi birkaç saniye durdurur. Açık sayfa yeniden bağlanır ve yeni
arayüzle kendini bir kez yeniler (v0.7.3). O sırada süren bir "Gmail'de eksikleri tara" durur ve yeniden
başlatılabileceğini söyler; yeniden başlatılınca eksikleri getirir.

