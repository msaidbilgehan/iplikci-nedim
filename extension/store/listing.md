# Mağaza metni

Chrome Web Store'un geliştirici panosuna girilecek metinler. Mağaza dili Türkçe; inceleme notu ve gizlilik politikasının
özeti incelemeciler için İngilizce de yazılır.

## Ad ve kısa açıklama

- **Ad:** İplikçi Nedim Köprüsü
- **Kısa açıklama** (manifestteki açıklama): Gmail'deki banka iletilerini bu bilgisayardaki İplikçi Nedim'e taşır.
  Gmail'de hiçbir şeyi değiştirmez.
- **Kategori:** Verimlilik
- **Görünürlük:** herkese açık (kullanıcının 2026-11-14 kararı,
  [ADR-0024](../../docs/adr/0024-extension-leads-to-download.md)): eklenti programın kapısıdır, adını duyan onu
  mağazada bulur.
- **İlk gönderilen sürüm:** 0.9.0 (programı olmayanı indirmeye götüren ilk sürüm); 0.8.0 mağazaya gitmez.

## Uzun açıklama

İplikçi Nedim, banka belgelerinizi ve e-postalarınızı kendi bilgisayarınızda toplayan, doğrulayan ve yorumlayan kişisel
finans asistanıdır. Bu eklenti onun Gmail köprüsüdür. Tarayıcınızdaki açık Gmail oturumuyla, listedeki bankaların
iletilerini okur ve bu bilgisayarda çalışan İplikçi Nedim'e taşır.

- Gmail'de hiçbir şeyi değiştirmez: iletiler okunmamış kalır, taşınmaz, silinmez, etiketlenmez.
- Yalnızca İplikçi Nedim'deki listede olan bankaların iletilerini alır. Gmail açıkken sekmede görünen banka iletilerini,
  okunmuş olsalar da kendiliğinden alır.
- Yalnızca Gmail'e (mail.google.com ve eklerin indirildiği mail-attachment.googleusercontent.com) ve bu bilgisayardaki
  İplikçi Nedim'e bağlanır. Şifre istemez, başka bir sunucuya veri göndermez, uzaktan kod yüklemez.
- İplikçi Nedim ile tek kullanımlık bir kodla eşleşir. Her teslimden önce, karşıdaki programın eşleştiği İplikçi Nedim
  olduğunu doğrular.
- Araç çubuğundaki düğmesi durumu gösterir ve İplikçi Nedim'in arayüzünü tek tıkla açar.
- Uygulama şifresi verilemeyen hesaplar için yoldur, örneğin Google'ın Gelişmiş Koruma programındaki hesaplar.

Kullanmak için bu bilgisayarda İplikçi Nedim'in kurulu olması gerekir. Kurulu değilse eklenti bunu söyler: ayarlar
sayfası kendiliğinden açılır, bilgisayarınızın sistemi için İplikçi Nedim'i indiren bir düğme ve kurulum adımları
gösterir (macOS, Windows ve Linux). İndirme, İplikçi Nedim'in GitHub'daki sürüm sayfasından, tarayıcınızın yeni bir
sekmesinde olur. Program açılınca eklenti eşleştirmeye geçer.

## Tek amaç

Gmail'deki banka iletilerini, kullanıcının kendi bilgisayarında çalışan İplikçi Nedim uygulamasına taşımak.

## İzinlerin gerekçeleri

| İzin | Gerekçe |
|---|---|
| `alarms` | Yeni banka iletilerine dakikada bir bakmak. |
| `scripting` | "Gmail'de eksikleri tara" sırasında, eklentinin kendi açtığı Gmail sekmesindeki arama listesinden yalnızca konuşma kimliklerini ve konuşmaların okunup okunmadığını okumak. Eklenti kurulunca ya da güncellenince, açık Gmail sekmelerine içerik betiğini (content.js) de bu izinle koyar; sekmenin yenilenmesi gerekmez. Bu izinle başka bir sayfada betik çalıştırılmaz; içerik betiğinin ne okuduğu `https://mail.google.com/*` satırındadır. |
| `storage` | Eşleşmeyi, okunacak Gmail hesabının sırasını, son denetimin özetini, listedeki göndericilerin alan adlarını ve son banka iletilerinin Gmail kimliklerini tarayıcıda saklamak. E-posta adresi saklanmaz. |
| `https://mail.google.com/*` | Gelen kutusu akışını, "Orijinali göster" sayfasını, arama listesini ve baştan sona okunmuş konuşmaların yazdırma görünümünü kullanıcının oturumuyla okumak. Yalnızca okuma (GET) istekleri. Kullanıcının açık Gmail sekmelerinde çalışan içerik betiği, görünen konuşma listesinden ve açılmış konuşmadan yalnızca listedeki bankaların iletilerinin kimliklerini eklentiye bildirir; göndericinin adresine yalnızca alan adı için bakar, konu, metin ve ad okumaz, istek yapmaz. |
| `https://mail-attachment.googleusercontent.com/*` | Eki olan bir iletinin tamamını "Orijinali indir" ile almak: Gmail bu indirmeyi kendi ek sunucusuna yönlendirir, "Orijinali göster" ise eklerin içeriğini boş verir. Yalnızca okuma (GET). |
| `http://127.0.0.1:8643/*` | İletileri bu bilgisayardaki İplikçi Nedim servisine teslim etmek. "İplikçi Nedim'i aç" ile servisin arayüzünü açmak: bu adreste açık bir sekme varsa onu bulup öne getirmek (yalnızca bu adresteki sekmelerin adresi ve başlığı görülür), yoksa servisten tek kullanımlık bir giriş bağlantısı isteyip açmak. Eşleşmeden önce, programın bu bilgisayarda olup olmadığını servisin sağlık denetimine (`/healthz`, belirteç ya da çerez gönderilmez) bakarak anlamak. |

Uzaktan kod: yok. Bütün kod pakettedir ve küçültülmemiştir.

Başka izin yoktur. Programı indirme düğmesi yalnızca bir sekme açar (`chrome.tabs.create`, izin istemez); dosyayı
tarayıcı indirir, eklenti GitHub'a istek yapmaz. `downloads`, `tabs` ve GitHub için adres izni yoktur.

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
> A content script runs in the user's Gmail tabs (content.js, within the mail.google.com host permission). While the
> tab shows the Gmail account the extension reads, it tells the extension's service worker the Gmail ids of the
> listed banks' messages the conversation list or an opened conversation shows, read or not, so that a message read
> before the next check is still delivered. It looks at a sender's address only for its domain; it reads no subject,
> snippet, body or name, makes no request and does not read the extension's storage, which the service worker
> restricts to trusted contexts (chrome.storage.local.setAccessLevel). When the extension is installed or updated it
> injects the same script into the Gmail tabs already open (chrome.scripting), so they need no reload. The service
> worker accepts only two requests from a Gmail tab: what to look for, and decimal message ids.
>
> Without the local app the extension stays unpaired and sends nothing. On install it opens its options page by
> itself. When it is not paired, it asks the local address whether the app is there (GET
> http://127.0.0.1:8643/healthz, no token, no cookie). Nothing answers on a reviewer's computer, so the page says that
> the İplikçi Nedim app is needed and shows "İplikçi Nedim'i indir" with the steps to install and open it for the
> computer's system (chrome.runtime.getPlatformInfo). The button opens
> https://github.com/msaidbilgehan/iplikci-nedim-surumler/releases/latest/download/<installer> in a new tab
> (chrome.tabs.create): the browser downloads the app's installer from its public releases. The extension makes no
> request to GitHub, sends nothing there and has no "downloads" or "tabs" permission. A system without an installer
> (ChromeOS, for example) gets the releases page instead. The page keeps asking the local address every few seconds
> and moves on to pairing once the app answers. To see the rest, install the app from that page; it is free. Its
> verification page (verify.html, linked from the options page) shows how it reads Gmail without changing anything.
> Pairing uses a one-time code from the local app, and before every delivery the local service proves with an HMAC
> that it is the app the extension paired with.
>
> The toolbar button opens a small window (popup.html) with the bridge's status, "Open İplikçi Nedim", "Check now"
> and a link to the options page. "Open İplikçi Nedim" brings a tab of the local app's interface to the front; without
> one, it has the local service prove itself, asks it for a one-time login link on 127.0.0.1 and opens that link in a
> tab. The host permission for 127.0.0.1:8643 is what lets it see the address and title of tabs on that address
> only; the extension has no "tabs" permission and never reads cookies.
