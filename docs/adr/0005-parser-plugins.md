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

## Uygulama notu (Aşama 2, 2026-11-01)

- **Yerleşim:** her okuyucu `src/iplikci/parsers/<banka>/<belge>.py` modülündedir ve bir `PARSER` nesnesi sunar
  (`garanti.bonus_card` → `parsers/garanti/bonus_card.py`). Sözleşme `parsers/contract.py`'de, kayıt defteri ve sürüm
  `parsers/registry.py`'dedir. Sözleşme ayrıca Türkçe bir `name` taşır; araçlar ve raporlar okuyucuyu onunla anar.
- **Seçim:** eşik 0,5'tir. Şirket belgesi denetimi dosya adında ve PDF'in ilk sayfasının ilk 600 karakterinde yapılır.
  Okuyucu bütün sayfaya bakıp belgeyi şirket belgesi olarak bildirebilir (TEB Bonus, İş Bankası Maximum).
- **Sürüm:** okuma, okuyucusunun sürümünü `<seçim>.<okuyucu>` olarak saklar (ör. `1.2`); seçimin sürümü bütün
  belgeleri ilgilendiren değişiklikler içindir. Hiçbir okuyucunun almadığı belge, bütün okuyucuların kimlik ve
  sürümlerinden çıkan bir imza saklar. Belgeyi tanıyıp vazgeçen ya da hata veren okuyucunun adı okumaya yazılır;
  belgeyi yalnızca onun yeni sürümü yeniden okur.
- **Yalıtım:** belge başına bir süreç yerine kalıcı bir okuma süreci kullanılır (`parsers/worker.py`). Sürecin açılışı
  (yaklaşık 0,25 sn) her belgede değil bir kez ödenir.
  - Süreç her hatadan sonra ve her 200 belgede yenilenir.
  - Başka belgeler okumuş bir süreç çöker ya da belleği yetmezse belge temiz bir süreçte bir kez daha okunur. Böylece
    bir belge yalnızca kendi yüzünden "okunamadı" olur.
  - Süreç `python -I -m iplikci.parsers.worker` ile başlar. Sonucu tek satır JSON olarak döner (pickle yok);
    uygulama her değerin türünü denetler (`parsers/wire.py`).
  - 60 saniyelik süre sınırı her sistemde geçerlidir. Uygulama ölmüşken takılan süreç POSIX'te kendini SIGALRM ile
    bitirir.
  - 1 GiB bellek sınırı bir adres alanı sınırıdır (`RLIMIT_AS`) ve yalnızca Linux'ta uygulanır. macOS bu sınırı kabul
    etmez, Windows'ta böyle bir sınır yoktur; orada bir belge sistemin verdiği kadar bellek kullanabilir.
  - pdfplumber bellek hatasını kendi istisnasının içine sarar; hata zinciri bu yüzden taranır.
  - Okuma süreci hiç başlayamazsa iş durur. Hiçbir belge bu yüzden "okunamadı" diye kaydedilmez.
  - Kurulum paketleri (Aşama 6) `sys.executable`'ın bir Python yorumlayıcısı olarak kalmasını sağlamalıdır.
- **Kaynak konumu:**
  - Konumla okuyan PDF okuyucuları sayfayı ve kutuyu verir.
  - Metni satır satır okuyan QNB okuyucuları sayfayı ve satır numarasını verir.
  - Tablolar sayfa adını ve satır numarasını verir; HTML tablosunda sayfa adı boştur.
  - QNB e-dekontu metindeki aralığı verir; PDF'te sayfasıyla birlikte.
  - Konum `transactions.ref` ve `evidence.ref` sütunlarında JSON olarak durur (göç 2).
- **Alarm:** `parser.format_alarm`, Aşama 3'ten önce açılan `events` tablosuna yazılır (göç 3,
  [ADR-0014](0014-event-log-and-jobs.md)).
  - Yazıldığı durumlar: okuyucu belgeyi tanıyıp okuyamadığında ya da vazgeçtiğinde, ya da okuduğu ekstre
    doğrulanmadığında.
  - Yükü okuyucuyu, sürümünü ve nedeni ya da doğrulanmayan hesapları taşır. Aynı alarm bir kez yazılır.
  - Bakiyesini denetleyecek kadar satırı olmayan hesap dökümü alarm vermez.
- **Sahte belgeler:** üreticiler `iplikci.fakes` paketindedir: her bankaya bir modül, dosya biçimleri için `files.py`
  (metinli PDF, BIFF8 XLS, her seferinde aynı baytları veren XLSX).
  - Her okuyucunun en az bir örneği (`Specimen`) vardır: belge, onu okuması gereken okuyucu, hesap ve satır sayısı.
  - `fakes.check` ve `iplikci dev parser test` örnekleri denetler. pytest, hiçbir okuyucunun örneksiz kalmadığını da
    denetler.
- **Araçlar:** `iplikci dev parser probe | debug | test` okuyucuları geliştiricinin sürecinde çalıştırır; böylece hata
  izi görünür. Şirket adlarını veri klasörünün ayarlarından okur; klasöre yazmaz.

## Değerlendirilen seçenekler

- **Sıralı `if` zinciri:** seçim sıraya bağlıdır; çakışmalar sessiz kalır.
- **Tek genel sürüm:** her değişiklik her şeyi yeniden okutur.
- **Süreç içinde okuma:** bozuk bir PDF bütün servisi dondurabilir.
