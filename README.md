# İplikçi Nedim

İngilizce alternatif adı: **Money-Grubber**. Adını bir filmde paraları tutan karakterden alır.

Depo: <https://github.com/msaidbilgehan/iplikci-nedim> · Komut ve Python paketi kısa adla `iplikci`'dir.

Kişisel finans asistanı platformu:

- Bankaların e-postayla gönderdiği ekstreleri, dekontları, bildirimleri ve ödeme hatırlatmalarını kendiliğinden
  toplar, doğrular ve belgeleriyle birlikte saklar.
- Harcamaları, gelirleri, hesapları, abonelikleri ve döviz varlıklarını yorumlar.
- Aylık raporların yanında güncel akışı da anlık izletir; her rakamdan dayandığı belgeye gidilebilir.
- Bilgisayarda bir servis olarak çalışır; tarayıcıdan (PWA) ve MCP üzerinden Claude ile kullanılır.

## Durum

Uygulama [yol haritası](docs/v1/roadmap.md)'nı izler. Aşama 0 (Zemin, v0.1.0) başlangıç sürümünün (MVP,
`gider-analizi`) kodunu `iplikci` paketi olarak depoya getirdi. Kod kişisel izlerden temizlendi; uygulamayla gelen genel
kategori kuralları, bir doğrulama tabanı ve sahte belgelerle bir demo çalışma alanı eklendi.

Aşama 1 (Veri çekirdeği, v0.2.0) her şeyi bilgisayardaki veri klasörüne taşıdı:

- Belgeler içerik adresli bir arşivde aslıyla durur.
- Okunan satırlar ve kullanıcının düzeltmeleri SQLite veritabanındadır.
- Tutarlar kesin ondalık sayılardır.
- Arşivin bozulmadığı ve veritabanının arşivden aynen yeniden kurulabildiği birer komutla denetlenir.

Aşama 2 (Okuyucu eklentileri, v0.3.0) belgeleri okuyan okuyucuları ayrı eklentilere çevirdi:

- Her belgeyi tanıyan tek bir okuyucu okur; iki okuyucu tanırsa belge "okunamadı" olur, sıraya bırakılmaz.
- Her okuyucunun kendi sürümü vardır: bir okuyucu değişince yalnızca onun belgeleri yeniden okunur.
- Belgeler ayrı bir süreçte, süre ve bellek sınırıyla okunur; bozuk bir belge uygulamayı durduramaz.
- Her satır, belgede yazdığı yeri (sayfa ve kutu, satır ya da tablo satırı) bilir.
- Bir banka biçimini değiştirirse biçim alarmı kaydedilir.
- Her okuyucunun kodla üretilen sahte belgeleri ve testleri vardır.

Sıradaki Aşama 3, servistir.

MVP 2026-10-31'de emekliye ayrıldı. İplikçi Nedim onun kodundan başlar ama verisini devralmaz; belgeleri kendisi toplar.
Uygulama henüz son kullanıcıya hazır değil: kurulum sihirbazı ve arayüz sonraki aşamalarda gelir.

## Belgeler

- [Belge dizini ve okuma sırası](docs/README.md)
- [V1 gereksinimleri ve kararlar](docs/v1/requirements.md)
- [Mimari](docs/v1/architecture.md) · [Özellikler](docs/v1/features.md) · [Yol haritası](docs/v1/roadmap.md) ·
  [MVP'den geçiş](docs/v1/migration.md)
- [Mimari karar kayıtları](docs/adr/README.md)
- Geliştiriciler ve ajanlar için kurallar: [`CLAUDE.md`](CLAUDE.md)

## Geliştiriciler için

Son kullanıcı terminal kullanmaz; aşağıdaki komutlar geliştirme içindir. Gerekenler: [uv](https://docs.astral.sh/uv/)
ve [gitleaks](https://github.com/gitleaks/gitleaks).

```bash
uv sync                                          # Python 3.13 ve kilitli bağımlılıklar
uv run pre-commit install                        # her commit'ten önce ruff ve gitleaks
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
```

Veri klasörü macOS'ta `~/Library/Application Support/iplikci/`'dir; `IPLIKCI_HOME` onu değiştirir. Gerçek belgeler
depoya hiç girmez: testler ve demo, kodla üretilen sahte belgelerle ve kendi klasörlerinde çalışır.

## İlkeler

- Banka akışları esastır: her para hareketi bir banka belgesine dayanır; diğer e-postalar kanıt ve bilgi katmanıdır.
- Yerel öncelik: belgeler ve veriler bu bilgisayarda, deponun dışındaki veri klasöründe durur. Ağa yalnızca e-posta
  okumak, döviz kurlarını almak ve bildirim göndermek için çıkılır.
- Yalnızca kişisel para hareketleri; şirket belgeleri kapsam dışıdır.
- Hiçbir belge kalıcı silinmez.
- Finanstan anlayan da anlamayan da kullanmak istemeli.
- Kişisel ihtiyaçlar için yapılan bir hobi projesi, kurumsal bir ürün değil; yine de her kullanıcıya azami verim
  sağlamalı.

## Lisans

[BSD 3-Clause](LICENSE.txt).
