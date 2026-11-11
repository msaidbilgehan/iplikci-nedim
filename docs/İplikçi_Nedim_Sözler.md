# İplikçi Nedim'in sözleri

Proje: İplikçi Nedim · Tarih: 2026-11-03, güncelleme 2026-11-11 (v0.10.1) · İlgili belgeler:
[özellikler, F06](v1/features.md#f06--pano), [ADR-0020](adr/0020-bridge-sayings.md), [K26](v1/requirements.md#kararlar)

İplikçi Nedim, dizideki sözlerinden birini paranın durumuna göre söyler: Pano'nun en üstünde ve tarayıcı eklentisinin
penceresinde, yüzüyle (logo) birlikte. Sözleri servis seçer (`src/iplikci/app/sayings.py`); listenin kendisi de
oradadır, bu belge onun Türkçe karşılığıdır.

## Nasıl seçilir

- Her durumun ona uyan sözleri vardır; bir söz birden çok duruma uyabilir. "Veri yok" dışında her durumun en az iki
  sözü vardır. Durumlar belgelerden çıkar: biten son ay, öngörü, borçlar, bu ay, zamlar, gelirler.
- O gün doğru olan bütün durumlar aşağıdaki tablonun sırasıyla dizilir; en üstteki en acil olandır.
  - Gösterilen söz ilk durumunkidir. Söz o durumun sözleri arasında günden güne değişir, gün içinde aynı kalır.
  - "Başka bir söz" sıradaki sözü gösterir; hepsi o gün doğru olan durumlardandır. Birden çok duruma uyan söz bir kez,
    en acil olanıyla gelir. Bütün sözleri daha önce gelmiş bir durum kendi cümlesini günün sözüyle bir kez daha söyler.
  - Hiçbir durum yoksa "Veri yok" söylenir.
- v0.10.1'e dek her söz tek bir duruma bağlıydı ve 15 durumun 8'inin tek sözü vardı. Pano'nun ayı haftalarca aynı
  kalınca her gün aynı söz görünüyordu: "Parasız güç, motorsuz araba, bin gez canım." O gün
  21 sözün 7'sine "Başka bir söz"le ulaşılabiliyordu.
- Sözün altında hangi durum için söylendiği bir cümleyle yazar. Cümle sözcük, gün ve pay taşır; tutar, hesap, kart,
  kişi ya da işyeri adı taşımaz. Eklenti de aynı cümleyi gösterir.
- Yüz durumun rengini alır: iyi giderken logonun kendisi (yeşil), dikkat isteyen durumda turuncu, kritik durumda
  kırmızı, veri yokken ve sessiz ayda gri. Renk tek başına bir şey söylemez; söz ve cümlesi aynı şeyi söyler.
- Ayın hükmü Pano'nunkiyle aynıdır: gelirin bilindiği, biten en yeni ay. Ay belgelerini hâlâ bekliyorsa (kartın ayın
  son günlerini kapsayan ekstresi gelmediyse) cümle "şimdilik" der; gelecek belgeler gideni ancak artırabileceği için
  gelenden fazla çıkan para "şimdiden" fazladır. Kalan, gelenin %10'undan azsa "az kaldı" sayılır. "Kapanan son N ay"
  Pano'nun son yedi ayı içindeki kapanmış aylardır; en iyi ay en az üç kapanmış ay arasından, yalnızca kapanmış bir
  ay için seçilir.
- Bu ayın tipik ayla karşılaştırması Pano'nun koşullarıyla yapılır: en az üç tam ay ve bugüne kadarki günlerin yarısını
  kapsayan belgeler. Fark %10'dan azsa söylenmez.

## Durumlar ve sözleri

| Sıra | Durum | Renk | Ne zaman | Sözler (günün sözü bu sırayla döner) |
|---|---|---|---|---|
| 1 | Öngörü eksiye düşüyor | kritik (bir hafta içinde), değilse dikkat | Öngörüye göre bir hesap ya da hesapların toplamı eksiye düşecek | "Değil ıhlamur içmek, ıhlamur ağacı yesem gevşemez sinirlerim." · "Bize iki ıhlamur getir kızım." · "Kara bahtım, kör talihim benim; geleceğim çok karanlık." · "Elin şeyiyle gerdeğe giren, güvey değil gelin olur." |
| 2 | Ay eksiyle bitti | kritik | Biten son ayda giden para (ve birikim) gelen paradan fazla | "Kara bahtım, kör talihim benim; geleceğim çok karanlık." · "Beni, hiçbir şey değil bu Türk milletinin bonkörlüğü öldürecek." · "Parasız güç, motorsuz araba, bin gez canım." · "Değil ıhlamur içmek, ıhlamur ağacı yesem gevşemez sinirlerim." · "Elin şeyiyle gerdeğe giren, güvey değil gelin olur." |
| 3 | Borç varlıktan fazla | dikkat | Borçlar hesaplardaki paradan fazla; TL değeri bilinmeyen bir hesap varken söylenmez | "Elin şeyiyle gerdeğe giren, güvey değil gelin olur." · "Parasız güç, motorsuz araba, bin gez canım." · "Kara bahtım, kör talihim benim; geleceğim çok karanlık." |
| 4 | Bu ay fazla harcanıyor | dikkat | Bu ay bugüne kadar tipik ayın aynı günlerinden en az %10 fazla | "Beni, hiçbir şey değil bu Türk milletinin bonkörlüğü öldürecek." · "Bize iki ıhlamur getir kızım." · "Değil ıhlamur içmek, ıhlamur ağacı yesem gevşemez sinirlerim." |
| 5 | Az kaldı | dikkat | Biten son ayda kalan, gelenin %10'undan az | "Parasız güç, motorsuz araba, bin gez canım." · "Beni, hiçbir şey değil bu Türk milletinin bonkörlüğü öldürecek." · "Ha param ha canım kuzum." |
| 6 | En iyi ay | iyi | Biten son ay kapanmış ve kapanan son aylar içinde en çok paranın kaldığı ay | – "Ortadoğu mu büyük? Ben mi büyüğüm? Çabuk söyle." – "Siz efendim." – "Hıh. Tamam canım." · "Para size ne lazım, para ehline lazım." · "Türkiye büyümeyi çok sever, bu nedenle sıcak paraya hayır demez." |
| 7 | Döviz geliri | iyi | Biten son ayda döviz hesabına gelir girdi | "Türkiye dövize doymaz, para girsin de nasıl girerse girsin." · "Dışarıdan gelen sıcak paranın sahipleri, bıyıklı yabancılardır. Yani biziz." · "Türkiye büyümeyi çok sever, bu nedenle sıcak paraya hayır demez." · "Nerede görülmüş iplikçinin paraya hayır dediği canım." · "Bizim en güzel özelliğimiz; paraya asla hayır demek yok." |
| 8 | Bu ay az harcanıyor | iyi | Bu ay bugüne kadar tipik ayın aynı günlerinden en az %10 az | "Çakır, nereden buldun bu sert adamı?" · "Bak evladım; Türk'ten karını, Çeçen'den canını, Azeri'den malını saklayacaksın." |
| 9 | Birikim | iyi | Biten son ayda birikime ya da yatırıma para ayrıldı | "Bak evladım; Türk'ten karını, Çeçen'den canını, Azeri'den malını saklayacaksın." · "Ha param ha canım kuzum." · "Evladım, para alacağın zaman kapısını aç kasanın! Kerhane kapısı mıdır bu? Kasa kapısıdır!" |
| 10 | Gelir geldi | iyi | Son 7 günde düzenli bir gelir hesaba geçti | "Evladım, para alacağın zaman kapısını aç kasanın! Kerhane kapısı mıdır bu? Kasa kapısıdır!" · "Nerede görülmüş iplikçinin paraya hayır dediği canım." · "Bizim en güzel özelliğimiz; paraya asla hayır demek yok." |
| 11 | İyi bir ay | iyi | Biten son ayda kalan, gelenin en az %10'u | "Para size ne lazım, para ehline lazım." · "Bizim en güzel özelliğimiz; paraya asla hayır demek yok." · "Bak evladım; Türk'ten karını, Çeçen'den canını, Azeri'den malını saklayacaksın." |
| 12 | Zam | dikkat | Son 45 günde bir düzenli ödemenin tutarı arttı | "İnsaf kalmamış ben-i âdemde, anamı ağlattılar Acıbadem'de." · "Allah belasını versin büyük Ortadoğu'nun… Tuvalet mi canım bu? Küçük bin, büyük iki bin." |
| 13 | Faiz ve ücret | dikkat | Biten son ayda bankalara faiz ya da ücret ödendi | "Allah belasını versin büyük Ortadoğu'nun… Tuvalet mi canım bu? Küçük bin, büyük iki bin." · "İnsaf kalmamış ben-i âdemde, anamı ağlattılar Acıbadem'de." |
| 14 | Sessiz ay | yansız | Biten son ayda ne gelir geldi ne harcama yapıldı | "Çakır, kuzum…" · "İsa Muhammed aşkına bilmiyorum." |
| 15 | Veri yok | yansız | Yukarıdakilerin hiçbiri yok: belge yok ya da gelirin bilindiği, biten bir ay yok | "İsa Muhammed aşkına bilmiyorum." |

## Liste üzerine notlar

- Kullanıcının 2026-11-03'te verdiği listede "Bak evladım…" iki kez yazılıydı; bir kez alındı.
- Yazım düzeltildi: Türkçe harfler ("canım", "kızım", "evladım", "karanlık", "kapısını", "Çakır"), "ıhlamur",
  "Çeçen'den canını", "Azeri'den", "ben-i âdemde" ve "Acıbadem'de".
- Sözler dizinin dilindedir; bazıları kaba ya da şakacıdır. Bir söz değişecekse hem `app/sayings.py` hem bu belge
  değişir; testler her sözün en az bir durumu, "veri yok" dışında her durumun en az iki sözü ve her rengin bir yüzü
  olduğunu denetler. Kötü haberin sözleri (kara baht, sinirler, elin parası, bonkörlük, zam) iyi bir durumun sözleri
  arasında yer almaz.
