# Geçiş: MVP'den İplikçi Nedim'e

Proje: İplikçi Nedim · Durum: MVP emekliye ayrıldı, kodu Aşama 0'da alındı · Tarih: 2026-10-31 · İlgili belgeler:
[yol haritası](roadmap.md), [ADR-0013](../adr/0013-mvp-migration.md), [ADR-0018](../adr/0018-retire-mvp-clean-start.md),
[mimari](architecture.md)

MVP 2026-10-31'de emekliye ayrıldı ([K17](requirements.md#kararlar)). İplikçi Nedim veriyi kendisi toplar: MVP'nin
belge klasörleriyle (`Bankalar/`, `Gelen Belgeler/`), çıktılarıyla ve taşıma kayıtlarıyla çalışmaz. Bu belge MVP'den
neyin alındığını ve V1'in geçmişi nasıl kendisi kurduğunu anlatır.

## İlkeler

- **Kod alınır, veri alınmaz.**
  - V1 yalnızca kendi topladığı belgelerle çalışır. Kaynakları tarayıcı eklentisi, IMAP, gelen klasörü, Telegram botu
    ve arayüzden yüklemedir.
  - MVP'den yalnızca kod, testler ve genel kategori kuralları alınır (Aşama 0).
- **Kalıcı silme yok.** Kaldırılan her şey sistemin çöp kutusuna taşınır ve her taşıma bir kayda yazılır.
  - Kalıcı silme yalnızca kullanıcı çöp kutusunu boşalttığında olur; sistem çöp kutusunu hiçbir zaman kendisi
    boşaltmaz.
  - Tek istisna sırlardır: düz metin bir şifre dosyası çöp kutusunda bekletilmez, silinir.
- **Depoya kişisel veri girmez:** gerçek belgeler, kişisel ayarlar ve kişisel kurallar.

## MVP'nin arşivi

- **Yer:** veri klasöründe `archive/mvp/` ([mimari §9](architecture.md#9-veri-klasörü)). Klasörlerin izni 0700,
  dosyalarınki 0600'dür.
- **İçerik:** MVP'nin kodu ve testleri (`src/`, `tests/`, `pyproject.toml`, `uv.lock`), `README.md`, `.gitignore`,
  `CLAUDE.md`, `kategoriler.yaml` ve `ayarlar.toml`. Sanal ortam, önbellekler ve çıktılar alınmadı.
- **Kullanım**
  - Aşama 0 kodu ve testleri buradan kopyaladı. Bu klasöre hiçbir şey yazılmaz.
  - `kategoriler.yaml`'ın yalnızca genel kısmı depoya girer (Aşama 0).
  - Şunlar depoya girmez ve V1'e aktarılmaz: `kategoriler.yaml`'ın kişisel kısmı, `ayarlar.toml` ve `CLAUDE.md`.
    Yalnızca başvuru içindir.
  - Çalışan V1 bu klasörü okumaz.

## V1'in geçmişi nasıl dolar

- **E-postayla gelenler**
  - Eklenti kutuyu başlangıç gününden itibaren partilerle okur (ADR-0016'nın web araması katmanı). Okunmuş ve
    arşivlenmiş iletiler de dahildir; başlangıç günü kurulum sihirbazında seçilir.
  - Her belge ve her gövde arşive girer; kullanılmayanlar da aslıyla durur (K11).
- **E-postayla gelmeyenler:** bankanın sitesinden indirilen hesap dökümleri gibi.
  - Kullanıcı isterse onları arayüzden yükler, gelen klasörüne bırakır ya da Telegram botuna gönderir (F02).
  - Sistem eksik dönemleri ve hangi bankanın dökümünün beklendiğini gösterir (F19).
  - Döküm e-postayla gelmiyorsa kullanıcıdan istenmez; hesabın hareketleri bankanın bildirimlerinden okunur (K21).
- **Kurallar:** genel kategori kuralları uygulamayla gelir (`src/iplikci/rules/default.yaml`). Kişisel kurallar boş
  başlar; kullanıcının düzeltmeleri `rules/personal.yaml`'a yazılır.
- **Ayarlar:** kurulum sihirbazında girilir (F17). MVP'nin `ayarlar.toml`'u okunmaz.

## Adımlar

### Aşama 0: kod arşivden depoya

- [x] **Kod arşivden alınır:** `archive/mvp/src/gider_analizi`, `src/iplikci` olur; `tests/` ve şablonlar da gelir.
  - Paket ve komut adı değişir, davranış aynı kalır ([yol haritası, Aşama 0](roadmap.md#aşama-0--zemin)).
  - MVP testleri geçer.
- [x] **MVP kodundaki kişisel izler temizlenir.**
  - Kodda sabit duran şirket adı `identity.business_names` ayarına taşınır; kodda yalnızca genel işaretler kalır.
    Şirket adı, hukuki biçimi nasıl yazılırsa yazılsın eşleşir; değişince okuma önbelleği yenilenir.
  - Testlerdeki şirket adı sahte bir ad olur (ör. "ÖRNEK TEKNOLOJİ A.Ş.").
  - Gerçek ekstrelerden kalan değerler (yerler, tutarlar, kart ön ekleri, portföy ve abonelik satırları) sahteleriyle
    değiştirilir. Test IBAN'ları da tek tek gözden geçirilir.
  - Bitiş koşulu: gitleaks ve elle arama (ad, e-posta, IBAN, hesap numarası, tutar) temiz.
- [x] **Varsayılan kurallar:** arşivdeki `kategoriler.yaml`'dan genel işyeri kuralları ayıklanır.
  - Kişisel sayılanlar dışarıda kalır: "Aile & Kişiler" ve "Gelir" grupları, kira ve aidat kuralları, `_biten`,
    `_gereklilik_işyeri`; küçük, yerel ya da niş işyerleri de.
  - Tek bir seçimi ele verecek kalemler (BES şirketi, muhasebe hizmeti, bağış kurumu) yaygın seçeneklerin listesi
    olur.
  - Sonuç `src/iplikci/rules/default.yaml`'dır.
- [x] **Demo tabanı:** `iplikci dev demo` sahte belgelerle bir çalışma alanı kurar. `iplikci dogrula --taban`'ın bu
  alandaki sonucu altın dosya olarak testlere girer (`tests/golden/demo_baseline.json`).
  - Demoda TEB dökümleri, Garanti dekontları ve Garanti Yatırım ekstreleri var. Kart ekstrelerinin sahte belgeleri
    Aşama 2'de geldi (`iplikci.fakes`); demoya katılmaları altın tabanı değiştireceği için kullanıcının onayını bekler.

### Aşama 1: çalışma alanından veri klasörüne

- [x] **MVP düzeni bırakılır:** `ayarlar.toml`, `kategoriler.yaml`, `Bankalar/` ve `cikti/` yerine veri klasörünün
  düzeni gelir ([mimari §9](architecture.md#9-veri-klasörü)): `settings.toml`, `rules/personal.yaml`, `vault/`,
  `iplikci.db`, `inbox/`, `exports/` ve `baseline.json`.
  - Her yol (gelen klasörü, kullanıcının verdiği yollar, e-posta ekleri) aynı alımdan geçer: önce dokunmayan bir plan,
    sonra tam o plan. Okuma önbelleği yerine okunan satırlar veritabanında durur.
  - `iplikci dev demo` belgelerini aynı alımla arşive koyar.
  - MVP'nin çalışma alanı dosyaları okunmaz; aktarılacak veri yok ([K17](requirements.md#kararlar)).

### Aşama 3: e-posta ve geçmiş

- [x] Kurulum sihirbazında ADR-0016'da seçilen bağlayıcı kurulur.
  - Eklenti kurulup eşleştirilir; şifre yoktur.
  - `imap` bağlayıcısında şifre anahtar zincirinde `iplikci` hizmetine yazılır.
  - Başlangıç gününü kullanıcı seçer; varsayılanı iki yıl öncesinin 1 Ocak'ıdır.
- [x] Kutu baştan okunur; eklenti başlangıç gününden itibaren partilerle okur. E-postayla gelmiş her belge
  (kullanılmayanlar dahil) ve her gövde arşive girer. Tam tarama doğrulamada tutmadığı için "Gmail'de eksikleri tara"
  kullanılır (ADR-0016); ekleri boş gelen kopyalar "Orijinali indir" ile tamamlanır.
- [x] **İlk gerçek taban:** kutu okunduktan sonra `iplikci dogrula --taban` arşivdeki belgelerle çalışır.
  - Doğrulanamayan ekstreler ve okunamayan belgeler listelenip giderilir.
  - Taban veri klasöründe saklanır ve sonraki her aşama onu korur.
- [x] Servis kurulur: Aşama 3'te geliştirici komutuyla, Aşama 6'dan sonra kurulum paketiyle (ADR-0017).

### Geri dönüş

- MVP'nin kodu ve kuralları veri klasöründeki arşivde durur. Aşama 0'dan sonra kod, depoda `v0.1.0` etiketiyle de
  bulunur.
- E-postayla gelen belgeler Gmail'den yeniden okunur. Diğerleri yalnızca bankadan yeniden indirilerek ya da yeniden
  yüklenerek geri gelir.
