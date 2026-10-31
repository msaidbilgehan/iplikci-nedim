# ADR-0006: Para tipi ve alan kodları

Durum: Kabul edildi · Tarih: 2026-10-31 · Dayanak: tasarım, G6

## Bağlam

MVP tutarları `float` olarak tutuyor ve ekstre kontrolünde 0,015'lik bir tolerans kullanıyor; alan kodları Türkçe
(`harcama`, `kisiye_transfer`). V1'de birden çok para birimi, altın ve dış kur kaynakları var; kod tabanı İngilizce
adlandırılıyor.

## Karar

**Para ve miktar**

- Alan modelinde tutarlar `Money(amount: Decimal, currency: str)` tipindedir. Para birimi ISO kodudur (`TRY`, `EUR`,
  `USD`); arayüzde TRY "TL" olarak yazılır.
- Veritabanında tutar, en küçük birim cinsinden bir tamsayı (kuruş, sent) ile para birimi olarak saklanır.
- Altın gramı ve menkul kıymet adedi `Decimal` metni olarak saklanır (birimiyle birlikte `Quantity` tipi). Kurlar da
  `Decimal` metnidir.
- Belge okunurken tutarlar iki haneye `ROUND_HALF_UP` ile yuvarlanır.
- Kart ekstresi kontrolü: |fark| ≤ 1 kuruş. MVP'deki 0,015 eşiğiyle aynı sonucu verir.

**Alan kodları**

- Alan kodları İngilizcedir. Türkçe etiketleri tek bir eşleme modülünde ve arayüz çevirilerindedir.
- Eşleme tablosu [domain/ledger.md](../domain/ledger.md) dosyasındadır.
- `kategoriler.yaml` anahtarları (`_gereklilik`, `_düzenli`, `_biten`…) kullanıcıya açık olduğu için Türkçe kalır.

## Sonuçlar

- Olumlu: toplamlar kesindir; kur çevirisi açıktır ve kaynağı bellidir; kod tabanı İngilizcedir.
- Olumsuz: Aşama 1'de kodların bir kez çevrilmesi gerekir. MVP önbelleği taşınmaz; belgeler yeniden okunur.

## Değerlendirilen seçenekler

- **`float` + tolerans:** yuvarlama hatalarını gizler; döviz toplamlarında hata birikir.
- **Tutarları metin olarak saklamak:** SQL'de sıralama ve toplama zorlaşır.
