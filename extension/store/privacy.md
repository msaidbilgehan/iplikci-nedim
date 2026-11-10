# İplikçi Nedim Köprüsü — Gizlilik politikası

Bu politika, Chrome eklentisi "İplikçi Nedim Köprüsü"nün hangi verileri nasıl işlediğini anlatır.

## Ne okunur

Eklenti, tarayıcıdaki açık Gmail oturumuyla yalnızca şunları okur:

- Gmail'in gelen kutusu akışını, yani en yeni okunmamış iletilerin listesini;
- İplikçi Nedim'de listesi tutulan bankaların iletilerini, Gmail'in "Orijinali göster" sayfasından; eki olan bir
  iletinin tamamını "Orijinali indir" ile, Gmail'in ek sunucusundan (mail-attachment.googleusercontent.com);
- "Gmail'de eksikleri tara" sırasında, eklentinin açtığı sekmedeki arama listesinden yalnızca konuşma kimliklerini ve
  konuşmanın okunup okunmadığını; baştan sona okunmuş bir konuşmanın yazdırma görünümünden yalnızca ekli iletilerin
  kimliklerini ve göndericilerin alan adlarını;
- Gmail bu tarayıcıda açıkken, eklentinin okuduğu hesabın sekmesinde görünen konuşma listesinden ve açılmış
  konuşmadan yalnızca listedeki bankaların iletilerinin kimliklerini. Bunun için göndericinin adresine yalnızca alan
  adı için bakılır; konu, önizleme, ileti metni ve ad okunmaz. Kimlikler yalnızca eklentinin kendisine gider.

Gmail'de hiçbir şey değişmez: iletiler okundu işaretlenmez, taşınmaz, etiketlenmez ve silinmez.

"İplikçi Nedim'i aç" düğmesine basılınca eklenti, yalnızca bu bilgisayardaki İplikçi Nedim'in adresinde
(127.0.0.1:8643) açık sekmelerin adresine ve başlığına bakar; başka sekmeleri göremez. Tarayıcının çerezlerini okumaz.

## Nereye gider

Okunan iletiler yalnızca aynı bilgisayarda çalışan İplikçi Nedim uygulamasına gider (127.0.0.1). Eklenti başka hiçbir
sunucuya veri göndermez. Analiz, reklam ya da izleme yoktur; uzaktan kod yüklenmez.

## Tarayıcıda ne saklanır

- İplikçi Nedim ile eşleşmenin belirteci;
- okunacak Gmail hesabının sırası (adres değil);
- son denetimin ve taramanın özeti (sayılar; adres, konu ya da ileti metni değil);
- İplikçi Nedim'in hiç alamayacağı iletilerin Gmail kimlikleri, yeniden indirilmesinler diye;
- İplikçi Nedim'in listesindeki göndericilerin alan adları; son teslim edilen ya da teslim bekleyen banka iletilerinin
  Gmail kimlikleri.

Bunlar eklenti kaldırılınca tarayıcıdan silinir.

## Paylaşım

Veriler satılmaz, kimseyle paylaşılmaz ve eklentinin tek amacı dışında kullanılmaz: banka iletilerini kullanıcının kendi
bilgisayarındaki İplikçi Nedim'e taşımak.

## İletişim

Sorular için: projenin sahibine, eklentinin mağaza sayfasındaki geliştirici iletişim adresinden.

---

## Privacy policy (English)

The Chrome extension "İplikçi Nedim Köprüsü" reads, with the browser's signed-in Gmail session, only the inbox feed,
the "Show original" page of messages from the bank senders the local İplikçi Nedim app lists (and, for a message
with attachments, the whole message through "Download original", from Gmail's attachment server), and, during a "scan
Gmail for missing mail", the conversation ids of the search list in a tab it opens, whether each conversation is
read, and, from the print view of a conversation read throughout, only the ids of its messages with attachments and
their senders' domains. While Gmail is open in the browser, a script in the tabs of the Gmail account it reads tells
the extension the ids of the listed banks' messages the conversation list or an opened conversation shows; it looks at
a sender's address only for its domain and reads no subject, snippet, body or name. Nothing in Gmail changes: no
message is marked read, moved, labelled or deleted. When "Open İplikçi Nedim" is pressed, it looks only at the address
and title of tabs open on the local app's address (127.0.0.1:8643); it cannot see other tabs and does not read the
browser's cookies.

What it reads goes only to the İplikçi Nedim app on the same computer (127.0.0.1). It sends no data to any other
server, and has no analytics, ads, tracking or remote code. The browser keeps only the pairing token, which Gmail
account to read (its position, not its address), counts from the last check and scan, the Gmail ids of messages the
app can never take, the domains of the senders the app lists, and the Gmail ids of the bank messages delivered lately
or waiting to be. All of it goes when the extension is removed. Data is not sold, not shared and not used for
anything but the extension's single purpose.
