# Değişiklik günlüğü

Biçim [Keep a Changelog](https://keepachangelog.com/tr-TR/1.1.0/)'a, sürüm numaraları
[anlamsal sürümlemeye](https://semver.org/lang/tr/) dayanır. Her aşama bir sürümle biter
([yol haritası](docs/v1/roadmap.md)).

## [0.1.0] — Aşama 0: Zemin (yayımlanmadı)

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
