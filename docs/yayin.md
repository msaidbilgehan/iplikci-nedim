# Sürüm yayını ve güncellemeler

Bir sürümün nasıl yayımlandığı, kurulu kopyaların onu nasıl bulup kurduğu ve eklentinin Chrome Web Store'a nasıl
gittiği. Kararlar [K29](v1/requirements.md#kararlar) ve [ADR-0022](adr/0022-releases-and-updates.md)'de, kullanıcıya
görünen özellik [F21](v1/features.md#f21--güncellemeler)'dedir. Bu belge geliştiriciler içindir; kullanıcı hiçbir adımda
terminal kullanmaz.

## Bir sürüm nasıl çıkar

1. `pyproject.toml` ve `src/iplikci/__init__.py`'deki sürüm yükseltilir, `CHANGELOG.md`'ye o sürümün bölümü yazılır
   (`## [X.Y.Z] — GG-AA-YYYY — Başlık`). Eklenti değiştiyse `extension/package.json`'un sürümü de yükselir.
2. `master`'a birleştirilir, `vX.Y.Z` etiketi atılır ve gönderilir.
3. "Paketler" iş akışı (`.github/workflows/packages.yml`) çalışır:
   - **paket** (macOS, Windows, Linux): `packaging/build.py` kurulum paketini ve güncelleme dosyasını yapar. Önce
     kurulan programla servisi boş bir veri klasöründe başlatır, yanıt ve sürüm bekler. Güncelleme dosyasını kurulu
     programın açacağı gibi açar, Python'unun sürümü söylemesini bekler.
   - **eklenti:** tip denetimi, testler ve `npm run package` (`iplikci-kopru-<sürüm>.zip`).
   - **surum:** `packaging/release.py` etiketi `pyproject.toml`'la karşılaştırır, her sistemin dosyası var mı bakar.
     Kurulum paketlerini sürüm numarası olmayan kararlı adlarına çevirir (aşağıda, "Sürümlerin yeri"). Bildirgeyi
     (`iplikci-nedim-surum.json`) yazar ve `UPDATE_SIGNING_KEY` ile imzalar; imzayı programın güvendiği anahtarla
     doğrular. Ardından `gh release create` sürümü dosyalarıyla açar; notu CHANGELOG'un bölümüdür. Son olarak her
     kararlı adres hesapsız indirilmeyi dener; olmazsa iş uyarı yazar.
   - **magaza:** `CWS_ITEM_ID` tanımlıysa `packaging/chrome_store.py` eklentiyi mağazaya yükler ve incelemeye
     gönderir; sürümü mağazadakinden yeni değilse yüklemez. Daha eski bir sürüm incelemedeyse hiçbir şey yüklemez ve iş
     başarısız olur: inceleme bitince bu iş yeniden çalıştırılır (Actions → çalışma → "Re-run failed jobs").
4. Kurulu kopyalar ertesi sabah (05.00'ten sonraki ilk fırsatta) yeni sürümü bulur. Ayarları "Kendiliğinden kur" ise
   önce yedek alır, sonra kurar.

İş akışı elle de çalıştırılabilir (`workflow_dispatch`): o zaman yalnızca derler, dosyaları iki hafta saklar ve hiçbir
şey yayımlamaz.

## Sırlar ve değişkenler

Deponun Settings → Secrets and variables → Actions sayfasında:

| Ad | Tür | Ne | Gerekli mi |
|---|---|---|---|
| `UPDATE_SIGNING_KEY` | sır | Bildirgeyi imzalayan Ed25519 gizli anahtarı (PEM, PKCS8) | Evet; yoksa sürüm yayımlanmaz |
| `RELEASE_REPO` | değişken | Sürümün konacağı depo, `sahip/depo` | Hayır; yoksa bu depo |
| `RELEASE_TOKEN` | sır | `RELEASE_REPO` başka bir depoysa, o depoda yalnızca "Contents: write" izni olan ince ayarlı belirteç | Yalnızca başka depoda |
| `CWS_ITEM_ID` | değişken | Eklentinin mağazadaki 32 harflik kimliği | Mağaza için; yoksa adım atlanır |
| `CWS_PUBLISHER_ID` | sır, `chrome-web-store` ortamında | Chrome Web Store geliştirici panosundaki yayıncı kimliği | Mağaza için |
| `CWS_SERVICE_ACCOUNT_KEY` | sır, `chrome-web-store` ortamında | Mağazaya yükleyen servis hesabının JSON anahtarı | Mağaza için |

`chrome-web-store` ortamına yalnızca `v*` etiketleri girer (Settings → Environments). Mağaza işi o ortamda çalışır;
başka bir iş ya da dal bu iki sırrı okuyamaz.

## İmza anahtarı

- Anahtarın adı `2026-11`. Açık anahtarı `src/iplikci/update/keys.py`'dedir. Gizli anahtarı yalnızca GitHub'daki
  `UPDATE_SIGNING_KEY` sırrında ve sahibinin macOS anahtar zincirinde durur (hizmet `iplikci-nedim-release`, hesap
  `update-signing-key-2026-11`). Depoya, bir dosyaya ya da günlüğe yazılmaz.
- GitHub sırrı okunamaz. Sır kaybolursa ya da depo değişirse anahtar zincirindeki kopyadan yeniden yazılır. macOS
  anahtar zincirine erişim için izin sorar. `security -w` satır sonu taşıyan bir parolayı onaltılık (hex) yazar;
  `xxd -r -p` onu PEM'e geri çevirir:

  ```bash
  security find-generic-password -s iplikci-nedim-release -a update-signing-key-2026-11 -w \
    | xxd -r -p | gh secret set UPDATE_SIGNING_KEY
  ```
- **Anahtar değiştirmek:** `release.py` bildirgeyi, sırdaki anahtarın `TRUSTED`'daki adıyla imzalar.
  1. Yeni anahtar üretilir; açık anahtarı `TRUSTED`'a yeni bir adla eklenir, eskisi de durur. Bu sürüm sır değişmeden,
     eski anahtarla imzalanarak çıkar: kurulu kopyalar onunla yeni anahtarı tanır.
  2. Sonraki sürümden önce `UPDATE_SIGNING_KEY` yeni anahtar olur; yeni anahtarın yedeği anahtar zincirine yazılır.
  3. Eski anahtar daha sonraki bir sürümde `TRUSTED`'dan çıkar.
- Anahtar her ikisi de kaybolursa kurulu kopyalar yeni sürümleri kabul etmez: yeni anahtarı taşıyan sürüm elle
  kurulmalıdır.

## Sürümlerin yeri

Kurulu kopyalar sürümü kimlik bilgisi olmadan indirir:
`https://github.com/<depo>/releases/latest/download/iplikci-nedim-surum.json`, sonra GitHub'ın dosya sunucusu. Depo
(`src/iplikci/update/source.py`'deki `REPO`) herkese açık olmalıdır.

- Kod deposu `msaidbilgehan/iplikci-nedim` herkese açıktır (2026-11-12'den beri) ve sürümler onun sürüm sayfasında durur
  ([K32](v1/requirements.md#kararlar)); `REPO` onu gösterir, iş akışı `RELEASE_REPO` ve `RELEASE_TOKEN` olmadan kendi
  deposuna yayımlar. Mağazanın istediği gizlilik politikası adresi depodaki `extension/store/privacy.md`'nin GitHub
  sayfasıdır; ayrı bir web sayfası şimdilik yoktur.
- **Ayrı sürüm deposunun kısa ömrü:** v0.11.1 sürümleri bir gecelik `msaidbilgehan/iplikci-nedim-surumler` deposunda
  aradı (K31). O sürümü kuran Mac'in 1.0.0'a kendiliğinden geçmesi için 1.0.0 bir kez de oraya konur; sonra depo
  kaldırılır. v0.10.0–v0.11.0 güncellemeyi kod deposunda arar ve 1.0.0'ı orada bulur.
- **Kurulum paketlerinin kararlı adları** ([ADR-0024](adr/0024-extension-leads-to-download.md)): her sürüm kurulum
  paketlerini sürüm numarası olmayan adlarla taşır. Son sürümün paketi bu yüzden hep aynı adrestedir:

  | Sistem | Adres |
  |---|---|
  | macOS (Apple Silicon) | `https://github.com/msaidbilgehan/iplikci-nedim/releases/latest/download/iplikci-nedim-macos-aarch64.dmg` |
  | Windows (x64) | `https://github.com/msaidbilgehan/iplikci-nedim/releases/latest/download/iplikci-nedim-windows-x86_64.exe` |
  | Linux (x64) | `https://github.com/msaidbilgehan/iplikci-nedim/releases/latest/download/iplikci-nedim-linux-x86_64.AppImage` |

  - Programı bulamayan tarayıcı eklentisi kullanıcıyı bu adreslere götürür; README de onlara bağlantı verebilir.
  - Bildirge kurulum paketlerini bu adlarla yazar. Windows'un kurulum programı güncelleme dosyası da olduğu için
    güncelleme girişi de bu adı taşır; macOS'un `.zip`'i ve Linux'un `.tar.gz`'si sürümlü adlarını korur. Kurulu
    kopyalar dosyayı bildirgedeki adla, sürümün etiketli adresinden (`releases/download/<etiket>/<ad>`) indirir.
  - Hangi sistemlerin paketinin bulunması gerektiği `packaging/release.py`'deki `OFFERED`'dadır: iş akışının
    makineleri. Biri eksikse sürüm yapılmaz. Eklentinin sabitleri (`extension/src/bridge/program.ts`) bunlarla ve
    `update/source.REPO` ile aynı kalır; testler denetler.
  - Kararlı adları taşıyan ilk sürüm 1.0.0'dır; ondan öncekilerin paketleri sürümlü adlarla durur.

## Bir sürümü elle doğrulamak

```bash
gh release download vX.Y.Z --pattern 'iplikci-nedim-surum.json*' --dir /tmp/surum
uv run python -c "
from pathlib import Path
from iplikci.update import manifest
d = Path('/tmp/surum')
m = manifest.verify((d / 'iplikci-nedim-surum.json').read_bytes(), (d / 'iplikci-nedim-surum.json.sig').read_bytes())
print(m.version, sorted(m.updates))
"
```

Kurulu bir kopyada: Ayarlar → Güncellemeler → "Şimdi denetle", ya da `iplikci guncelleme denetle` ve
`iplikci guncelleme durum`.

## Chrome Web Store

Mağaza metinleri, izinlerin gerekçeleri ve gizlilik politikası [`extension/store/`](../extension/store/README.md)'dadır.
Eklenti mağazada herkese açık listelenir: programın kapısıdır, programı olmayanı son kurulum paketine götürür
(kullanıcının 2026-11-14 kararı, [ADR-0024](adr/0024-extension-leads-to-download.md)).

**İlk yayın (elle, bir kez):**

1. Chrome Web Store geliştirici kaydı (tek seferlik ücret, Google hesabıyla, iki adımlı doğrulama açık).
2. Gizlilik politikasının herkese açık bir adresi.
3. Kurulum paketlerini kararlı adlarıyla taşıyan bir program sürümü herkese açık depoda yayımlanmış olmalı (yukarıda,
   "Sürümlerin yeri"); yoksa eklentinin indirme düğmesi GitHub'ın "bulunamadı" sayfasını açar.
4. Mağazaya ilk giden sürüm 0.9.0'dır (0.8.0 yüklenmez): `iplikci-kopru-0.9.0.zip` (GitHub sürümünden ya da
   `cd extension && npm run package`) geliştirici panosundan yüklenir; mağaza sayfası doldurulur; görünürlük: herkese
   açık.
5. İnceleme geçince eklentinin mağaza adresi `src/iplikci/app/extension.py`'deki `STORE_URL`'e yazılır ve bir sürüm
   çıkar: arayüz önce mağazayı gösterir (v1.0.1).

0.9.0 2026-11-15'te gönderildi, aynı gün incelemeden geçti ve herkese açık yayımlandı. Mağazadaki kimliği
`biegljgcnlkdokmfpdejecddgaekplof`, adresi <https://chromewebstore.google.com/detail/biegljgcnlkdokmfpdejecddgaekplof>;
v1.0.1'den beri `STORE_URL` odur. Gönderilenler [mağaza notlarında](../extension/store/README.md#gönderilen-2026-11-15).

**Sonraki sürümleri iş akışı yükler** (2026-11-15'ten beri kurulu):

1. Google Cloud'da yalnızca bunun için açılan `chrome-web-store-yayin` projesinde "Chrome Web Store API" etkindir.
2. Projede rolü olmayan bir servis hesabı (`cws-yayinci`) vardır. JSON anahtarı yalnızca deponun `chrome-web-store`
   ortamında ve sahibinin macOS anahtar zincirinde durur (hizmet `chrome-web-store`, hesap yayıncı kimliği). Depoya,
   bir dosyaya ya da günlüğe yazılmaz.
3. Servis hesabının e-posta adresi geliştirici panosunun Settings sayfasında, "Service account" bölümündedir
   (yayıncı başına bir servis hesabı). Yetkisi oradan gelir; panodan silinirse iş akışı yükleyemez.
4. Depoda `CWS_ITEM_ID` değişkeni, `chrome-web-store` ortamında `CWS_PUBLISHER_ID` ve `CWS_SERVICE_ACCOUNT_KEY`
   sırları vardır (yukarıda, "Sırlar ve değişkenler").
5. Deneme: `CWS_…` ortam değişkenleriyle `uv run python packaging/chrome_store.py <zip> --deneme` neyi yükleyeceğini
   söyler, hiçbir şey göndermez. 2026-11-15'te gerçek mağazaya karşı "0.9.0 mağazadakinden (0.9.0) yeni değil" dedi.

Geliştiricinin bilgisayarında aynı işleri Claude Code'un `chrome-web-store` becerisi yapar. Becerinin `cws.py`
betiği anahtarı anahtar zincirinden okur ve bütün eklentiler için çalışır. Mağazadaki durum (`status`), yükleme ve
incelemeye gönderme (`upload --submit`), ilk yayın ve mağaza sayfası gibi yalnızca panoda yapılanlar onunla yapılır.
Anahtar yenilenirken önce Google Cloud'da yeni anahtar oluşturulur; `cws.py setup-key` ve `cws.py github` onu anahtar
zincirine ve ortamın sırlarına yazar. Eski anahtar en son Google Cloud'dan silinir.

Panoda görünürlük elle değiştirilirse API ile yayın, yeni görünürlükle bir kez elle yayımlanana dek çalışmaz.
