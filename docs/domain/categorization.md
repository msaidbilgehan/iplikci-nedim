# Kategori kuralları

Kaynak: MVP'nin `CLAUDE.md` ve `README.md` dosyaları (2026-10-31), kişisel kararlardan arındırılmıştır.

## Katmanlar (V1)

| Katman | Yer | İçerik |
|---|---|---|
| Varsayılan | `src/iplikci/rules/default.yaml` (depoda) | Türkiye'de yaygın işyerleri için genel kurallar. Kişisel bilgi içermez. |
| Kişisel | `<veri klasörü>/rules/personal.yaml` | Kullanıcının kararları ve kişileri: kira, aile, işveren, `_biten`, işyerine göre gereklilik… |

Kişisel katman önce denenir:

- Bir açıklama önce kişisel kurallarla eşleştirilir (isimli işyerleri, sonra genel kelimeler). Biri tutarsa o geçerlidir;
  varsayılan katmanın isimli bir işyeri de olsa. Hiçbiri tutmazsa varsayılan kurallar aynı sırayla denenir.
- Bankanın kategori başlığı ve `_zayıf` kelimeler, hiçbir katmanın isimli kuralı ya da genel kelimesi tutmazsa denenir;
  yine önce kişisel katman.
- Ana grupların sırası, dolayısıyla renkleri, varsayılan dosyadan gelir. Yalnızca kişisel dosyada olan gruplar onlardan
  sonra gelir.
- Kişisel dosyadaki gereklilik, `_tür`, `_biten`, `_gereklilik_işyeri` ve `_banka_kategorileri` değerleri varsayılanların
  üstüne yazılır; `_düzenli` listeleri birleşir.
- Kişisel dosyada olmayan bir varsayılan kategoriye kural eklenirse kategori, varsayılandaki grubuyla kişisel dosyaya
  eklenir.

Her değişiklik yazılmadan önce doğrulanır: kişisel dosya, varsayılanların üstünde kurulabiliyor mu. Önceki sürüm
`rules/history/`'ye alınır. Sonuç olarak hangi işlemlerin kategorisinin değiştiği döner.

## Yapı

```yaml
Yeme & İçme:                    # ana grup
  Kafe & Kahve:                 # kategori
    Starbucks: [STARBUCKS]         # isimli işyeri: desenler
    _: [CAFE, KAHVE]               # genel anahtar kelimeler (işyeri adı açıklamadan alınır)
  Market & Gıda:
    Migros: [MIGROS, MJET]
    _zayıf: [GIDA]                 # başka hiçbir şey tutmazsa

_gereklilik:                    # kategorilerin gereklilik düzeyi
  Gerekli: [Market & Gıda, Kira]
  İsteğe bağlı: [Kafe & Kahve]
  Gereksiz: [Kredi Kartı Faizi]

_gereklilik_işyeri:             # kategorisinden farklı değerlendirilen işyerleri
  <İşyeri>: İsteğe bağlı

_düzenli:                       # taahhüt kategorileri: tutar değişse de düzenli ödeme
  - Kira
  - Elektrik, Su & Doğalgaz
  - Dijital Abonelikler

_biten:                         # bittiğini bildiğiniz ödemeler: işyeri ve son ödeme ayı
  <İşyeri>: 2026-10

_banka_kategorileri: …          # Garanti'nin ekstrede yazdığı başlıkların eşlemesi
```

- `re:` ile başlayan desen, katlanmış ASCII metin üzerinde çalışan bir düzenli ifadedir.
- `_tür`, o kategorideki transferlerin türünü belirler: `gelir`, `kişi`, `borç`, `yatırım`
  ([defter kuralları](ledger.md)).
- `_biten`: YAML tam tarihleri tarih nesnesine çevirir; yalnızca yıl ve ay kullanılır.
- Dosya kullanıcıya açık olduğu için anahtarları ve yorumları Türkçedir.

## Eşleştirme sırası

1. İsimli işyerleri, dosyadaki sırayla.
2. Genel anahtar kelimeler; açıklamada en önce geçen kazanır.
3. Garanti'nin ekstrede yazdığı kategori başlığı (`_banka_kategorileri`).
4. `_zayıf` kelimeler.

- Desenler büyük-küçük harfe ve Türkçe karakterlere duyarsızdır; bir kelimenin başından itibaren aranır.
- Ücretler nedenlerine göre bölünür (`categorize._fee_category`).
- `_gereklilik`'te olmayan kategoriler "Belirsiz" (`unknown`) sayılır; faiz ve ücretler varsayılan olarak "Gereksiz"dir.
- İlk 8 ana grup renklidir; "Diğer" her zaman gridir (`categorize.group_slot`).

## İlkeler

- Kullanıcı bilgisi koda değil kurallara yazılır:
  - Kullanıcının bittiğini söylediği bir ödeme ya da alışkanlık `_biten`'e yazılır.
  - Yanlış sınıflanan bir işyeri için isimli bir kural eklenir.
- Komşusunu yakalayabilecek desenler `re:` ve çevre denetimiyle (lookaround) sabitlenir. Örnek:
  `(?<![A-Z])GETIR(?! ?ARAC)`.
- Genel işyeri bilgisi varsayılan katmana gider:
  - "GETIR ARAC" araç kiralamadır.
  - "UBER EATS" yemek siparişidir, yolculuk değil.
- Kişiye özgü kararlar kişisel katmana gider: bir işyerinin gerekliliği, bir aboneliğin bittiği, bir kişinin kim olduğu.
- Kategorisiz kalanlar Yapılacaklar'da sık görülenden seyreğe sıralanır; tek tıkla kural eklenir.
