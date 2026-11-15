# Mağaza metni

Chrome Web Store'un geliştirici panosuna girilecek metinler. Mağaza dili Türkçe; inceleme notu ve gizlilik politikasının
özeti incelemeciler için İngilizce de yazılır.

## Ad ve kısa açıklama

- **Ad:** İplikçi Nedim Köprüsü
- **Kısa açıklama** (manifestteki açıklama, en çok 132 karakter; mağaza onu adın altında ve aramada gösterir, panoda
  değişmez, yeni bir eklenti sürümüyle gelir): "İplikçi Nedim kişisel finans programının Gmail eklentisi: bankaların
  gönderdiği ekstre, dekont ve bildirimleri programa aktarır."
- **Kategori:** Verimlilik
- **Görünürlük:** herkese açık (kullanıcının 2026-11-14 kararı,
  [ADR-0024](../../docs/adr/0024-extension-leads-to-download.md)): eklenti programın kapısıdır, adını duyan onu
  mağazada bulur.
- **İlk gönderilen sürüm:** 0.9.0 (programı olmayanı indirmeye götüren ilk sürüm); 0.8.0 mağazaya gitmez.

## Uzun açıklama

Panonun "Description" alanına bu bloğun içi aynen girilir: her paragraf ve her madde kendi satırındadır.

```text
İplikçi Nedim kişisel finans programının Gmail eklentisidir. Bankaların Gmail'inize gönderdiği ekstreleri, dekontları ve bildirimleri programa aktarır; belgeleri tek tek indirip eklemeniz gerekmez.

İplikçi Nedim nedir?
Banka belgelerinizi okuyup paranızın nereye gittiğini anlatan ücretsiz bir program. Biten ayda ne geldiğini, ne gittiğini ve ne kaldığını grafiklerle gösterir. Kart son ödemelerini ve düzenli ödemeleri takvimde tutar, zamanı yaklaşınca haber verir. Kendi bilgisayarınızda çalışır: bulut yok, hesap açmak yok, verileriniz bilgisayarınızdan çıkmaz.

Eklenti ne yapar, ne yapmaz?
- Yalnızca bankaların ve programa sizin eklediğiniz fatura göndericilerinin e-postalarını alır. Öbür e-postalarınız hiçbir yere gitmez.
- Gmail'de hiçbir şeyi değiştirmez: e-postalar okunmamış kalır, silinmez, taşınmaz.
- Şifrenizi istemez. E-postaları yalnızca bilgisayarınızdaki İplikçi Nedim'e verir; Gmail dışında hiçbir sunucuya bağlanmaz.

Nasıl kullanılır?
1. İplikçi Nedim'i bilgisayarınıza kurun. Program yoksa eklenti bunu söyler ve indirme düğmesini gösterir.
2. Programın "Tarayıcı eklentisi" ekranından bir eşleştirme kodu alın ve eklentinin ayarlar sayfasına yazın.
3. Eklenti önce Gmail'deki geçmiş banka e-postalarını bir kez tarar, sonra yenilerini kendiliğinden getirir.

Hangi bankalar?
- Garanti BBVA: Bonus kart ve Paracard ekstresi, dekont, Garanti BBVA Yatırım ekstresi (PDF); hesap hareketleri (Excel); para transferi bildirimleri
- İş Bankası: Maximum kart ekstresi, dekont, e-cüzdan (PDF); hesap hareketleri (Excel); kart borcu tahsilatı bildirimi
- QNB: kart ve hesap hareketleri (PDF); e-dekont (PDF ya da HTML); FAST, havale, EFT ve para çıkışı bildirimleri
- TEB: Bonus kart ekstresi, dijital hesap cüzdanı, dekont (PDF); hesap hareketleri (Excel)
- VakıfBank: e-cüzdan, dekont (PDF); hesap hareketleri (Excel); FAST ve EFT bildirimleri
- e-Fatura ve e-Arşiv faturaları (XML)
E-postayla gelmeyen belgeleri programın "Belge ekle" ekranından eklersiniz. Ayrıntılı liste: https://github.com/msaidbilgehan/iplikci-nedim/blob/master/docs/desteklenen-bankalar.md

İplikçi Nedim ücretsiz ve açık kaynaklıdır. Şimdilik macOS (Apple Silicon) için; Windows ve Linux sürümleri yolda. Program, kurulum adımları ve sorularınız için: https://github.com/msaidbilgehan/iplikci-nedim
```

Yazarken (kullanıcının 2026-11-15 uyarısı: önceki metin neyin eklentisi olduğunu ve ne işe yaradığını söylemiyordu,
gereksiz açıklamalarla doluydu):

- İlk iki cümle eklentinin İplikçi Nedim'in Gmail eklentisi olduğunu ve ne yaptığını söyler; mağaza aramada onları
  gösterir.
- Kullanıcıya bir şey söylemeyen ayrıntı yazılmaz: sunucu adları, izinler, eşleşmenin nasıl doğrulandığı. Onlar
  incelemecilere giden metindedir (aşağıda).
- Kısa cümleler; "köprü", "teslim" gibi programın kendi sözleri yerine kullanıcının sözleri.
- Banka listesi [desteklenen bankalar ve belgeler](../../docs/desteklenen-bankalar.md) sayfasının kısaltmasıdır: yeni
  bir okuyucu gelince ikisi birlikte değişir.
- Mağaza sayfasının "Ana sayfa" alanı herkese açık sayfada görünmüyor (2026-11-15'te denendi): kod deposunun adresi bu
  yüzden açıklamanın sonundadır. Destek adresi deponun soru ve sorun sayfasıdır:
  <https://github.com/msaidbilgehan/iplikci-nedim/issues>.

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

## İncelemecilere giden metin

Panonun gizlilik sekmesi incelemeciler içindir; 2026-11-15'te İngilizce şöyle girildi (Türkçesi yukarıda):

- **Single purpose:** Moves the bank e-mails in the user's Gmail to İplikçi Nedim, the personal finance app that runs
  on the user's own computer (a local service on 127.0.0.1:8643). It does nothing else.
- **alarms:** Checks for new bank e-mails once a minute while the browser runs.
- **scripting:** During "Gmail'de eksikleri tara" (scan Gmail for missing mail) it reads only the conversation ids,
  and whether each is read, from the search list in the Gmail tab the extension itself opened. When the extension is
  installed or updated it injects its content script (content.js) into the Gmail tabs already open, so they need no
  reload. No script runs on any other page; what the content script reads is described under the mail.google.com host
  permission.
- **storage:** Keeps in the browser the pairing with the local app, which Gmail account to read (its position, not its
  address), a summary of the last check, the domains of the senders the local app lists and the Gmail ids of recently
  delivered bank e-mails. No e-mail address is stored.
- **Host permissions:** https://mail.google.com/*: reads, with the user's signed-in session, the inbox feed, the "Show
  original" page of bank e-mails, the search list and the print view of conversations read throughout. GET requests
  only; nothing in Gmail changes. The content script in the user's Gmail tabs tells the extension only the ids of the
  listed banks' messages that the conversation list or an opened conversation shows; it looks at a sender's address
  only for its domain and reads no subject, body or name. https://mail-attachment.googleusercontent.com/*: Gmail's
  "Download original" for a message with attachments leads to this attachment server. GET only.
  http://127.0.0.1:8643/*: delivers the e-mails to the İplikçi Nedim service on the same computer; "Open İplikçi
  Nedim" finds or opens the local app's interface (only tabs on this address are seen); before pairing it checks
  whether the app is installed through its health check (/healthz, no token or cookie).
- **Data usage:** Personal communications; Financial and payment information. Veri kullanımı beyanında yalnızca kişisel
  iletişim yazıyordu; banka iletileri hesap hareketleri ve ekstre bilgisi taşıdığı için finansal bilgi de işaretlendi.

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
> https://github.com/msaidbilgehan/iplikci-nedim/releases/latest/download/<installer> in a new tab
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
