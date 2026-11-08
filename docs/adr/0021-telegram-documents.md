# ADR-0021: Eşleşmiş Telegram sohbetinden bota gönderilen belgeler arşive alınır

Durum: Kabul edildi · Tarih: 2026-11-08 · Dayanak: K28 · [ADR-0010](0010-notification-channels.md)'un Telegram
kanalını ve [ADR-0009](0009-network-egress-policy.md)'un Telegram bağlantısını genişletir

## Bağlam

- Kullanıcı 2026-11-08'de belge yüklemeyi Telegram botu üzerinden de yapabilmek istedi (K28). Telefonda bankanın
  uygulamasından indirilen bir ekstre, bilgisayara taşınmadan eklenebilmeli.
- Telegram kanalı şimdiye dek yalnızca gönderiyordu. Botun iletileri yalnızca eşleştirme sırasında, beklemeden
  okunuyordu (ADR-0010'un uygulama notu).
- Servis yalnızca 127.0.0.1'e bağlanır (ADR-0012): Telegram'ın webhook'u servise ulaşamaz.
- Bot API bir bota en çok 20 MB büyüklüğünde dosya indirtir. Okunmayan iletileri 24 saat saklar.

## Karar

- **Kim gönderebilir:** yalnızca eşleşmiş sohbet, o da yalnızca botla bire bir (özel) sohbetse.
  - Başka bir sohbetten gelen ileti işlenmez: dosyası indirilmez, yanıt verilmez. Botun adı gizli değildir; bir
    yabancının dosyası bilgisayara hiç inmez.
  - Eşleşen sohbet bir grupsa belgeler alınmaz; bot bunu söyler.
- **Onay:** dosyayı bota göndermek onaydır, gelen klasörüne dosya bırakmak gibi (F02). Plan gösterilmez; bot her
  dosyaya ne olduğunu yazar.
- **Okuma:** servisin bota bakan dinleyicisi (`ingest/telegram`) iletileri uzun yoklamayla okur. Her okuma Telegram'da
  en çok 25 saniye bekler; servis bir port açmaz, yalnızca Telegram'a sorar.
  - Okunacak bir şey yokken Telegram'a sorulmaz, anahtar zinciri de okunmaz: bot yok, belirteç reddedilmiş, sohbet
    eşleşmemiş ve açık bir eşleştirme kodu yok, ya da belge alma kapalı. Dinleyici o zaman on saniyede bir ayarlara
    bakar.
  - Ulaşılamayan Telegram'ı her seferinde iki katı bekleyerek, en çok 15 dakika arayla yeniden dener.
- **Alım:** belge iş kuyruğuna girer (`telegram.document`). İşçi dosyayı Telegram'ın dosya sunucusundan indirir ve
  arayüzdeki bir yükleme gibi alır:
  - türü içeriğinden anlaşılır, şirket belgesi alınmaz, arşivdeki baytlar yeni bir geliş sayılır;
  - belgenin kaynağı `telegram`'dır (Belgeler ekranında "Telegram");
  - indirme yarıda kalırsa iş yeniden denenir; indirilmiş dosya bir sonraki denemeyi bekler, ikinci kez indirilmez.
- **Yanıt:** bot belgeyi getiren iletiye yanıt verir: arşivdeki adı ve ne olduğu (arşive alındı, zaten arşivde,
  okunamadı, para hareketi yok, şirket belgesi, belge değil). Ekstre ve hesap dökümü için satır sayısını ve denetimini
  de yazar; tutar yazmaz. Zip ya da e-posta dosyası belge belge yanıtlanır.
- **Alınamayanlar:** fotoğraf, 20 MB'den büyük dosya, belge olmayan dosya ve Telegram'ın vermediği dosya için bot ne
  yapılacağını yazar (dosya olarak gönderin, Belge ekle ekranını kullanın). Sohbetteki başka sözlere kısa bir yardımla
  yanıt verir.
- **Bir kez:** botun iletilerini hem dinleyici hem eşleştirme denetimi okuyabilir. Her ileti, kim okursa okusun,
  kaldığı yerle (offset) aynı veritabanı işleminde bir kez işlenir; iş kuyruğunun anahtarı aynı belgeyi ikinci kez
  kuyruğa almaz. İkisi aynı anda okursa Telegram bekleyen okumayı keser (409); dinleyici beş saniye sonra yeniden okur.
  Eşleştirme kodunu dinleyici bulursa sohbeti o eşleştirir; arayüzün denetimi eşleşmeyi bir sonraki soruşta görür.
- **Anahtar:** Bildirimler → Kanallar → Telegram kartında "Bota gönderilen belgeleri arşive al"
  (`[notify] telegram_documents`, baştan açık). Komut satırında `iplikci telegram belgeler ac|kapat`.
  - Kapalıyken servis botun iletilerini okumaz. Açılınca Telegram'ın sakladığı son 24 saatteki belgeler de alınır.
- **Reddedilen belirteç:** okuma ya da indirme 401 alırsa Telegram kanalı durur (ADR-0010'daki gibi). Kullanıcı
  belirteci yeniden girene dek ne bildirim gider ne ileti okunur.

## Güvenlik ve gizlilik

- Telegram'ın bot iletileri uçtan uca şifreli değildir: gönderilen belge Telegram'ın sunucularında da durur. Kart
  bunu anahtarın altında söyler; kullanıcı belgeyi sohbetten silebilir.
- Yanıtlara ayrıntı düzeyi (ADR-0010) uygulanmaz. Belgenin kendisi zaten Telegram'dan geçti; yanıt ondan fazlasını
  söylemez ve tutar taşımaz.
- İndirme adresi belirteci taşır (`/file/bot<belirteç>/…`). Hata iletileri ve günlük adresi yazmaz.
- İndirilen belge güvenilmeyen girdidir: her belge gibi kendi sürecinde okunur (ADR-0005), adı yükleme gibi
  temizlenir.
- Yeni dış sunucu yoktur: dosya sunucusu da `api.telegram.org`'dur. İzin listesi değişmez. `egress.https_get`'in
  yanıt sınırı çağıran tarafından verilebilir; belge indirmesi 20 MB'ye kadar alır, kurların 1 MB'lık sınırı aynı
  kalır.

## Sonuçlar

- Olumlu:
  - Kullanıcı belgeyi telefondan ekler ve ne olduğunu hemen öğrenir.
  - Belge ekle ekranıyla aynı kurallar geçer: tür içerikten, aynı belge bir kez, şirket belgesi hiç.
  - Eşleştirme kodu dinleyici çalışırken arayüz açık olmasa da işlenir.
- Olumsuz:
  - Servis Telegram'a sürekli sorar: 25 saniyelik okumalar, günde yaklaşık 3.500 istek. Belge alma kapatılırsa bu da
    durur.
  - Belgeler Telegram'ın sunucularından geçer.
  - 20 MB'den büyük dosyalar için Belge ekle ekranı gerekir.

## Değerlendirilen seçenekler

- **Webhook:** servisin internetten ulaşılabilir olmasını ister; ADR-0012 bunu reddeder.
- **Planı gösterip düğmeyle onay istemek:** telefonda her belge için iki adım olurdu. Gönderme zaten kullanıcının
  isteğidir; gelen klasörü de onaysızdır. Sonucu söyleyen yanıt yeter.
- **Belgeyi gelen klasörüne bırakmak:** klasörün 20 saniye sessiz kalması beklenirdi ve sonucu sohbete yazacak bir yol
  kalmazdı.
- **Kısa yoklama (birkaç saniyede bir sormak):** aynı hız için günde on binlerce istek gerekirdi.
- **Fotoğraftan okumak (OCR):** bankanın verdiği dosya doğrulanabilir; fotoğrafın rakamları doğrulanamaz.
