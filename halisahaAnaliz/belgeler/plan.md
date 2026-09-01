# Halısaha Maç Analizi — Sıfırdan Yeniden Yazım Planı

> **Bu belge yaşayan plandır.** Ölçüm bir varsayımı çürüttüğünde burası güncellenir;
> çürütülen varsayım silinmez, ne olduğu ve neyle değiştirildiği yazılır.
> Son güncelleme: Faz 0 ve Faz 3a tamamlandıktan, gerçek kalibrasyon dosyaları
> incelendikten sonra.

## Durum

| Faz | Durum | Ölçülen sonuç |
|---|---|---|
| 0 · Temel | **Bitti** | Tüm selftest'ler geçiyor |
| 1 · Kalibrasyon | Sırada | Gerçek JSON'lar devralındı ve analiz edildi |
| 2 · Tespit + tanı | Bekliyor | Video gerekiyor |
| 3a · Kimlik temeli | **Bitti** | IDF1 0,882 → **0,976**, takas −%67 |
| 3b · Kimlik global | Bekliyor | 3a'nın tıkandığı yerler ölçüldü, aşağıda |
| 4–6 | Bekliyor | — |

Dal: `claude/futsal-match-analysis-pplzgc` — push'landı.

### Ölçümle çürütülen iki varsayım

**1. "Sabit 3,5 m kapı hatanın kaynağı" — YANLIŞ ÇIKTI.**
Planın ilk sürümünün merkezî iddiasıydı. Sentetik tezgâhta ölçülünce eski
mimaride 3,5 m'nin neredeyse en iyi değer olduğu, daraltmanın felaket olduğu
görüldü:

    eski mimari, sabit 1,3 m  ->  IDF1 0,727   takas 17,7
    eski mimari, sabit 3,5 m  ->  IDF1 0,982   takas  5,7
    yeni mimari, 8*dt + 1,0   ->  IDF1 0,999   takas  0,0

Eski mimari kendi savrulmasını telafi etmek için geniş kapıya *muhtaç*. Kazanç
kapının darlığından değil **öngörünün kalitesinden** geliyor: Kalman + gözlem
yokken durumu bozmamak + RTS düzleştirici. Aynı 1,8 m kapı eski mimaride 0,879,
yenisinde 0,999. Seçilen kapı 1,3 m değil **8·dt + 1,0 m** (dt=0,1'de 1,80 m).

**2. Test tezgâhının kendisi hatalıydı — düzeltildi.**
Gerçek veriden ölçülen 0,15 / 0,44 m adım değerleri **gözlem** üzerindendi
(gürültü dahil); ilk sürüm bunları sentetiğin **gürültüsüz gerçek konumlarıyla**
kıyaslıyordu. Gürültü üstüne eklenince sentetik gözlem adımı p90 1,96 m oluyordu,
gerçeğin 4,5 katı, ve o sahnede yapılan ilk kapı taraması tamamen yanıltıcıydı.

### Ölçümle ortaya çıkan yeni bulgu: hata iki bileşenli

Gerçek veri iki ölçümü aynı anda veriyor ve tek bir gürültü terimi ikisini birden
açıklayamaz:

    aynı kameranın ardışık kare adımı ... p90 0,44 m   (küçük)
    iki kameranın aynı anda uyuşmazlığı . med 0,85 m   (büyük)

Tek tutarlı açıklama: hatanın büyük kısmı rastgele değil **sistematik** —
kalibrasyon artığı konuma bağlı ve zamanla sabit. Sonuçları:

- **Eşleştirme/kapı** rastgele bileşene bakar, o küçüktür → dar kapı çalışır.
- **Füzyon** sistematik bileşene bakar, o ortalamayla yok olmaz.
- **Füzyon kaynağı değiştiğinde konum sıçrar** (12 → 1 → 12 → 2), çünkü iki
  kameranın sapması farklı. Ölçülen: sıçrama 0,55 m medyan / 1,01 m p90, yani
  1,80 m'lik kapının yarısı. Kimlik hatalarının ana kaynağı buydu.

**Çözüm — `kameraKaynastirma.sapmaAlaniFitEt`:** doğru cevap gerekmiyor. Aynı
kişiyi gören iki kameranın konum farkı, o noktadaki göreli sapmadır; saha
ızgarasında biriktirilip yumuşatılınca sapma alanı çıkar. Farkın yarısı birinden
çıkarılıp yarısı diğerine eklenince göreli sapma sıfırlanır ve sıçrama biter.
Uyuşmazlık her sahnede yarıya indi (0,82 → 0,41 m); tıkanan sahnede IDF1
0,591 → 0,948.

### Gerçek kalibrasyondan hesaplanan geometri (video gerekmedi)

Devralınan `kamera1/2_kalibrasyon.json` dosyalarından doğrudan çıkarıldı:

**Yer çözünürlüğü — 1 piksellik ayak noktası hatası kaç metre:**

| | X=0 | X=25 | X=50 |
|---|---|---|---|
| kamera 1 | 0,01–0,12 m | ~0,10 | 0,41–0,55 m |
| kamera 2 | 0,41–0,55 m | ~0,10 | 0,01–0,13 m |

Her kamera kendi yarısında diğerinden **4–40 kat** hassas. Ağırlıklı füzyonun
gerekçesi artık varsayım değil, hesaplanmış.

**Kapsama** (1 m ızgara, 1500 nokta): kamera 1 %98,4 · kamera 2 %98,7 · ikisi
birden %97,1 · **hiçbiri %0,0**.

**Birleşik belirsizlik** (2 px ayak hatası): sahanın çoğunda 0,03–0,31 m. Tek
zayıf nokta (0,28) ve (50,28) köşeleri, 0,82 m — her kamera tam kendi dibini
göremiyor, o köşe yalnızca uzaktaki kameraya kalıyor.

**Bundan çıkan asıl sonuç:** çözünürlük 0,03–0,31 m verirken ölçülen uyuşmazlık
0,85 m. **Darboğaz çözünürlük değil, kalibrasyonun kendisi.** Faz 1'de
kalibrasyonu iyileştirmenin getirisi yüksek; sapma düzeltmesinin bu kadar işe
yaramasının sebebi de bu.

## Bağlam

Tesiste kurulu iki sabit kameranın maç kaydından oyuncuların saha konumunu çıkarıp ısı haritası,
koşu metrikleri ve işaretli video üreten bir bilgisayarlı görü hattı. Önceki sürüm (Claude Web ile
geliştirilen, devir raporu ile teslim edilen hâli) konumu doğru ölçüyor — kalibrasyon RMS 0,31–0,36 m,
iki kameranın aynı oyuncu için uyuşması medyan 0,85 m — ama **oyuncu kimliğini maç boyunca sabit
tutamıyor.** Kişi bazlı her metrik bu yüzden güvenilmez ve proje kullanılamaz durumda.

Bu yeniden yazımın amacı, ölçülmüş konum doğruluğunu koruyup kimlik katmanını çalışır hâle getirmek
ve etrafına profesyonel bir yerel web arayüzü kurmak.

### Yeniden yazımı tetikleyen ölçümler

`kamera1_izler.csv` (60 sn, 10 fps, 603 kare, 7.631 satır) üzerinde yapılan üç ölçüm önceki teşhisi
değiştiriyor:

**1. Kimlik takası bir doğa kanunu değil, bir eşik hatası.**

| Ölçüm | Değer |
|---|---|
| Oyuncunun kare başına yer değiştirmesi (0,1 sn) | medyan 0,15 m · p90 **0,44 m** |
| En yakın komşu oyuncuya mesafe | p10 **2,23 m** · medyan 5,07 m |
| İki oyuncunun 1 m'den yakın olduğu an oranı | %1 |
| Kare başına tespit (14 kişi için) | ort. 12,66 → **~1,3 kişi eksik** |

Oyuncu 0,44 m hareket ederken en yakın rakip 2,23 m ötede: **5 kat marj.** 10 fps'te eşleştirme
kolay bir problem. `birlestir.py:115` kapıyı 3,5 m açıyor ve doğru değer dosyada zaten yazılı
(`KAPI_M = 1.8`, satır 25) ama **hiçbir yerde kullanılmıyor**; `KAYIP_SN`, `DIK_SN`, `DIK_M`,
`DOYGUN_ESIK`, `DIK_HIZ` ile birlikte altı ölü sabit.

> **DÜZELTME — bu paragrafın ilk hâli "3,5 m kapı takasların ana kaynağı" diyordu ve ölçülünce
> yanlış çıktı.** Eski mimaride 3,5 m neredeyse en iyi değerdir; daraltmak IDF1'i 0,982'den
> 0,727'ye düşürür. Belirleyici olan kapı değil öngörünün kalitesi. Ayrıntı için yukarıdaki
> "Ölçümle çürütülen iki varsayım" bölümüne bak. Ölü sabitler tespiti geçerliliğini koruyor.

**2. Raporun övündüğü "piksel taşıma" fiilen çalışmıyor.** CSV başlığı
`t_s,iz_id,x_m,y_m,guven,u_px,v_px,h,s,v` — `g_px`/`y_px` yok. `birlestir.py:44` bunları
`.get("g_px", -1)` ile okuyup sessizce −1 alıyor; kimlik kartlarına ve işaretli videoya −1 kutu
boyutu gidiyor. Raporun 1 numaralı tuzağı (CSV başlık uyuşmazlığı) hâlâ açık.

**3. Renk ölçümü gerçeği yakalamıyor.** Fotoğraflarda formalar bariz ayrışıyor (turuncu, sarı-siyah,
mavi, sarı-kırmızı, lacivert). Ama 60 sn yaşayan 7 izin ölçülen doygunlukları 20/36/61/10/24/27/33 —
sadece biri 60'ı geçiyor, tonların çoğu 184–256° bandında, yani arkadaki mavi duvar sızıyor. Sebep:
renk, dikdörtgen kutunun bir diliminden alınıyor ve o dilim çim + duvar + yandaki oyuncu içeriyor.

### Kaybedilen en büyük avantaj

Bu iş **çevrimdışı**: maç bitmiş, video elimizde. Ama `yurut_sabit` kare kare ilerleyip her kararı
geri dönülmez veriyor — sanki canlı yayın işliyormuş gibi. Geleceği görebiliyoruz ve kullanmıyoruz.
Yeni tasarımın merkezinde bu var.

---

## Mülakatta alınan kararlar

| Konu | Karar |
|---|---|
| Hedef | Kendi takımı için; elle müdahale kabul edilebilir |
| Çıktılar | Isı haritası · koşu metrikleri · işaretli video/klipler · uzun HTML rapor · 1920×1080 tek PNG özet |
| Olay istatistikleri | Gol/asist/pas ağı/top hâkimiyeti → **sonraki faz, kapsam dışı** (top takibi gerekir) |
| Kimlik | Yarı otomatik + düzeltme paneli |
| Kadro | Her maç sıfırdan, maç başında hızlı seçim/atama. Oyuncu değişimi **yok** |
| Takım ayrımı | Kullanıcı kendi takımına **siyah forma** (~%85 siyah üst), rakibe **yelek** giydirecek |
| Hız | 4 saat → 40–60 dk. Doğruluktan ödün yok |
| Arayüz | Yerel Python sunucu + tarayıcı dashboard, tam Türkçe |
| İsimlendirme | camelCase + Türkçe ASCII: `sahaKalibrasyon.py`, `oyuncuTespit.py` |
| Saha ölçüsü | Ayarlanabilir, varsayılan 50×30 m |
| Kalibrasyon | Mevcut JSON'lar içe aktarılacak; yeniden kalibrasyon seçeneği de olacak |
| Python | 3.12 (ayrı sanal ortam; mevcut 3.14 durur) |
| Doğrulama | Referans kesit, ayarlanabilir, varsayılan 1 dakika |

---

## Mimari

Üç katman, aralarında tek yönlü bağımlılık. Çekirdek arayüzü hiç bilmez; her modül tek başına
komut satırından çalışır ve kendi sentetik selftest'ine sahiptir.

```
halisahaAnaliz/
├─ kurulum/
│   ├─ gereksinimler.txt
│   ├─ kurulumBetigi.ps1          Windows tek komut: venv + torch(cu128) + paketler + model
│   └─ ortamDogrula.py            CUDA / torch / ultralytics / ffmpeg / NVDEC kontrolü, tek rapor
├─ cekirdek/                       saf algoritma — arayüz bağımsız, GPU'suz test edilebilir
│   ├─ veriSemasi.py              TÜM tabloların tek doğru kaynağı
│   ├─ ayarlar.py                 tüm eşikler tek dataclass'ta, JSON'a serileşir
│   ├─ lensModeli.py              bölme modeli, ileri/geri dönüşüm
│   ├─ sahaKalibrasyon.py         λ + H ortak çözümü; çizgi/nokta/daire/dikdörtgen kısıtları
│   ├─ kalibrasyonDenetim.py      aynalama denetimi + çapraz kamera hata haritası
│   ├─ videoOkuyucu.py            kare-doğru okuma, NVDEC, toplu besleme
│   ├─ oyuncuTespit.py            YOLO11-seg · FP16 · toplu · uzak yarı karolama
│   ├─ gorunumOzniteligi.py       maskeden renk profili + ReID gömme
│   ├─ kameraKaynastirma.py       hata haritasına göre ağırlıklı füzyon
│   ├─ parcaOlusturucu.py         şüphesiz tracklet üretimi (belirsizlikte kes)
│   ├─ kimlikCozucu.py            global parça bağlama + çapa kısıtları + RTS düzleştirici
│   ├─ takimAyrimi.py             siyahlık/doygunluk ayrımı + elle geçersiz kılma
│   ├─ hareketMetrikleri.py       Savitzky-Golay, hız, sprint, rol, veri kalitesi
│   └─ isiHaritasi.py
├─ sunucu/
│   ├─ uygulama.py                FastAPI kurulumu, statik arayüz servisi
│   ├─ isKuyrugu.py               arka plan iş yürütücü + SSE ilerleme akışı
│   ├─ ucNoktalar.py              REST uçları
│   └─ kareSunucu.py              video karesi / oyuncu kırpıntısı servisi (önbellekli)
├─ arayuz/                         tarayıcı — çerçevesiz, CDN'siz, çevrimdışı çalışır
│   ├─ index.html
│   ├─ stil/anaStil.css           elle yazılmış tasarım sistemi (token'lı, açık/koyu tema)
│   └─ betik/
│       ├─ kalibrasyonTuvali.js   yakınlaştır/kaydır · geri al · sil · sürükle · büyüteç
│       ├─ kimlikDuzeltme.js      zaman çizgisi · senkron oynatıcı · çapa · takas
│       ├─ panoGrafikler.js       SVG/canvas grafik modülü (harici kütüphane yok)
│       └─ ortak/
├─ ciktilar/
│   ├─ raporUretici.py            tek dosyalık uzun HTML (gömülü görseller)
│   ├─ ozetGorsel.py              1920×1080 paylaşım PNG'si
│   └─ videoUretici.py            işaretli video + öne çıkan klipler
├─ testler/
│   ├─ sentetikSahne.py           bilinen gerçekli sahne üreteci (kimlik testinin temeli)
│   ├─ testKalibrasyon.py · testKimlik.py · testMetrik.py · testSema.py
│   └─ puanla.py                  referansa karşı IDF1 / takas / MOTA / konum RMS
└─ belgeler/
```

**Neden çerçevesiz arayüz:** kalibrasyon ve düzeltme ekranlarının ikisi de canvas ağırlıklı; React
gibi bir katman burada yardım etmez, engel olur. CDN de yok — uygulama internetsiz makinede de
açılmalı. Grafikler için harici kütüphane yerine kendi SVG/canvas modülümüz; uygulama genelinde tek
tutarlı görsel dil verir.

---

## Kritik tasarım kararları

### 1. Veri şeması — tek doğru kaynak

`veriSemasi.py` her tabloyu ad+tip listesi olarak tanımlar; **yazan da okuyan da aynı yerden import
eder.** Disk formatı **Parquet**: sütun adları dosyanın içinde gömülü olduğu için raporun 1 numaralı
tuzağı (başlık kayması) yapısal olarak imkânsız hâle gelir. Ayrıca tam maç için CSV'den ~10 kat
küçük ve hızlı. Kullanıcı isterse CSV dışa aktarımı ayrı bir düğme.

`testSema.py` her tablo için yazma→okuma turu yapıp sütun adı ve tip eşleşmesini doğrular.

Ana tablolar:

| Tablo | İçerik |
|---|---|
| `tespitler` | `t_s, kare_no, kamera, x_m, y_m, guven, u_px, v_px, g_px, y_px, maske_alan, ton, doygunluk, parlaklik, siyahlik` |
| `parcalar` | tracklet kimliği, zaman aralığı, görünüm tanımlayıcısı, kesilme sebebi |
| `oyuncuIzleri` | `t_s, kare_no, oyuncu_id, ad, takim, x_m, y_m, kaynak, dolgu, supheSkoru, k1_u..k1_y, k2_u..k2_y` |
| `oyuncuMetrikleri` | rol, mesafe, hız, sprint, tempo, saha kullanımı, veri kalitesi |

### 2. Kalibrasyon

**Matematik korunuyor.** Tek parametreli bölme modeli + homografi, birlikte ve doğrudan **metre**
hatası küçültülerek çözülüyor. Bu kurgu ölçülerek çalıştığı kanıtlanmış (0,31–0,36 m); dokunulmaz.
Raporun elediği yollar (undistort+warp, Brown-Conrady, "çizgiler ne kadar düz" ölçütü) tekrar
denenmeyecek.

**Eklenenler:**

- **Daire kısıtı** — orta daire üzerindeki her nokta `|p − merkez| = r` denklemi. Sahanın ortasından
  gelen güçlü bir global kısıt; şu an hiç kullanılmıyor.
- **Ceza sahası dikdörtgeni** — kenarlarına ek kısıt.
- **Mevcut JSON içe aktarma** — `lam` ve `H` yüklenir, ızgara çizilir; kullanıcı sıfırdan başlamak
  yerine nokta ekleyerek iyileştirir.
- **Otomatik aynalama denetimi** (raporun 2 numaralı tuzağı, bir kez düşülmüş): iki kamera kalibre
  edildikten sonra aynı zaman damgasındaki tespitler sahaya yansıtılır; medyan uyuşmazlık büyükse
  X/Y aynalaması denenir, düzelen varyant tek tıkla uygulanır. Elle `kontrol.py --ayna x`
  çalıştırma zorunluluğu kalkar.
- **Tek RMS yerine hata haritası** (raporun 4 numaralı açık sorunu): birkaç yüz kare boyunca iki
  kameranın aynı oyuncu için verdiği bağımsız konumlar toplanır, saha üzerinde uyuşmazlık haritası
  çıkarılır. Böylece "uzak yarıda doğruluk ölçülmedi" belirsizliği kapanır — **ve bu harita
  doğrudan füzyon ağırlıklarını besler.**

**Arayüz gereksinimleri** (kullanıcının açıkça şikâyet ettiği eksikler):

| Özellik | Not |
|---|---|
| Yakınlaştırma / kaydırma | Tekerlek + boşluk-sürükle |
| Büyüteç | İmleç yanında, ince uzak çizgilere piksel hassasiyetiyle tıklamak için |
| Nokta silme | Noktaya tıkla → `Del` |
| Geri al / ileri al | `Ctrl+Z` / `Ctrl+Shift+Z`, tüm oturum boyunca |
| Nokta sürükleme | Yanlış tıklamayı silmeden düzeltme |
| Kısıt grubu paneli | Her grup için nokta sayısı, görünürlük, grubu temizle |
| Kare seçici | Çizgiyi oyuncu kapatıyorsa başka kareye geç |
| **Canlı çözüm** | Yeterli kısıt olur olmaz her değişiklikte yeniden çöz, ızgarayı ve RMS'i anında güncelle |
| Artık renklendirmesi | Her nokta kendi hatasına göre yeşil→kırmızı; kötü tıklama gözle görünür |

### 3. Tespit hattı

| Karar | Değer | Gerekçe |
|---|---|---|
| Model | **YOLO11m-seg** | Maske, rengi arka plandan tamamen ayırır — 3 numaralı bulgunun çözümü |
| Hassasiyet | FP16 | ~1,7× hız, doğrulukta kayıp yok |
| Toplu işleme | 8–16 kare | GPU doyurma, ~1,5–2× |
| Çözünürlük | 1920 | Uzak yarıdaki 15–40 px oyuncular için şart |
| Uzak yarı karolama | Karenin uzak ~%40'ında 2 örtüşen kırpıntı | Kare başına 12,66→14 tespit boşluğunu kapatmayı hedefler. **Önce kazanç ölçülecek, sonra kalıcılaştırılacak** |
| Ayak noktası | Maskenin en alt piksel kütlesi | Kutu altından daha kararlı (kutu payı ve kısmi örtülmede kaymaz) |
| Zaman | `kare_no / fps` | `cap.set(POS_MSEC)` **kullanılmaz** (raporun 3 numaralı tuzağı); pencere başından birkaç saniye önce başlanıp kareler sayılarak yürünür |
| Takipçi | Ultralytics takipçisi **kapalı** | Kendi eşleştirmemizi yapıyoruz; `iz_id` zaten atılıyordu |

Beklenen hız: 59 dk × 2 kamera × 10 fps ≈ 70.800 kare. FP16 + toplu ile ~30 kare/sn hedefi →
**~40 dakika.** Yetmezse TensorRT dışa aktarımı ikinci kademe olarak devreye alınır.

### 4. Kimlik katmanı — projenin kalbi

**Aşama 1 · Ağırlıklı füzyon.** Eşleştirme yine Macar algoritması, ama eşleşen çift artık **eşit
ağırlıkla ortalanmıyor**: her kameranın o saha noktasındaki hata haritası değerine göre
`1/σ²` ağırlığı alır. Kamera kendi yakın yarısında baskın olur. Raporun 4 numaralı açık sorunu kapanır.
Görünüm özniteliği de oyuncuyu **daha yakın gören** kameradan alınır — uzak yarıdaki bozuk maskeler
renk profilini kirletmez.

**Aşama 2 · Şüphesiz parça üretimi.** Tasarımın yönü tersine çevriliyor: parçalanma ucuz, takas pahalı.

- **Zamana uyarlı kapı:** `kapi(dt) = v_azami·dt + konum_gurultusu`. dt=0,1 sn'de ~1,2 m
  (eski sabit 3,5 m yerine). Boşluk büyüdükçe kapı doğal olarak genişler — 12 sn boşlukta 14 m
  atlamak makul, 0,1 sn'de değil.
- **Belirsizlik testi:** en iyi aday ikinciden belirgin şekilde iyi değilse parça **kesilir**.
  Kısa ama temiz parçalar üretilir.
- **Kalman süzgeci** (sabit hız, 4 durumlu), ölçüm gürültüsü hata haritasından. Eski `0.8/0.2`
  karışımı ve tahminin konum olarak kalıcılaştırılması (`k.k, k.h = p, k.h*0.7`) kaldırılır —
  bu, gözlem yokken hatayı biriktiriyordu.

**Aşama 3 · Global bağlama.** Parçalar tüm pencere birden görülerek 14 zincire bağlanır.

- Her parça bir görünüm tanımlayıcısı taşır: maske tabanlı renk histogramı + OSNet ReID gömmesi
  (en yüksek çözünürlüklü karelerinden ortalanmış).
- Yönlü çizge: `i → j` kenarı, j i'den sonra başlıyorsa ve `mesafe/boşluk ≤ 7 m/s` ise. Kenar
  maliyeti = hareket + görünüm + boşluk cezası.
- Kısıt: **tam olarak N zincir**, ve zamanda örtüşen iki parça aynı zincire giremez.
- Çözüm: **asgari maliyetli akış** (`networkx`, parça başına kapasite 1, N birim akış). Birkaç bin
  parça ve 14 zincir için anlık çözülür.
- Yedek/temel çizgi: hiyerarşik birleştirme (en ucuz uyumlu çifti tekrar tekrar birleştir). Daha
  kolay hata ayıklanır; ikisi de referansa karşı puanlanıp kazanan seçilir.

**Aşama 4 · Boşluk doldurma.** Zincirlerdeki delikler ileri-geri **RTS düzleştirici** ile doldurulur.
Oyuncunun nerede tekrar göründüğünü bildiğimiz için ara konum çok daha isabetli olur; eski sürümün
sadece ileri yürüyen kestirimi (%6,6 dolgu) yerini gerçekten bilgilendirilmiş bir ara değere bırakır.

**Aşama 5 · Şüphe skoru.** Her oyuncu-zaman için kaydedilir: atama marjı (en iyi vs ikinci), gözlem
yokluğu, iki zincirin 1,5 m'ye yaklaşması, görünümün zincir modeliyle çelişmesi. Bunlar tek bir
**riskli an listesi**ne indirgenir ve düzeltme paneli bunları en riskliden başlayarak kullanıcıya
gezdirir.

### 5. Düzeltme paneli ve kadro tanıtma

**Kadro tanıtma:** sistem 14 oyuncunun hepsinin tespit edildiği ve en iyi ayrıştığı kareyi kendisi
bulur. Kullanıcı her kutuya tıklayıp isim yazar (yerel isim listesinden otomatik tamamlamalı) ve
takımını seçer. Maçlar birbirinden bağımsızdır; sadece isim listesi hatırlanır.

**Düzeltme paneli:**

- Senkron üçlü görünüm: kamera 1 · kamera 2 · üstten harita
- Zaman çizgisinde oyuncu başına risk bandı; en riskli anlar işaretli
- Kutuya tıkla → kadrodan doğru oyuncuyu seç
- "Buradan itibaren şu ikisini takasla" düğmesi
- Klavye: `←/→` kare adımı, `boşluk` oynat/durdur, rakam tuşları oyuncu seçimi
- **Her düzeltme bir çapadır.** "Yeniden çöz" 3. aşamayı çapaları katı kısıt olarak alıp saniyeler
  içinde tekrarlar (parçalar önbellekte). Tek bir düzeltme dakikalarca videoyu toparlar; risk
  listesi gözle görülür şekilde kısalır.

### 6. Takım ayrımı

Kullanıcının siyah forma + yelek düzeniyle problem tekil bir eşiğe iner:

- Maskeden `siyahlik` = düşük parlaklık **ve** düşük doygunluk piksellerinin oranı; ayrıca medyan
  ton/doygunluk/parlaklık.
- İki küme beklenir: siyah forma (yüksek `siyahlik`) vs yelek (yüksek doygunluk). Ayrım kalitesi
  kümeler arası boşlukla **ölçülür ve kullanıcıya bir güven sayısı olarak gösterilir**.
- Bölünme 7/7'ye yakın değilse veya boşluk darsa otomatik atama **öneri** olarak kalır; kullanıcı
  zaten isim verirken takımı da seçiyor, dolayısıyla ek iş doğmaz.
- Eski kayıtlar (bu düzen uygulanmadan çekilmiş maçlar) için elle atama tam destekli kalır.

Numaralandırma **takımdan bağımsız** yapılır (raporun 10 numaralı tuzağı) — takım etiketi değişince
numaralar kaymaz.

### 7. Metrikler

Kanıtlanmış düzeltmeler korunuyor (yumuşatma, ±3 örneklik türev tabanı, fiziksel hız kırpması), üstüne:

- **Savitzky-Golay süzgeci**, hareketli ortalama yerine. Hareketli ortalama tepe noktalarını
  sistematik olarak bastırır ve maksimum hızı olduğundan düşük gösterir; sprint sayımı bundan
  doğrudan etkilenir.
- Yeni metrikler: hız bölgelerine göre mesafe dağılımı, en uzun sprint, toplam sprint mesafesi,
  dakika bazlı tempo eğrisi (yorgunluk), takım ortalamasıyla karşılaştırma.
- Bölgeler **sol / orta / sağ** olarak adlandırılır (raporun adlandırma uyarısı).
- **Veri kalitesi her metriğin yanında.** Örneklerin gözlemden mi dolgudan mı geldiği, hangi
  kameranın gördüğü ve hata haritası biliniyor; eşiğin altındaki oyuncunun metrikleri soluk
  gösterilip uyarı basılır.

### 8. Doğrulama disiplini

Raporun 11 numaralı dersinin ("değişiklik önerilmeden önce *bunun işe yaradığını ne kanıtlayacak*
sorusu cevaplanmalı") kurumsallaştırılması:

- **Tanı görüntüleyici Faz 2'de yazılır, sonda değil.** Kimlik sorunuyla karşılaştığımızda araç
  hazır olur.
- **Referans kesit:** kullanıcı düzeltme panelinde bir kesiti (varsayılan 1 dk, ayarlanabilir)
  kusursuz hâle getirir; `referans.parquet` olarak saklanır.
- `puanla.py` her koşuyu referansa karşı **IDF1, kimlik takas sayısı, MOTA, konum RMS** ile
  puanlar. Skorlar koşu bazında saklanır; her algoritma değişikliğinin etkisi sayıyla görülür.
- Her çekirdek modülün sentetik selftest'i (önceki projenin iyi fikri) korunur — GPU ve video
  gerektirmez, saniyeler içinde çalışır.

### 9. Çıktılar

| Çıktı | İçerik |
|---|---|
| Dashboard | Etkileşimli ısı haritaları, sıralanabilir metrik tablosu, grafikler, video oynatıcı |
| **Uzun HTML rapor** | Tek dosya, kendi kendine açılır, görseller gömülü. Tüm oyuncular, ısı haritaları, tablolar, grafikler. WhatsApp'tan atılabilir |
| **Özet PNG 1920×1080** | Tek paylaşım görseli: takım özeti + oyuncu başına anahtar istatistik tablosu + mini ısı haritaları. Telefonda okunacak şekilde tasarlanır |
| İşaretli video | Kutu, isim, iz, üstten görünüm minimap |
| Klipler | En hızlı koşular, en yüksek tempolu bölümler |

Grafik ve dashboard tasarımı, uygulama anında `dataviz` becerisinin rehberliğiyle yapılır
(renk paleti, grafik tipi seçimi, açık/koyu tema tutarlılığı).

---

## Fazlar

Her faz sonunda ölçülebilir bir kabul ölçütü var; ölçüt karşılanmadan sonraki faza geçilmez.

| Faz | Kapsam | Kabul ölçütü | Durum |
|---|---|---|---|
| **0 · Temel** | Repo iskeleti, `veriSemasi`, `ayarlar`, kurulum betiği, `ortamDogrula`, sentetik test altyapısı | `ortamDogrula.py` yeşil; tüm selftest'ler geçiyor | **Bitti** |
| **3a · Kimlik (temel)** | Ağırlıklı füzyon, sistematik sapma düzeltmesi, zamana uyarlı kapı, Kalman, RTS düzleştirici | Eski sürümle sayısal karşılaştırma | **Bitti** — IDF1 0,882 → 0,976, takas −%67 |
| **1 · Kalibrasyon** | Çekirdek çözüm + daire/ceza sahası kısıtları, tuval arayüzü (yakınlaştır/geri al/sil/sürükle/büyüteç/canlı çözüm), JSON içe aktarma, aynalama denetimi, hata haritası | Mevcut JSON'lar içe aktarılıyor; RMS ≤ 0,40 m; geometrik hata haritası `HataModeli`'ni besliyor | Sırada |
| **2 · Tespit + tanı** | Hızlandırılmış seg hattı, uzak yarı karolama, kare-doğru zaman, **işaretli tanı videosu** | Kare başına tespit 12,66 → ≥13,5; kamera başına 60 sn penceresi < 25 sn'de işleniyor | Video gerekiyor |
| **3b · Kimlik (global)** | Parça üretimi + asgari maliyetli akışla global bağlama | 3a'yı IDF1'de yenerse kalır, yenemezse elenir. **Hedef: 3a'nın tıkandığı sahneler** (#3: 0,860 · #6: 0,948) | Bekliyor |
| **4 · Düzeltme** | Kadro tanıtma, düzeltme paneli, çapa + yeniden çözüm, referans üretimi ve `puanla.py` | 1 dk kesit ≤ 10 dk elle işle kusursuz; bir çapa risk listesini ölçülebilir şekilde kısaltıyor | Bekliyor |
| **5 · Analiz** | Takım ayrımı, metrikler, ısı haritaları, dashboard görselleştirme | Takım ayrımı siyah/yelek maçında %100; metrikler sentetik testte doğru | Bekliyor |
| **6 · Çıktılar** | Uzun HTML rapor, 1920×1080 özet PNG, işaretli video, klipler | Rapor tek dosya olarak telefonda açılıyor | Bekliyor |
| **7 · Tam maç** | 59 dk uçtan uca koşu, performans ayarı, doğrulama raporu | Tam maç ≤ 60 dk; bellek taşması yok | Bekliyor |

Faz sırası değişti: 3a, 1'den önce yapıldı. Sebebi, sentetik tezgâhın video
gerektirmemesi ve projenin tek gerçek riskinin kimlik katmanı olmasıydı — riski
önce ölçmek doğru oldu, çünkü merkezî varsayımın yanlış olduğu orada çıktı.

### Faz 3a'nın nerede tıkandığı (3b'nin hedefi)

8 sahnede ölçüldü. Yeni hat 5 sahnede kusursuz (IDF1 1,000, sıfır takas), ama
ikisinde tıkanıyor: #3 (0,860) ve #6 (0,948). İkisinde de sapma düzeltmesi
sonrası kalan hata, **ileri yönlü ve geri dönülmez** karar yapısından geliyor —
bir yuva bir kez yanlış kişiye kilitlendiğinde geri dönemiyor. 3b'nin
(parça + global bağlama) çözmesi gereken tam olarak bu.

**Erken uçtan uca dilim:** Faz 3a sonunda arayüz olmadan da çalışan tam bir hat var — video girer,
oyuncu izleri ve tanı videosu çıkar. Böylece kimlik kalitesini arayüz işine girmeden ölçebiliriz.

---

## Çalışma düzeni

- Kod bu oturumda `claude/futsal-match-analysis-pplzgc` dalına yazılıp push edilir.
- Kullanıcı yerelde (Windows, RTX 4060 Ti 16 GB, Python 3.12) `git pull` yapıp çalıştırır; ya da
  aynı dal üzerinde yerel Claude Code ile devam eder.
- GPU ve video burada olmadığı için buradaki her modül **sentetik selftest ile doğrulanmış** olarak
  teslim edilir; gerçek video doğrulaması yerelde yapılır.

### Depoya alınan gerçek veri

Bulut oturumuna yüklenen her şey repoya kaydedildi; Desktop'a geçişte hiçbir şey
kaybolmuyor ve hangi sürümün geçerli olduğu belirsiz kalmıyor.

| Yol | İçerik |
|---|---|
| `testler/veri/kamera1_kalibrasyon.json`, `kamera2_kalibrasyon.json` | **Gerçek kalibrasyon, devralındı.** Yeniden kalibrasyon gerekmez |
| `testler/veri/kamera1_izler.csv` | Gerçek tespit verisi; sentetik sahne bundan kalibre edildi |
| `testler/veri/OKU.md` | Bu dosyalardan hesaplanan geometrik gerçekler (çözünürlük, kapsama, belirsizlik) |
| `belgeler/devirRaporu.html` | Önceki sürümün devir raporu |
| `belgeler/eskiSurum/*.py` | Önceki sürümün kodu — **salt referans**, yeni kod import etmez |
| `belgeler/eskiSurum/OKU.md` | Her dosyanın hangi ölçülen sorun yüzünden değiştirildiği |

Hâlâ eksik olan tek şey **video**. Boyut nedeniyle buluta yüklenemiyor; Faz 2
(tespit hattı) ve Faz 7 (tam maç) bu yüzden yerelde yapılacak.

### Desktop'a geçiş

Bulut oturumunda yapılan her şey `claude/futsal-match-analysis-pplzgc` dalında
ve push'lu. Yerelde:

```
git clone https://github.com/mfatihtuz/sosyal-halisaha-image-processing
cd sosyal-halisaha-image-processing
git checkout claude/futsal-match-analysis-pplzgc
powershell -ExecutionPolicy Bypass -File halisahaAnaliz\kurulum\kurulumBetigi.ps1
python halisahaAnaliz\kurulum\ortamDogrula.py
```

Videolar repoya **girmez** (`.gitignore` içinde). Yerelde ayrı bir klasörde
dursun, arayüzden dosya seçilerek verilir.

Sıra: video gerektirmeyen işler (Faz 1 çekirdeği, Faz 3b, kalibrasyon arayüzü)
bulutta da yapılabilir; Faz 2 ve sonrası yerelde.

---

## Kapsam dışı (not edildi, sonraki faz)

- **Top takibi** ve ona bağlı olay istatistikleri: gol, asist, pas ağı, top hâkimiyeti, şut.
- **Oyuncu değişimi** desteği (şu an sabit kadro varsayımı geçerli, kullanıcı teyit etti).
- Maçlar arası kalıcı oyuncu havuzu ve sezon istatistikleri (isim listesi hatırlanır, geçmiş tutulmaz).

## Tekrar denenmeyecekler

Raporda **ölçülerek** elenmiş yollar; zaman harcanmayacak:

- Görüntüyü düzleştirip (undistort) warp etmek — kenarları yok ediyor
- Brown-Conrady (k1,k2,k3) + "çizgiler ne kadar düz" ölçütü — aşırı serbestlik, fiziksel anlamsız katsayılar
- ReID açık BoT-SORT'a güvenmek — istatistiksel olarak fark yok
- Ham forma renginden takım ayrımı (maskesiz, kutu diliminden) — kesintisiz dağılım
- Hareket korelasyonundan takım ayrımı — 30×50 m sahada herkes birlikte hareket ediyor
- Kimlik yaratıp öldüren serbest takip + parça dikme
- Kimlik kartında yeniden tespit + en yakına bağlama
