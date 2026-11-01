# İplikçi Nedim arayüzü

Servisin `127.0.0.1`'de sunduğu tek sayfalık uygulama: React, TypeScript (katı), Vite, Tailwind ve TanStack Query
([ADR-0008](../docs/adr/0008-frontend-pwa.md)). Derlenen dosyalar Python paketine girer
(`src/iplikci/api/ui/`) ve servis onları kendisi sunar; çalışırken Node gerekmez.

## Durum

Aşama 3'ün iskeleti: Sistem ekranı, Belgeler listesi (belge ekleme, plan ve onayla) ve tarayıcı eklentisinin
eşleştirilmesi. Giriş, servisin açtığı tek kullanımlık bağlantıyla olur; oturum çerezi tarayıcıda kalır. Ekranların
geri kalanı, PWA, çeviri altyapısı ve sade/ayrıntılı görünüm Aşama 6'da gelir.

## İlkeler

- Satır içi betik ya da stil yok; dış yazı tipi, betik ya da CDN yok (CSP: `default-src 'self'`).
- Sunucu durumu TanStack Query'dedir; servisin olay akışı (`/api/events/stream`) ilgili sorguları tazeler.
- Kodlar veride gelir, Türkçe etiketleri `/api/labels`'tan: etiketlerin tek kaynağı `domain/labels.py`'dir.
- Her veri ekranının yükleniyor, hata (yeniden deneme düğmesiyle) ve boş durumu vardır; durum rengi her zaman ikon ve
  etiketle birliktedir.
- Testler sahte API ile (MSW) çalışır; gerçek servise, ağa ya da veriye dokunmaz.

## Geliştirme

```bash
npm ci              # sabitlenmiş bağımlılıklar (package-lock.json)
npm run typecheck   # TypeScript, katı denetim
npm test            # vitest, Testing Library ve MSW
npm run build       # ../src/iplikci/api/ui/: servisin sunduğu dosyalar
npm run dev         # 127.0.0.1:5173; /api ve /giris istekleri 127.0.0.1:8643'teki servise gider
```

Geliştirme sunucusunda oturum açmak için servisin verdiği giriş bağlantısını açın (`uv run iplikci ac`); çerez
`127.0.0.1` için geçerlidir ve geliştirme sunucusunda da kullanılır.
