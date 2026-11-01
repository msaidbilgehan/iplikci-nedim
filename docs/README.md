# İplikçi Nedim belgeleri

Bütün belgeler Türkçedir; ajan talimatları deponun kökündeki `CLAUDE.md`'dedir (İngilizce).

## Okuma sırası

1. [Revizyonlar](REVISIONS.md): hangi revizyon nerede, değişiklik kaydı.
2. [V1 gereksinimleri](v1/requirements.md): kullanıcının istekleri ve yanıtları, ürün ilkeleri, kararlar (K1–K21),
   gereksinimler (G1–G13).
3. [V1 mimarisi](v1/architecture.md): bileşenler, veri modeli, veri klasörü, API, MCP, güvenlik, hedefler.
4. [V1 özellikleri](v1/features.md): ekran ekran davranış, kabul ölçütleri, MVP eşitlik listesi.
5. [V1 yol haritası](v1/roadmap.md): aşamalar, çıkış koşulları, ilk oturumun adımları.
6. [Geçiş](v1/migration.md): eski çalışma alanındaki her dosyanın akıbeti, MVP'nin arşivi ve V1'in geçmişi nasıl
   kurduğu.

## Başvuru

| Belge | İçerik |
|---|---|
| [Mimari karar kayıtları](adr/README.md) | ADR-0001 … ADR-0018: neden böyle tasarlandı |
| [Banka biçimleri](domain/bank-formats.md) | Bankaların belgelerindeki biçimler ve tuzaklar |
| [Defter kuralları](domain/ledger.md) | İşaret, türler, doğrulama, kanıt uzlaştırma, transferler, kur, kapsama |
| [Kategori kuralları](domain/categorization.md) | Kural dosyası yapısı, katmanlar, eşleştirme sırası |
| [Yorum ve ay sonu](domain/interpretation.md) | Düzenli ödemeler, alışkanlıklar, tahmin, varlıklar, ay kapanışı |
| [V2 gereksinimleri](v2/requirements.md) | Strateji uzmanları ve yapay zekâ asistanı (gelecek) |
| [Beyin fırtınası](BRAINSTORM.md) | Kararların çıktığı tartışma (kapandı; tarihçe) |

## Belgeleri güncel tutmak

- Bir özelliği getiren değişiklik, belgesini de getirir: features, mimari, gerekiyorsa bir ADR.
- Kararlar değişince eski ADR değiştirilmez; yenisi yazılır.
- Kullanıcının yeni bir kararı `v1/requirements.md`'deki Kararlar tablosuna ve `REVISIONS.md`'nin değişiklik kaydına
  işlenir.
- Belgelere kişisel veri yazılmaz: ad, hesap numarası, IBAN, tutar, e-posta adresi yok. Depo herkese açıkmış gibi
  yazılır.
