# Halisaha Mac Analizi — proje kurallari

Iki sabit kameranin mac kaydindan oyuncu konumu, isi haritasi, kosu metrikleri
ve isaretli video ureten bilgisayarli goru hatti.

## Isimlendirme

- Dosya adlari **camelCase + Turkce**, ASCII: `sahaKalibrasyon.py`, `oyuncuTespit.py`
- Fonksiyon ve degisken adlari da camelCase + Turkce: `kareOku`, `hataHaritasi`
- Sinif adlari PascalCase: `Sahne`, `KimlikCozucu`
- Modul duzeyi sabitler BUYUK_HARF: `TESPITLER`, `KAMERA_KONUMLARI`
- Kod ve yorumlar ASCII (Turkce karakter yok) — konsol kodlama sorunlarini onler
- **Kullaniciya gorunen her metin tam Turkce ve Turkce karakterli** (arayuz, rapor, grafik)

## Mimari

```
cekirdek/   saf algoritma, arayuzden bagimsiz, GPU'suz test edilebilir
sunucu/     FastAPI — arayuze veri ve is yurutme
arayuz/     tarayici, cerceve yok, CDN yok, cevrimdisi calisir
ciktilar/   rapor, ozet gorsel, video uretimi
testler/    sentetik sahne + selftest'ler + puanlama
```

Bagimlilik tek yonlu: `arayuz -> sunucu -> cekirdek`. Cekirdek digerlerini bilmez.

## Degismez kurallar

1. **Veri semasi tek yerde.** Her tablo `cekirdek/veriSemasi.py`'de tanimli. Yazan
   da okuyan da oradan alir. Elle CSV basligi yazmak yasak.
2. **Goruntu asla warp edilmez.** Sadece ilgilenilen noktalar donusturulur.
3. **`cap.set(POS_MSEC)` kullanilmaz.** Anahtar kareye yuvarlar ve sapma olculemez.
   Hedefin oncesinden baslayip kareleri sayarak yurunur.
4. **Kapi yalnizca mesafeye bakar.** Renk kapi ICINDE ayirt edici olarak kullanilir,
   kapiyi genisletmez.
5. **Esikler `cekirdek/ayarlar.py`'de.** Modul icine gomulu sabit yazilmaz.
6. **Her cekirdek modulun `selftest()`'i olur.** GPU ve video gerektirmez.
7. **Bir degisiklik once olculur.** "Bunun ise yaradigini ne kanitlayacak?" sorusu
   cevaplanmadan degisiklik yapilmaz. Olcum araci: `testler/sentetikSahne.py` +
   `testler/puanla.py`.

## Test

```
python cekirdek/veriSemasi.py          # sema turu ve reddetme testleri
python cekirdek/ayarlar.py             # esik tutarliligi
python testler/sentetikSahne.py        # sentetik sahne gercek olcumleri tutuyor mu
python kurulum/ortamDogrula.py         # ortam hazir mi
```

## Sentetik sahne

`testler/sentetikSahne.py`, gercek `kamera1_izler.csv` verisinden olculen dokuz
istatistigi yeniden uretir (adim dagilimi, komsu mesafesi, tespit anmasi, guven,
iki kamera uyusmazligi). Kimlik algoritmasi once burada puanlanir; sahne gercege
benziyorsa sahnede calisan algoritma gercekte de calisir.
