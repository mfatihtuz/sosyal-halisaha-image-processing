"""Bilinen gercekli sentetik sahne ureteci -- kimlik testinin temeli.

Neden gerekli: kimlik takasini olcmek icin dogru cevabi bilmek sart. Gercek
videoda dogru cevap yok (referans kesiti elle uretilene kadar). Onceki surumun
en pahali hatasi buydu -- raporun 11 numarali dersi: "art arda yama denendi ve
her yama kullanicinin makinesinde calistirilip sonuc tek karelerden anlasilmaya
calisildi".

Bu modul, GERCEK VERIDEN OLCULEN istatistikleri yeniden ureten bir sahne kurar.
Sahne gercege benziyorsa, sahnede calisan algoritma gercekte de calisir.

Hedeflenen olcumler (kamera1_izler.csv, 60 sn, 10 fps, 603 kare, 7.631 satir):

    kare basina hareket        medyan 0,15 m   p90 0,44 m
    en yakin komsu mesafesi    p10 2,23 m      medyan 5,07 m
    kare basina tespit         12,66 / 14      (~%90 anma)
    guven                      yakin 0,856     uzak 0,705
    saha kullanimi             x 0-50, y 0-30

    python sentetikSahne.py --selftest
    python sentetikSahne.py --istatistik     # uretilen sahnenin olcumleri
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cekirdek.ayarlar import Ayarlar  # noqa: E402


# Kameralar sahanin iki ucunda, kale arkasinda ve yukarida.
# Gercek yerlesim: kamera 1 kale A'nin, kamera 2 kale B'nin arkasinda.
KAMERA_KONUMLARI = {
    1: np.array([-6.0, 15.0, 7.0]),
    2: np.array([56.0, 15.0, 7.0]),
}


@dataclass
class Sahne:
    """Uretilen sahnenin tamami: gercek konumlar + her kameranin gozlemleri."""

    zamanlar: np.ndarray            # (T,) saniye
    gercekKonum: np.ndarray         # (T, N, 2) metre -- DOGRU CEVAP
    oyuncuAdlari: list[str]         # (N,)
    oyuncuTakimlari: np.ndarray     # (N,) 1 yelekli / 0 siyah forma
    oyuncuRenkleri: np.ndarray      # (N, 4) ton, doygunluk, parlaklik, siyahlik
    gozlemler: dict[int, list]      # kamera -> kare basina gozlem listesi

    @property
    def oyuncuSayisi(self) -> int:
        return self.gercekKonum.shape[1]

    @property
    def kareSayisi(self) -> int:
        return len(self.zamanlar)


def _birimVektor(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-9)


def sahneUret(
    oyuncuSayisi: int = 14,
    sureSn: float = 60.0,
    fps: float = 10.0,
    baslangicZamani: float = 900.0,
    ayarlar: Ayarlar | None = None,
    tohum: int = 0,
) -> Sahne:
    """Futbol benzeri hareket ureten sahne.

    Hareket modeli: her oyuncu, topun konumu ile kendi dizilis noktasi arasinda
    bir hedefe dogru cekilir; birbirine cok yaklasan oyuncular itisir. Bu ucu
    birlikte, gercek veride olculen "herkes topun pesinde ama birbirine
    girmiyor" desenini uretir.
    """
    a = ayarlar or Ayarlar()
    rng = np.random.default_rng(tohum)
    uz, gen = a.saha.uzunluk, a.saha.genislik

    T = int(round(sureSn * fps))
    dt = 1.0 / fps
    zamanlar = baslangicZamani + np.arange(T) * dt

    n = oyuncuSayisi

    # Dizilis: her takim 1 kaleci + 6 oyuncu, saha genisligine yayilmis.
    # Yayilim onemli -- gercek veride en yakin komsu medyani 5,07 m, yani oyuncular
    # topun pesinde kosarken bile birbirlerine girmiyorlar.
    derinlikler = [0.03, 0.19, 0.19, 0.40, 0.40, 0.60, 0.74]
    yKonumlari = [0.50, 0.16, 0.84, 0.10, 0.90, 0.28, 0.72]

    dizilis = np.zeros((n, 2))
    kaleciler = np.zeros(n, bool)
    for i in range(n):
        takimda = i % 2                      # donusumlu -> takimlar esit
        sira = (i // 2) % len(derinlikler)
        derinlik = derinlikler[sira]
        dizilis[i, 0] = uz * (derinlik if takimda == 0 else 1.0 - derinlik)
        dizilis[i, 1] = gen * yKonumlari[sira]
        kaleciler[i] = (sira == 0)

    sahaMerkezi = np.array([uz / 2, gen / 2])
    konum = dizilis + rng.normal(0, 1.0, (n, 2))
    hiz = np.zeros((n, 2))

    top = sahaMerkezi.copy()
    topHiz = rng.normal(0, 3.0, 2)

    gercek = np.zeros((T, n, 2))
    for k in range(T):
        # Top: yumusak rastgele yuruyus, sahada kalir
        topHiz += rng.normal(0, 2.4, 2)
        topHiz = np.clip(topHiz, -9.0, 9.0)
        top = top + topHiz * dt
        for eksen, sinir in enumerate((uz, gen)):
            if top[eksen] < 1.0 or top[eksen] > sinir - 1.0:
                top[eksen] = np.clip(top[eksen], 1.0, sinir - 1.0)
                topHiz[eksen] *= -0.7

        # Takim topla birlikte blok halinde kayar. Raporda olculen "tum oyuncu
        # ciftlerinin x korelasyonu +0,34 ile +0,96" deseni bundan dogar; yayilim
        # korunur, cunku kayan sey dizilisin tamami.
        kayanDizilis = dizilis + (top - sahaMerkezi) * 0.42

        # Topa ilgi mesafeyle hizla duser: yalnizca yakindakiler kosar, gerisi
        # yurur. Gercek veride adim medyani 0,15 m ama p90 0,44 m -- yani cogunluk
        # yavas, azinlik hizli. Tekduze bir model bu agir kuyrugu uretmez.
        topaMesafe = np.linalg.norm(konum - top, axis=1)
        ilgi = np.exp(-(topaMesafe / 12.0) ** 2)
        ilgi = np.where(kaleciler, ilgi * 0.10, ilgi)

        hedef = ilgi[:, None] * top + (1.0 - ilgi[:, None]) * kayanDizilis
        hedefeYon = _birimVektor(hedef - konum)
        hedefeMesafe = np.linalg.norm(hedef - konum, axis=1)

        # Istenen hiz: yuruyusten sprinte. Hedefe cok yaklasinca yavasla.
        istenenHiz = (0.35 + 6.4 * ilgi) * np.clip(hedefeMesafe / 2.0, 0.0, 1.0)
        istenenHiz = np.where(kaleciler, istenenHiz * 0.45, istenenHiz)
        istenenHizVek = hedefeYon * istenenHiz[:, None]

        # Itisme: dar menzilli ama sert. Menzil genis tutulunca herkes surekli
        # itisip adim medyanini sisiriyordu; 3,5 m'nin altinda sert, ustunde sifir
        # olan bu bicim olculen komsu dagilimini (p10 2,23 m) yeniden uretiyor.
        fark = konum[:, None, :] - konum[None, :, :]
        uzaklik = np.linalg.norm(fark, axis=2)
        np.fill_diagonal(uzaklik, np.inf)
        itme = np.zeros_like(konum)
        yakin = uzaklik < 3.5
        if yakin.any():
            agirlik = np.where(yakin, ((3.5 - np.minimum(uzaklik, 3.5)) / 3.5) ** 1.5, 0.0)
            itme = (_birimVektor(fark) * agirlik[:, :, None]).sum(axis=1) * 30.0

        # Hiza dogru yumusak yaklasim + kucuk gurultu. Gurultu kucuk tutulur ki
        # duran oyuncu gercekten dursun (adim medyanini dusuk tutan sey bu).
        hiz += ((istenenHizVek - hiz) * 3.2 + itme) * dt + rng.normal(0, 0.30, (n, 2)) * dt / 0.1 * 0.1
        buyukluk = np.linalg.norm(hiz, axis=1, keepdims=True)
        hiz = np.where(buyukluk > a.metrik.azamiHiz,
                       hiz / np.maximum(buyukluk, 1e-9) * a.metrik.azamiHiz, hiz)
        konum = np.clip(konum + hiz * dt, [0.2, 0.2], [uz - 0.2, gen - 0.2])
        gercek[k] = konum

    # Renkler: yarisi siyah forma, yarisi yelekli.
    # Kullanicinin planladigi duzen -- kendi takimina siyah, rakibe yelek.
    adlar, takimlar, renkler = [], np.zeros(n, np.int32), np.zeros((n, 4))
    for i in range(n):
        yelekli = (i % 2 == 1)
        takimlar[i] = 1 if yelekli else 0
        adlar.append("%s%d" % ("Y" if yelekli else "S", i // 2 + 1))
        if yelekli:
            # Turuncu yelek: dar ton bandi, yuksek doygunluk, dusuk siyahlik
            renkler[i] = [rng.normal(24, 5), rng.normal(185, 18), rng.normal(180, 15),
                          np.clip(rng.normal(0.06, 0.03), 0, 1)]
        else:
            # Siyah forma: ton anlamsiz, dusuk doygunluk ve parlaklik, yuksek siyahlik
            renkler[i] = [rng.uniform(0, 360), rng.normal(38, 15), rng.normal(45, 12),
                          np.clip(rng.normal(0.82, 0.07), 0, 1)]

    gozlemler = {kam: _gozlemUret(gercek, zamanlar, renkler, KAMERA_KONUMLARI[kam], rng, a)
                 for kam in (1, 2)}

    return Sahne(zamanlar=zamanlar, gercekKonum=gercek, oyuncuAdlari=adlar,
                 oyuncuTakimlari=takimlar, oyuncuRenkleri=renkler, gozlemler=gozlemler)


def _gozlemUret(gercek, zamanlar, renkler, kameraKonumu, rng, a: Ayarlar):
    """Bir kameranin gozlemleri: kacirilan tespitler, mesafeyle buyuyen konum hatasi.

    Gercek veriden olculen davranis: guven yakin yarida 0,856, uzak yarida 0,705;
    kare basina 12,66/14 tespit. Hata modelinin mesafeyle buyumesi kritik --
    kameralarin birbirini tamamlamasinin sebebi bu ve fuzyon agirliklandirmasi
    tam olarak buna dayanacak.
    """
    T, n, _ = gercek.shape
    kareler = []
    for k in range(T):
        satirlar = []
        for i in range(n):
            p = gercek[k, i]
            d = float(np.linalg.norm(np.array([p[0], p[1], 0.0]) - kameraKonumu))

            # Tespit olasiligi mesafeyle duser (uzak yarida oyuncu 15-40 piksel)
            olasilik = float(np.clip(1.0 - (d / 95.0) ** 2.3, 0.78, 0.995))
            if rng.random() > olasilik:
                continue

            # Konum hatasi mesafenin karesiyle buyur: ayak noktasindaki 1-2
            # piksellik hata uzakta metrelere karsilik gelir.
            sigma = 0.08 + 0.12 * (d / 20.0) ** 2

            # Agir kuyruk: hatalarin kucuk bir kismi cok buyuk. Ortulme, iki
            # oyuncuyu kapsayan kutu, yansima, havada olan ayak. Saf Gauss bunu
            # uretmez -- ama gercek veride VAR: iki kameranin uyusmazliginin
            # medyani 0,85 m iken %8'i 2 m'nin disinda. Kimligi bozan sey tam
            # olarak bu kuyruk, dolayisiyla modelde bulunmasi sart.
            kabaHata = rng.random() < 0.04
            olculen = p + rng.normal(0, sigma * (7.0 if kabaHata else 1.0), 2)
            guven = float(np.clip(rng.normal(1.00 - 0.0066 * d, 0.06), 0.25, 0.99))

            ton, doy, parl, siyah = renkler[i]
            # Uzaktaki maske kucuk ve kirli -> renk olcumu gurultulenir
            renkGurultu = 1.0 + (d / 45.0) ** 2
            satirlar.append({
                "oyuncu": i,
                "x_m": float(olculen[0]), "y_m": float(olculen[1]),
                "guven": guven, "uzaklik": d, "sigma": sigma,
                "ton": float((ton + rng.normal(0, 6 * renkGurultu)) % 360.0),
                "doygunluk": float(np.clip(doy + rng.normal(0, 12 * renkGurultu), 0, 255)),
                "parlaklik": float(np.clip(parl + rng.normal(0, 12 * renkGurultu), 0, 255)),
                "siyahlik": float(np.clip(siyah + rng.normal(0, 0.05 * renkGurultu), 0, 1)),
                "maskeAlan": int(max(20, 90000 / max(d, 1.0) ** 2)),
            })

        # Nadir yanlis tespit (yansima, kenarda bekleyen)
        if rng.random() < 0.02:
            satirlar.append({
                "oyuncu": -1,
                "x_m": float(rng.uniform(0, a.saha.uzunluk)),
                "y_m": float(rng.uniform(0, a.saha.genislik)),
                "guven": float(rng.uniform(0.25, 0.45)), "uzaklik": 40.0, "sigma": 1.0,
                "ton": float(rng.uniform(0, 360)), "doygunluk": float(rng.uniform(0, 120)),
                "parlaklik": float(rng.uniform(40, 200)), "siyahlik": float(rng.uniform(0, 1)),
                "maskeAlan": 60,
            })
        kareler.append(satirlar)
    return kareler


# ----------------------------------------------------------------- olcumler

def sahneIstatistikleri(sahne: Sahne) -> dict[str, float]:
    """Sahnenin gercek veriyle kiyaslanabilir olcumleri."""
    g = sahne.gercekKonum
    adim = np.linalg.norm(np.diff(g, axis=0), axis=2).ravel()

    komsu = []
    for k in range(sahne.kareSayisi):
        d = np.linalg.norm(g[k][:, None, :] - g[k][None, :, :], axis=2)
        np.fill_diagonal(d, np.inf)
        komsu.append(d.min(axis=1))
    komsu = np.concatenate(komsu)

    tespitSayisi = [len(kare) for kare in sahne.gozlemler[1]]
    tumGozlem = [s for kare in sahne.gozlemler[1] for s in kare if s["oyuncu"] >= 0]
    yakin = [s["guven"] for s in tumGozlem if s["x_m"] <= 25]
    uzak = [s["guven"] for s in tumGozlem if s["x_m"] > 25]

    uyusmazlik = kameraUyusmazligi(sahne)

    return {
        "adimMedyan": float(np.median(adim)),
        "adimP90": float(np.percentile(adim, 90)),
        "komsuP10": float(np.percentile(komsu, 10)),
        "komsuMedyan": float(np.median(komsu)),
        "kareBasinaTespit": float(np.mean(tespitSayisi)),
        "guvenYakin": float(np.mean(yakin)) if yakin else 0.0,
        "guvenUzak": float(np.mean(uzak)) if uzak else 0.0,
        "uyusmazlikMedyan": float(np.median(uyusmazlik)),
        "uyusmazlik2mOran": float(100.0 * np.mean(uyusmazlik <= 2.0)),
        "xMin": float(g[..., 0].min()), "xMaks": float(g[..., 0].max()),
        "yMin": float(g[..., 1].min()), "yMaks": float(g[..., 1].max()),
    }


def kameraUyusmazligi(sahne: Sahne) -> np.ndarray:
    """Iki kameranin AYNI oyuncu icin verdigi konumlar arasindaki mesafe.

    Bu, kalibrasyon ve tespit kalitesinin BAGIMSIZ olcusudur -- dogru cevabi
    bilmeye gerek yok, iki bagimsiz olcumun birbirini tutup tutmadigina bakiyor.
    Gercek veride medyan 0,85 m ve %92'si 2 m icinde. Sentetik sahnenin bu iki
    sayiyi tutturmasi, gurultu modelinin gercekci oldugunun kanitidir.
    """
    farklar = []
    for k in range(sahne.kareSayisi):
        a = {s["oyuncu"]: (s["x_m"], s["y_m"]) for s in sahne.gozlemler[1][k] if s["oyuncu"] >= 0}
        b = {s["oyuncu"]: (s["x_m"], s["y_m"]) for s in sahne.gozlemler[2][k] if s["oyuncu"] >= 0}
        for i in a.keys() & b.keys():
            farklar.append(float(np.hypot(a[i][0] - b[i][0], a[i][1] - b[i][1])))
    return np.array(farklar)


# Gercek veriden olculen degerler; sentetik sahne bunlara yakin olmali.
GERCEK_OLCUMLER = {
    "adimMedyan": 0.15, "adimP90": 0.44,
    "komsuP10": 2.23, "komsuMedyan": 5.07,
    "kareBasinaTespit": 12.66,
    "guvenYakin": 0.856, "guvenUzak": 0.705,
    "uyusmazlikMedyan": 0.85, "uyusmazlik2mOran": 92.0,
}


def istatistikYazdir(sahne: Sahne) -> None:
    ist = sahneIstatistikleri(sahne)
    print("%-22s %10s %10s" % ("olcum", "sentetik", "gercek"))
    print("-" * 44)
    for anahtar, gercekDeger in GERCEK_OLCUMLER.items():
        print("%-22s %10.2f %10.2f" % (anahtar, ist[anahtar], gercekDeger))
    print("%-22s %10s %10s" % ("saha x araligi", "%.1f-%.1f" % (ist["xMin"], ist["xMaks"]), "-0.2-52.1"))
    print("%-22s %10s %10s" % ("saha y araligi", "%.1f-%.1f" % (ist["yMin"], ist["yMaks"]), "0.0-30.7"))


# ----------------------------------------------------------------- selftest

def selftest() -> None:
    sahne = sahneUret(tohum=0)
    ist = sahneIstatistikleri(sahne)

    assert sahne.kareSayisi == 600, sahne.kareSayisi
    assert sahne.oyuncuSayisi == 14
    assert sahne.gercekKonum.shape == (600, 14, 2)

    # ASIL TEST: sentetik sahne gercek veriden olculen istatistikleri uretiyor mu.
    # Uretmiyorsa uzerinde calisan algoritma gercekte calismaz.
    def yakinMi(anahtar, tolerans, birim="kat"):
        s, g = ist[anahtar], GERCEK_OLCUMLER[anahtar]
        oran = s / g if birim == "kat" else abs(s - g)
        assert (1 / tolerans <= oran <= tolerans) if birim == "kat" else oran <= tolerans, \
            "%s: sentetik %.3f, gercek %.3f" % (anahtar, s, g)

    yakinMi("adimMedyan", 1.45)
    yakinMi("adimP90", 1.30)
    yakinMi("komsuP10", 1.20)
    yakinMi("komsuMedyan", 1.25)
    yakinMi("kareBasinaTespit", 1.05)
    yakinMi("guvenYakin", 0.06, "fark")
    yakinMi("guvenUzak", 0.10, "fark")

    # Kameralar birbirini tamamlamali: kamera 1 yakin yarida, kamera 2 uzak yarida iyi
    def yarilardaAnma(kamera):
        sayac = {"yakin": [0, 0], "uzak": [0, 0]}
        for k, kare in enumerate(sahne.gozlemler[kamera]):
            gorulen = {s["oyuncu"] for s in kare if s["oyuncu"] >= 0}
            for i in range(sahne.oyuncuSayisi):
                bolge = "yakin" if sahne.gercekKonum[k, i, 0] <= 25 else "uzak"
                sayac[bolge][1] += 1
                sayac[bolge][0] += (i in gorulen)
        return sayac["yakin"][0] / sayac["yakin"][1], sayac["uzak"][0] / sayac["uzak"][1]

    k1Yakin, k1Uzak = yarilardaAnma(1)
    k2Yakin, k2Uzak = yarilardaAnma(2)
    assert k1Yakin > k1Uzak + 0.05, (k1Yakin, k1Uzak)
    assert k2Uzak > k2Yakin + 0.05, (k2Yakin, k2Uzak)

    # Birlestirilmis anma tek kameradan belirgin sekilde iyi olmali --
    # iki kamera kullanmanin tum gerekcesi bu
    birlesikAnma = 0.0
    for k, (kare1, kare2) in enumerate(zip(sahne.gozlemler[1], sahne.gozlemler[2])):
        gorulen = ({s["oyuncu"] for s in kare1 if s["oyuncu"] >= 0}
                   | {s["oyuncu"] for s in kare2 if s["oyuncu"] >= 0})
        birlesikAnma += len(gorulen) / sahne.oyuncuSayisi
    birlesikAnma /= sahne.kareSayisi
    tekAnma = (k1Yakin + k1Uzak) / 2
    assert birlesikAnma > 0.97, birlesikAnma
    assert birlesikAnma > tekAnma + 0.05, (birlesikAnma, tekAnma)

    # Konum hatasi mesafeyle buyumeli. Fuzyon agirliklandirmasinin (1/sigma^2)
    # tum dayanagi bu; hata mesafeden bagimsiz olsaydi esit agirlikli ortalama
    # dogru olurdu ve raporun 4 numarali acik sorunu diye bir sey olmazdi.
    hatalar = {"yakin": [], "uzak": []}
    for k, kare in enumerate(sahne.gozlemler[1]):
        for s in kare:
            if s["oyuncu"] < 0:
                continue
            p = sahne.gercekKonum[k, s["oyuncu"]]
            h = float(np.hypot(s["x_m"] - p[0], s["y_m"] - p[1]))
            hatalar["yakin" if s["uzaklik"] < 25 else "uzak"].append(h)
    hataOrani = np.median(hatalar["uzak"]) / np.median(hatalar["yakin"])
    assert hataOrani > 2.0, (hataOrani, np.median(hatalar["yakin"]), np.median(hatalar["uzak"]))

    # ASIL CIPA: iki kameranin uyusmazligi. Dogru cevabi bilmeye gerek duymayan,
    # gercek veride dogrudan olculmus bir buyukluk -- medyan 0,85 m, %92'si 2 m
    # icinde. Gurultu modelinin gercekciliginin tek nesnel kaniti bu.
    yakinMi("uyusmazlikMedyan", 1.15)
    assert abs(ist["uyusmazlik2mOran"] - GERCEK_OLCUMLER["uyusmazlik2mOran"]) < 3.0, \
        ist["uyusmazlik2mOran"]

    # Takim renkleri ayrismali: siyah forma vs yelek, siyahlik ekseninde
    siyahlik = sahne.oyuncuRenkleri[:, 3]
    siyahForma = siyahlik[sahne.oyuncuTakimlari == 0]
    yelekli = siyahlik[sahne.oyuncuTakimlari == 1]
    assert siyahForma.min() > yelekli.max() + 0.3, (siyahForma.min(), yelekli.max())

    # Farkli tohum farkli sahne uretmeli, ayni tohum ayni sahneyi
    assert not np.allclose(sahneUret(tohum=1).gercekKonum, sahne.gercekKonum)
    assert np.allclose(sahneUret(tohum=0).gercekKonum, sahne.gercekKonum)

    print("selftest ok  (%d kare x %d oyuncu; adim %.2f/%.2f m, komsu %.2f/%.2f m, "
          "tespit %.2f/14, birlesik anma %.1f%%)"
          % (sahne.kareSayisi, sahne.oyuncuSayisi, ist["adimMedyan"], ist["adimP90"],
             ist["komsuP10"], ist["komsuMedyan"], ist["kareBasinaTespit"], 100 * birlesikAnma))


if __name__ == "__main__":
    if "--istatistik" in sys.argv:
        istatistikYazdir(sahneUret())
    else:
        selftest()
