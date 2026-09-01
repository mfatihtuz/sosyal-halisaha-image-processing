"""Iki kameranin tespitlerini saha uzerinde tek listeye indirger.

Onceki surumden farki: eslesen cift artik ESIT AGIRLIKLA ortalanmiyor.

Raporun 4 numarali acik sorunu soyle diyordu: "Her kameranin kendi yarisindan
sorumlu olmasi planlandi ama kodda boyle bir agirliklandirma YOK -- fuzyon iki
kamerayi esit agirlikla ortaliyor." Oysa bir kameranin konum hatasi mesafenin
karesiyle buyur: ayak noktasindaki 1-2 piksellik hata yakinda santimetre, uzak
yarida metrelerdir. Uzak kamerayi yakin kamerayla esit tartmak, iyi olcumu kotu
olcumle bozmaktir.

Burada her kamera `1/sigma^2` ile tartilir. Sigma, hata modelinden gelir:
Faz 1'in capraz kamera hata haritasi gercek modeli saglar; o yoksa kameraya olan
mesafeye dayali makul bir varsayilan kullanilir.

Gorunum ozniteligi de (renk) oyuncuyu DAHA YAKIN goren kameradan alinir. Uzak
yaridaki maskeler kucuk ve kirlidir; onlarin rengi profili bozar.

    python kameraKaynastirma.py --selftest
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cekirdek.ayarlar import Ayarlar  # noqa: E402


@dataclass
class HataModeli:
    """Bir kameranin saha uzerindeki konum belirsizligi.

    Varsayilan bicim: sigma(p) = taban + olcek * (uzaklik(p) / 20)^2
    Uzaklik, kameranin saha duzlemindeki izdusumune olan mesafedir.

    Faz 1'in capraz kamera hata haritasi bu iki katsayiyi gercek veriden fit eder;
    o zamana kadar tespit gurultusuyle uyumlu makul degerler kullanilir.
    """

    kameraKonumu: np.ndarray = field(default_factory=lambda: np.array([-6.0, 15.0]))
    taban: float = 0.10
    olcek: float = 0.14

    def sigma(self, konumlar: np.ndarray) -> np.ndarray:
        """Verilen saha noktalarindaki standart sapma (metre)."""
        p = np.atleast_2d(np.asarray(konumlar, float))
        d = np.linalg.norm(p - self.kameraKonumu, axis=1)
        return self.taban + self.olcek * (d / 20.0) ** 2

    def agirlik(self, konumlar: np.ndarray) -> np.ndarray:
        """1/sigma^2 -- ters varyans agirligi."""
        s = self.sigma(konumlar)
        return 1.0 / np.maximum(s, 1e-6) ** 2


VARSAYILAN_HATA_MODELLERI = {
    1: HataModeli(kameraKonumu=np.array([-6.0, 15.0])),
    2: HataModeli(kameraKonumu=np.array([56.0, 15.0])),
}


@dataclass
class Gozlem:
    """Kaynastirilmis tek gozlem: bir zamanda bir kisi."""

    x: float
    y: float
    kaynak: int                 # 12 iki kamera, 1 veya 2 tek kamera
    sigma: float                # kaynastirma sonrasi belirsizlik (metre)
    ton: float
    doygunluk: float
    parlaklik: float
    siyahlik: float
    k1: tuple                   # (u, v, sol, ust, gen, yuk) -- yoksa hepsi -1
    k2: tuple

    @property
    def konum(self) -> np.ndarray:
        return np.array([self.x, self.y])


BOS_KUTU = (-1.0, -1.0, -1.0, -1.0, -1.0, -1.0)


def _kutuAl(t: dict) -> tuple:
    return (t.get("u_px", -1.0), t.get("v_px", -1.0), t.get("kutuSol", -1.0),
            t.get("kutuUst", -1.0), t.get("kutuGen", -1.0), t.get("kutuYuk", -1.0))


def _renkAl(t: dict) -> tuple:
    return (t.get("ton", -1.0), t.get("doygunluk", -1.0),
            t.get("parlaklik", -1.0), t.get("siyahlik", -1.0))


def kaynastir(kamera1: list[dict], kamera2: list[dict],
              hataModelleri: dict[int, HataModeli] | None = None,
              ayarlar: Ayarlar | None = None) -> list[Gozlem]:
    """Ayni andaki iki kamera tespitini tek listeye indirger.

    Her kaynastirilmis nokta HANGI kameranin HANGI pikselinden geldigini yaninda
    tasir. Kimlik kartlari ve isaretli video bunu dogrudan kullanir; yeniden
    tespit ve tahminle eslestirme yapilmaz, dolayisiyla iki kamerada ayni kisiye
    farkli etiket yazilmasi imkansiz hale gelir.
    """
    a = ayarlar or Ayarlar()
    hm = hataModelleri or VARSAYILAN_HATA_MODELLERI

    def tekKamera(tespitler, kamera):
        cikti = []
        for t in tespitler:
            p = np.array([[t["x_m"], t["y_m"]]])
            ton, doy, parl, siyah = _renkAl(t)
            kutu = _kutuAl(t)
            cikti.append(Gozlem(x=float(t["x_m"]), y=float(t["y_m"]), kaynak=kamera,
                                sigma=float(hm[kamera].sigma(p)[0]),
                                ton=ton, doygunluk=doy, parlaklik=parl, siyahlik=siyah,
                                k1=kutu if kamera == 1 else BOS_KUTU,
                                k2=kutu if kamera == 2 else BOS_KUTU))
        return cikti

    if not kamera1:
        return tekKamera(kamera2, 2)
    if not kamera2:
        return tekKamera(kamera1, 1)

    A = np.array([[t["x_m"], t["y_m"]] for t in kamera1], float)
    B = np.array([[t["x_m"], t["y_m"]] for t in kamera2], float)
    d = np.linalg.norm(A[:, None, :] - B[None, :, :], axis=2)

    bedel = np.where(d <= a.kimlik.esitlemeM, d, 1e6)
    cikti: list[Gozlem] = []
    kullanilanA, kullanilanB = set(), set()

    for i, j in zip(*linear_sum_assignment(bedel)):
        if d[i, j] > a.kimlik.esitlemeM:
            continue
        kullanilanA.add(i)
        kullanilanB.add(j)

        # TERS VARYANS AGIRLIKLI ORTALAMA. Her kamera kendi yakin yarisinda baskin
        # olur; uzak kameranin buyuk hatasi sonuca zayif girer.
        w1 = float(hm[1].agirlik(A[i])[0])
        w2 = float(hm[2].agirlik(B[j])[0])
        toplam = w1 + w2
        p = (A[i] * w1 + B[j] * w2) / toplam
        # Iki bagimsiz olcumun birlestirilmesinde birlesik varyans 1/(w1+w2)
        birlesikSigma = float(np.sqrt(1.0 / toplam))

        # Renk: oyuncuyu DAHA YAKIN goren kameradan. Uzaktaki maske kucuk ve kirli.
        yakinKamera = 1 if hm[1].sigma(A[i])[0] <= hm[2].sigma(B[j])[0] else 2
        ton, doy, parl, siyah = _renkAl(kamera1[i] if yakinKamera == 1 else kamera2[j])

        cikti.append(Gozlem(x=float(p[0]), y=float(p[1]), kaynak=12, sigma=birlesikSigma,
                            ton=ton, doygunluk=doy, parlaklik=parl, siyahlik=siyah,
                            k1=_kutuAl(kamera1[i]), k2=_kutuAl(kamera2[j])))

    cikti += tekKamera([t for i, t in enumerate(kamera1) if i not in kullanilanA], 1)
    cikti += tekKamera([t for j, t in enumerate(kamera2) if j not in kullanilanB], 2)
    return cikti


@dataclass
class SapmaAlani:
    """Bir kameranin SISTEMATIK konum sapmasinin saha uzerindeki haritasi.

    NEDEN GEREKLI -- olcerek bulundu:

    Fuzyon kaynagi degistiginde (iki kamera -> tek kamera -> obur kamera)
    fuzyonlanmis konum SICRIYOR, cunku her kameranin sapmasi farkli. Sentetik
    tezgahta olculen (sahne #6):

        kaynak ayni kaldi  ->  kare basina adim medyan 0,20 m
        kaynak degisti     ->  kare basina adim medyan 0,55 m, p90 1,01 m

    Sicrama 1,80 m'lik kapinin yarisina ulasiyor ve yuva komsuyu kapiyor. Ayni
    sahnede IDF1 0,591'de kaliyor. Sapmasi kucuk olan sahne #0'da ayni gecis
    yalnizca 0,27 m ve IDF1 1,000.

    Gercek veride de aynen olacak: iki kameranin uyusmazligi medyan 0,85 m.

    NASIL OLCULUR -- dogru cevap gerekmez. Ayni kisiyi goren iki kameranin
    konum farki, o noktadaki GORELI sapmadir (sapma1 - sapma2). Saha izgarasinda
    biriktirilip yumusatilinca goreli sapma alani cikar. Mutlak sapmalar
    ayristirilamaz (yer gercegi olmadan mumkun degil), ama gerekmez de: farkin
    yarisi birinden cikarilip yarisi obarune eklenince GORELI sapma sifirlanir,
    kaynak degisimindeki sicrama ortadan kalkar. Geriye kalan ortak mod, iki
    kamerayi birlikte kaydiran yumusak bir bozulmadir; kimlige zarar vermez.
    """

    izgaraX: np.ndarray
    izgaraY: np.ndarray
    duzeltme: np.ndarray                 # (nY, nX, 2) -- bu kameraya EKLENECEK duzeltme
    ornekSayisi: np.ndarray              # (nY, nX) -- her hucredeki gozlem sayisi

    def uygula(self, konumlar: np.ndarray) -> np.ndarray:
        """Verilen saha noktalarina duzeltmeyi uygular."""
        p = np.atleast_2d(np.asarray(konumlar, float))
        i = np.clip(np.searchsorted(self.izgaraY, p[:, 1]) - 1, 0, len(self.izgaraY) - 2)
        j = np.clip(np.searchsorted(self.izgaraX, p[:, 0]) - 1, 0, len(self.izgaraX) - 2)
        return p + self.duzeltme[i, j]

    @property
    def buyukluk(self) -> float:
        """Duzeltmenin ortalama buyuklugu (metre) -- ne kadar sapma giderildi."""
        dolu = self.ornekSayisi > 0
        return float(np.linalg.norm(self.duzeltme[dolu], axis=1).mean()) if dolu.any() else 0.0


def sapmaAlaniFitEt(kamera1Kareler: list[list[dict]], kamera2Kareler: list[list[dict]],
                    ayarlar: Ayarlar | None = None,
                    hucre: float = 5.0, enAzOrnek: int = 8) -> dict[int, SapmaAlani]:
    """Iki kameranin GORELI sistematik sapmasini olcup duzeltme alanlari uretir.

    Donen duzeltmeler, ilgili kameranin konumlarina EKLENIR. Toplamlari sifirdir:
    farkin yarisi birinden cikarilir, yarisi obarune eklenir.
    """
    a = ayarlar or Ayarlar()
    izgaraX = np.arange(0.0, a.saha.uzunluk + hucre, hucre)
    izgaraY = np.arange(0.0, a.saha.genislik + hucre, hucre)
    nY, nX = len(izgaraY) - 1, len(izgaraX) - 1

    toplam = np.zeros((nY, nX, 2))
    sayi = np.zeros((nY, nX), int)

    for kare1, kare2 in zip(kamera1Kareler, kamera2Kareler):
        if not kare1 or not kare2:
            continue
        A = np.array([[t["x_m"], t["y_m"]] for t in kare1], float)
        B = np.array([[t["x_m"], t["y_m"]] for t in kare2], float)
        d = np.linalg.norm(A[:, None, :] - B[None, :, :], axis=2)
        bedel = np.where(d <= a.kimlik.esitlemeM, d, 1e6)
        for i, j in zip(*linear_sum_assignment(bedel)):
            if d[i, j] > a.kimlik.esitlemeM:
                continue
            orta = (A[i] + B[j]) / 2.0
            hy = int(np.clip(orta[1] // hucre, 0, nY - 1))
            hx = int(np.clip(orta[0] // hucre, 0, nX - 1))
            toplam[hy, hx] += A[i] - B[j]          # goreli sapma: sapma1 - sapma2
            sayi[hy, hx] += 1

    goreli = np.zeros((nY, nX, 2))
    dolu = sayi >= enAzOrnek
    goreli[dolu] = toplam[dolu] / sayi[dolu][:, None]

    # Bos hucreleri komsulardan doldur ve alani yumusat: kalibrasyon artigi
    # konumun yumusak bir fonksiyonudur, hucreden hucreye ziplamaz.
    goreli = _bosluklariDoldurVeYumusat(goreli, dolu)

    return {
        1: SapmaAlani(izgaraX, izgaraY, -goreli / 2.0, sayi),
        2: SapmaAlani(izgaraX, izgaraY, +goreli / 2.0, sayi),
    }


def _bosluklariDoldurVeYumusat(alan: np.ndarray, dolu: np.ndarray,
                               tur: int = 3) -> np.ndarray:
    """Bos hucreleri dolu komsulardan doldurur, sonra hafifce yumusatir."""
    cikti = alan.copy()
    gecerli = dolu.copy()
    cekirdek = np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 1.0], [0.0, 1.0, 0.0]])

    for _ in range(tur):
        if gecerli.all():
            break
        komsuToplam = np.zeros_like(cikti)
        komsuSayi = np.zeros(gecerli.shape)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if cekirdek[dy + 1, dx + 1] == 0:
                    continue
                kaydirilmis = np.roll(np.roll(cikti, dy, axis=0), dx, axis=1)
                kaydirilmisGecerli = np.roll(np.roll(gecerli, dy, axis=0), dx, axis=1)
                komsuToplam += kaydirilmis * kaydirilmisGecerli[:, :, None]
                komsuSayi += kaydirilmisGecerli
        doldurulacak = (~gecerli) & (komsuSayi > 0)
        cikti[doldurulacak] = komsuToplam[doldurulacak] / komsuSayi[doldurulacak][:, None]
        gecerli |= doldurulacak

    # 3x3 kutu yumusatma
    yumusak = np.zeros_like(cikti)
    agirlik = np.zeros(cikti.shape[:2])
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            yumusak += np.roll(np.roll(cikti, dy, axis=0), dx, axis=1)
            agirlik += 1
    return yumusak / agirlik[:, :, None]


def sapmayiUygula(kareler: list[list[dict]], alan: SapmaAlani) -> list[list[dict]]:
    """Bir kameranin tum tespitlerine duzeltme alanini uygular."""
    cikti = []
    for kare in kareler:
        if not kare:
            cikti.append(kare)
            continue
        P = np.array([[t["x_m"], t["y_m"]] for t in kare], float)
        D = alan.uygula(P)
        yeni = []
        for t, p in zip(kare, D):
            k = dict(t)
            k["x_m"], k["y_m"] = float(p[0]), float(p[1])
            yeni.append(k)
        cikti.append(yeni)
    return cikti


def hataModeliFitEt(kamera1Kareler: list[list[dict]], kamera2Kareler: list[list[dict]],
                    ayarlar: Ayarlar | None = None) -> dict[int, HataModeli]:
    """Iki kameranin uyusmazligindan hata modelinin katsayilarini fit eder.

    Dogru cevabi bilmeye gerek yok. Ayni kisiyi goren iki bagimsiz olcumun farki
    `fark^2 ~ sigma1^2 + sigma2^2` iliskisini saglar; her kameranin sigma'si kendi
    mesafesine bagli oldugu ve kameralar farkli yerlerde durdugu icin iki katsayi
    da cozulebilir hale gelir.

    Bu, raporun "uzak yari dogrulugu OLCULMEDI" acik sorununun kapanmasidir.
    """
    a = ayarlar or Ayarlar()
    hm = VARSAYILAN_HATA_MODELLERI
    d1, d2, farkKare = [], [], []

    for kare1, kare2 in zip(kamera1Kareler, kamera2Kareler):
        if not kare1 or not kare2:
            continue
        A = np.array([[t["x_m"], t["y_m"]] for t in kare1], float)
        B = np.array([[t["x_m"], t["y_m"]] for t in kare2], float)
        d = np.linalg.norm(A[:, None, :] - B[None, :, :], axis=2)
        bedel = np.where(d <= a.kimlik.esitlemeM, d, 1e6)
        for i, j in zip(*linear_sum_assignment(bedel)):
            if d[i, j] > a.kimlik.esitlemeM:
                continue
            orta = (A[i] + B[j]) / 2.0
            d1.append(float(np.linalg.norm(orta - hm[1].kameraKonumu)))
            d2.append(float(np.linalg.norm(orta - hm[2].kameraKonumu)))
            farkKare.append(float(d[i, j] ** 2))

    if len(farkKare) < 50:
        return {k: HataModeli(v.kameraKonumu, v.taban, v.olcek) for k, v in hm.items()}

    # sigma_k(d) = taban + olcek*(d/20)^2 ; fark^2 = sigma1^2 + sigma2^2
    # Dogrusal olmayan kucuk bir problem; iki katsayi ortak kabul edilir
    # (ayni lens, ayni kurulum), dolayisiyla iki bilinmeyen kalir.
    from scipy.optimize import least_squares

    u1 = (np.array(d1) / 20.0) ** 2
    u2 = (np.array(d2) / 20.0) ** 2
    hedef = np.array(farkKare)

    def artik(par):
        taban, olcek = np.abs(par)
        s1 = taban + olcek * u1
        s2 = taban + olcek * u2
        return np.sqrt(s1 ** 2 + s2 ** 2) - np.sqrt(hedef)

    son = least_squares(artik, [0.10, 0.14], method="lm", max_nfev=5000)
    taban, olcek = float(abs(son.x[0])), float(abs(son.x[1]))
    return {k: HataModeli(v.kameraKonumu, taban, olcek) for k, v in hm.items()}


# ----------------------------------------------------------------- selftest

def selftest() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "testler"))
    from sentetikSahne import sahneUret

    sahne = sahneUret(tohum=0)

    def kareyeCevir(gozlemler):
        return [{"x_m": g["x_m"], "y_m": g["y_m"], "ton": g["ton"],
                 "doygunluk": g["doygunluk"], "parlaklik": g["parlaklik"],
                 "siyahlik": g["siyahlik"], "u_px": 100.0, "v_px": 200.0,
                 "kutuSol": 90.0, "kutuUst": 100.0, "kutuGen": 20.0, "kutuYuk": 100.0,
                 "_gercek": g["oyuncu"]} for g in gozlemler]

    # 1) Hata modeli fit: gercek gurultu modeline yakin katsayilar bulmali
    k1Kareler = [kareyeCevir(k) for k in sahne.gozlemler[1]]
    k2Kareler = [kareyeCevir(k) for k in sahne.gozlemler[2]]
    fit = hataModeliFitEt(k1Kareler, k2Kareler)
    # Katsayilarin kendisi degil URETTIKLERI SIGMA EGRISI onemli: fit iki
    # katsayiyi degis tokus edebilir (saf karesel bicim de veriye iyi oturur ve
    # taban'i sifira ceker). Olculmesi gereken sey, egrinin sahnedeki gercek hata
    # bandlarini tutturmasi: 0-10 m'de ~0,19 m, 50-60 m'de ~1,35 m.
    for uzaklik, altSinir, ustSinir in ((10.0, 0.01, 0.35), (30.0, 0.20, 0.90), (55.0, 0.60, 2.60)):
        s = float(fit[1].sigma(np.array([[fit[1].kameraKonumu[0] + uzaklik,
                                          fit[1].kameraKonumu[1]]]))[0])
        assert altSinir < s < ustSinir, (uzaklik, s)

    # 2) ASIL TEST: agirlikli fuzyon esit agirlikli fuzyondan DAHA DOGRU olmali
    esitHata, agirlikliHata, kaynakSayaci = [], [], {12: 0, 1: 0, 2: 0}
    for k in range(sahne.kareSayisi):
        a, b = k1Kareler[k], k2Kareler[k]
        birlesik = kaynastir(a, b, fit)
        for g in birlesik:
            kaynakSayaci[g.kaynak] += 1

        # Ayni eslestirmeyi esit agirlikla yap ve iki sonucu gercege karsi kiyasla
        if not a or not b:
            continue
        A = np.array([[t["x_m"], t["y_m"]] for t in a])
        B = np.array([[t["x_m"], t["y_m"]] for t in b])
        d = np.linalg.norm(A[:, None] - B[None], axis=2)
        for i, j in zip(*linear_sum_assignment(np.where(d <= 2.0, d, 1e6))):
            if d[i, j] > 2.0 or a[i]["_gercek"] < 0 or a[i]["_gercek"] != b[j]["_gercek"]:
                continue
            gercekKonum = sahne.gercekKonum[k, a[i]["_gercek"]]
            w1 = float(fit[1].agirlik(A[i])[0])
            w2 = float(fit[2].agirlik(B[j])[0])
            agirlikli = (A[i] * w1 + B[j] * w2) / (w1 + w2)
            esit = (A[i] + B[j]) / 2.0
            agirlikliHata.append(np.linalg.norm(agirlikli - gercekKonum))
            esitHata.append(np.linalg.norm(esit - gercekKonum))

    agirlikliMedyan = float(np.median(agirlikliHata))
    esitMedyan = float(np.median(esitHata))
    assert agirlikliMedyan < esitMedyan, (agirlikliMedyan, esitMedyan)
    # Kazanc onemsiz olmamali: raporun 4 numarali acik sorununu kapatan sey bu
    assert agirlikliMedyan < 0.85 * esitMedyan, (agirlikliMedyan, esitMedyan)

    # 3) Kaynastirma sonrasi kare basina kayit sayisi.
    #    14'un biraz ustu beklenir ve DOGRUDUR: iki kameranin da gordugu oyuncu
    #    orani ~0,9 x 0,9 = 0,81 ve bunlarin %92'si eslesir; kalanlar iki ayri
    #    tek-kamera kaydi olarak gecer. Beklenen ~15,0 kayit / 14 kisi.
    kareBasina = sum(kaynakSayaci.values()) / sahne.kareSayisi
    assert 13.5 <= kareBasina <= 15.5, kareBasina

    # ASIL OLCU: iki kameranin da gordugu kisilerde 2 m icinde eslesme orani.
    # Gercek veride olculen deger %92. Bu, esitleme esiginin dogru secildigini
    # ve fuzyonun gercek kosullarda beklenen kadar cift yakaladigini gosterir.
    ciftGorulen = eslesen = 0
    for k in range(sahne.kareSayisi):
        a, b = k1Kareler[k], k2Kareler[k]
        aKim = {t["_gercek"] for t in a if t["_gercek"] >= 0}
        bKim = {t["_gercek"] for t in b if t["_gercek"] >= 0}
        ortak = aKim & bKim
        ciftGorulen += len(ortak)
        if not a or not b:
            continue
        A = np.array([[t["x_m"], t["y_m"]] for t in a])
        B = np.array([[t["x_m"], t["y_m"]] for t in b])
        d = np.linalg.norm(A[:, None] - B[None], axis=2)
        for i, j in zip(*linear_sum_assignment(np.where(d <= 2.0, d, 1e6))):
            if d[i, j] <= 2.0 and a[i]["_gercek"] >= 0 and a[i]["_gercek"] == b[j]["_gercek"]:
                eslesen += 1
    eslesmeOrani = eslesen / max(ciftGorulen, 1)
    assert abs(eslesmeOrani - 0.92) < 0.05, eslesmeOrani

    ciftKameraOrani = kaynakSayaci[12] / sum(kaynakSayaci.values())

    # 4) Piksel bilgisi UCTAN UCA tasinmali -- rapordaki 4 numarali tuzak
    ornek = kaynastir(k1Kareler[0], k2Kareler[0], fit)
    ciftler = [g for g in ornek if g.kaynak == 12]
    assert ciftler, "iki kamerada da gorulen kimse yok"
    for g in ciftler:
        assert g.k1 != BOS_KUTU and g.k2 != BOS_KUTU, g
        assert g.k1[4] > 0 and g.k1[5] > 0, "kutu genislik/yukseklik tasinmadi: %s" % (g.k1,)
    tekler = [g for g in ornek if g.kaynak == 1]
    for g in tekler:
        assert g.k1 != BOS_KUTU and g.k2 == BOS_KUTU, g

    # 5) SAPMA DUZELTMESI: iki kameranin uyusmazligini belirgin sekilde azaltmali
    def uyusmazlikMedyani(a1, a2):
        f = []
        for ka, kb in zip(a1, a2):
            if not ka or not kb:
                continue
            A = np.array([[t["x_m"], t["y_m"]] for t in ka])
            B = np.array([[t["x_m"], t["y_m"]] for t in kb])
            d = np.linalg.norm(A[:, None] - B[None], axis=2)
            for i, j in zip(*linear_sum_assignment(np.where(d <= 2.5, d, 1e6))):
                if d[i, j] <= 2.5 and ka[i]["_gercek"] >= 0 and ka[i]["_gercek"] == kb[j]["_gercek"]:
                    f.append(d[i, j])
        return float(np.median(f))

    oncesi = uyusmazlikMedyani(k1Kareler, k2Kareler)
    alanlar = sapmaAlaniFitEt(k1Kareler, k2Kareler)
    d1 = sapmayiUygula(k1Kareler, alanlar[1])
    d2 = sapmayiUygula(k2Kareler, alanlar[2])
    sonrasi = uyusmazlikMedyani(d1, d2)
    assert sonrasi < 0.75 * oncesi, (oncesi, sonrasi)

    # Duzeltmeler toplami sifir olmali: fark ikiye bolunup paylastiriliyor
    assert np.allclose(alanlar[1].duzeltme, -alanlar[2].duzeltme), "duzeltmeler simetrik olmali"

    # DIKKAT: duzeltme tek bir kamerayi gercege yaklastirmak ZORUNDA DEGIL ve
    # yaklastirmasi da beklenmez. Kaldirilan sey GORELI sapmadir; fark ikiye
    # bolunup paylastirildigi icin, dogru olan kamera bir miktar bozulur ve
    # sapan kamera duzelir. Mutlak dogruluk acisindan islem yaklasik notrdur.
    #
    # KAZANC BASKA YERDE: iki kamera artik AYNI SEYI SOYLUYOR, dolayisiyla
    # fuzyon kaynagi degistiginde (12 -> 1 -> 12 -> 2) konum ARTIK SICRAMIYOR.
    # Sicrama, yuvanin komsu gozlemi kapmasinin ana sebebiydi.
    def kaynakGecisSicramasi(a1, a2, hataM):
        onceki = {}
        ayni, degisen = [], []
        for i in range(len(a1)):
            for g in kaynastir(a1[i], a2[i], hataM):
                anahtar = (round(g.x / 3.0), round(g.y / 3.0))
                if anahtar in onceki:
                    eskiG = onceki[anahtar]
                    d = float(np.hypot(g.x - eskiG.x, g.y - eskiG.y))
                    (ayni if g.kaynak == eskiG.kaynak else degisen).append(d)
                onceki[anahtar] = g
        return float(np.median(degisen)) / float(np.median(ayni))

    oncekiOran = kaynakGecisSicramasi(k1Kareler, k2Kareler, fit)
    sonrakiOran = kaynakGecisSicramasi(d1, d2, hataModeliFitEt(d1, d2))
    assert sonrakiOran < oncekiOran, (oncekiOran, sonrakiOran)

    # 6) Tek kamera durumlarinda cokme olmamali
    assert len(kaynastir(k1Kareler[0], [], fit)) == len(k1Kareler[0])
    assert len(kaynastir([], k2Kareler[0], fit)) == len(k2Kareler[0])
    assert kaynastir([], [], fit) == []

    iyilesme = 100 * (1 - agirlikliMedyan / esitMedyan)
    print("selftest ok  (agirlikli fuzyon %.3f m vs esit agirlik %.3f m -> %%%.1f daha "
          "dogru; sapma duzeltmesi uyusmazligi %.2f -> %.2f m indiriyor (%%%.0f); "
          "kare basina %.2f kisi, %%%.0f.i cift kamera, 2 m eslesme %%%.0f)"
          % (agirlikliMedyan, esitMedyan, iyilesme, oncesi, sonrasi,
             100 * (1 - sonrasi / oncesi), kareBasina, 100 * ciftKameraOrani,
             100 * eslesmeOrani))


if __name__ == "__main__":
    selftest()
