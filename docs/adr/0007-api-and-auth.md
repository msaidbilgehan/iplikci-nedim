# ADR-0007: HTTP API ve oturum modeli

Durum: Kabul edildi · Tarih: 2026-10-31 · Dayanak: K5, tasarım

## Bağlam

PWA, CLI, MCP ve gerektiğinde Tailscale üzerinden uzaktan erişim aynı servise bağlanacak. MVP panelinin güvenlik
modeli işe yaradı:

- Başlangıç adresindeki tek kullanımlık anahtar, HttpOnly bir çereze dönüşür.
- Her istekte Host ve Origin denetlenir.
- Yazan isteklerde özel bir başlık aranır.

## Karar

**Sunucu ve yollar**

- FastAPI ve pydantic v2, uvicorn üzerinde çalışır.
- Varsayılan adres `127.0.0.1:8643`'tür. MVP'nin paneli 8642'deydi; MVP 2026-10-31'de emekliye ayrıldı
  ([ADR-0018](0018-retire-mvp-clean-start.md)).
- Yollar: JSON API `/api/…`, olay akışı `/api/events/stream` (SSE), MCP `/mcp`, PWA dosyaları `/`.

**Kimlik doğrulama**

- *Tarayıcı, bu bilgisayarda:* `iplikci ac` tek kullanımlık bir giriş bağlantısı üretir. Bağlantı
  `HttpOnly; SameSite=Strict` bir oturum çerezi bırakır; çerez 90 gün geçerlidir ve kullanıldıkça uzar.
- *Tarayıcı, Tailscale üzerinden:* bu bilgisayardaki bir oturumdan kaydedilen passkey (WebAuthn).
- *CLI ve MCP:* anahtar zincirindeki API belirteci (`Authorization: Bearer`).

**İstek güvenliği**

- Her istekte Host izin listesi (DNS rebinding'e karşı) ve kimlik denetlenir.
- Durum değiştiren isteklerde ayrıca Origin denetlenir ve `X-Iplikci: 1` başlığı aranır.
- Yüklemelerde tür ve boyut sınırı vardır. Dosya gizli bir adla `vault/staging/` altına yazılır ve tamamlanınca arşive
  alınır.

**Hatalar ve istemci**

- Hatalar `application/problem+json` biçimindedir: makine kodu ve Türkçe kullanıcı iletisi. İç ayrıntılar yalnızca
  günlüğe yazılır.
- Arayüzün TypeScript istemcisi OpenAPI şemasından üretilir.

## Sonuçlar

- Olumlu: bu bilgisayardaki başka bir site ya da kullanıcı API'ye erişemez; uzaktan erişim güçlü kimlik doğrulamayla
  olur.
- Olumsuz: çerezin süresi dolarsa kullanıcı `iplikci ac` ile (ileride menü çubuğu simgesinden) yeniden girer.

## Uygulama notu (Aşama 3, 2026-11-01)

- **Giriş bağlantısı** iki dakika geçerlidir ve tek kullanımlıktır. Oturum çerezi 90 gün geçerlidir ve en çok günde bir
  uzatılır. Giriş anahtarları servisin belleğinde, oturumlar veritabanında durur; ikisinden de yalnızca SHA-256
  saklanır.
- **Üç kimlik:**
  - tarayıcı oturumu;
  - API belirteci (CLI ve MCP): servisin ilk açılışında üretilir ve anahtar zincirine yazılır;
  - tarayıcı eklentisinin belirteci: yalnızca e-posta alım uçlarını açar ([ADR-0016](0016-mail-connectors.md)).
- **Kimlik istemeyen uçlar:** `/healthz`, `/giris` ve eklentinin eşleştirme ile kanıt uçları (`/api/bridge/pair`,
  `/api/bridge/hello`). Eşleştirmeyi yalnızca bir eklenti kökeni ya da kökensiz bir istemci tamamlayabilir.
- **Arayüz** servisin içinden, derlenmiş olarak sunulur (`src/iplikci/api/ui`); her sayfa oturum ister. İçerik
  güvenlik politikası yalnızca servisin kendi kökenine izin verir.
- **Yüklemeler** `vault/staging/` altında bir partiye yazılır. Bir dosya en çok 1 GiB, bir parti en çok 2.000 dosya ve
  2 GiB'tır. Uygulanmayan parti bir gün sonra çöp kutusuna gider.

## Değerlendirilen seçenekler

- **Yerelde kimliksiz API:** DNS rebinding ya da CSRF ile başka bir site veriye ulaşabilir.
- **HTTP Basic:** kullanım deneyimi kötü; tarayıcı parolayı saklar.
- **OAuth sağlayıcısı:** tek kullanıcı için aşırı karmaşık.
