# Mağaza metni

Chrome Web Store'un geliştirici panosuna girilecek metinler. Mağaza dili Türkçe; inceleme notu ve gizlilik politikasının
özeti incelemeciler için İngilizce de yazılır.

## Ad ve kısa açıklama

- **Ad:** İplikçi Nedim Köprüsü
- **Kısa açıklama** (manifestteki açıklama): Gmail'deki banka iletilerini bu bilgisayardaki İplikçi Nedim'e taşır.
  Gmail'de hiçbir şeyi değiştirmez.
- **Kategori:** Verimlilik
- **Görünürlük:** listelenmemiş

## Uzun açıklama

İplikçi Nedim, banka belgelerinizi ve e-postalarınızı kendi bilgisayarınızda toplayan, doğrulayan ve yorumlayan kişisel
finans asistanıdır. Bu eklenti onun Gmail köprüsüdür. Tarayıcınızdaki açık Gmail oturumuyla, listedeki bankaların
iletilerini okur ve bu bilgisayarda çalışan İplikçi Nedim'e taşır.

- Gmail'de hiçbir şeyi değiştirmez: iletiler okunmamış kalır, taşınmaz, silinmez, etiketlenmez.
- Yalnızca İplikçi Nedim'deki listede olan bankaların iletilerini alır.
- Yalnızca Gmail'e (mail.google.com ve eklerin indirildiği mail-attachment.googleusercontent.com) ve bu bilgisayardaki
  İplikçi Nedim'e bağlanır. Şifre istemez, başka bir sunucuya veri göndermez, uzaktan kod yüklemez.
- İplikçi Nedim ile tek kullanımlık bir kodla eşleşir. Her teslimden önce, karşıdaki programın eşleştiği İplikçi Nedim
  olduğunu doğrular.
- Uygulama şifresi verilemeyen hesaplar için yoldur, örneğin Google'ın Gelişmiş Koruma programındaki hesaplar.

Kullanmak için bu bilgisayarda İplikçi Nedim'in kurulu olması gerekir.

## Tek amaç

Gmail'deki banka iletilerini, kullanıcının kendi bilgisayarında çalışan İplikçi Nedim uygulamasına taşımak.

## İzinlerin gerekçeleri

| İzin | Gerekçe |
|---|---|
| `alarms` | Yeni banka iletilerine dakikada bir bakmak. |
| `scripting` | "Gmail'de eksikleri tara" sırasında, eklentinin kendi açtığı Gmail sekmesindeki arama listesinden yalnızca konuşma kimliklerini ve konuşmaların okunup okunmadığını okumak. Başka bir sayfada betik çalışmaz. |
| `storage` | Eşleşmeyi, okunacak Gmail hesabının sırasını ve son denetimin özetini tarayıcıda saklamak. E-posta adresi saklanmaz. |
| `https://mail.google.com/*` | Gelen kutusu akışını, "Orijinali göster" sayfasını, arama listesini ve baştan sona okunmuş konuşmaların yazdırma görünümünü kullanıcının oturumuyla okumak. Yalnızca okuma (GET) istekleri. |
| `https://mail-attachment.googleusercontent.com/*` | Eki olan bir iletinin tamamını "Orijinali indir" ile almak: Gmail bu indirmeyi kendi ek sunucusuna yönlendirir, "Orijinali göster" ise eklerin içeriğini boş verir. Yalnızca okuma (GET). |
| `http://127.0.0.1:8643/*` | İletileri bu bilgisayardaki İplikçi Nedim servisine teslim etmek. |

Uzaktan kod: yok. Bütün kod pakettedir ve küçültülmemiştir.

## Veri kullanımı beyanı

- Eklentinin işlediği veri: **kişisel iletişim**, yani listedeki bankalardan gelen e-postalar. İletiler yalnızca bu
  bilgisayardaki İplikçi Nedim'e gider.
- Satılmaz ve üçüncü kişilere aktarılmaz.
- Eklentinin tek amacı dışında kullanılmaz.
- Kredi değerliliği ya da borç verme amacıyla kullanılmaz.

## İnceleme notu (incelemeciler için)

> The extension is the Gmail bridge of İplikçi Nedim, a personal finance app that runs only on the user's own computer
> (a local service on 127.0.0.1:8643). It reads, with the user's signed-in Gmail session, the messages of the bank
> senders the local app lists, and hands their raw text to that local service. Nothing leaves the computer: the only
> hosts are mail.google.com and its attachment server mail-attachment.googleusercontent.com, where Gmail's "Download
> original" leads (GET requests only; nothing is marked read, moved, labelled or deleted), and 127.0.0.1.
> There is no remote code, analytics or third-party request.
>
> Without the local app the extension stays unpaired and sends nothing. Its verification page (verify.html, linked
> from the options page) shows how it reads Gmail without changing anything. Pairing uses a one-time code from the
> local app, and before every delivery the local service proves with an HMAC that it is the app the extension paired
> with.
