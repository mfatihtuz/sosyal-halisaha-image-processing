# Halisaha Mac Analizi

Tesiste kurulu iki sabit kameranin mac kaydindan oyuncularin saha konumunu
cikarip **isi haritasi**, **kosu metrikleri** ve **isaretli video** ureten
bilgisayarli goru hatti. Tarayicidan calisan yerel bir arayuzu var.

## Kurulum (Windows)

```powershell
cd C:\Users\MFT\Desktop\sosyal-halisaha-image-processing
powershell -ExecutionPolicy Bypass -File halisahaAnaliz\kurulum\kurulumBetigi.ps1
```

Betik ne yapar:

1. Python 3.10-3.13 arar (3.14'e DOKUNMAZ; cu128 indeksinde 3.14 tekerlegi yok)
2. `halisahaAnaliz\.venv` altinda ayri bir sanal ortam acar
3. torch + torchvision'i CUDA cu128 indeksinden **ayni komutta** kurar
   (ayri kurulunca `operator torchvision::nms does not exist` ilk tespitte patlar)
4. Kalan paketleri kurar
5. `videolar\` klasorunu acar
6. Ortami dogrular

Kurulumdan sonra istediginiz zaman:

```powershell
python halisahaAnaliz\kurulum\ortamDogrula.py
```

CUDA, torchvision::nms, ffmpeg/NVENC ve yedi cekirdek modulun selftest'ini
denetler, eksik varsa ne yapilmasi gerektigini yazar.

## Videolar

Mac kayitlari depoya **girmez** (`.gitignore`). Proje kokundeki `videolar\`
klasorune koyun:

```
sosyal-halisaha-image-processing\
  videolar\
    kamera1.mp4
    kamera2.mp4
```

## Durum

| Faz | Durum |
|---|---|
| 0 · Temel (sema, ayarlar, kurulum, test altyapisi) | Bitti |
| 3a · Kimlik temeli (fuzyon, sapma duzeltmesi, Kalman, RTS) | Bitti — IDF1 0,882 -> 0,976 |
| 1 · Kalibrasyon | Sirada |
| 2 · Tespit hatti | Video gerekiyor |
| 3b–7 | Bekliyor |

Ayrinti: `halisahaAnaliz/belgeler/plan.md`

## Yon bulma

| Yol | Ne |
|---|---|
| `halisahaAnaliz/cekirdek/` | Saf algoritma. Arayuzden bagimsiz, GPU'suz test edilebilir |
| `halisahaAnaliz/testler/` | Sentetik sahne, puanlayici, deneyler |
| `halisahaAnaliz/testler/veri/` | **Gercek kalibrasyon ve olcum verisi.** `OKU.md`'yi okuyun |
| `halisahaAnaliz/belgeler/` | Plan, devir raporu, onceki surum (salt referans) |
| `CLAUDE.md` | Isimlendirme, mimari ve degismez kurallar |

## Proje kurallari

`CLAUDE.md` — camelCase + Turkce isimlendirme, tek yonlu bagimlilik, ve
"bir degisiklik once olculur" kurali.
