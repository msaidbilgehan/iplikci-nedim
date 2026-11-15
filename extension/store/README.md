# Chrome Web Store hazırlığı

Eklenti Chrome Web Store'da **herkese açık** olarak yayımlanacak: mağazanın aramasında çıkar, herkes kurabilir.
Kullanıcı 2026-11-14'te listelenmemiş yayından vazgeçti, çünkü eklenti artık programın kapısıdır: programı olmayan
birini son kurulum paketinin indirilmesine ve kurulumuna götürür, programın da ayrı bir web sayfası yoktur
([ADR-0024](../../docs/adr/0024-extension-leads-to-download.md), [K31](../../docs/v1/requirements.md#kararlar)).
Yayımlamayı kullanıcı yapacak ([K29](../../docs/v1/requirements.md#kararlar)); mağazadan kurulan eklentiyi tarayıcı
kendisi günceller ([ADR-0022](../../docs/adr/0022-releases-and-updates.md)). Mağazaya ilk giden sürüm 0.9.0'dır;
0.8.0 yüklenmez.

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
- [Gizlilik politikası](privacy.md): mağaza herkese açık bir adres ister. Depo herkese açık olduğu için (K32) mağazaya
  bu dosyanın GitHub'daki adresi yazılır:
  <https://github.com/msaidbilgehan/iplikci-nedim/blob/master/extension/store/privacy.md>
  ([sürüm yayını](../../docs/yayin.md#sürümlerin-yeri)).

## İlk yayın (elle, bir kez)

1. Geliştirici kaydı: tek seferlik ücret, Google hesabıyla; hesapta iki adımlı doğrulama açık olmalı.
2. Gizlilik politikasının herkese açık adresi.
3. Ekran görüntüleri: eklentinin penceresi (araç çubuğundaki düğmeden), ayarlar sayfası ve doğrulama sayfası,
   1280×800. Görüntülerde gerçek adres, banka adı ya da tutar olmamalı. Demo veri klasörüyle eşleşmiş bir eklentiden
   alınır; programı olmayan bir bilgisayardaki ayarlar sayfası (indirme rehberi) da bir görüntü olabilir.
4. Önce kurulum paketlerini kararlı adlarıyla taşıyan bir program sürümü (1.0.0 ve sonrası) deponun sürüm sayfasında
   yayımlanmış olmalı (`iplikci-nedim-macos-aarch64.dmg` gibi; [sürüm yayını](../../docs/yayin.md)): eklentinin
   indirme düğmesi son sürümün bu adlı dosyasını açar.
5. `iplikci-kopru-0.9.0.zip` (o sürümün GitHub sayfasından ya da `npm run package`) geliştirici panosundan yüklenir;
   görünürlük: herkese açık.
6. Yeni geliştiricilerin eklentileri ilk aylarda Gelişmiş Güvenli Tarama'da "dikkatli olun" uyarısı alabilir
   (ADR-0016).
7. İnceleme geçince eklentinin mağaza adresi `src/iplikci/app/extension.py`'deki `STORE_URL`'e yazılır: arayüz önce
   mağazayı gösterir (v1.0.1). Eklentiyi önce paketlenmemiş yüklemiş olanlar onu kaldırır; ikisi birden aynı iletileri getirir.

## Gönderilen (2026-11-15)

0.9.0 geliştirici panosundan gönderildi ve aynı gün incelemeden geçip herkese açık yayımlandı (API: `PUBLISHED`).
Öğe kimliği `biegljgcnlkdokmfpdejecddgaekplof`, sayfası
<https://chromewebstore.google.com/detail/biegljgcnlkdokmfpdejecddgaekplof>. Panoya girilenler:

- **Paket:** 1.0.0 sürümünün GitHub sayfasındaki `iplikci-kopru-0.9.0.zip`.
- **Mağaza sayfası:** [mağaza metnindeki](listing.md) uzun açıklama; kategori Verimlilik › Araçlar (Tools); dil
  Türkçe; ana sayfa adresi kod deposu; destek adresi boş. Simge `static/icons/icon-128.png`.
- **Görseller:** beş ekran görüntüsü (1280×800) ve küçük tanıtım kartı (440×280): araç çubuğundaki pencere, eşleşmiş
  ayarlar sayfası, doğrulama sayfası, programı olmayan bilgisayardaki indirme rehberi ve demo verisiyle Pano. Hepsi
  demo veri klasöründen; gerçek veri yok.
- **Gizlilik:** tek amaç ve izinlerin gerekçeleri incelemeciler için İngilizce ([mağaza metni](listing.md),
  "İncelemecilere giden metin"); veri kullanımında "Personal communications" ile "Financial and payment information"
  (banka iletileri finansal bilgi taşır), üç taahhüt ve gizlilik politikasının adresi.
- **Dağıtım:** ücretsiz, herkese açık, bütün bölgeler. **Test instructions:** [mağaza metnindeki](listing.md) inceleme
  notu.

Ekran görüntüleri gerçek servise dokunmadan alındı: `extension/dist`'in bir kopyasında `127.0.0.1:8643` başka bir
porta çevrildi (sayfalar adresi göstermez), demo veri klasörü o portta `servis calistir --ev` ile çalıştı ve kopya ayrı
bir tarayıcı profilinde onunla eşleştirildi. Kullanıcının tarayıcısındaki eklenti 8643'te başka bir servis görse
eşleşmeyi iptal edilmiş sayıp teslimi durdururdu.

## Sonraki sürümler

Sürüm iş akışı eklentinin yeni sürümünü mağazaya kendisi yükleyip incelemeye gönderir; sürüm mağazadakinden yeni
değilse yüklemez. Daha eski bir sürüm incelemedeyse beklenir: iş başarısız olur, inceleme bitince yeniden
çalıştırılır. Servis hesabı 2026-11-15'te kuruldu. Anahtarı ve yayıncı kimliği deponun `chrome-web-store` ortamının
sırlarıdır, eklentinin kimliği `CWS_ITEM_ID` değişkenidir ([sürüm yayını](../../docs/yayin.md#chrome-web-store)).
Mağaza sayfası, görseller ve gizlilik beyanı API'yle değişmez; onlar panodan değiştirilir.
