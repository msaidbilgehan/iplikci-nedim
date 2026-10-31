# V2 — Finansal strateji uzmanları ve yapay zekâ asistanı

Durum: gelecek (V1'den sonra) · Kaydedildi: 2026-10-31

İlgili belgeler: [Revizyonlar](../REVISIONS.md) · [V1](../v1/requirements.md) · [Beyin fırtınası](../BRAINSTORM.md)

## Kullanıcının ifadesiyle (2026-10-31)

> [FUTURE->V2]
> - Gelir-Gider ve finansal strateji uzmanları ile kullanıcıya gelir maksimizasyonu sağlayabilmesi için asiste
>   edilmeli.
> - AI Asistan hem gemini, claude, openai gibi servislerin subscription'larına bağlanabilmeli hem de api usage
>   eklenerek kullanılabilmeli

## Gereksinimler

### G1 — Uzman desteğiyle gelir maksimizasyonu

İstenen: gelir-gider ve finansal strateji uzmanlarıyla kullanıcıya, gelirini en üst düzeye çıkarması için yardım
edilir.

Açık nokta: "uzmanlar" yapay zekâ ajanları mı (her biri bir alanda uzman rolünde), insan uzmanlar (mali müşavir,
finans danışmanı) için rapor paylaşımı mı, yoksa ikisi mi?

Notlar:
- Gider tarafı (tasarruf adımları, bütçe) V0'da var; V2'nin farkı gelir tarafı: atıl nakdin getirisi, döviz gelirinin
  bozdurma zamanı ve kur makası, BES devlet katkısından tam yararlanma, ek gelir senaryoları.
- Asistanın söylediği her rakam araçlardan gelir (V0'ın MCP ilkesi); olgu ile öneri ayrı gösterilir.
- Türkiye'de yatırım danışmanlığı SPK iznine bağlı bir faaliyettir: asistanın çıktıları kişisel analiz ve bilgi
  olarak çerçevelenmeli (ürün başkalarına açılırsa önem kazanır).

### G2 — Abonelikle ve API ile çalışan yapay zekâ asistanı

İstenen: asistan Gemini, Claude, OpenAI gibi servislerin aboneliklerine bağlanabilir; ayrıca API kullanımıyla
(API anahtarı) çalışabilir.

Notlar:
- API kipi: sağlayıcıdan bağımsız bir katman (Anthropic, OpenAI, Google); anahtarlar anahtar zincirinde; kullanım ve
  maliyet takibi, aylık üst sınır, görev başına model seçimi.
- Abonelik kipi sağlayıcı koşullarına bağlı. Anthropic, önceden onay olmadan üçüncü taraf ürünlerin claude.ai girişi
  ya da abonelik kullanım limitleri sunmasına izin vermiyor, API anahtarıyla kimlik doğrulamayı istiyor (Agent SDK
  belgeleri, 2026-10-31'de okundu). OpenAI ve Google'ın güncel koşulları V2'ye başlarken kontrol edilmeli.
- Aboneliği kullanmanın sağlam yolu: abonelik, sağlayıcının kendi istemcisinde çalışır (yerel MCP destekleyen Claude
  Desktop, Claude Code, Gemini CLI gibi), uygulama verisini ve araçlarını MCP ile sunar (V1-G9). Web istemcilerinin
  bağlayıcıları genellikle internetten erişilebilen bir HTTPS adresi ister; bu, yerel öncelik ilkesiyle çelişir.
- Uygulama içi asistan kendi MCP sunucumuzun bir istemcisi olur: dış istemciler ve iç asistan aynı araçları kullanır.
- Gizlilik: hangi verinin hangi sağlayıcıya gittiği kullanıcının onayıyla; maskeleme (IBAN, hesap numarası, kişi
  adları); gönderilenlerin kaydı. Tam gizlilik için yerel model seçeneği (Ollama, LM Studio, MLX).

## V1'den beklenenler

- Kapsamlı MCP araçları ve kaynakları (V1-G9, [ADR-0011](../adr/0011-mcp.md)): asistanın tek veri yolu.
- Ağ politikası ([ADR-0009](../adr/0009-network-egress-policy.md)): yapay zekâ sağlayıcılarına bağlantı yeni bir dış
  bağlantıdır. Bu bağlantı, hangi verinin gideceğini ve kullanıcı onayını tanımlayan yeni bir ADR ile eklenir.
- İşlemden belgeye iz (V1-G2): asistan her iddiasını belgesiyle gösterebilmeli.
- Kalıcı işlem kimlikleri ve saklanan kullanıcı kararları: asistanın önerdiği kural ve düzeltmeler yeniden okumada
  kaybolmamalı.
- Deterministik senaryo hesapları: asistan "ya şöyle olursa" sorularını hesaplatır, rakam uydurmaz.
