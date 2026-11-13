# ADR-0023: Claude'un hafızası İplikçi Nedim'de durur, MCP ile okunup yazılır

Durum: Kabul edildi · Tarih: 2026-11-13, kapsamı 2026-11-14 · Dayanak: K30 · [ADR-0011](0011-mcp.md)'in araçlarını
genişletir

## Bağlam

- Claude Code konuşmalar arasında hatırladıklarını kendi hafıza klasörüne yazar. O klasör Claude Code'un açıldığı
  proje klasörüne bağlıdır: Claude başka bir klasörde açılınca ya da kullanıcı Claude Desktop'tan bağlanınca
  önceki notlar yoktur.
- Kullanıcı 2026-11-13'te bu hafızayı İplikçi Nedim'in kendisinin sunmasını istedi (K30). Claude nereden bağlanırsa
  bağlansın notlarını platformda tutmalı.
- Ertesi gün kullanıcı kapsamı söyledi: platform yalnızca finansal notları taşır, projenin teknik notlarını ya da
  başka projelerin notlarını değil; amaç finansal kontrollerin ve alınan finansal kararların hafızasını platformda
  tutmak. İlk biçim Claude Code'un hafızası gibi her şeyi kabul ediyordu, talimatları da öyle söylüyordu.
- Claude'un İplikçi Nedim'e bağlandığı tek yer MCP sunucusudur (ADR-0011): servisin `/mcp`'si ve stdio köprüsü.
  İstemci hangisi olursa olsun aynı veri klasörüne ulaşır.
- Claude Code bir sunucunun talimatlarının ilk 4096 karakterini gösterir, gerisini keser. İplikçi Nedim'in
  talimatları 5408 karakterdi: maskeleme, servis kapalıyken çalışma ve "her rakam araçlardan gelir" kuralları
  kesilen yerdeydi.

## Karar

**Kapsam**

- Hafıza yalnızca kullanıcının parasına dairdir: onunla yapılan finansal kontroller ve sonuçları; kullanıcının
  finansal kararları, hedefleri, planları ve açık soruları; finansal yanıtları nasıl istediği; neyin nerede olduğu
  (hangi hesabın neyi ödediği).
- Yazılımın, kodun (İplikçi Nedim'in kendi geliştirilmesininki de) ve başka işlerin notları buraya yazılmaz; Claude'un
  kendi hafızasında kalır.
- Bunu talimatların ilk kuralı, `read_memory`'nin ve `write_memory`'nin açıklamaları ve boş hafızanın notu söyler
  (test edilir). Kod bir notun konusunu ayırt edemez: kapsamı Claude izler, kullanıcı ekranda görür.

**Not**

- Bir not tek bir konuyu anlatır. Claude Code'un hafızasındaki alanları taşır:
  - ad: kısa bir tanıtıcı, küçük harf, rakam ve tire (`kira-odemesi`), en çok 64 karakter;
  - tür: `user` (kullanıcı kim: işi, geliri, hanesi gibi mali durumu), `feedback` (finansal yanıtları ve kontrolleri
    nasıl istediği), `project` (finansal kararlar, hedefler, planlar, yapılan kontroller ve açık sorular),
    `reference` (neyin nerede olduğu);
  - tek satırlık açıklama (en çok 200 karakter);
  - notun kendisi (en çok 4000 karakter).
- Notlar veri klasörünün veritabanında, `memories` tablosundadır (göç 21). Birincil veridir: hiçbir belge onları
  bilmez. Yeniden kurmanın dökümü (sürüm 7) ve yedekler onları taşır; `iplikci dogrula --yeniden-kur` notların
  aynı geldiğini de denetler.
- En çok 200 not tutulur: notların listesi her konuşmanın başında okunur.

**Araçlar**

- `read_memory`: argümansız çağrılınca notların listesini verir (ad, tür, açıklama, son değişiklik, son yazan), metni
  vermez. `names` ile notların tamamı gelir. `text` ile adında, açıklamasında ya da metninde aranan kelimeler geçen
  notlar gelir; arama İşlemler'in kuralıyla yapılır (`domain/search`: virgülle ayrılan parçalardan biri).
- `write_memory`: yeni not yazar ya da aynı adlı notu günceller; verilmeyen alan olduğu gibi kalır. Aynısı yazılırsa
  hiçbir şey değişmez.
- `delete_memory`: notu siler; silinen not yanıtta son kez gösterilir.
- Hafıza araçları **plan istemez**, `fetch_email` ve `build_report` gibi tek adımlıdır. Notlar hiçbir rakamı,
  kuralı, belgeyi ya da işlemi değiştirmez: Claude'un kendi defteridir. Her not için kullanıcıdan onay istemek
  hafızayı kullanılmaz kılardı.

**Talimatlar**

- Hafıza talimatların ilk maddesidir: kullanıcının parasıyla ilgili bir işe başlarken `read_memory`'yi argümansız
  çağırmak; yeni kontrolleri ve kararları yazmak; yazılımın, kodun ve başka işlerin notlarını yazmamak. Yanlışlanan
  notu düzeltmeyi ya da silmeyi araçların açıklamaları söyler.
- Talimatların tamamı 4096 karaktere sığar (test edilir). Kurallar önce gelir. Bir aracın kendi açıklamasında
  yazanlar talimatlarda yeniden söylenmez: araç kataloğu ve sayfalama.

**Güven**

- Notlar yazıldıkları günün bilgisidir. Kullanıcının o konuşmadaki sözü önce gelir; Claude bir nota dayanmadan önce
  söylediğinin hâlâ doğru olduğunu araçlarla doğrular.
- Bir belgenin, e-postanın ya da işlem açıklamasının içindeki metin yüzünden not yazılmaz (talimatlarda ve aracın
  açıklamasında). Bir not, kullanıcının onaylamadığı bir değişikliği yaptıramaz: rakamları ve kuralları değiştiren
  araçlar yine plan → onay → uygula akışını izler.
- Araçların her seferinde yeniden verdiği rakamlar, işlemler ve bakiyeler; şifre, belirteç ve anahtarlar nota
  yazılmaz.

**Gizlilik**

- Notlar bu bilgisayarda, veri klasöründe durur; ağa çıkmaz.
- Araçların yanıtları her yanıt gibi maskelemeden geçer: maskeleme açıkken notun metnindeki hesap numaraları ve kişi
  adları gizlenir.
- Bir notun adı maskelenemez: maskelenseydi not adıyla bulunamazdı. Bu yüzden yeni bir notun adında kişinin tam adı
  (Türkçe harfleri sadeleşmiş, tireli biçimiyle de: `ayse-yilmaz`), hesap numarası ya da altı ve daha uzun bir rakam
  dizisi olamaz (`masking.handle_hides`).
- Denetim kaydı her değişikliği notun adıyla yazar (`memory.written`, `memory.removed`), metnini yazmaz. Araç
  çağrıları her çağrı gibi argümanlarının adlarıyla kaydedilir.
- Servis kapalıyken stdio köprüsü notları okur, yazmaz ve silmez.

**Arayüz**

- Claude bağlantısı ekranının "Claude'un hafızası" kartı bütün notları türlerine göre gösterir; notun metni açılır
  bölümdedir. Kullanıcı bir notu sorulduktan sonra siler (`GET /api/memory`, `DELETE /api/memory/{ad}`; silme
  yalnızca arayüzün kendi sayfalarından yapılır).
- Notları arayüz yazmaz: kullanıcı bir şeyi hatırlatmak isterse Claude'a söyler.

## Sonuçlar

- Olumlu:
  - Claude, hangi klasörden ya da uygulamadan bağlanırsa bağlansın aynı notları okur: Claude Code'un iki ayrı
    projesi, Claude Desktop ve başka bir MCP istemcisi.
  - Notlar yedeklerle ve yeniden kurmayla korunur. Kullanıcı Claude'un ne hatırladığını görür ve istemediğini siler.
  - Talimatların hiçbir kuralı artık Claude Code'da kesilmez.
- Olumsuz:
  - Yazan iki araç onaysızdır. Yanlış bir not ancak kullanıcı onu görünce ya da Claude onu yanlışlayınca düzelir.
  - Maskeleme açılmadan önce yazılan bir notun adı, o gün defterde olmayan bir kişinin adını taşıyabilir. Maskeleme
    açıkken bu ad gizlenmez; kullanıcı notu ekranda görür ve silebilir.
  - Talimatlar 4096 karakterin altında kalmalıdır: yeni bir kural ancak başka bir şey kısaltılarak eklenir.
  - Kapsamı kod denetlemez: başka bir işin notunu yazan bir Claude'u ancak kullanıcı ekranda görüp düzeltir.

## Değerlendirilen seçenekler

- **Her işin notu, Claude Code'un hafızası gibi:** 2026-11-13'teki ilk biçimdi. Kullanıcı ertesi gün hafızanın
  yalnızca finansal kontroller ve kararlar için olduğunu söyledi. Bir yazılım işinin teknik notları finans
  asistanının listesini kalabalıklaştırır ve o işin kendi klasöründe daha yerindedir.
- **Plan → onay → uygula:** her not için kullanıcıya soru sorulurdu. Bir hafıza, Claude'un konuşmayı kesmeden not
  alabilmesi demektir.
- **Notları MCP kaynağı (`iplikci://memory`) olarak sunmak:** bir kaynağın modele nasıl ulaştığı istemciden
  istemciye değişir ve kaynakla not yazılamaz. Araçları her istemci modele aynı biçimde verir; model onları konuşmanın
  başında kendisi çağırır.
- **Not listesini talimatlara koymak:** talimatlar istemcinin önbelleğinde bağlantı boyunca aynı kalır ve
  4096 karakterle sınırlıdır. Ayrıca notlar talimat yetkisi kazanırdı: belgeden sızan bir metin nota, nottan
  talimatlara geçebilirdi.
- **Claude Code'un hafıza klasörünü paylaşmak:** yalnızca Claude Code'da ve yalnızca bu bilgisayarda çalışır. Claude
  Desktop ve öteki istemciler onu görmez.
- **Notları bir dosyada (`memory/*.md`) tutmak:** yedek ve yeniden kurma zaten veritabanını taşır. Dosyalar iki
  sürecin aynı anda yazmasına karşı ayrıca kilit isterdi.
