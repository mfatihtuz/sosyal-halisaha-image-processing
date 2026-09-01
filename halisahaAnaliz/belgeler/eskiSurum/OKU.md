# Onceki surum — SALT REFERANS

Bu klasordeki dosyalar, Claude Web ile gelistirilen ilk surumden kalmadir.
**Yeni kod bunlarin hicbirini kullanmaz ve import etmez.** Burada durmalarinin
tek sebebi, bir kararin neden degistirildigini gerektiginde kaynagindan
gosterebilmektir.

Uzerlerinde degisiklik yapma. Yeni hat `cekirdek/`, `sunucu/`, `arayuz/`
altindadir.

## Neden degistirildigi olculen noktalar

| dosya | tespit edilen sorun | yeni karsiligi |
|---|---|---|
| `birlestir.py` | `KAPI_M = 1.8` tanimli ama hic kullanilmiyor; gercek kapi `yurut_sabit(..., kapi=3.5)` varsayilani. Ayrica `KAYIP_SN`, `DIK_SN`, `DIK_M`, `DOYGUN_ESIK`, `DIK_HIZ` de olu sabit | `cekirdek/ayarlar.py` — tek kaynak, kullanilmayan sabit kalmiyor |
| `birlestir.py` | gozlem yokken `k.k, k.h = p, k.h * 0.7` ile tahmin konum olarak kalicilastiriliyor, hata birikiyor | `cekirdek/kimlikCozucu.py` — Kalman, durum sahte olcumle guncellenmez |
| `birlestir.py` | `kaynastir()` iki kamerayi ESIT agirlikla ortaliyor | `cekirdek/kameraKaynastirma.py` — 1/sigma^2 agirlik + sistematik sapma duzeltmesi |
| `birlestir.py:44` | `g_px`/`y_px` sutunlari `.get(..., -1)` ile okunuyor; teslim edilen CSV'de bu sutunlar HIC YOK, sessizce -1 aliniyor | `cekirdek/veriSemasi.py` — eksik sutun yazmayi/okumayi reddeder |
| `kalibrasyon.py` | `cap.set(CAP_PROP_POS_MSEC)` kullaniyor (raporun kendi 3 numarali tuzagi) | `cekirdek/videoOkuyucu.py` — kare sayarak yurunur |
| `kalibrasyon.py` | `plt.ginput` ile tiklama: silme, geri alma, yakinlastirma yok | `arayuz/betik/kalibrasyonTuvali.js` |
| `arayuz.py` | tkinter, alt surecleri `subprocess` ile cagiriyor | `sunucu/` + `arayuz/` |
