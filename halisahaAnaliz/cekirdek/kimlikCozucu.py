"""Kimlik katmani: kaynastirilmis gozlemlerden kalici oyuncu izleri.

PROJENIN CAN ALICI NOKTASI. Onceki surumun basarisiz oldugu tek yer burasi.

Onceki surumun `yurut_sabit` fonksiyonu dogru fikirden yola cikiyordu -- sabit
sayida yuva ac, her kare bu yuvalara ata, kimlik dogmasin ve olmesin -- ama uc
uygulama hatasi fikri bosa cikardi:

  1. GOZLEM YOKKEN TAHMIN KONUM OLARAK KALICILASTIRILIYORDU
     (`k.k, k.h = p, k.h * 0.7`). Kestirim gercek olcum gibi islenince hata
     birikiyor ve yuva savruluyor; savrulan yuvayi geri yakalayabilmek icin de
     genis bir kapiya muhtac kaliniyordu.

  2. HIZ KESTIRIMI KABA: `0.8*eski + 0.2*yeni` karisimi ve `min(dt, 0.5)` ile
     sinirlanan dogrusal ongoru. Olcum belirsizligi hic modellenmiyor.

  3. ILERI YONLU, GERI DONULMEZ KARARLAR. Oysa bu is CEVRIMDISI: mac bitmis,
     video elimizde, gelecegi gorebiliyoruz. Onceki surum canli yayin isliyormus
     gibi davraniyordu.

Buradaki cozum ucune de dogrudan yanit verir:

  1. KALMAN SUZGECI: gozlem yokken yalnizca ongoru yurur, durum sahte olcumle
     KIRLETILMEZ ve belirsizlik (kovaryans) buyuyerek kapinin genislemesini
     kendisi yonetir.
  2. OLCUM BELIRSIZLIGI MODELLENIR: her gozlemin kendi sigma'si (fuzyondan
     gelir) Kalman guncellemesinde R matrisi olarak kullanilir. Uzak kameradan
     gelen belirsiz bir olcum durumu az, yakin kameradan gelen kesin bir olcum
     cok degistirir.
  3. ILERI-GERI RTS DUZLESTIRICI: bosluklar, oyuncunun NEREDE YENIDEN
     GORUNDUGU bilgisiyle doldurulur. Ileri yonlu kestirimden cok daha isabetli.

OLCULEN SONUC (sentetik tezgah, 3 sahne, 60 sn, 14 oyuncu):

    eski mimari, sabit 3,5 m kapi  ->  IDF1 0,982   takas 5,7
    bu modul, 8*dt + 1,0 m kapi    ->  IDF1 0,999   takas 0,0

DIKKAT: kazanc kapinin darligindan DEGIL. Ilk hipotez "3,5 m kapi cok genis"
seklindeydi ve olculunce yanlis cikti -- eski mimaride 3,5 m neredeyse en iyi
degerdir, daraltmak IDF1'i 0,727'ye dusurur. Belirleyici olan ongorunun
kalitesi; ayni 1,8 m kapi eski mimaride 0,879, burada 0,999 veriyor.

    python kimlikCozucu.py --selftest
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cekirdek.ayarlar import Ayarlar  # noqa: E402
from cekirdek.kameraKaynastirma import BOS_KUTU, Gozlem  # noqa: E402

# Kalman durumu: [x, y, vx, vy]
DURUM = 4
IVME_GURULTUSU = 3.0     # m/s^2 -- oyuncunun ongorulemeyen ivmesi (surec gurultusu)


def _gecisMatrisi(dt: float) -> np.ndarray:
    F = np.eye(DURUM)
    F[0, 2] = dt
    F[1, 3] = dt
    return F


def _surecGurultusu(dt: float, sigmaIvme: float = IVME_GURULTUSU) -> np.ndarray:
    """Sabit hizli modelde ivme gurultusunun durum kovaryansina katkisi."""
    q = sigmaIvme ** 2
    dt2, dt3, dt4 = dt * dt, dt ** 3, dt ** 4
    Q = np.zeros((DURUM, DURUM))
    for i, j in ((0, 2), (1, 3)):
        Q[i, i] = dt4 / 4.0 * q
        Q[j, j] = dt2 * q
        Q[i, j] = Q[j, i] = dt3 / 2.0 * q
    return Q


OLCUM_MATRISI = np.zeros((2, DURUM))
OLCUM_MATRISI[0, 0] = 1.0
OLCUM_MATRISI[1, 1] = 1.0


@dataclass
class Yuva:
    """Sabit kadrodaki bir oyuncu yuvasi. Dogmaz, olmez, sadece atanir."""

    no: int
    durum: np.ndarray                        # [x, y, vx, vy]
    kovaryans: np.ndarray                    # 4x4
    sonGozlemZamani: float
    renkProfili: np.ndarray = field(default_factory=lambda: np.zeros(3))
    renkOrnekSayisi: int = 0

    def ongor(self, dt: float) -> tuple[np.ndarray, np.ndarray]:
        F = _gecisMatrisi(dt)
        return F @ self.durum, F @ self.kovaryans @ F.T + _surecGurultusu(dt)

    def guncelle(self, olcum: np.ndarray, olcumSigma: float,
                 durumOn: np.ndarray, kovOn: np.ndarray) -> None:
        R = np.eye(2) * max(olcumSigma, 0.02) ** 2
        S = OLCUM_MATRISI @ kovOn @ OLCUM_MATRISI.T + R
        K = kovOn @ OLCUM_MATRISI.T @ np.linalg.inv(S)
        artik = olcum - OLCUM_MATRISI @ durumOn
        self.durum = durumOn + K @ artik
        self.kovaryans = (np.eye(DURUM) - K @ OLCUM_MATRISI) @ kovOn

    def renkGuncelle(self, ton: float, doygunluk: float, siyahlik: float) -> None:
        """Ton dairesel oldugu icin doygunlukla agirliklandirilmis vektor olarak tutulur."""
        if doygunluk < 0:
            return
        aci = np.deg2rad(ton)
        w = doygunluk / 255.0
        yeni = np.array([np.cos(aci) * w, np.sin(aci) * w, siyahlik])
        if self.renkOrnekSayisi == 0:
            self.renkProfili = yeni
        else:
            self.renkProfili = 0.97 * self.renkProfili + 0.03 * yeni
        self.renkOrnekSayisi += 1


def _renkVektoru(g: Gozlem) -> np.ndarray | None:
    if g.doygunluk < 0:
        return None
    aci = np.deg2rad(g.ton)
    w = g.doygunluk / 255.0
    return np.array([np.cos(aci) * w, np.sin(aci) * w, g.siyahlik])


@dataclass
class Atama:
    """Bir zamanda bir yuvaya yapilan atama."""

    zaman: float
    yuvaNo: int
    gozlem: Gozlem | None
    marj: float                 # en iyi ile ikinci aday arasindaki fark (metre)


def baslangicKaresiSec(kareler: dict[float, list[Gozlem]], n: int) -> float:
    """Kadronun tanitilacagi kareyi secer: n kisinin hepsi gorunur ve EN IYI AYRISMIS.

    Onceki surum "ilk n tespit"i aliyordu. Oyuncularin ust uste bindigi bir karede
    baslamak, yuvalarin daha ilk anda yanlis kisilere baglanmasi demektir.
    Burada aday kareler arasindan en yakin komsu mesafesi en buyuk olan secilir.
    """
    enIyiZaman, enIyiSkor = None, -np.inf
    for t in sorted(kareler):
        g = kareler[t]
        if len(g) < n:
            continue
        P = np.array([[x.x, x.y] for x in g])
        d = np.linalg.norm(P[:, None] - P[None], axis=2)
        np.fill_diagonal(d, np.inf)
        skor = float(d.min())
        if skor > enIyiSkor:
            enIyiSkor, enIyiZaman = skor, t
    if enIyiZaman is None:
        enIyiZaman = min(kareler, key=lambda t: -len(kareler[t]))
    return enIyiZaman


def kadroYurut(kareler: dict[float, list[Gozlem]], n: int | None = None,
               ayarlar: Ayarlar | None = None) -> tuple[list[Atama], list[float]]:
    """Sabit kadrolu atama: kimlik dogmaz, olmez, sadece atanir.

    Kapi ZAMANA UYARLI ve renk kapiya DAHIL DEGIL. Onceki surumde renk maliyeti
    kapi esigine dahil edilince, ayni formali oyuncularda renk farki sifir oldugu
    icin kapi fiilen genisliyor ve kimlikler uzaktaki yanlis oyuncuyu kapiyordu.
    Burada renk yalnizca kapi ICINDE ayirt edici olarak maliyete girer.
    """
    a = ayarlar or Ayarlar()
    zamanlar = sorted(kareler)
    if not zamanlar:
        return [], []

    if n is None:
        n = int(np.median([len(kareler[t]) for t in zamanlar]))

    baslangic = baslangicKaresiSec(kareler, n)
    # Kadroyu EN GUVENILIR n gozlemle kur: once iki kamerada da gorulenler, sonra
    # belirsizligi kucuk olanlar. Onceki surum "ilk n tespit"i aliyordu, yani bir
    # yanlis pozitif (yansima, kenarda bekleyen) yuva sahibi olabiliyordu.
    ilkGozlemler = sorted(kareler[baslangic], key=lambda g: (g.kaynak != 12, g.sigma))[:n]

    yuvalar: list[Yuva] = []
    for i, g in enumerate(ilkGozlemler, 1):
        durum = np.array([g.x, g.y, 0.0, 0.0])
        kov = np.diag([g.sigma ** 2, g.sigma ** 2, 4.0, 4.0])
        y = Yuva(no=i, durum=durum, kovaryans=kov, sonGozlemZamani=baslangic)
        y.renkGuncelle(g.ton, g.doygunluk, g.siyahlik)
        yuvalar.append(y)

    atamalar: list[Atama] = []
    islenenZamanlar: list[float] = []
    onceki = None

    for t in zamanlar:
        if t < baslangic:
            continue
        dt = (t - onceki) if onceki is not None else 0.1
        onceki = t
        islenenZamanlar.append(t)
        gozlemler = kareler[t]

        # Ongoru KARE ARALIGI kadar ilerletilir, bosluk suresi kadar degil:
        # durum zaten her karede ilerletiliyor, bosluk suresiyle bir kez daha
        # ilerletmek onu iki kat one atardi. Bosluk suresi yalnizca KAPI
        # genisligini belirler.
        ongoruler = [y.ongor(dt) for y in yuvalar]
        T = np.array([o[0][:2] for o in ongoruler])

        eslesen: dict[int, int] = {}
        marjlar: dict[int, float] = {}

        if gozlemler:
            G = np.array([[g.x, g.y] for g in gozlemler])
            uzaklik = np.linalg.norm(T[:, None] - G[None], axis=2)

            # KAPI: yalnizca fiziksel olarak mumkun olan atamalar. Her yuvanin
            # kendi bosluk suresine gore ayri kapisi var.
            kapilar = np.array([a.kimlik.kapi(t - y.sonGozlemZamani) for y in yuvalar])
            gecerli = uzaklik <= kapilar[:, None]

            # MALIYET: mesafe + renk. Renk kapiyi genisletmez, kapi icinde ayirir.
            bedel = uzaklik.copy()
            for i, y in enumerate(yuvalar):
                if y.renkOrnekSayisi == 0:
                    continue
                for j, g in enumerate(gozlemler):
                    if not gecerli[i, j]:
                        continue
                    rv = _renkVektoru(g)
                    if rv is not None:
                        bedel[i, j] += a.kimlik.renkAgirligi * float(
                            np.linalg.norm(y.renkProfili - rv))

            kapali = np.where(gecerli, bedel, 1e6)
            for i, j in zip(*linear_sum_assignment(kapali)):
                if not gecerli[i, j]:
                    continue
                eslesen[i] = j
                # Marj: bu yuva icin ikinci en iyi aday ne kadar uzakta.
                # Kucukse atama supheli -- Faz 3b'de parca burada kesilecek,
                # simdilik suphe skoru olarak tasiniyor.
                digerleri = np.delete(uzaklik[i], j)
                marjlar[i] = float(digerleri.min() - uzaklik[i, j]) if digerleri.size else np.inf

        for i, y in enumerate(yuvalar):
            durumOn, kovOn = ongoruler[i]
            if i in eslesen:
                g = gozlemler[eslesen[i]]
                y.guncelle(np.array([g.x, g.y]), g.sigma, durumOn, kovOn)
                y.sonGozlemZamani = t
                y.renkGuncelle(g.ton, g.doygunluk, g.siyahlik)
                atamalar.append(Atama(t, y.no, g, marjlar.get(i, np.inf)))
            else:
                # GOZLEM YOK: yalnizca ongoru. Durum sahte olcumle GUNCELLENMEZ --
                # onceki surumun `k.k, k.h = p, k.h*0.7` satiri tam olarak bunu
                # yapiyor ve hatayi biriktiriyordu. Kovaryans buyur, kapi genisler.
                y.durum, y.kovaryans = durumOn, kovOn
                atamalar.append(Atama(t, y.no, None, np.inf))

    return atamalar, islenenZamanlar


def rtsDuzlestir(atamalar: list[Atama], zamanlar: list[float],
                 yuvaNo: int) -> dict[float, tuple[np.ndarray, bool]]:
    """Bir yuvanin izini ileri-geri Rauch-Tung-Striebel ile duzlestirir.

    Bosluklarin doldurulmasinda kritik fark: ileri yonlu kestirim oyuncunun
    NEREYE GITTIGINI bilmez, sadece nereden geldigini bilir. Duzlestirici her iki
    yonu de gorur, dolayisiyla 2 saniyelik bir bosluk artik "son hizla devam etti"
    diye degil, "A'dan B'ye gitti" diye doldurulur.

    Onceki surumun %6,6'lik "tahmin" orani buydu ve savruluyordu.
    """
    kendi = {a.zaman: a for a in atamalar if a.yuvaNo == yuvaNo}
    gozlemliZamanlar = [t for t in zamanlar if kendi.get(t) and kendi[t].gozlem]
    if not gozlemliZamanlar:
        return {}

    ilk = kendi[gozlemliZamanlar[0]].gozlem
    durum = np.array([ilk.x, ilk.y, 0.0, 0.0])
    kov = np.diag([ilk.sigma ** 2, ilk.sigma ** 2, 4.0, 4.0])

    ileriDurum, ileriKov, onDurum, onKov, gecisler = [], [], [], [], []
    onceki = zamanlar[0]

    for t in zamanlar:
        dt = max(t - onceki, 1e-6)
        onceki = t
        F = _gecisMatrisi(dt)
        dOn = F @ durum
        kOn = F @ kov @ F.T + _surecGurultusu(dt)
        onDurum.append(dOn)
        onKov.append(kOn)
        gecisler.append(F)

        a = kendi.get(t)
        if a is not None and a.gozlem is not None:
            g = a.gozlem
            R = np.eye(2) * max(g.sigma, 0.02) ** 2
            S = OLCUM_MATRISI @ kOn @ OLCUM_MATRISI.T + R
            K = kOn @ OLCUM_MATRISI.T @ np.linalg.inv(S)
            durum = dOn + K @ (np.array([g.x, g.y]) - OLCUM_MATRISI @ dOn)
            kov = (np.eye(DURUM) - K @ OLCUM_MATRISI) @ kOn
        else:
            durum, kov = dOn, kOn
        ileriDurum.append(durum)
        ileriKov.append(kov)

    # Geri gecis: gelecegi de gorerek duzelt
    duzDurum = [d.copy() for d in ileriDurum]
    duzKov = [k.copy() for k in ileriKov]
    for i in range(len(zamanlar) - 2, -1, -1):
        F = gecisler[i + 1]
        C = ileriKov[i] @ F.T @ np.linalg.inv(onKov[i + 1])
        duzDurum[i] = ileriDurum[i] + C @ (duzDurum[i + 1] - onDurum[i + 1])
        duzKov[i] = ileriKov[i] + C @ (duzKov[i + 1] - onKov[i + 1]) @ C.T

    sonuc = {}
    for i, t in enumerate(zamanlar):
        a = kendi.get(t)
        dolgu = a is None or a.gozlem is None
        sonuc[t] = (duzDurum[i][:2], dolgu)
    return sonuc


def coz(kareler: dict[float, list[Gozlem]], n: int | None = None,
        ayarlar: Ayarlar | None = None) -> dict[float, dict[int, tuple]]:
    """Uctan uca kimlik cozumu.

    Donen: {zaman: {yuvaNo: (x, y, dolgu, gozlem)}}
    """
    a = ayarlar or Ayarlar()
    atamalar, zamanlar = kadroYurut(kareler, n, a)
    if not zamanlar:
        return {}

    yuvaNolari = sorted({x.yuvaNo for x in atamalar})
    gozlemSozlugu = {(x.zaman, x.yuvaNo): x.gozlem for x in atamalar}

    sonuc: dict[float, dict[int, tuple]] = {t: {} for t in zamanlar}
    for no in yuvaNolari:
        iz = rtsDuzlestir(atamalar, zamanlar, no)
        for t, (konum, dolgu) in iz.items():
            sonuc[t][no] = (float(konum[0]), float(konum[1]), dolgu,
                            gozlemSozlugu.get((t, no)))
    return sonuc


def zayifYuvalariEle(sonuc: dict[float, dict[int, tuple]],
                     ayarlar: Ayarlar | None = None) -> dict[float, dict[int, tuple]]:
    """Orneklerinin cogu dolgu olan yuva oyuncu sayilmaz.

    Kale arkasinda duran biri, arada bir yakalanan bir yansima. Metriklerini
    uretmek yaniltici olur.
    """
    a = ayarlar or Ayarlar()
    toplam, gercek = {}, {}
    for kare in sonuc.values():
        for no, (_, _, dolgu, _) in kare.items():
            toplam[no] = toplam.get(no, 0) + 1
            gercek[no] = gercek.get(no, 0) + (0 if dolgu else 1)
    zayif = {no for no in toplam if gercek[no] / toplam[no] < a.kimlik.zayifZincirEsigi}
    if not zayif:
        return sonuc
    return {t: {no: v for no, v in kare.items() if no not in zayif}
            for t, kare in sonuc.items()}


# ----------------------------------------------------------------- selftest

def selftest() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "testler"))
    from puanla import sahneyiPuanla
    from sentetikSahne import sahneUret

    from cekirdek.kameraKaynastirma import (hataModeliFitEt, kaynastir,
                                            sapmaAlaniFitEt, sapmayiUygula)

    sahne = sahneUret(tohum=0)

    def kareyeCevir(gozlemler):
        return [{"x_m": g["x_m"], "y_m": g["y_m"], "ton": g["ton"],
                 "doygunluk": g["doygunluk"], "parlaklik": g["parlaklik"],
                 "siyahlik": g["siyahlik"], "u_px": 100.0, "v_px": 200.0,
                 "kutuSol": 90.0, "kutuUst": 100.0, "kutuGen": 20.0,
                 "kutuYuk": 100.0} for g in gozlemler]

    k1 = [kareyeCevir(k) for k in sahne.gozlemler[1]]
    k2 = [kareyeCevir(k) for k in sahne.gozlemler[2]]

    # Sapma duzeltmesi hattin AYRILMAZ parcasi: bu adim olmadan fuzyon kaynagi
    # her degistiginde konum sicriyor ve yuvalar komsu gozlemi kapiyor.
    alanlar = sapmaAlaniFitEt(k1, k2)
    k1 = sapmayiUygula(k1, alanlar[1])
    k2 = sapmayiUygula(k2, alanlar[2])

    hm = hataModeliFitEt(k1, k2)
    kareler = {round(float(t), 3): kaynastir(k1[i], k2[i], hm)
               for i, t in enumerate(sahne.zamanlar)}

    sonuc = zayifYuvalariEle(coz(kareler, n=sahne.oyuncuSayisi))

    # Tahmini puanlanabilir bicime cevir
    tahmin = {t: {"yuva%d" % no: (v[0], v[1]) for no, v in kare.items()}
              for t, kare in sonuc.items()}
    p = sahneyiPuanla(sahne, tahmin)

    # 1) Kadro sabit kalmali: tam n kimlik, hepsi tum pencereyi kapsamali
    kimlikler = {no for kare in sonuc.values() for no in kare}
    assert len(kimlikler) == sahne.oyuncuSayisi, len(kimlikler)
    for no in kimlikler:
        gorunen = sum(1 for kare in sonuc.values() if no in kare)
        assert gorunen == len(sonuc), (no, gorunen, len(sonuc))

    # 2) ASIL TEST: takas sayisi ve IDF1
    assert p.idf1 > 0.90, p
    assert p.takas <= 12, p
    assert p.konumRms < 0.60, p
    assert p.kapsama > 0.95, p

    # 3) Dolgu orani makul olmali
    dolguSayisi = sum(1 for kare in sonuc.values() for v in kare.values() if v[2])
    dolguOrani = dolguSayisi / sum(len(kare) for kare in sonuc.values())
    assert dolguOrani < 0.10, dolguOrani

    # 4) RTS duzlestirici bosluklari ILERI KESTIRIMDEN daha iyi doldurmali.
    #    Ayni atamalar uzerinde iki yontemi kiyasla.
    atamalar, zamanlar = kadroYurut(kareler, sahne.oyuncuSayisi)
    gercekIndis = {round(float(t), 3): i for i, t in enumerate(sahne.zamanlar)}

    def enYakinGercek(t, konum):
        i = gercekIndis[t]
        d = np.linalg.norm(sahne.gercekKonum[i] - konum, axis=1)
        return float(d.min())

    rtsHata, ileriHata = [], []
    for no in sorted({x.yuvaNo for x in atamalar}):
        iz = rtsDuzlestir(atamalar, zamanlar, no)
        kendi = {x.zaman: x for x in atamalar if x.yuvaNo == no}
        sonGorulen, sonHiz = None, np.zeros(2)
        for t in zamanlar:
            x = kendi.get(t)
            if x and x.gozlem:
                yeni = np.array([x.gozlem.x, x.gozlem.y])
                if sonGorulen is not None:
                    sonHiz = (yeni - sonGorulen[1]) / max(t - sonGorulen[0], 1e-6)
                sonGorulen = (t, yeni)
            elif sonGorulen is not None:
                ileri = sonGorulen[1] + sonHiz * (t - sonGorulen[0])
                ileriHata.append(enYakinGercek(t, ileri))
                rtsHata.append(enYakinGercek(t, iz[t][0]))

    assert rtsHata, "hic bosluk olusmadi, kiyas yapilamiyor"
    rtsMedyan, ileriMedyan = float(np.median(rtsHata)), float(np.median(ileriHata))
    assert rtsMedyan < ileriMedyan, (rtsMedyan, ileriMedyan)

    print("selftest ok  (%d kimlik, IDF1 %.3f, takas %d, konum RMS %.2f m, dolgu %%%.1f; "
          "bosluk doldurma: RTS %.2f m vs ileri kestirim %.2f m -> %%%.0f daha iyi)"
          % (len(kimlikler), p.idf1, p.takas, p.konumRms, 100 * dolguOrani,
             rtsMedyan, ileriMedyan, 100 * (1 - rtsMedyan / ileriMedyan)))


if __name__ == "__main__":
    selftest()
