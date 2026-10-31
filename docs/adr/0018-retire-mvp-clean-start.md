# ADR-0018: MVP'yi V1'den önce emekliye ayırmak ve veri taşımadan başlamak

Durum: Kabul edildi · Tarih: 2026-10-31 · Dayanak: K17 · [ADR-0013](0013-mvp-migration.md)'ün 2.–5. maddelerinin
yerini alır

## Bağlam

[ADR-0013](0013-mvp-migration.md)'e göre MVP, V1 eşitliği sağlayana dek donmuş olarak çalışacaktı. Plan şöyleydi:

- V1'in tabanı, MVP'nin gerçek belgeler üzerindeki tabanıyla karşılaştırılacaktı.
- `Bankalar/` ve `Gelen Belgeler/`deki belgeler V1'in arşivine kopyalanacaktı.
- MVP'nin taşıma kayıtları V1'in denetim kaydına alınacaktı.

2026-10-31'de durum değişti:

- MVP'nin e-posta alımı uygulama şifresine dayanır; Gelişmiş Koruma'daki hesaplarda bu yol kapalıdır ve reddedilen
  girişi yeniden denemek hesabı kilitletebilir.
- Kullanıcı, V1'in veriyi kendisi toplamasını istedi (K17). V1 elle taşınan belgelerle, MVP'nin klasörleriyle ve
  taşıma kayıtlarıyla çalışmayacak; bunlar kaldırılacak.

## Karar

1. **MVP emekliye ayrıldı (2026-10-31).** Arka plan görevi (`gider-analizi otomatik --kaldir`) ve e-posta kaydı
   (`gider-analizi eposta --kaldir`, anahtar zincirindeki şifresiyle) kaldırıldı.
2. **Kod korunur, veri taşınmaz.**
   - MVP'nin şu dosyaları veri klasörüne kopyalandı: kodu, testleri, `README.md`, `CLAUDE.md`, `kategoriler.yaml` ve
     `ayarlar.toml`. Yeri `archive/mvp/`'dir ([mimari §9](../v1/architecture.md#9-veri-klasörü)).
   - Aşama 0 kodu ve testleri buradan depoya alır, genel kategori kurallarını da buradaki `kategoriler.yaml`'dan
     ayıklar.
   - V1'e aktarılmayanlar: belgeler, taşıma kayıtları, MVP çıktıları, ayarlar ve kişisel kurallar.
   - V1 çalışırken bu klasörü okumaz ve klasöre hiçbir şey yazılmaz.
3. **MVP'nin klasörleri kullanılmaz.** Belge klasörleri, çıktıları ve taşıma kayıtları V1'e girmez; kaldırılanlar
   taşıma kaydıyla sistemin çöp kutusuna gider, kalıcı silme yok (ADR-0003). Ayrıntılar
   [geçiş belgesinde](../v1/migration.md).
4. **Taban.**
   - V1'in arşivine gerçek belge girene dek güvenlik ağı iki şeydir: MVP'nin testleri ve demo çalışma alanının altın
     tabanı. Demo çalışma alanı sahte belgelerle kurulur (`iplikci dev demo`); ikisi de CI'da çalışır.
   - Arşivde gerçek belge olunca `iplikci dogrula --taban` onların tabanını alır ve her aşama bu tabanı korur. Bu
     doğrulama yerelde yapılır.
5. **Geçmiş.**
   - V1'in geçmişi, posta kutusu baştan okunarak kurulur (ADR-0016'nın web araması katmanı). Başlangıç günü kurulum
     sihirbazında seçilir.
   - E-postayla gelmeyen belgeler (bankanın sitesinden indirilen dökümler gibi) yalnızca kullanıcı yüklerse girer.
     Sistem eksik dönemleri gösterir.
6. **Sürüm 1.0.** ADR-0013'ün "geçiş" aşaması kalktı. `v1.0.0`, [yol haritası](../v1/roadmap.md#sürüm-10)'ndaki
   koşullar sağlanınca atılır.

## Sonuçlar

**Olumlu**

- V1, elle kurulmuş bir klasör düzenine ve onun kayıtlarına bağlı değildir. Tek veri kaynağı kendi arşividir.
- MVP'nin reddedilen girişi yeniden denemesi biter; hesabın kilitlenme riski kalmaz.
- Yazılmayacak geçiş işleri: kopyalama komutu, eski düzene dışa aktarım ve iki sistemin yan yana çalışması. Yol
  haritası kısalır.

**Olumsuz**

- Aşama 3'e dek çalışan bir sistem yok: rapor, panel ve otomatik belge alımı durdu. Bu sürede bankaların e-postaları
  Gmail'de bekler, kaybolmaz.
- Gerçek belgelerle ilk doğrulama Aşama 3'te yapılır. Aşama 1 ve 2'deki dönüşümleri yalnızca testler korur.
- E-postayla gelmeyen eski dökümler, kullanıcı yeniden yüklemedikçe V1'de olmaz. Çöp kutusu boşaltılırsa geri
  getirmenin tek yolu bankadan yeniden indirmektir.
- Kişisel kurallar (kira, aile, biten abonelikler…) boş başlar ve kullanıcının düzeltmeleriyle yeniden oluşur.
  Eskileri arşivde başvuru için durur.

## Değerlendirilen seçenekler

- **Belgeleri V1'e taşımak ve MVP'yi eşitliğe dek çalıştırmak (ADR-0013):** kullanıcı istemedi (K17).
- **Klasörleri kalıcı silmek:** kalıcı silmeme ilkesine aykırıdır ve geri dönüş yolu bırakmaz.
- **MVP kodunu da yalnızca çöp kutusunda bırakmak:** kodun başka kopyası yoktu. Çöp kutusu boşaltılınca Aşama 0'ın
  kaynağı ve okuyucuların birikimi kaybolurdu.
- **Kodu hemen depoya almak:** kişisel izlerin temizliği Aşama 0'ın işidir ve depo herkese açık olabilir.
