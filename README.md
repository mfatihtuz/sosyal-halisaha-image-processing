# Halisaha Mac Analizi

Tesiste kurulu iki sabit kameranin mac kaydindan oyuncularin saha konumunu
cikarip **isi haritasi**, **kosu metrikleri** ve **isaretli video** ureten
bilgisayarli goru hatti. Tarayicidan calisan yerel bir arayuzu var.

## Kurulum (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File kurulum\kurulumBetigi.ps1
```

Betik projeye ait ayri bir sanal ortam acar, torch + torchvision'i CUDA
indeksinden **ayni komutta** kurar ve ortami dogrular. Mevcut Python
kurulumunuza dokunmaz.

## Durum

Gelistirme suruyor. Faz ilerlemesi icin `belgeler/` klasorune bakin.

## Proje kurallari

`CLAUDE.md` — isimlendirme, mimari ve degismez kurallar.
