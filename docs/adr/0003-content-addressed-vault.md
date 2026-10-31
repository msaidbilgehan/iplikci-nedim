# ADR-0003: İçerik adresli belge arşivi

Durum: Kabul edildi · Tarih: 2026-10-31 · Dayanak: K3, K4, K11, G2

## Bağlam

MVP'de belgeler `Bankalar/<Banka>/<Hesap>/` altında okunaklı adlarla duruyor. Adlandırma, kopyaların yakalanması ve
yeniden sınıflandırma, dosya taşımaya dayanıyor.

V1'in istekleri:

- Her işlem belgesine ve geldiği e-postaya bağlanmalı; belge gösterilebilmeli (K4).
- İşlenmeyen banka belgeleri çöpe gitmemeli (K11).

Kalıcı kurallar:

- Hiçbir belge kalıcı silinmez.
- sha256'sı farklı bir dosyanın üzerine yazılmaz.
- Şirket belgeleri hiç saklanmaz.

## Karar

**Saklama**

- Her belge bir kez ve değiştirilmeden, salt okunur izinle saklanır:
  `vault/objects/<sha256[0:2]>/<sha256[2:4]>/<sha256>`. Aynı içerik yeniden gelirse yalnızca yeni kaynak kaydı eklenir.
- Üst veri veritabanındadır:
  - `documents`: tür, banka, durum, neden, okuyucu ve sürümü, doğrulama, dönem, görünen ad.
  - `document_sources`: kaynak türü (e-postada Message-ID, gönderen, tarih ve konu) ve özgün dosya adı.
- Güvenilen göndericilerin e-postaları `.eml` olarak saklanır. Ekler (zip içleri dahil) ayrı belgelerdir ve geldikleri
  e-postaya bağlıdır.

**Şirket belgeleri**

- Yeni gelen belge önce `vault/staging/` altında okunur. Şirket belgesi çıkarsa atılır. Değilse nesne ile satırları
  tek bir işlemde kaydedilir.
- Şirket içeriği taşıyan bir e-postanın kendisi saklanmaz; kişisel ekleri varsa kaynak bilgisiyle birlikte saklanır.
- Saklanmış bir belge sonradan şirket belgesi çıkarsa sistemin çöp kutusuna taşınır, satırları silinir ve durum
  denetim kaydına yazılır.

**Durumlar**

| Kod | Anlamı |
|---|---|
| `processed` | İşlendi. |
| `unprocessed` | İşlenmedi: tanınmadı ya da para hareketi taşımıyor; nedeniyle birlikte saklanır. |
| `unreadable` | Okunamadı: şifreli PDF, bozuk zip, OCR yok. |
| `removed` | Kaldırıldı: dosyası sistemin çöp kutusunda. |

**Kaldırma, türetilmiş veriler ve bütünlük**

- Kaldırma, nesneyi sistemin çöp kutusuna taşır ve denetim kaydı yazar. Kalıcı silme yoktur.
- Türetilmiş veriler (sayfa resimleri, metin, kelime kutuları) `vault/derived/<sha256>/` altındadır; her an yeniden
  üretilebilir.
- Görünen ad, MVP'deki düzenleyicinin adlandırma şemasını izler (`<kesim> <banka> <hesap> Ekstre.pdf` gibi) ve
  indirilen dosyanın adı olur.
- `iplikci dogrula --arsiv` her nesnenin sha256'sını yeniden hesaplar.

## Sonuçlar

- Olumlu:
  - Aynı dosya ikinci kez saklanamaz.
  - Yeniden sınıflandırma dosya taşımaz.
  - Her belge kaynağıyla izlenir.
  - Veritabanı arşivden yeniden kurulabilir (ADR-0004).
- Olumsuz:
  - Finder'da gezilecek bir klasör ağacı yoktur. Gezinme arayüzdeki belge sayfasından yapılır; isteğe bağlı olarak
    sabit bağlantılı, salt okunur bir ağaç dışa aktarılabilir.
  - `.eml` ile ekleri aynı baytları iki kez taşır; bu ölçekte önemsizdir.

## Değerlendirilen seçenekler

- **`Bankalar/` ağacını sürdürmek:** sınıflandırma değişince dosya taşınır; kopyalar ad üzerinden yakalanır; kaynak
  bilgisi tutulmaz.
- **Belgeleri veritabanında BLOB olarak tutmak:** veritabanı şişer, yedekler ağırlaşır, dosyayı bir araca vermek
  zorlaşır.
