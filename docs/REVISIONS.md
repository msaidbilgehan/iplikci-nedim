# Revizyonlar

İplikçi Nedim'in (İngilizce alternatif adı Money-Grubber) revizyonları: her revizyonun gereksinimleri ve kararları
kendi klasöründe, fikirler ve karar bekleyen sorular [`BRAINSTORM.md`](BRAINSTORM.md)'de.

| Revizyon | Konu | Durum | Belge |
|---|---|---|---|
| V0 | MVP `gider-analizi`: banka belgelerini okuyan, doğrulayan, yorumlayan yerel komut satırı programı, web paneli ve MCP sunucusu | 2026-10-31'de emekliye ayrıldı (K17) | Depo dışında, veri klasöründeki arşivde: `archive/mvp/CLAUDE.md` ve `README.md` |
| V1 | Tam teşekküllü kişisel finans analizi ve gelir-gider yorumlama platformu | Aşama 0 (v0.1.0) uygulandı; sırada Aşama 1 var | [`v1/requirements.md`](v1/requirements.md), [`v1/architecture.md`](v1/architecture.md), [`v1/features.md`](v1/features.md), [`v1/roadmap.md`](v1/roadmap.md), [`v1/migration.md`](v1/migration.md) |
| V2 | Finansal strateji uzmanları ve yapay zekâ asistanı | Gelecek (V1'den sonra) | [`v2/requirements.md`](v2/requirements.md) |

## Değişiklik kaydı

- 2026-11-01 (12) — Aşama 1 uygulandı (`asama-1` dalı); belgeler kodla uyumlu hâle getirildi:
  - README'nin durum bölümü ve geliştirici komutları güncellendi; `CHANGELOG.md`'ye 0.2.0 eklendi.
  - [Mimari §9](v1/architecture.md#9-veri-klasörü): doğrulama tabanının yeri (`baseline.json`).
  - [Defter](domain/ledger.md#doğrulama-değişmezleri): taban veri klasöründe; `--arsiv` ve `--yeniden-kur` eklendi.
  - [ADR-0006](adr/0006-money-and-codes.md)'ya uygulama notu: satır tutarları `Decimal`; satırlar `Money`'yi, defter
    ve yorum hesapları kendi paketlerine taşınırken alır. Geçişte demonun tabanı değişmedi.
  - [Geçiş](v1/migration.md#aşama-1-çalışma-alanından-veri-klasörüne) belgesine Aşama 1 adımı eklendi.
  - [Eşitlik listesi](v1/features.md#mvp-eşitlik-listesi)'nde kopyalar işaretlendi.
  - Kullanıcıya görünen metinler `kategoriler.yaml` yerine kişisel kuralları anıyor.
- 2026-11-01 (11) — Kullanıcı kararı [K18](v1/requirements.md#kararlar): depo özel kalır, lisans BSD 3-Clause
  (`LICENSE.txt`, kullanıcı ekledi). CLAUDE.md, gereksinimlerdeki açık soru, README ve `pyproject.toml`'un lisans
  alanları buna göre güncellendi.
- 2026-11-01 (10) — Aşama 0 uygulandı (`asama-0` dalı); belgeler kodla uyumlu hâle getirildi:
  - README'nin durum bölümü güncellendi; geliştiriciler için komutlar eklendi. `CHANGELOG.md` başladı.
  - [Yol haritası](v1/roadmap.md)'nın ilk oturum bölümü, adımların uygulandığını söylüyor.
  - [Geçiş](v1/migration.md#aşama-0-kod-arşivden-depoya) belgesindeki Aşama 0 adımları yapılanlarla işaretlendi.
  - [Defter](domain/ledger.md#doğrulama-değişmezleri) belgesine doğrulama tabanının içeriği, `--tarih` ve `--kabul`
    eklendi.
  - [ADR-0001](adr/0001-modular-monolith-service.md)'deki servis komutu, mimarideki adıyla (`iplikci servis calistir`)
    eşlendi. Mimarinin ölçek bölümü, verinin MVP'ye ait olduğunu ve V1'e devredilmediğini söylüyor.
- 2026-11-01 (9) — İlk commit'ten önceki düzeltmeler:
  - [Kategori kuralları](domain/categorization.md)'ndaki örnek işyeri, kişisel kurallardan gelen bir ad yerine genel bir
    zincir oldu.
- 2026-10-31 (8) — Eski yapı kaldırıldı ve MVP emekliye ayrıldı ([K17](v1/requirements.md#kararlar),
  [ADR-0018](adr/0018-retire-mvp-clean-start.md)). Kullanıcı, İplikçi Nedim'in veriyi kendisi toplamasını istedi;
  sistem MVP'nin belge klasörleriyle ve taşıma kayıtlarıyla çalışmayacak.
  - MVP'nin kodu, testleri, kuralları ve ayarları veri klasörünün arşivine (`archive/mvp/`) kopyalandı. Aşama 0 kodu
    oradan alır; kişisel kurallar ve ayarlar V1'e aktarılmaz.
  - Geçiş planı yeniden yazıldı.
  - Yol haritasından `migrate-mvp` ve geçiş aşaması çıkarıldı. Gerçek belgeler gelene dek taban demo çalışma alanında
    alınır; `v1.0.0` sürüm koşulları sağlanınca atılır.
  - CLAUDE.md, gereksinimler, mimari, özellikler ve ilgili ADR'ler buna göre güncellendi.
- 2026-10-31 (7) — Son düzeltmeler; çalışma artık yalnızca depo klasöründe.
- 2026-10-31 (6) — Kullanıcı eklentinin okuma yolu olarak B'yi, yani Gmail'in web arayüzünü seçti
  ([K16](v1/requirements.md#kararlar)). Apps Script kendiliğinden kurulamıyor ve kurulumu son kullanıcıya göre değil.
  - [ADR-0016](adr/0016-mail-connectors.md) kabul edildi. Gmail'den okuma üç katmana ayrıldı: belgelenmiş gelen
    kutusu akışı, web araması ve ham ileti. Doğrulaması Aşama 3'ün ilk işi oldu.
  - Eşleştirme, kod yazmak yerine eklentide tek bir onaya indi.
- 2026-10-31 (5) — Kullanıcı Thunderbird köprüsünü reddetti, bir Chrome eklentisi önerdi ve iki ilke koydu: platformdan
  bağımsızlık ve terminalsiz kullanım ([K14, K15](v1/requirements.md#kararlar)).
  - [ADR-0016](adr/0016-mail-connectors.md) tarayıcı eklentisi köprüsü olarak yeniden yazıldı (önerildi). Okuma yolu
    (A: Apps Script, B: Gmail web) tarayıcıdaki bir denemeyle seçilecek.
  - [ADR-0017](adr/0017-no-terminal-install.md) eklendi: işletim sistemi başına kurulum paketi ve her işin arayüzde
    olması (önerildi).
  - Mimari, özellikler, yol haritası (eklenti Aşama 3'te, paketler Aşama 6'da), geçiş planı ve CLAUDE.md buna göre
    güncellendi.
- 2026-10-31 (4) — Ad düzeltmesi ve e-posta bağlantısı:
  - Ad **İplikçi Nedim** oldu ([K1](v1/requirements.md#kararlar)). Depo ve dağıtım adı `iplikci-nedim`. Python paketi, komut ve diğer teknik adlar kısa adla `iplikci` kalır.
  - Gelişmiş Koruma'daki (Advanced Protection) Gmail hesaplarında uygulama şifresi yok; MVP'nin e-posta alımı bu hesaplarda çalışmaz. E-posta bağlantısı için [ADR-0016](adr/0016-mail-connectors.md) önerildi. Önerilen yol Thunderbird
    köprüsü; kabulü kullanıcının denemesine bağlı.
- 2026-10-31 (3) — Belgeler son hâline getirildi; uygulama yeni bir oturumda Aşama 0 ile başlayacak. Eklenenler:
  - [Mimari](v1/architecture.md), [özellikler](v1/features.md) (kabul ölçütleri ve MVP eşitlik listesiyle),
    [yol haritası](v1/roadmap.md) ve [geçiş planı](v1/migration.md).
  - [ADR-0001 … ADR-0015](adr/README.md).
  - [Alan kuralları](domain/): MVP'nin `CLAUDE.md`'sindeki bilgi kişisel verilerden arındırılıp Türkçe olarak buraya
    taşındı.
  - Deponun `CLAUDE.md`'si, belge dizini ve `.gitignore`.

  Beyin fırtınası kapatıldı. Açık sorular varsayılan kararlarla kapatıldı (V1 gereksinimleri → Açık sorular).
- 2026-10-31 (2) — Kullanıcının yanıtları işlendi: ad İplikçi (`iplikci`), İngilizce alternatif Money-Grubber;
  belgeler `iplikci` deposuna taşındı ve depoya README eklendi. V1'e ürün ilkeleri, karar kaydı (K1–K13), kural
  değişiklikleri tablosu ve yeni gereksinimler eklendi: G10 anlık finansal akış, G11 hesap türlerine göre toplu ve
  ayrı akışlar, G12 kural tabanlı bildirimler (e-posta, Telegram), G13 banka dışı e-postalar. Beyin fırtınasında
  onaylanan öneriler işaretlendi; yeni bölümler §16–§20 eklendi; yol haritası §21'e, sorular §22'ye taşındı.
- 2026-10-31 (1) — V1 ve V2 gereksinimleri kullanıcının ifadesiyle kaydedildi; gereksinimlere kimlik verildi (V1-G1 …
  V1-G9, V2-G1, V2-G2) ve her birinin bugünkü durumu yazıldı. Beyin fırtınası belgesi açıldı.
