# ADR-0004: SQLite birincil veri deposu; veritabanı yeniden kurulabilir

Durum: Kabul edildi · Tarih: 2026-10-31 · Dayanak: K3, tasarım

## Bağlam

Kullanıcı tek ve veri küçük: yılda birkaç bin işlem. Servis, CLI ve MCP köprüsü aynı veriyi okur. Tam metin arama ve
süzülebilir bir işlem listesi gerekiyor. MVP ise JSON önbellek ve CSV kayıtlarla çalışıyor.

## Karar

- Standart kütüphanenin `sqlite3` modülü kullanılır: WAL kipi, yabancı anahtarlar açık, `busy_timeout` tanımlı.
- ORM yoktur; ince depo modülleri ve elle yazılmış SQL kullanılır.
- Şema göçleri numaralı SQL dosyalarıdır (`storage/migrations/NNNN_ad.sql`). Açılışta sırayla uygulanırlar; önce
  veritabanının bir yedeği alınır.
- FTS5 tam metin araması işlem açıklamasını, karşı tarafı, işyerini ve belge metnini kapsar.
- JSON1 eklentisi olay yüklerini ve analiz anlık görüntülerini tutar.
- Yazmalar tek bir yazar üzerinden (iş kuyruğu, ADR-0014) sıraya girer; okumalar eşzamanlıdır.

Verinin dört sınıfı vardır:

| Sınıf | Nerede | Kaynak mı, türev mi? |
|---|---|---|
| Belgeler | arşiv (ADR-0003) | asıl kaynak |
| Okunan satırlar: hesaplar, ekstreler, işlemler, kanıtlar, faturalar | veritabanı | belgelerden türer, yeniden üretilir |
| Kullanıcı kararları | kurallar YAML dosyalarında; notlar, düzeltmeler ve eşleştirme kararları veritabanında, her gün JSON olarak yedeğe dökülür | birincil veri, kaybolmamalı |
| Analiz anlık görüntüleri ve olaylar | veritabanı | türev ya da günlük |

Veritabanı kaybolursa arşiv, kurallar ve son karar dökümü kullanılarak yeniden kurulur
(`iplikci dogrula --yeniden-kur`).

## Sonuçlar

- Olumlu: kurulum ve işletim gerekmez; tek dosyadır; çevrimiçi yedek API'si vardır; bütün sorgular yereldir.
- Olumsuz: tek yazar vardır (iş kuyruğu bunu düzenler); ağ istemcisi yoktur (gerekmiyor).

## Değerlendirilen seçenekler

- **PostgreSQL:** sunucu işletimi gerektirir; tek kullanıcı için gereksiz.
- **DuckDB:** analizde güçlü ama sık küçük yazmalarda ve eşzamanlı okumada zayıf. İleride analiz kopyası olarak
  eklenebilir.
- **MVP'deki JSON dosyaları:** sorgu, not ve eşzamanlı erişim desteği yok.
