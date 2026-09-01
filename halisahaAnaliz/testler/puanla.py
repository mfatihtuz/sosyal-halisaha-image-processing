"""Kimlik kalitesini SAYIYLA olcer. Projenin en onemli araci.

Raporun 11 numarali dersi: "bir degisiklik onerilmeden once 'bunun ise
yaradigini ne kanitlayacak' sorusu cevaplanmali". Onceki surumde kimlik sorunu
ortaya ciktiginda art arda yama denendi ve her yama tek karelerden goz karariyla
degerlendirildi. Bu modul o donguyu bitirir.

Uretilen olcumler:

  IDF1     Kimlik F1 skoru. TEK ONEMLI OLCU. Tahmin kimlikleri ile gercek
           kimlikler arasindaki en iyi 1-1 eslemede tutan gozlem orani.
           Parcalanma ve takas, ikisi de bu skoru dusurur.
  takas    Bir oyuncunun etiketinin baska bir oyuncuya atlama sayisi.
  MOTA     Tespit odakli klasik olcu; FN + FP + takas cezasi.
  konumRms Dogru eslesen orneklerdeki konum hatasi (metre).
  kapsama  Her gercek oyuncunun etiketlenmis oldugu zaman orani.

    python puanla.py --selftest
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@dataclass
class Puan:
    """Bir kosunun kimlik kalitesi."""

    idf1: float
    idTespit: int
    idYanlisPozitif: int
    idYanlisNegatif: int
    takas: int
    mota: float
    konumRms: float
    kapsama: float
    gercekOrnek: int
    tahminOrnek: int

    def __str__(self) -> str:
        return ("IDF1 %.3f | takas %d | MOTA %.3f | konum RMS %.2f m | kapsama %.1f%%"
                % (self.idf1, self.takas, self.mota, self.konumRms, 100 * self.kapsama))

    def satir(self, etiket: str = "") -> str:
        return ("%-26s %6.3f %7d %7.3f %9.2f %9.1f"
                % (etiket, self.idf1, self.takas, self.mota, self.konumRms, 100 * self.kapsama))


BASLIK = "%-26s %6s %7s %7s %9s %9s" % ("kosu", "IDF1", "takas", "MOTA", "RMS(m)", "kapsama%")


def _kareyeGore(zamanlar, kimlikler, x, y) -> dict[float, dict]:
    """(t, kimlik) -> konum sozlugu."""
    kareler: dict[float, dict] = {}
    for t, k, xx, yy in zip(zamanlar, kimlikler, x, y):
        kareler.setdefault(round(float(t), 3), {})[k] = (float(xx), float(yy))
    return kareler


def puanla(gercek: dict[float, dict], tahmin: dict[float, dict],
           eslesmeYaricapi: float = 2.0) -> Puan:
    """Tahmini gercege karsi puanlar.

    `gercek` ve `tahmin`: {zaman: {kimlik: (x, y)}}

    IDF1 hesabi iki asamali:
      1. Her karede konuma gore eslestir (Macar, yaricap kapili).
      2. Tahmin kimlikleri ile gercek kimlikler arasinda, toplam eslesme sayisini
         AZAMILEYEN kuresel 1-1 atama bul. Yerel olarak dogru ama kimligi surekli
         degisen bir cikti bu adimda cezalandirilir -- takasi goren sey budur.
    """
    ortakZaman = sorted(set(gercek) & set(tahmin))
    if not ortakZaman:
        raise ValueError("Gercek ve tahmin arasinda ortak zaman damgasi yok")

    gercekKimlikler = sorted({k for kare in gercek.values() for k in kare})
    tahminKimlikler = sorted({k for kare in tahmin.values() for k in kare})
    gIndis = {k: i for i, k in enumerate(gercekKimlikler)}
    tIndis = {k: i for i, k in enumerate(tahminKimlikler)}

    # Adim 1: kare bazinda konum eslestirmesi
    birlikte = np.zeros((len(gercekKimlikler), len(tahminKimlikler)), np.int64)
    kareEslesmeleri: list[dict] = []
    hatalar: list[float] = []
    toplamGercek = toplamTahmin = 0

    for t in ortakZaman:
        gKare, tKare = gercek[t], tahmin[t]
        toplamGercek += len(gKare)
        toplamTahmin += len(tKare)
        if not gKare or not tKare:
            kareEslesmeleri.append({})
            continue

        gAdlar, tAdlar = list(gKare), list(tKare)
        G = np.array([gKare[a] for a in gAdlar], float)
        T = np.array([tKare[a] for a in tAdlar], float)
        d = np.linalg.norm(G[:, None, :] - T[None, :, :], axis=2)

        bedel = np.where(d <= eslesmeYaricapi, d, 1e6)
        eslesme = {}
        for i, j in zip(*linear_sum_assignment(bedel)):
            if d[i, j] <= eslesmeYaricapi:
                eslesme[gAdlar[i]] = tAdlar[j]
                birlikte[gIndis[gAdlar[i]], tIndis[tAdlar[j]]] += 1
                hatalar.append(float(d[i, j]))
        kareEslesmeleri.append(eslesme)

    # Adim 2: kuresel kimlik eslemesi (toplam eslesmeyi azamileyen 1-1 atama)
    satir, sutun = linear_sum_assignment(-birlikte)
    idTespit = int(birlikte[satir, sutun].sum())
    kimlikEslemesi = {gercekKimlikler[i]: tahminKimlikler[j] for i, j in zip(satir, sutun)}

    idYanlisNegatif = toplamGercek - idTespit
    idYanlisPozitif = toplamTahmin - idTespit
    idf1 = (2 * idTespit / (2 * idTespit + idYanlisPozitif + idYanlisNegatif)
            if idTespit else 0.0)

    # Takas: bir gercek oyuncunun eslestigi tahmin kimligi degisirse
    takas = 0
    onceki: dict = {}
    for eslesme in kareEslesmeleri:
        for gKimlik, tKimlik in eslesme.items():
            if gKimlik in onceki and onceki[gKimlik] != tKimlik:
                takas += 1
            onceki[gKimlik] = tKimlik

    dogruEslesme = sum(len(e) for e in kareEslesmeleri)
    yanlisNegatif = toplamGercek - dogruEslesme
    yanlisPozitif = toplamTahmin - dogruEslesme
    mota = 1.0 - (yanlisNegatif + yanlisPozitif + takas) / max(toplamGercek, 1)

    kapsama = dogruEslesme / max(toplamGercek, 1)
    konumRms = float(np.sqrt(np.mean(np.square(hatalar)))) if hatalar else float("nan")

    return Puan(idf1=idf1, idTespit=idTespit, idYanlisPozitif=idYanlisPozitif,
                idYanlisNegatif=idYanlisNegatif, takas=takas, mota=mota,
                konumRms=konumRms, kapsama=kapsama,
                gercekOrnek=toplamGercek, tahminOrnek=toplamTahmin)


def sahneyiPuanla(sahne, tahmin: dict[float, dict], eslesmeYaricapi: float = 2.0) -> Puan:
    """Sentetik sahnenin bilinen gercegine karsi puanlar."""
    gercek = {}
    for k, t in enumerate(sahne.zamanlar):
        gercek[round(float(t), 3)] = {
            sahne.oyuncuAdlari[i]: tuple(sahne.gercekKonum[k, i])
            for i in range(sahne.oyuncuSayisi)}
    return puanla(gercek, tahmin, eslesmeYaricapi)


# ----------------------------------------------------------------- selftest

def selftest() -> None:
    from sentetikSahne import sahneUret

    sahne = sahneUret(tohum=0)
    zaman = [round(float(t), 3) for t in sahne.zamanlar]

    def gercekTahmin(gurultu=0.0, tohum=1):
        rng = np.random.default_rng(tohum)
        return {t: {sahne.oyuncuAdlari[i]:
                    tuple(sahne.gercekKonum[k, i] + rng.normal(0, gurultu, 2))
                    for i in range(sahne.oyuncuSayisi)}
                for k, t in enumerate(zaman)}

    # 1) Kusursuz tahmin -> kusursuz puan
    p = sahneyiPuanla(sahne, gercekTahmin(0.0))
    assert p.idf1 == 1.0, p
    assert p.takas == 0, p
    assert p.mota == 1.0, p
    assert p.konumRms < 1e-9, p

    # 2) Kucuk gurultu skoru bozmamali (konum RMS haric)
    p = sahneyiPuanla(sahne, gercekTahmin(0.10))
    assert p.idf1 > 0.999, p
    assert p.takas == 0, p
    assert 0.08 < p.konumRms < 0.25, p

    # 3) ASIL TEST: iki oyuncunun etiketi ortadan itibaren takaslanirsa
    #    IDF1 dusmeli ve takas gorulmeli
    orta = len(zaman) // 2
    takasli = gercekTahmin(0.0)
    a, b = sahne.oyuncuAdlari[0], sahne.oyuncuAdlari[1]
    for t in zaman[orta:]:
        takasli[t][a], takasli[t][b] = takasli[t][b], takasli[t][a]
    p = sahneyiPuanla(sahne, takasli)
    assert p.takas == 2, p                       # iki oyuncu da etiket degistirdi
    assert p.idf1 < 0.96, p                      # yarim sure boyunca iki kimlik yanlis
    assert p.konumRms < 1e-9, p                  # konumlar hala kusursuz

    # Takas konumdan degil KIMLIKTEN yakalanmali: konum RMS'i sifirken IDF1 dusuk
    print("    takas testi: konum RMS %.3f m ama IDF1 %.3f -- takas konumdan gizlenemiyor"
          % (p.konumRms, p.idf1))

    # 4) Surekli yeniden dogan kimlikler (onceki surumun parcalanma sorunu):
    #    her 50 karede bir tum etiketler yenilensin
    parcali = {}
    for k, t in enumerate(zaman):
        kusak = k // 50
        parcali[t] = {"%s_p%d" % (sahne.oyuncuAdlari[i], kusak):
                      tuple(sahne.gercekKonum[k, i]) for i in range(sahne.oyuncuSayisi)}
    p = sahneyiPuanla(sahne, parcali)
    assert p.idf1 < 0.20, p                      # 12 kusak -> her kimlik surenin 1/12'sini kapsiyor
    assert p.kapsama > 0.99, p                   # ama konumlar dogru: kapsama tam
    print("    parcalanma testi: kapsama %.1f%% ama IDF1 %.3f -- parcalanma da cezalandiriliyor"
          % (100 * p.kapsama, p.idf1))

    # 5) Eksik oyuncu -> kapsama ve IDF1 duser
    eksik = {t: {ad: xy for ad, xy in kare.items() if ad != sahne.oyuncuAdlari[0]}
             for t, kare in gercekTahmin(0.0).items()}
    p = sahneyiPuanla(sahne, eksik)
    assert 0.90 < p.idf1 < 0.97, p
    assert 0.90 < p.kapsama < 0.95, p

    print("selftest ok  (kusursuz/gurultulu/takasli/parcali/eksik senaryolari dogru puanlaniyor)")


if __name__ == "__main__":
    selftest()
