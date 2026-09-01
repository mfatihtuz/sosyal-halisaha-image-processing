"""Kimlik algoritmalarini yan yana olcen deney.

Bu dosyanin varlik sebebi raporun 11 numarali dersi: "bir degisiklik onerilmeden
once 'bunun ise yaradigini ne kanitlayacak' sorusu cevaplanmali". Onceki surumde
kimlik sorununa art arda yama denendi ve hicbiri sayiyla dogrulanmadi.

Burada eski yontem SADAKATLE yeniden yazilir ve yenisiyle ayni sahnede, ayni
gozlemlerle, ayni puanlayiciyla karsilastirilir.

    python deneyKimlik.py                 # eski vs yeni
    python deneyKimlik.py --kapi          # kapi parametresi taramasi
    python deneyKimlik.py --tohum 0,1,2   # birden fazla sahnede
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cekirdek.ayarlar import Ayarlar  # noqa: E402
from cekirdek.kameraKaynastirma import (hataModeliFitEt, kaynastir,  # noqa: E402
                                        sapmaAlaniFitEt, sapmayiUygula)
from cekirdek.kimlikCozucu import coz  # noqa: E402
from puanla import BASLIK, sahneyiPuanla  # noqa: E402
from sentetikSahne import sahneUret  # noqa: E402


# ------------------------------------------------------- eski yontem (referans)

class _EskiKimlik:
    """`birlestir.py` icindeki `Kimlik` sinifinin birebir davranisi."""

    AZAMI_HIZ = 9.0

    def __init__(self, g):
        self.k = np.array([g.x, g.y], float)
        self.h = np.zeros(2)
        self.renk = self._renkVek(g.ton, g.doygunluk)

    @staticmethod
    def _renkVek(ton, doygunluk):
        # Onceki surum ton degerini OpenCV olceginde (0-179) tutup 2 ile carpiyordu
        a = np.deg2rad(np.asarray(ton, float))
        w = np.asarray(doygunluk, float) / 255.0
        return np.stack([np.cos(a) * w, np.sin(a) * w], axis=-1)

    def tahmin(self, dt):
        return self.k + self.h * min(dt, 0.5)

    def guncelle(self, g, dt):
        yeni = np.array([g.x, g.y], float)
        if dt > 0:
            ham = np.clip((yeni - self.k) / dt, -self.AZAMI_HIZ, self.AZAMI_HIZ)
            self.h = 0.8 * self.h + 0.2 * ham
        self.k = yeni
        self.renk = 0.95 * self.renk + 0.05 * self._renkVek(g.ton, g.doygunluk)


def eskiYontem(kareler, n, kapi=3.5, renkAgirlik=1.0):
    """Onceki surumun `yurut_sabit` fonksiyonu.

    Uc belirleyici ozelligi aynen korunmustur:
      * SABIT kapi (varsayilan 3,5 m) -- bosluk suresinden bagimsiz
      * gozlem yokken tahminin konum olarak KALICILASTIRILMASI ve hizin 0,7 ile
        carpilmasi (`k.k, k.h = p, k.h * 0.7`)
      * yalnizca ileri yonlu, geri donusu olmayan kararlar
    """
    zamanlar = sorted(kareler)
    baslangic = next((t for t in zamanlar if len(kareler[t]) >= n), zamanlar[0])
    yuvalar = [_EskiKimlik(g) for g in kareler[baslangic][:n]]

    sonuc, onceki = {}, None
    for t in zamanlar:
        if t < baslangic:
            continue
        dt = (t - onceki) if onceki is not None else 0.1
        onceki = t
        gozlemler = kareler[t]
        T = np.array([y.tahmin(dt) for y in yuvalar])

        eslesen = {}
        if gozlemler:
            G = np.array([[g.x, g.y] for g in gozlemler])
            uzak = np.linalg.norm(T[:, None] - G[None], axis=2)
            gr = _EskiKimlik._renkVek([g.ton for g in gozlemler],
                                      [g.doygunluk for g in gozlemler])
            bedel = uzak + renkAgirlik * np.linalg.norm(
                np.array([y.renk for y in yuvalar])[:, None] - gr[None], axis=2)
            bedel[uzak > kapi] = 1e6
            for i, j in zip(*linear_sum_assignment(bedel)):
                if uzak[i, j] <= kapi:
                    eslesen[i] = j

        kare = {}
        for i, y in enumerate(yuvalar):
            if i in eslesen:
                g = gozlemler[eslesen[i]]
                y.guncelle(g, dt)
                kare[i + 1] = (y.k[0], y.k[1], False)
            else:
                p = y.tahmin(dt)
                y.k, y.h = p, y.h * 0.7      # tahmini konum olarak kalicilastir
                kare[i + 1] = (p[0], p[1], True)
        sonuc[t] = kare
    return sonuc


# ------------------------------------------------------- ortak yardimcilar

def sahneyiHazirla(tohum: int, ayarlar: Ayarlar | None = None,
                   sapmaDuzelt: bool = True):
    """Sahneyi uretip kaynastirilmis kareleri dondurur."""
    sahne = sahneUret(tohum=tohum, ayarlar=ayarlar)

    def cevir(gozlemler):
        return [{"x_m": g["x_m"], "y_m": g["y_m"], "ton": g["ton"],
                 "doygunluk": g["doygunluk"], "parlaklik": g["parlaklik"],
                 "siyahlik": g["siyahlik"], "u_px": 100.0, "v_px": 200.0,
                 "kutuSol": 90.0, "kutuUst": 100.0, "kutuGen": 20.0,
                 "kutuYuk": 100.0} for g in gozlemler]

    k1 = [cevir(k) for k in sahne.gozlemler[1]]
    k2 = [cevir(k) for k in sahne.gozlemler[2]]

    if sapmaDuzelt:
        # Iki kameranin goreli sistematik sapmasini olcup gider. Bu adim
        # olmadan fuzyon kaynagi her degistiginde konum sicriyor ve yuvalar
        # komsu kapiyor -- sahne #6'da IDF1'i 0,591'e dusuren sey buydu.
        alanlar = sapmaAlaniFitEt(k1, k2, ayarlar)
        k1 = sapmayiUygula(k1, alanlar[1])
        k2 = sapmayiUygula(k2, alanlar[2])

    hm = hataModeliFitEt(k1, k2, ayarlar)
    kareler = {round(float(t), 3): kaynastir(k1[i], k2[i], hm, ayarlar)
               for i, t in enumerate(sahne.zamanlar)}
    return sahne, kareler


def _tahmineCevir(sonuc):
    """Cozucu ciktisini puanlayicinin bekledigi bicime cevirir."""
    cikti = {}
    for t, kare in sonuc.items():
        cikti[t] = {}
        for no, v in kare.items():
            cikti[t]["yuva%d" % no] = (v[0], v[1])
    return cikti


def _dolguOrani(sonuc):
    toplam = sum(len(k) for k in sonuc.values())
    dolgu = sum(1 for k in sonuc.values() for v in k.values() if v[2])
    return dolgu / max(toplam, 1)


# ------------------------------------------------------- deneyler

def eskiYeniKiyas(tohumlar=(0, 1, 2)) -> None:
    print("\nESKI YONTEM vs YENI YONTEM")
    print("Ayni sahne, ayni kaynastirilmis gozlemler, ayni puanlayici.\n")
    print(BASLIK + "  dolgu%")
    print("-" * 78)

    toplamlar = {"eski": [], "yeni": []}
    for tohum in tohumlar:
        sahne, kareler = sahneyiHazirla(tohum)
        n = sahne.oyuncuSayisi

        eski = eskiYontem(kareler, n)
        p = sahneyiPuanla(sahne, _tahmineCevir(eski))
        print(p.satir("eski (sabit 3,5 m)  #%d" % tohum) + "  %6.1f" % (100 * _dolguOrani(eski)))
        toplamlar["eski"].append(p)

        yeni = {t: {no: (v[0], v[1], v[2]) for no, v in kare.items()}
                for t, kare in coz(kareler, n).items()}
        p = sahneyiPuanla(sahne, _tahmineCevir(yeni))
        print(p.satir("yeni (uyarli kapi)  #%d" % tohum) + "  %6.1f" % (100 * _dolguOrani(yeni)))
        toplamlar["yeni"].append(p)
        print()

    print("ORTALAMALAR")
    print("-" * 78)
    for ad, puanlar in toplamlar.items():
        print("%-26s %6.3f %7.1f %7.3f %9.2f %9.1f"
              % (ad, np.mean([p.idf1 for p in puanlar]),
                 np.mean([p.takas for p in puanlar]),
                 np.mean([p.mota for p in puanlar]),
                 np.mean([p.konumRms for p in puanlar]),
                 100 * np.mean([p.kapsama for p in puanlar])))

    eskiIdf1 = np.mean([p.idf1 for p in toplamlar["eski"]])
    yeniIdf1 = np.mean([p.idf1 for p in toplamlar["yeni"]])
    eskiTakas = np.mean([p.takas for p in toplamlar["eski"]])
    yeniTakas = np.mean([p.takas for p in toplamlar["yeni"]])
    print("\nIDF1: %.3f -> %.3f  (%+.1f%%)   takas: %.0f -> %.0f  (%+.0f%%)"
          % (eskiIdf1, yeniIdf1, 100 * (yeniIdf1 / eskiIdf1 - 1),
             eskiTakas, yeniTakas, 100 * (yeniTakas / max(eskiTakas, 1) - 1)))


def kapiTaramasi(tohumlar=(0, 1, 2)) -> None:
    """Kapi parametresini tarar. Merkezi iddianin dogrudan sinanmasi."""
    print("\nKAPI TARAMASI")
    print("Iddia: onceki surumun 3,5 m sabit kapisi cok genis; dogru kapi zamana uyarli.\n")
    print("%-30s %6s %7s %9s %8s" % ("kapi", "IDF1", "takas", "RMS(m)", "dolgu%"))
    print("-" * 64)

    # Sabit kapilar (eski mimari, farkli esiklerle)
    for kapi in (1.0, 1.3, 1.8, 2.5, 3.5, 5.0):
        idf1, takas, rms, dolgu = [], [], [], []
        for tohum in tohumlar:
            sahne, kareler = sahneyiHazirla(tohum)
            s = eskiYontem(kareler, sahne.oyuncuSayisi, kapi=kapi)
            p = sahneyiPuanla(sahne, _tahmineCevir(s))
            idf1.append(p.idf1); takas.append(p.takas); rms.append(p.konumRms)
            dolgu.append(_dolguOrani(s))
        print("%-30s %6.3f %7.1f %9.2f %8.1f"
              % ("eski mimari, sabit %.1f m" % kapi, np.mean(idf1), np.mean(takas),
                 np.mean(rms), 100 * np.mean(dolgu)))

    print()
    # Zamana uyarli kapilar (yeni mimari)
    for vAzami, taban in ((4.0, 0.5), (6.0, 0.5), (8.0, 0.5), (8.0, 1.0), (12.0, 0.5)):
        a = Ayarlar()
        a.kimlik.vAzami, a.kimlik.kapiTabani = vAzami, taban
        idf1, takas, rms, dolgu = [], [], [], []
        for tohum in tohumlar:
            sahne, kareler = sahneyiHazirla(tohum, a)
            s = {t: {no: (v[0], v[1], v[2]) for no, v in kare.items()}
                 for t, kare in coz(kareler, sahne.oyuncuSayisi, a).items()}
            p = sahneyiPuanla(sahne, _tahmineCevir(s))
            idf1.append(p.idf1); takas.append(p.takas); rms.append(p.konumRms)
            dolgu.append(_dolguOrani(s))
        print("%-30s %6.3f %7.1f %9.2f %8.1f"
              % ("yeni, %.0f*dt + %.1f m" % (vAzami, taban), np.mean(idf1), np.mean(takas),
                 np.mean(rms), 100 * np.mean(dolgu)))


if __name__ == "__main__":
    tohumlar = (0, 1, 2)
    if "--tohum" in sys.argv:
        tohumlar = tuple(int(x) for x in sys.argv[sys.argv.index("--tohum") + 1].split(","))
    if "--kapi" in sys.argv:
        kapiTaramasi(tohumlar)
    else:
        eskiYeniKiyas(tohumlar)
