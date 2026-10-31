# ADR-0002: Kod ile veri ayrımı ve veri klasörü

Durum: Kabul edildi · Tarih: 2026-10-31 · Dayanak: K2, tasarım

## Bağlam

Depo GitHub'da ve herkese açık olabilir; belgeler ve onlardan türeyen her şey ise kişisel finans verisidir. Depo
içinde git'in yok saydığı bir klasör tek bir `git clean -xfd` ile tamamen silinebilir ya da yanlışlıkla commit
edilebilir. macOS'ta Belgeler ve Masaüstü klasörleri iCloud'a eşitlenebilir.

## Karar

Bütün kişisel veri, deponun dışındaki veri klasöründe durur:

| Sistem | Varsayılan yol |
|---|---|
| macOS | `~/Library/Application Support/iplikci/` |
| Linux | `${XDG_DATA_HOME:-~/.local/share}/iplikci/` |
| Windows | `%LOCALAPPDATA%\iplikci\` |

- `IPLIKCI_HOME` ortam değişkeni bu yolu değiştirir (testler ve demo çalışma alanı için).
- Klasörün izni 0700, dosyaların izni 0600'dür. Klasörün düzeni [mimari §9](../v1/architecture.md#9-veri-klasörü)'dadır.
- Depoda yalnızca kod, uygulamayla gelen genel kurallar, belgeler ve sahte verili testler bulunur.
- Depo herkese açıkmış gibi yazılır. `.gitignore` banka belgesi türlerini ve veri klasörlerini dışarıda tutar; commit
  öncesinde gizli veri taraması (gitleaks) çalışır.

## Sonuçlar

- Olumlu: `git clean` veriyi silemez, veri iCloud'a gitmez, depo paylaşılabilir.
- Olumsuz: veri Finder'da gizli bir yerdedir. Arayüz "veri klasörünü aç" ve "gelen klasörünü aç" komutlarını sunar.
- Geliştirme gerçek veriyle değil, sahte belgelerle kurulan bir demo çalışma alanında yapılır (`iplikci dev demo`).

## Değerlendirilen seçenekler

- **Depo içinde, git'in yok saydığı bir klasör:** yukarıdaki silinme ve sızma riskleri.
- **Ev klasöründe elle seçilmiş görünür bir klasör:** tek bir kullanıcının düzenine bağlar, başka bir kullanıcıya
  taşınmaz.
- **`~/Documents` altı:** iCloud eşitlemesi açıksa belgeler buluta gider.
