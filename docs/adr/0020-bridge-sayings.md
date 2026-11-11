# ADR-0020: Eşleşmiş tarayıcı eklentisi İplikçi Nedim'in sözlerini servisten alır

Durum: Kabul edildi · Tarih: 2026-11-03 · Dayanak: K26, tasarım · [ADR-0016](0016-mail-connectors.md)'nın ve
[ADR-0019](0019-bridge-login-link.md)'un eklenti belirtecine tanıdığı kapsamı genişletir

## Bağlam

- Kullanıcı 2026-11-03'te İplikçi Nedim'in dizideki sözlerinin, maddi duruma göre ve İplikçi Nedim'in yüzüyle (logo)
  hem arayüzde hem eklentinin penceresinde gösterilmesini istedi (K26). Sözlerin listesi
  [İplikçi Nedim'in sözleri](../İplikçi_Nedim_Sözler.md) belgesindedir.
- Hangi sözün söyleneceğini paranın durumu belirler: son kapanan ayın geleni ve gideni, öngörünün eksiye düştüğü gün,
  borçlar, bu ayın tipik ayla karşılaştırması, zamlar, döviz geliri. Bunları yalnızca servis bilir; eklenti belgeleri
  ve defteri görmez.
- Eklentinin belirteci şimdiye dek e-posta alım uçlarını ve "İplikçi Nedim'i aç"ın giriş bağlantısını açıyordu.
  Başka bir uca giden istek `forbidden` ile reddedilir.

## Karar

- **Sözleri servis seçer** (`app/sayings`). Her söz bir duruma bağlıdır: öngörü eksiye düşüyor, ay eksiyle kapandı,
  borç varlıktan fazla, bu ay tipik aydan fazla ya da az harcanıyor, az kaldı, en iyi ay, döviz geliri, birikim,
  gelir geldi, iyi bir ay, zam, faiz ve ücret, sessiz ay, veri yok.
  - Durumlar en acil olandan başlayarak sıralanır. Gösterilen söz ilk durumunkidir ve o durumun sözleri arasında günden
    güne değişir. Öbür durumların sözleri "Başka bir söz" için sırayla gelir.
  - Her sözün yanında durumu söyleyen bir cümle vardır. Bu cümle yalnızca sözcük, gün ve pay taşır ("Ekim 2026'da
    gelen paranın %49'u elde kaldı."). Tutar, hesap, kart, kişi ya da işyeri adı taşımaz.
  - Her durumun bir rengi vardır: iyi, dikkat, kritik ya da yansız. İplikçi Nedim'in yüzü bu renge boyanır.
- **Pano** sözleri kendi yanıtında alır (`GET /api/dashboard`'un `sayings` alanı). Söz sade görünümde de ayrıntılı
  görünümde de en üstte durur.
- **Yeni uç:** eşleşmiş eklentinin belirteci bir uç daha açar, `GET /api/bridge/sayings`. Yanıt Pano'nunkiyle aynı
  sözlerdir (`{items: [...]}`).
  - Uç yalnızca etkin bir eklentinin belirteciyle açılır. API belirteci ve tarayıcı oturumu reddedilir: onlar Pano'yu
    okur.
  - Belgeler işlenirken uç `503 busy` döner; eklenti o zaman söz göstermez.
- **Eklentinin penceresi:** pencere açılınca eklenti önce servisten kanıt ister (ADR-0016'daki HMAC), sonra sözleri.
  Başlıktaki logo sözün rengine boyanır, söz logonun altında bir balonda durur.
  - Eklenti eşleşmemişse, servis çalışmıyorsa, yanıt veren program kanıtı veremiyorsa, eşleşme iptal edilmişse ya da
    servis bu uçtan eskiyse pencere söz göstermez. Durum kartı zaten neyin engel olduğunu söyler.
  - Pencere sözleri yalnızca açılırken ister; açık kaldıkça yeniden istemez.
- **İzinler değişmez.** Eklenti yine yalnızca `mail.google.com`'a, Gmail'in ek sunucusuna ve 127.0.0.1'e ulaşır.

## Güvenlik

- Eklentinin belirteci ADR-0019'dan beri bir tarayıcı oturumu açabilir, yani arayüzün bütün yetkisine ulaşır. Salt
  okunur ve tutar taşımayan bir uç bu yetkiyi büyütmez.
- Söz ve cümle tutar, hesap ya da ad taşımadığı için eklentinin penceresi omuz üstünden bakan birine de paranın
  rakamını göstermez. Gösterdiği, ayın iyi ya da kötü geçtiği ve o günün durumudur.
- Belirteç yalnızca kanıtı veren servise gider. 127.0.0.1:8643'te başka bir program dinliyorsa istek ona gitmez.

## Sonuçlar

- Olumlu:
  - Kullanıcı paranın durumunu tarayıcının araç çubuğundan, arayüzü açmadan, İplikçi Nedim'in diliyle görür.
  - Pano ile eklenti aynı sözü aynı nedenle söyler: ikisi de servisin tek seçiminden gelir.
- Olumsuz:
  - Eklenti belirtecinin açtığı uçlar bir tane daha arttı.
  - Pencere her açılışta servise iki istek gönderir (kanıt ve sözler); servis her seferinde Pano'yu hesaplar.
  - Sözler dizinin dilindedir; bazıları kaba ya da şakacıdır. Kapatma seçeneği yoktur.

## Not (2026-11-11, v0.10.1)

Kullanıcı Pano'da sürekli aynı sözü gördüğünü söyledi. İki nedeni vardı: her söz tek bir duruma bağlıydı ve 15
durumun 8'inin tek sözü vardı; ayın hükmü yalnızca kapanmış ayı anlattığı için Eylül 2026 haftalarca Pano'nun ayı
kaldı ve "az kaldı" durumu her gün aynı sözü söyletti. Karar değişmeden kalır (sözleri servis seçer, eklenti aynı uçtan
alır); seçimin kuralları şöyle değişti:

- Bir söz anlamına uyan birden çok durumda söylenebilir. "Veri yok" dışında her durumun en az iki sözü vardır, böylece
  aynı durum sürdükçe söz günden güne değişir. "Başka bir söz" her sözü bir kez, en acil durumuyla gösterir.
- Ayın hükmü Pano'nun ayıdır: gelirin bilindiği, biten en yeni ay. Ay belgelerini hâlâ bekliyorsa cümle "şimdilik"
  der; en iyi ay yalnızca kapanmış aylar arasından seçilir.

Listenin kendisi ve durumların sözleri [İplikçi Nedim'in sözleri](../İplikçi_Nedim_Sözler.md) belgesindedir.

## Değerlendirilen seçenekler

- **Sözleri eklentide tutup durumu servisten istemek:** sözler iki yerde, arayüzde ve eklentide yaşardı ve birbirinden
  ayrılabilirdi. Durumu yine servis bilmek zorundaydı.
- **Pano'nun yanıtını eklentiye açmak:** eklenti tutarları, hesapları ve adları da alırdı. Penceresinin ihtiyacı
  yalnızca söz ve onun cümlesidir.
- **Eklentide yalnızca logoyu boyamak, sözü arayüze bırakmak:** kullanıcı sözlerin eklentide de görünmesini istedi.
