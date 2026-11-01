# İplikçi Nedim Köprüsü

Chromium tabanlı tarayıcılar (Chrome, Edge, Brave) için Manifest V3 eklentisi. Gmail'deki banka iletilerini, tarayıcının
açık Gmail oturumuyla okuyup bu bilgisayardaki İplikçi Nedim servisine taşır. Uygulama şifresi olmayan hesaplar,
örneğin Gelişmiş Koruma'daki Gmail, için yoldur ([ADR-0016](../docs/adr/0016-mail-connectors.md)).

## Durum

Şu an yalnızca ADR-0016'nın doğrulama sayfası var (Aşama 3'ün ilk işi). Sayfa dört şeyi denetler: gelen kutusu
akışını, ham iletiyi ve DMARC'ı, tam taramayı ve platformu. Eşleştirme, üç katmanlı okuma ve servise teslim, doğrulama
geçince gelir.

## İlkeler

- İzinler yalnızca `alarms` ve `storage`, artı iki adres: `https://mail.google.com/*` ve `http://127.0.0.1:8643/*`.
- Gmail'e yalnızca okuma istekleri gider: okundu işareti, etiket, taşıma ya da silme yoktur.
- İstekler sıralıdır ve aralarında en az bir saniye vardır.
- Uzaktan yüklenen kod, dış yazı tipi ya da dış betik yoktur.
- Gmail'e dokunan kod yalnızca `src/gmail/` altındadır. Kayıtlı sahte yanıtlarla test edilir; testlerde gerçek adres,
  konu ya da ileti yoktur.
- Doğrulama raporu e-posta adresi, konu ya da ileti içeriği taşımaz.

## Geliştirme

```bash
npm ci              # sabitlenmiş bağımlılıklar (package-lock.json)
npm run typecheck   # TypeScript, katı denetim
npm test            # vitest
npm run build       # dist/: tarayıcıya yüklenecek klasör
```

Geliştirme sırasında `dist/` klasörü tarayıcıda "Paketlenmemiş öğe yükle" ile yüklenir. Kullanıcılar eklentiyi Chrome
Web Store'dan kuracak; bu yol yalnızca geliştirme ve doğrulama içindir.
