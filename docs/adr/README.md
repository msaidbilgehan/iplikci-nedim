# Mimari karar kayıtları (ADR)

Her önemli tasarım kararı bir kayıttır: bağlam, karar, sonuçlar ve değerlendirilen seçenekler. Kabul edilmiş bir kayıt
değiştirilmez; karar değişirse yeni bir kayıt yazılır ve eskisinin durumu "Yerini ADR-NNNN aldı" olur.

Dayanak sütunu kararın kaynağını gösterir. `K…` kullanıcının kararıdır ([V1 kararları](../v1/requirements.md#kararlar)).
"Tasarım" ise mühendislik kararıdır: kullanıcı 2026-10-31'de belgelerin son hâline getirilmesini istedi; bu kararlar
kullanıcı aksini söylemedikçe geçerlidir.

| No | Karar | Dayanak |
|---|---|---|
| [0001](0001-modular-monolith-service.md) | Tek süreçli modüler monolit servis | K5, G4, G10, G12 |
| [0002](0002-code-data-separation.md) | Kod ile veri ayrımı ve veri klasörü | K2, tasarım |
| [0003](0003-content-addressed-vault.md) | İçerik adresli belge arşivi | K3, K4, K11 |
| [0004](0004-sqlite-primary-store.md) | SQLite birincil veri deposu; veritabanı yeniden kurulabilir | K3, tasarım |
| [0005](0005-parser-plugins.md) | Okuyucu eklenti sözleşmesi ve okuyucu başına sürüm | K6 |
| [0006](0006-money-and-codes.md) | Para tipi ve alan kodları | tasarım |
| [0007](0007-api-and-auth.md) | HTTP API ve oturum modeli | K5, tasarım |
| [0008](0008-frontend-pwa.md) | Ön yüz: React + TypeScript + Vite + Tailwind PWA | K5, tasarım |
| [0009](0009-network-egress-policy.md) | Ağ çıkışı politikası | K8, K10, K5 |
| [0010](0010-notification-channels.md) | Bildirim kanalları ve içerik düzeyleri | K10, tasarım |
| [0011](0011-mcp.md) | MCP: resmî SDK, servis üzerinden HTTP ve stdio köprüsü | K9 |
| [0012](0012-remote-access-tailscale.md) | Uzaktan erişim yalnızca Tailscale ile | K5 |
| [0013](0013-mvp-migration.md) | MVP'den geçiş: kodu ilk sürüm olarak alıp kademeli dönüştürmek (2.–5. maddelerin yerini 0018 aldı) | K2, tasarım |
| [0014](0014-event-log-and-jobs.md) | Olay kaydı ve SQLite tabanlı iş kuyruğu | tasarım |
| [0015](0015-email-ingestion.md) | E-posta alımı: IDLE, güven kuralı, gövde okuma, `.eml` saklama | G1, G13, K12 |
| [0016](0016-mail-connectors.md) | E-posta bağlayıcıları; uygulama şifresi olmayan Gmail için Gmail'in web arayüzünü okuyan tarayıcı eklentisi | G1, G12, K5, K10, K14, K15, K16 |
| [0017](0017-no-terminal-install.md) | Terminalsiz kurulum ve kullanım: işletim sistemi başına kurulum paketi (kabul edildi 2026-11-02; imzasız, K22) | K14, K22, G4 |
| [0018](0018-retire-mvp-clean-start.md) | MVP'yi V1'den önce emekliye ayırmak ve veri taşımadan başlamak | K17 |
| [0019](0019-bridge-login-link.md) | Eşleşmiş tarayıcı eklentisi arayüzü tek kullanımlık giriş bağlantısıyla açar | K14, tasarım |
| [0020](0020-bridge-sayings.md) | Eşleşmiş tarayıcı eklentisi İplikçi Nedim'in sözlerini servisten alır | K26, tasarım |
| [0021](0021-telegram-documents.md) | Eşleşmiş Telegram sohbetinden bota gönderilen belgeler arşive alınır | K28 |
| [0022](0022-releases-and-updates.md) | Sürümler GitHub'da yayımlanır; uygulama imzalı bildirgeyle kendini, eklentiyi mağaza günceller | K29, K14, K22 |
| [0023](0023-claude-memory.md) | Claude'un hafızası İplikçi Nedim'de durur, MCP ile okunup yazılır | K30, K9 |
| [0024](0024-extension-leads-to-download.md) | Programı bulamayan eklenti, son kurulum paketinin indirilmesine yeni bir sekmede yol gösterir; eklenti mağazada herkese açık | K31, K29, K14, K22 |

Yeni kayıt: sıradaki numarayla `NNNN-kisa-ad.md`; başlık karar cümlesi olur; bu tabloya eklenir.
