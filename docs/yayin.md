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
   - **surum:** `packaging/release.py` etiketi `pyproject.toml`'la karşılaştırır, her sistemin dosyası var mı bakar,
     bildirgeyi (`iplikci-nedim-surum.json`) yazar ve `UPDATE_SIGNING_KEY` ile imzalar. İmzayı programın güvendiği
     anahtarla doğrular. Ardından `gh release create` sürümü dosyalarıyla açar; notu CHANGELOG'un bölümüdür.
   - **magaza:** `CWS_ITEM_ID` tanımlıysa `packaging/chrome_store.py` eklentiyi mağazaya yükler ve incelemeye
     gönderir; sürümü mağazadakinden yeni değilse yüklemez.
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
| `CWS_PUBLISHER_ID` | değişken | Chrome Web Store geliştirici panosundaki yayıncı kimliği | Mağaza için |
| `CWS_ITEM_ID` | değişken | Eklentinin mağazadaki 32 harflik kimliği | Mağaza için; yoksa adım atlanır |
| `CWS_SERVICE_ACCOUNT_KEY` | sır | Mağazaya yükleyen servis hesabının JSON anahtarı | Mağaza için |

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

- Kod deposu özel kaldıkça (K18) sürümler o depoda yalnızca depoya erişimi olanlarca görülür; kurulu kopyaların denetimi
  "sürümler henüz herkese açık bir yerde değil" der.
- İki yol var; seçim kullanıcınındır:
  - **Kod deposunu herkese açmak.** Ek ayar gerekmez. Önce bütün geçmiş kişisel veri için gözden geçirilir.
  - **Sürümler için ayrı, herkese açık bir depo** (ör. `iplikci-nedim-surumler`). İçinde bir README yeterlidir.
    `RELEASE_REPO` değişkeni o depoyu, `RELEASE_TOKEN` sırrı o depoya yazabilen belirteci tutar, `update/source.py`'deki
    `REPO` o depoya çevrilip bir sürüm çıkar. Mağazanın istediği gizlilik politikası da o deponun GitHub Pages'inde
    yayımlanabilir.

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

**İlk yayın (elle, bir kez):**

1. Chrome Web Store geliştirici kaydı (tek seferlik ücret, Google hesabıyla, iki adımlı doğrulama açık).
2. Gizlilik politikasının herkese açık bir adresi.
3. Son sürümün `iplikci-kopru-<sürüm>.zip` dosyası (GitHub sürümünden ya da `cd extension && npm run package`)
   geliştirici panosundan yüklenir; mağaza sayfası doldurulur; görünürlük: listelenmemiş.
4. İnceleme geçince eklentinin mağaza adresi `src/iplikci/app/extension.py`'deki `STORE_URL`'e yazılır ve bir sürüm
   çıkar: arayüz önce mağazayı gösterir.

**Sonraki sürümleri iş akışı yükler** (isteğe bağlı):

1. Google Cloud'da bir proje açılır, "Chrome Web Store API" etkinleştirilir.
2. Bir servis hesabı oluşturulur (rol gerekmez) ve JSON anahtarı indirilir.
3. Geliştirici panosunun Account sayfasına servis hesabının e-posta adresi eklenir (yayıncı başına bir servis hesabı).
4. Depoya `CWS_PUBLISHER_ID` ve `CWS_ITEM_ID` değişkenleri ve `CWS_SERVICE_ACCOUNT_KEY` sırrı eklenir.
5. Deneme: `CWS_…` ortam değişkenleriyle `uv run python packaging/chrome_store.py <zip> --deneme` neyi yükleyeceğini
   söyler, hiçbir şey göndermez.

Panoda görünürlük elle değiştirilirse API ile yayın, yeni görünürlükle bir kez elle yayımlanana dek çalışmaz.
