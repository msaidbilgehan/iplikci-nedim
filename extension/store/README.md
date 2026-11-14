# Chrome Web Store hazırlığı

Eklenti Chrome Web Store'da **listelenmemiş** olarak yayımlanacak: yalnızca bağlantıyı bilen kurar, aramada çıkmaz
(ADR-0016). Yayımlamayı kullanıcı yapacak ([K29](../../docs/v1/requirements.md#kararlar)); mağazadan kurulan eklentiyi
tarayıcı kendisi günceller ([ADR-0022](../../docs/adr/0022-releases-and-updates.md)).

## Paket

```bash
npm run package     # dist/'i derler ve iplikci-kopru-<sürüm>.zip'i yapar (macOS ve Linux)
```

Paket yalnızca `dist/`'in içeriğidir: derlenmiş betikler küçültülmeden durur, mağaza incelemesi ne yaptığını okuyabilir.
Manifestin sürümü `package.json`'unkidir; `key` alanı taşıyan manifest paketlenmez. Her sürüm etiketinde iş akışı bu
paketi GitHub sürümüne de koyar. Simgeler ürünün logosundan `packaging/icons.py` ile çizilir:
`uv run python -I packaging/icons.py`.

## Mağaza sayfası

- [Mağaza metni](listing.md): kısa ve uzun açıklama, tek amaç, izinlerin gerekçeleri, veri kullanımı beyanı ve
  inceleme notu.
- [Gizlilik politikası](privacy.md): mağaza herkese açık bir adres ister. Kod deposu özel kaldığı için (K18) bu sayfanın
  bir kopyası sürümlerin herkese açık deposunda, `iplikci-nedim-surumler`'de durur; mağazaya o dosyanın GitHub'daki
  adresi yazılır ([K31](../../docs/v1/requirements.md#kararlar), [sürüm yayını](../../docs/yayin.md#sürümlerin-yeri)).

## İlk yayın (elle, bir kez)

1. Geliştirici kaydı: tek seferlik ücret, Google hesabıyla; hesapta iki adımlı doğrulama açık olmalı.
2. Gizlilik politikasının herkese açık adresi.
3. Ekran görüntüleri: eklentinin penceresi (araç çubuğundaki düğmeden), ayarlar sayfası ve doğrulama sayfası,
   1280×800. Görüntülerde gerçek adres, banka adı ya da tutar olmamalı. Demo veri klasörüyle eşleşmiş bir eklentiden
   alınır.
4. Son sürümün `iplikci-kopru-<sürüm>.zip` dosyası (GitHub sürümünden ya da `npm run package`) geliştirici
   panosundan yüklenir; görünürlük: listelenmemiş.
5. Yeni geliştiricilerin eklentileri ilk aylarda Gelişmiş Güvenli Tarama'da "dikkatli olun" uyarısı alabilir
   (ADR-0016).
6. İnceleme geçince eklentinin mağaza adresi `src/iplikci/app/extension.py`'deki `STORE_URL`'e yazılır: arayüz önce
   mağazayı gösterir. Eklentiyi önce paketlenmemiş yüklemiş olanlar onu kaldırır; ikisi birden aynı iletileri getirir.

## Sonraki sürümler

Sürüm iş akışı eklentinin yeni sürümünü mağazaya kendisi yükleyip incelemeye gönderir; sürüm mağazadakinden yeni
değilse yüklemez. Bunun için Google Cloud'da bir servis hesabı ve deponun `CWS_PUBLISHER_ID`, `CWS_ITEM_ID`
değişkenleri ile `CWS_SERVICE_ACCOUNT_KEY` sırrı gerekir; adımlar [sürüm yayını](../../docs/yayin.md#chrome-web-store)
belgesindedir. Bunlar yoksa adım atlanır ve paket panodan elle yüklenir.
