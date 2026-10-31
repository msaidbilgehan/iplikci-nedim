# ADR-0001: Tek süreçli modüler monolit servis

Durum: Kabul edildi · Tarih: 2026-10-31 · Dayanak: K5, G4, G10, G12

## Bağlam

MVP üç parçadan oluşuyor: komut satırı, saatte bir çalışıp kapanan bir arka plan görevi ve elle başlatılan bir panel.
V1 şunları istiyor: sürekli çalışan bir servis (K5), anlık akış (G10), kural tabanlı bildirimler (G12), PWA (G4) ve
servisin güncel verisini gören bir MCP sunucusu (G9). Tek kullanıcı ve tek bilgisayar var; veri küçük (yılda birkaç
bin işlem, birkaç yüz belge).

## Karar

Tek bir Python süreci (`iplikci servis calistir`) işletim sisteminin servis yöneticisi altında sürekli çalışır: macOS'ta
launchd, Linux'ta systemd kullanıcı servisi, Windows'ta Görev Zamanlayıcı. Aynı süreç şunları barındırır:

- HTTP API ve PWA dosyaları,
- SSE olay akışı,
- MCP (Streamable HTTP),
- zamanlayıcı ve iş kuyruğu,
- IMAP IDLE dinleyicisi,
- gelen klasörü izleyicisi,
- bildirim gönderici.

İç yapı modülerdir; bağımlılıklar dışarıdan içeriye doğrudur:

- `domain` saftır, giriş/çıkış yapmaz.
- `ledger`, `categorize`, `insights` ve `month_end` saf hesaplardır.
- `storage`, `vault`, `ingest`, `parsers`, `fx` ve bildirim kanalları uçtaki bağdaştırıcılardır.
- `api`, `mcp` ve `cli` sunum katmanıdır ve ortak kullanım durumlarına (`app`) bağlanır.
- `service` hepsini birbirine bağlar.

Modül tablosu [mimari §6](../v1/architecture.md#6-bileşenler)'dadır. Belge okuma alt süreçte çalışır (ADR-0005).
Analiz her alım partisinden sonra baştan hesaplanır; bu ölçekte artımlı analize gerek yoktur.

## Sonuçlar

- Olumlu: tek kurulum, tek günlük, tek kilit. Arayüz, MCP ve CLI aynı veriyi görür; dağıtık sistem sorunları yoktur.
- Olumsuz: süreç çökerse her şey durur. Servis yöneticisi süreci yeniden başlatır, okuma alt süreçte yalıtılmıştır.
  Uzun işler olay döngüsünü bloklamamalıdır (iş parçacığı ya da alt süreç havuzu).
- Nötr: ölçek büyürse ilk adım analizi hesap başına artımlı yapmaktır, servisi bölmek değil.

## Değerlendirilen seçenekler

- **MVP modelini sürdürmek** (zamanlanmış tek seferlik görevler): anlık akış ve anında bildirim olmaz; panel eski
  kodla kalır.
- **Çok servisli yapı** (API, işçi, Redis/Celery, Postgres, Docker): tek kullanıcı için işletim yükü getirir. Docker
  içinden anahtar zincirine ve macOS metin tanımaya erişmek de zordur.
- **Masaüstü uygulaması** (Electron, Tauri): paketleme yükü getirir; arka planda yine bir servis gerekir.

## Fikrimi ne değiştirir

Birden çok kişinin birden çok cihazdan aynı anda yazdığı bir hane kullanımı. O durumda sunucuya kurulum, Postgres ve
gerçek kullanıcı hesapları gerekir.
