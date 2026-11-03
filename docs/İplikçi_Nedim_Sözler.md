# İplikçi Nedim'in sözleri

Proje: İplikçi Nedim · Tarih: 2026-11-03 · İlgili belgeler: [özellikler, F06](v1/features.md#f06--pano),
[ADR-0020](adr/0020-bridge-sayings.md), [K26](v1/requirements.md#kararlar)

İplikçi Nedim, dizideki sözlerinden birini paranın durumuna göre söyler: Pano'nun en üstünde ve tarayıcı eklentisinin
penceresinde, yüzüyle (logo) birlikte. Sözleri servis seçer (`src/iplikci/app/sayings.py`); listenin kendisi de
oradadır, bu belge onun Türkçe karşılığıdır.

## Nasıl seçilir

- Her söz bir duruma bağlıdır. Durumlar belgelerden çıkar: son kapanan ay, öngörü, borçlar, bu ay, zamlar, gelirler.
- O gün doğru olan bütün durumlar aşağıdaki tablonun sırasıyla dizilir; en üstteki en acil olandır.
  - Gösterilen söz ilk durumunkidir. Bir durumun birden çok sözü varsa söz günden güne değişir, gün içinde aynı kalır.
  - "Başka bir söz" sıradaki sözü gösterir; hepsi o gün doğru olan durumlardandır.
  - Hiçbir durum yoksa "Veri yok" söylenir.
- Sözün altında hangi durum için söylendiği bir cümleyle yazar. Cümle sözcük, gün ve pay taşır; tutar, hesap, kart,
  kişi ya da işyeri adı taşımaz. Eklenti de aynı cümleyi gösterir.
- Yüz durumun rengini alır: iyi giderken logonun kendisi (yeşil), dikkat isteyen durumda turuncu, kritik durumda
  kırmızı, veri yokken ve sessiz ayda gri. Renk tek başına bir şey söylemez; söz ve cümlesi aynı şeyi söyler.
- Ayın hükmü Pano'nunkiyle aynıdır: gelirin bilindiği en yeni kapanmış ay. Kalan, gelenin %10'undan azsa "az kaldı"
  sayılır. "Kapanan son N ay" Pano'nun son yedi ayı içindeki kapanmış aylardır; en iyi ay en az üç ay arasından seçilir.
- Bu ayın tipik ayla karşılaştırması Pano'nun koşullarıyla yapılır: en az üç tam ay ve bugüne kadarki günlerin yarısını
  kapsayan belgeler. Fark %10'dan azsa söylenmez.

## Durumlar ve sözleri

| Sıra | Durum | Renk | Ne zaman | Söz |
|---|---|---|---|---|
| 1 | Öngörü eksiye düşüyor | kritik (bir hafta içinde), değilse dikkat | Öngörüye göre bir hesap ya da hesapların toplamı eksiye düşecek | "Değil ıhlamur içmek, ıhlamur ağacı yesem gevşemez sinirlerim." · "Bize iki ıhlamur getir kızım." |
| 2 | Ay eksiyle kapandı | kritik | Son kapanan ayda harcanan, gelen paradan fazla | "Kara bahtım, kör talihim benim; geleceğim çok karanlık." |
| 3 | Borç varlıktan fazla | dikkat | Borçlar hesaplardaki paradan fazla; TL değeri bilinmeyen bir hesap varken söylenmez | "Elin şeyiyle gerdeğe giren, güvey değil gelin olur." |
| 4 | Bu ay fazla harcanıyor | dikkat | Bu ay bugüne kadar tipik ayın aynı günlerinden en az %10 fazla | "Beni, hiçbir şey değil bu Türk milletinin bonkörlüğü öldürecek." |
| 5 | Az kaldı | dikkat | Son kapanan ayda kalan, gelenin %10'undan az | "Parasız güç, motorsuz araba, bin gez canım." |
| 6 | En iyi ay | iyi | Son kapanan ay, kapanan son aylar içinde en çok paranın kaldığı ay | – "Ortadoğu mu büyük? Ben mi büyüğüm? Çabuk söyle." – "Siz efendim." – "Hıh. Tamam canım." |
| 7 | Döviz geliri | iyi | Son kapanan ayda döviz hesabına gelir girdi | "Türkiye dövize doymaz, para girsin de nasıl girerse girsin." · "Dışarıdan gelen sıcak paranın sahipleri, bıyıklı yabancılardır. Yani biziz." · "Türkiye büyümeyi çok sever, bu nedenle sıcak paraya hayır demez." |
| 8 | Bu ay az harcanıyor | iyi | Bu ay bugüne kadar tipik ayın aynı günlerinden en az %10 az | "Çakır, nereden buldun bu sert adamı?" |
| 9 | Birikim | iyi | Son kapanan ayda birikime ya da yatırıma para ayrıldı | "Bak evladım; Türk'ten karını, Çeçen'den canını, Azeri'den malını saklayacaksın." · "Ha param ha canım kuzum." |
| 10 | Gelir geldi | iyi | Son 7 günde düzenli bir gelir hesaba geçti | "Evladım, para alacağın zaman kapısını aç kasanın! Kerhane kapısı mıdır bu? Kasa kapısıdır!" · "Nerede görülmüş iplikçinin paraya hayır dediği canım." |
| 11 | İyi bir ay | iyi | Son kapanan ayda kalan, gelenin en az %10'u | "Para size ne lazım, para ehline lazım." · "Bizim en güzel özelliğimiz; paraya asla hayır demek yok." |
| 12 | Zam | dikkat | Son 45 günde bir düzenli ödemenin tutarı arttı | "İnsaf kalmamış ben-i âdemde, anamı ağlattılar Acıbadem'de." |
| 13 | Faiz ve ücret | dikkat | Son kapanan ayda bankalara faiz ya da ücret ödendi | "Allah belasını versin büyük Ortadoğu'nun… Tuvalet mi canım bu? Küçük bin, büyük iki bin." |
| 14 | Sessiz ay | yansız | Son kapanan ayda ne gelir geldi ne harcama yapıldı | "Çakır, kuzum…" |
| 15 | Veri yok | yansız | Yukarıdakilerin hiçbiri yok: belge yok ya da gelirin bilindiği kapanmış ay yok | "İsa Muhammed aşkına bilmiyorum." |

## Liste üzerine notlar

- Kullanıcının 2026-11-03'te verdiği listede "Bak evladım…" iki kez yazılıydı; bir kez alındı.
- Yazım düzeltildi: Türkçe harfler ("canım", "kızım", "evladım", "karanlık", "kapısını", "Çakır"), "ıhlamur",
  "Çeçen'den canını", "Azeri'den", "ben-i âdemde" ve "Acıbadem'de".
- Sözler dizinin dilindedir; bazıları kaba ya da şakacıdır. Bir söz değişecekse hem `app/sayings.py` hem bu belge
  değişir; testler her sözün bir durumu olduğunu ve her durumun bir yüzü olduğunu denetler.
