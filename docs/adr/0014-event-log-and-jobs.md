# ADR-0014: Olay kaydı ve SQLite tabanlı iş kuyruğu

Durum: Kabul edildi · Tarih: 2026-10-31 · Dayanak: tasarım, G10, G12

## Bağlam

Anlık akış, bildirimler, denetim kaydı ve yeniden denenebilir işler gerekiyor. Hepsi tek bir süreçte çalışıyor
(ADR-0001). Bilgisayar uyuyabilir ve servis yeniden başlatılabilir; yarım kalan iş kaybolmamalı.

## Karar

**Tablolar**

- `events` yalnızca ekleme yapılan bir tablodur. Her satır olay türünü, zamanını, yükünü (JSON) ve ilgili kimlikleri
  tutar.
- `jobs` işleri tutar: tür, yük, durum, deneme sayısı, en erken çalışma zamanı, son hata.

**Çalışma**

- Bir işçi döngüsü işleri yürütür: belge okuma, defteri yeniden kurma, kur çekme, bildirim gönderme, yedek alma.
- Zamanlayıcı periyodik işleri kuyruğa ekler.
- Uyku ya da yeniden başlatmadan sonra kaçırılan işler bir kez çalışır.
- İşler ve teslimler tekrar engelleme anahtarı taşır. Aynı iş iki kez yapılmaz, aynı bildirim iki kez gönderilmez.

**Olayların üretilmesi ve dağıtılması**

- Analiz sonrasında yeni anlık görüntü bir öncekiyle karşılaştırılır ve fark olaylara dönüşür. Örnekler:
  - yeni işlem,
  - kesinleşen satır,
  - zamlanan abonelik,
  - kapanan ay.
- Yeni olaylar süreç içi yayınla SSE abonelerine iletilir ve bildirim kurallarına girer.
- Olay türlerinin listesi [mimari §13](../v1/architecture.md#13-olaylar-ve-anlık-akış)'tedir.

## Sonuçlar

- Olumlu: ek servis gerekmez; iş ve olay geçmişi sorgulanabilir; akış, bildirimler ve denetim aynı kaynaktan beslenir.
- Olumsuz: kuyruk SQLite'ın tek yazarına bağlıdır; bu ölçekte sorun değildir.

## Uygulama notu (Aşama 2, 2026-11-01)

- `events` tablosu, okuyucuların biçim alarmı (`parser.format_alarm`, [ADR-0005](0005-parser-plugins.md)) için
  Aşama 2'de açıldı (göç 3).
- Tür, hedef ve ayrıntısı aynı olan bir olay ikinci kez eklenmez. Böylece aynı belgenin yeniden okunması aynı alarmı
  çoğaltmaz.
- Birincil veri dökümü (2. sürüm) olayları da taşır.
- `jobs`, anlık görüntü farkı ve SSE yayını Aşama 3'te gelir.

## Değerlendirilen seçenekler

- **Celery, RQ ya da Redis:** ek servis gerektirir; tek kullanıcı için gereksiz.
- **APScheduler:** iş görür, ama kalıcı kuyruğu ve tekrar engellemeyi yine yazmak gerekir.
- **Yalnızca bellekte kuyruk:** yeniden başlatmada iş kaybolur.
