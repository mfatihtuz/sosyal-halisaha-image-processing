# Gercek olcum verisi

## `kamera1_kalibrasyon.json`, `kamera2_kalibrasyon.json`

Tesisteki iki kameranin GERCEK kalibrasyonu. Onceki surumde uretildi, dogrulandi
ve devralindi. Yeniden kalibrasyon gerekmez.

    kamera 1: lam = -0.5028   rms = 0.363 m
    kamera 2: lam = -0.5001   rms = 0.310 m
    ikisi de 1920x1080, saha varsayimi 50 x 30 m

Bu dosyalardan HESAPLANAN (video gerekmeden) geometrik gercekler:

**Yer cozunurlugu — 1 piksellik ayak noktasi hatasi kac metre:**

    kamera 1:  X=0'da 0,01-0,12 m   ->   X=50'de 0,41-0,55 m
    kamera 2:  X=0'da 0,41-0,55 m   ->   X=50'de 0,01-0,13 m

Her kamera kendi yarisinda obarunden 4-40 kat hassas. Esit agirlikli ortalama
almak, iyi olcumu kotu olcumle bozmak demektir; fuzyon bu yuzden 1/sigma^2 ile
tartar.

**Kapsama (1 m izgara, 1500 nokta):** kamera 1 %98,4 · kamera 2 %98,7 ·
ikisi birden %97,1 · hicbiri %0,0.

**Birlesik konum belirsizligi** (2 piksellik tespit hatasi varsayimiyla) sahanin
cogunda 0,03-0,31 m. Tek zayif nokta (0,28) ve (50,28) koseleri: 0,82 m, cunku
her kamera tam kendi dibini goremez ve o kose yalnizca uzaktaki kameraya kalir.

**Buradan cikan asil sonuc:** piksel cozunurlugu 0,03-0,31 m verirken olculen
iki kamera uyusmazligi 0,85 m. Darbogaz cozunurluk DEGIL, kalibrasyonun kendisi.
Sistematik sapma duzeltmesinin (`kameraKaynastirma.sapmaAlaniFitEt`) bu kadar
ise yaramasinin sebebi bu.

## `kamera1_izler.csv`

Onceki surumun urettigi gercek tespit verisi: 60 sn, 10 fps, 603 kare,
7.631 satir, ~14 kisi. `testler/sentetikSahne.py` bu dosyadan olculen dokuz
istatistige gore kalibre edildi:

    kare basina adim (gozlem)   medyan 0,15 m   p90 0,44 m   p99 1,13 m
    en yakin komsu (gozlem)     p10 2,23 m      medyan 5,07 m
    kare basina tespit          12,66 / 14
    guven                       yakin 0,856     uzak 0,705
    iki kamera uyusmazligi      medyan 0,85 m   %92'si 2 m icinde

DIKKAT: bu degerlerin hepsi GOZLEM uzerinden, yani gurultu dahil olculmustur.
Sentetik sahneyle kiyaslarken gurultusuz gercek konum degil, gozlem kullanilmali
-- bu ayrimi atlamak sahneyi 4,5 kat fazla gurultulu yapmisti.

Basligi `t_s,iz_id,x_m,y_m,guven,u_px,v_px,h,s,v` -- ESKI semadir, `g_px`/`y_px`
sutunlari YOKTUR. Yeni sema `cekirdek/veriSemasi.py`'de.
