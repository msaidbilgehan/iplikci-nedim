# ADR-0005: Okuyucu eklenti sözleşmesi ve okuyucu başına sürüm

Durum: Kabul edildi · Tarih: 2026-10-31 · Dayanak: K6, G5

## Bağlam

MVP'de okuyucu, `parsers/__init__.py`'deki sıralı bir `if` zinciriyle seçiliyor; tablo dökümleri `hesaplar.py` içinde
birer dal. Tek bir `PARSER_VERSION` var: bir okuyucu değişince bütün belgeler yeniden okunuyor ve posta kutusu baştan
taranıyor. Belgeler ise güvenilmez girdi.

## Karar

### Sözleşme

Her okuyucu aşağıdaki sözleşmeyi uygular:

```python
class Parser(Protocol):
    id: str                      # "garanti.bonus_card"
    version: int                 # çıktısı değişince artar
    bank: str                    # "Garanti BBVA"; banka dışı göndericide kurum adı
    document_type: DocumentType
    formats: frozenset[Format]   # PDF, SHEET, HTML, EMAIL

    def detect(self, probe: Probe) -> Detection | None: ...   # ucuz; güven ve neden döndürür
    def parse(self, doc: SourceDocument) -> ParseResult: ...  # her satır kaynak konumuyla (SourceRef)
```

- Kayıt defteri, yerleşik okuyuculardan ve `iplikci.parsers` giriş noktası (entry point) grubundaki paketlerden oluşur.
- E-posta gövdeleri ve banka dışı e-postalar da aynı sözleşmeyle okunur (`EMAIL` biçimi).

### Seçim

- Şirket belgesi denetimi okuyuculardan önce yapılır; okuyucu da bir belgeyi şirket belgesi olarak bildirebilir.
- Bütün okuyucuların `detect` sonuçları toplanır:
  - Eşiği tek bir okuyucu geçerse o okur.
  - Birden çok okuyucu geçerse belge "okunamadı: birden çok okuyucu" olur ve hata olarak raporlanır.
  - Hiçbiri geçmezse belge "işlenmedi" olur; ne olduğu (poliçe, sözleşme, form…) nedenine yazılır.

### Sürüm ve yeniden okuma

- Önbellek anahtarı (sha256, okuyucu kimliği, sürüm) üçlüsüdür.
- Açılışta kayıt defteri son okumalarla karşılaştırılır; yalnızca sürümü değişen okuyucunun belgeleri yeniden okunur.
- Okuyucu kümesi değişince işlenmeyen belgeler yeniden tanıtılır. Posta kutusu baştan taranmaz.

### Yalıtım ve alarm

- Okuma bir alt süreçte çalışır: 60 saniye süre sınırı, POSIX'te 1 GiB bellek sınırı. Sınırı aşan belge "okunamadı"
  olur.
- Biçim değişikliği alarmı: bir okuyucu belgeyi tanıyıp doğrulamadan geçiremezse `parser.format_alarm` olayı üretilir.

### Test ve araçlar

- Her okuyucunun bir sahte belge üreticisi ve testi vardır.
- Geliştirici komutları:
  - `iplikci dev parser probe <dosya>`
  - `iplikci dev parser debug <dosya>`
  - `iplikci dev parser test <id>`

## Sonuçlar

- Olumlu: bir bankadaki değişiklik diğerlerine dokunmaz; kötü bir belge servisi kilitleyemez; okuyucu seçimi sıraya
  bağlı ve sessiz değildir.
- Olumsuz: belge başına alt süreç maliyeti vardır (saniyenin onda biri mertebesinde, sorun değil). Belirsiz tespitler
  elle çözülür; bu tasarım gereğidir.

## Değerlendirilen seçenekler

- **Sıralı `if` zinciri:** seçim sıraya bağlıdır; çakışmalar sessiz kalır.
- **Tek genel sürüm:** her değişiklik her şeyi yeniden okutur.
- **Süreç içinde okuma:** bozuk bir PDF bütün servisi dondurabilir.
