# ADR-0008: Ön yüz: React + TypeScript + Vite + Tailwind PWA

Durum: Kabul edildi · Tarih: 2026-10-31 · Dayanak: K5, G4, G7, tasarım

## Bağlam

Arayüzde çok sayıda etkileşimli ekran olacak: akış, pano, hesaplar, işlemler, belge görüntüleyici, takvim, kurallar.
Bunlara ek olarak şunlar gerekiyor: canlı güncelleme, kurulabilir uygulama, sıkı CSP ve CDN'siz çalışma.

MVP raporu yaklaşık 1.500 satırlık çerçevesiz JavaScript. Grafik kuralları belirlenmiş: sabit renk yuvaları, her
grafiğe bir tablo görünümü, ayrı açık ve koyu paletler.

## Karar

**Yapı**

- `web/` altında tek sayfalık bir uygulama: React, TypeScript (strict), Vite ve Tailwind.
- Bileşenler shadcn/ui'den (Radix tabanlı, erişilebilir) gelir.
- Sunucu durumu TanStack Query ile yönetilir.
- Yönlendirme React Router ile yapılır; sayfalar tembel yüklenir.
- Çeviri react-i18next ile yapılır; başlangıçta yalnızca `tr` vardır.

**Grafikler**

- Grafikler d3-scale, d3-shape ve d3-sankey üzerine yazılmış kendi SVG bileşenlerimizdir.
- MVP'nin grafik kuralları korunur; büyük bir grafik kütüphanesi kullanılmaz.

**PWA ve dağıtım**

- Manifest ve service worker vite-plugin-pwa ile üretilir.
- Önbelleğe yalnızca uygulama kabuğu alınır; API verisi varsayılan olarak önbelleğe alınmaz.
- Yeni bir derleme hemen devreye girer (2026-11-03 notu): service worker beklemeden etkinleşir ve açık sekmeleri
  devralır, sayfa da bunu görünce kendini bir kez yeniler. Sekme her öne geldiğinde yeni bir derleme olup olmadığı
  sorulur, en çok dakikada bir. Önceden yeni service worker uygulamanın bütün sekmeleri kapanana dek bekliyordu; açık
  bırakılan bir sekme güncellemelerden sonra da eski arayüzü gösteriyordu.
- Derlenen dosyalar Python paketine girer ve servis tarafından sunulur. Çalışırken Node gerekmez.

**Güvenlik**

- CSP: `default-src 'self'; connect-src 'self'; img-src 'self' data: blob:; object-src 'none'; base-uri 'none';
  frame-ancestors 'none'`.
- Satır içi betik yoktur.

**Test**

- Bileşen testleri: Vitest, Testing Library ve MSW.
- Uçtan uca testler: Playwright, demo çalışma alanında.
- Erişilebilirlik denetimi: axe.

## Sonuçlar

- Olumlu: ekranlar birbirinden bağımsız gelişir; API istemcisi tiplidir; bileşenler erişilebilirdir; paket küçüktür.
- Olumsuz: Node derleme zinciri gerekir; her sürümde derlenmiş dosyaların pakete girmesi gerekir.

## Değerlendirilen seçenekler

- **Çerçevesiz JavaScript'i büyütmek:** bu kadar ekranda sürdürülemez.
- **Sunucuda üretilen HTML (HTMX):** daha basit, ama canlı ve çok etkileşimli görünümlerde zayıf.
- **Hazır grafik kütüphanesi (ECharts, Recharts):** paket boyutu büyür; MVP'nin grafik kurallarına uymak zorlaşır.
