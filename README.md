# İplikçi Nedim

İngilizce alternatif adı: **Money-Grubber**. Adını bir filmde paraları tutan karakterden alır.

Depo: <https://github.com/msaidbilgehan/iplikci-nedim> · Komut ve Python paketi kısa adla `iplikci` olacak.

Kişisel finans asistanı platformu:

- Bankaların e-postayla gönderdiği ekstreleri, dekontları, bildirimleri ve ödeme hatırlatmalarını kendiliğinden
  toplar, doğrular ve belgeleriyle birlikte saklar.
- Harcamaları, gelirleri, hesapları, abonelikleri ve döviz varlıklarını yorumlar.
- Aylık raporların yanında güncel akışı da anlık izletir; her rakamdan dayandığı belgeye gidilebilir.
- Bilgisayarda bir servis olarak çalışır; tarayıcıdan (PWA) ve MCP üzerinden Claude ile kullanılır.

## Durum

Tasarım tamamlandı, uygulama [yol haritası](docs/v1/roadmap.md)'nın Aşama 0'ıyla başlayacak. Bu depoda henüz kod yok.
Başlangıç sürümü (MVP, `gider-analizi`) 2026-10-31'de emekliye ayrıldı. İplikçi Nedim onun kodundan başlar ama
verisini devralmaz; belgeleri kendisi toplar.

## Belgeler

- [Belge dizini ve okuma sırası](docs/README.md)
- [V1 gereksinimleri ve kararlar](docs/v1/requirements.md)
- [Mimari](docs/v1/architecture.md) · [Özellikler](docs/v1/features.md) · [Yol haritası](docs/v1/roadmap.md) ·
  [MVP'den geçiş](docs/v1/migration.md)
- [Mimari karar kayıtları](docs/adr/README.md)
- Geliştiriciler ve ajanlar için kurallar: [`CLAUDE.md`](CLAUDE.md)

## İlkeler

- Banka akışları esastır: her para hareketi bir banka belgesine dayanır; diğer e-postalar kanıt ve bilgi katmanıdır.
- Yerel öncelik: belgeler ve veriler bu bilgisayarda, deponun dışındaki veri klasöründe durur. Ağa yalnızca e-posta
  okumak, döviz kurlarını almak ve bildirim göndermek için çıkılır.
- Yalnızca kişisel para hareketleri; şirket belgeleri kapsam dışıdır.
- Hiçbir belge kalıcı silinmez.
- Finanstan anlayan da anlamayan da kullanmak istemeli.
- Kişisel ihtiyaçlar için yapılan bir hobi projesi, kurumsal bir ürün değil; yine de her kullanıcıya azami verim
  sağlamalı.
