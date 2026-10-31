# ADR-0013: MVP'den geçiş: kodu ilk sürüm olarak alıp kademeli dönüştürmek

Durum: Kabul edildi; 2.–5. maddelerinin yerini [ADR-0018](0018-retire-mvp-clean-start.md) aldı (2026-10-31) ·
Tarih: 2026-10-31 · Dayanak: K2, tasarım

## Bağlam

MVP çalışıyor ve gerçek belgelerin tamamında doğrulanmış durumda. Okuyucular, uzlaştırma ve transfer kuralları en
değerli birikim. MVP kodu ise sürüm kontrolünde değil. Sıfırdan yazmak, uzun bir süre çalışan bir sistem olmaması ve
davranışların kayması riskini taşır.

## Karar

1. MVP kodu temizlenerek depoya ilk sürüm (`v0.1.0`) olarak alınır. Yalnızca paket adı değişir; davranış aynı kalır.
   Temizlik:
   - Şirket adı koddan ayara taşınır.
   - Test verisi taranır.
   - Kişisel değer kalmadığı gitleaks ve elle aramayla doğrulanır.
2. İlk sürümde testler geçmeli ve `iplikci dogrula` MVP'nin tabanıyla birebir aynı çıkmalıdır.
3. Sonra sistem yol haritasındaki aşamalarla yerinde dönüştürülür. Her aşama gerçek belgelerle eşitlik doğrulamasıyla
   biter. Bu doğrulama yerelde yapılır, CI'da asla yapılmaz.
4. MVP klasörü geçiş boyunca donmuş kalır (yalnızca hata düzeltmesi) ve çalışmayı sürdürür.
5. Geçişin son adımı [migration.md](../v1/migration.md)'deki gibi yapılır; eski klasörler kayıtla birlikte çöp kutusuna
   taşınır.

## Sonuçlar

- Olumlu: her an çalışan ve doğrulanabilir bir sistem vardır; dönüşüm küçük, geri alınabilir adımlarla ilerler; depo
  geçmişi MVP'den başlar.
- Olumsuz: bir süre eski ve yeni yapı yan yana durur; aşamalar arasında geçici bağdaştırıcılar gerekir.

## Değerlendirilen seçenekler

- **Yeni iskeleti sıfırdan yazıp okuyucuları tek tek taşımak:** uzun süre çalışan bir sistem yoktur ve davranış kayar.
- **MVP klasöründe geliştirmeye devam etmek:** depo geçmişi ve CI yoktur; kişisel veri kodla aynı klasördedir.
