# Chrome Web Store hazırlığı

Eklenti Chrome Web Store'da **listelenmemiş** olarak yayımlanacak: yalnızca bağlantıyı bilen kurar, aramada çıkmaz
(ADR-0016). Geliştirici kaydı ücretli bir hesap kararıdır; yayın kullanıcının onayını bekler.

## Paket

```bash
npm run package     # dist/'i derler ve iplikci-kopru.zip'i yapar (macOS ve Linux)
```

Paket yalnızca `dist/`'in içeriğidir: derlenmiş betikler küçültülmeden durur, mağaza incelemesi ne yaptığını okuyabilir.
Simgeler `tools/icons.py` ile çizilir: `uv run python -I extension/tools/icons.py`.

## Mağaza sayfası

- [Mağaza metni](listing.md): kısa ve uzun açıklama, tek amaç, izinlerin gerekçeleri, veri kullanımı beyanı ve
  inceleme notu.
- [Gizlilik politikası](privacy.md): mağaza herkese açık bir adres ister. Depo özel olduğu için (K18) bu sayfa ayrı bir
  yerde yayımlanmalı, örneğin herkese açık bir GitHub Pages sayfasında. Nerede yayımlanacağı kullanıcının kararıdır.

## Yayından önce

1. Geliştirici kaydı: tek seferlik ücret, Google hesabıyla (kullanıcı karar verir).
2. Gizlilik politikasının herkese açık adresi.
3. Ekran görüntüleri: eklentinin penceresi ve doğrulama sayfası, 1280×800. Görüntülerde gerçek adres, banka adı ya
   da tutar olmamalı. Demo veri klasörüyle eşleşmiş bir eklentiden alınır.
4. `npm run package`, ardından paketi geliştirici panosundan yükleme; görünürlük: listelenmemiş.
5. Yeni geliştiricilerin eklentileri ilk aylarda Gelişmiş Güvenli Tarama'da "dikkatli olun" uyarısı alabilir
   (ADR-0016).
