# Değişiklik günlüğü

Biçim [Keep a Changelog](https://keepachangelog.com/tr-TR/1.1.0/)'a, sürüm numaraları
[anlamsal sürümlemeye](https://semver.org/lang/tr/) dayanır. Her aşama bir sürümle biter
([yol haritası](docs/v1/roadmap.md)).

## [0.2.0] — 2026-11-01 — Aşama 1: Veri çekirdeği

### Eklenenler

- Veri klasörü: macOS'ta `~/Library/Application Support/iplikci/`, Linux'ta XDG, Windows'ta `LOCALAPPDATA`;
  `IPLIKCI_HOME` onu değiştirir. Klasörler yalnızca kullanıcıya açıktır (0700).
- `settings.toml`: her bölüm denetlenir. Bilinmeyen ya da yanlış bir anahtar, adını ve düzeltmesini söyleyen bir
  hatadır. Sırlar sistemin anahtar zincirinde (`iplikci` hizmeti), anahtar zinciri olmayan sistemde ortam değişkeninde.
- Belge arşivi: her belge bir kez, sha256'sıyla ve salt okunur saklanır. Bozulan nesne raporlanır, üzerine yazılmaz;
  kaldırılan belge sistemin çöp kutusuna gider.
- SQLite veritabanı (WAL, numaralı göçler): belgeler ve gelişleri, okunan satırlar, dekont kanıtları, düzeltmeler,
  denetim kaydı ve tam metin arama. Tutarlar en küçük birimde tamsayıdır.
- Tek alım yolu: gelen klasörü, kullanıcının verdiği yollar ve e-posta ekleri önce dokunmayan bir plandan, sonra tam o
  plandan geçer. Kayıtlı bir ekstrenin başka bir dosyası "kopyası" olarak tutulur ve defterde birleşir.
- İşlem parmak izi: hesap, gün, tutar, para birimi, sadeleştirilmiş açıklama ve benzer satırlar arasındaki sıra.
- `iplikci islem ara | duzelt | yetimler`: bir işleme not, etiket, kategori ya da gereklilik düzeltmesi. Düzeltme
  belgeler yeniden okununca da kalır; hiçbir satırın taşımadığı düzeltme silinmez, gösterilir.
- `iplikci dogrula --arsiv`: arşivi yeniden özetler ve veritabanını onunla karşılaştırır.
- `iplikci dogrula --yeniden-kur`: veritabanını arşivden ve birincil verilerden yanında yeniden kurar, sonucun aynı
  çıktığını denetler.
- Kural katmanları: kişisel kurallar (`rules/personal.yaml`) uygulamayla gelen genel kuralların üstüne biner.
- `Money` ve `Quantity` tipleri, İngilizce alan kodları ve Türkçe etiketleri tek bir modülde.
- Geliştirme: pyright (yeni paketlerde katı) ve hypothesis, sabit sürümlü; pyright CI'da da çalışır.

### Değişenler

- MVP'nin çalışma alanı (`ayarlar.toml`, `kategoriler.yaml`, `cikti/`) yerine veri klasörünün düzeni geldi. Rapor,
  CSV, Excel ve ay sonu sayfaları `exports/`'a, doğrulama tabanı `baseline.json`'a yazılır.
- Tutarlar `float` yerine kesin ondalık sayı (`Decimal`); belgeden okunan tutar iki haneye, buçuklar yukarı yuvarlanır.
  Demonun tabanı, CSV ve Excel çıktısı değişmedi. Tam lira gösterimi de buçukları yukarı yuvarlar.
- Alan kodları İngilizce, lira ISO koduyla (`TRY`) taşınır. Kullanıcının okuduğu her yer Türkçe etiketleri yazar.
- Ekstre kontrolü en çok 1 kuruş farka izin verir; MVP'nin 0,015 eşiğiyle aynı sonuç.
- Okuyucuların sürümü 14 oldu: kayıtlı her belge yeniden okunur.
- E-postayla gelen belgeler doğrudan arşive girer ve bildirilir.

### Kaldırılanlar

- MVP'nin okuma önbelleği (`cikti/.onbellek.json`), düzenleyicisi ve işlem hattı; yerlerini arşiv, veritabanı ve alım
  aldı.

## [0.1.0] — 2026-11-01 — Aşama 0: Zemin

### Eklenenler

- MVP'nin (`gider-analizi`) kodu ve testleri `iplikci` paketi olarak depoda; komut `iplikci`.
- `iplikci dogrula --taban`:
  - belgelerin doğrulama tabanını alır ve kayıtlı tabanla karşılaştırır,
  - gerilemede 1 ile biter ve kayıtlı tabanı korur.
- `iplikci dev demo`: sahte banka belgeleriyle bir demo çalışma alanı kurar. Tabanı testlerde altın dosyadır.
- Uygulamayla gelen genel kategori kuralları: `src/iplikci/rules/default.yaml`.
- Şirket adları ayardan gelir: `ayarlar.toml` içinde `[identity] business_names`. Adın hukuki biçimi (A.Ş., Ltd. Şti.)
  nasıl yazılırsa yazılsın eşleşir; adlar değişince okuma önbelleği yenilenir.
- `IPLIKCI_HOME` çalışma alanının klasörünü belirler.
- Lisans: BSD 3-Clause (`LICENSE.txt`).
- Geliştirme ortamı:
  - uv projesi ve ruff,
  - pre-commit (ruff, gitleaks),
  - GitHub Actions: Linux'ta ruff, pytest ve gitleaks; macOS'ta pytest.

### Değişenler

- Teknik adlar `iplikci` oldu:
  - e-posta şifresi değişkeni `IPLIKCI_MAIL_PASSWORD`,
  - anahtar zinciri hizmeti `iplikci`,
  - `com.iplikci.*` etiketleri ve `X-Iplikci` başlığı,
  - panel portu 8643.
- Ekstre açıklamalarının sonundaki yer adları:
  - bütün iller ve sık görülen fatura şehirleri kırpılır,
  - soyadı da olan il adları (Aydın, Bingöl, Karaman, Tokat) kırpılmaz.
- Kod `ruff format` ile biçimlendirildi.

### Kaldırılanlar

- Kodda, testlerde ve yorumlarda kalan kişisel izler: şirket adı, gerçek ekstrelerden kalan yerler ve tutarlar, kart ön
  ekleri, bir portföy satırı ve abonelik geçmişi.
