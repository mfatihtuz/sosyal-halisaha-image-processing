"""Tek parametreli bolme modeli: bozuk piksel <-> ideal piksel.

    x_ideal = x_bozuk / (1 + lam * r^2)

Koordinatlar goruntu merkezine gore alinir ve yarim kosegene bolunerek normalize
edilir, dolayisiyla `lam` cozunurlukten bagimsizdir.

NEDEN TEK PARAMETRE. Brown-Conrady modeli (k1, k2, k3) denendi ve OLCULEREK
elendi: uc serbestlik derecesi, olcutu memnun eden ama fiziksel anlami olmayan
katsayilar buldu (k2 = -5,2 ve k3 = 8,5 gibi) ve gercek geometriyi yakalamadi;
nokta hatasi 1,9-2,5 m'de kaldi. Tek parametreli bolme modeliyle ayni veride
0,31-0,36 m'ye inildi. Serbestlik derecesi az oldugu icin optimize edicinin
kacacak yeri yok.

Goruntu HICBIR ZAMAN duzlestirilmez (undistort/warp edilmez). Balik gozu kareyi
dikdortgene acmak kenarlari sonsuza esnetir; merkez duzelirken kenarlar dagilir
ve kullanilabilir alan yari sahanin altina iner. Yalnizca ILGILENILEN NOKTALAR
donusturulur -- oyuncunun ayak noktasi ve dogrulama izgarasi.

    python lensModeli.py --selftest
"""
from __future__ import annotations

import sys

import numpy as np


def olcekVeMerkez(genislik: int, yukseklik: int) -> tuple[float, np.ndarray]:
    """Normalizasyon olcegi (yarim kosegen) ve goruntu merkezi."""
    return float(np.hypot(genislik, yukseklik) / 2.0), np.array([genislik / 2.0, yukseklik / 2.0])


def duzeltNokta(pikseller, lam: float, genislik: int, yukseklik: int) -> np.ndarray:
    """Bozuk piksel -> ideal piksel.

    Bolme modeli: r_ideal = r_bozuk / (1 + lam * r_bozuk^2)
    """
    olcek, merkez = olcekVeMerkez(genislik, yukseklik)
    xd = (np.asarray(pikseller, float).reshape(-1, 2) - merkez) / olcek
    r2 = (xd ** 2).sum(axis=1, keepdims=True)
    return xd / (1.0 + lam * r2) * olcek + merkez


def bozNokta(pikseller, lam: float, genislik: int, yukseklik: int) -> np.ndarray:
    """Ideal piksel -> bozuk piksel. Bolme modelinin tersi.

    r_ideal = r_bozuk / (1 + lam*r_bozuk^2)  denklemi r_bozuk icin ikinci
    dereceden bir denklemdir:  lam*a*r^2 - r + a = 0,  a = r_ideal.
    Iki kokten KUCUK olani secilir -- buyuk kok, goruntunun disina dusen ve
    fiziksel karsiligi olmayan ikinci daldir.
    """
    olcek, merkez = olcekVeMerkez(genislik, yukseklik)
    xu = (np.asarray(pikseller, float).reshape(-1, 2) - merkez) / olcek
    a = np.linalg.norm(xu, axis=1)
    guvenli = np.maximum(a, 1e-12)

    if abs(lam) < 1e-12:
        b = a
    else:
        ayirtac = np.maximum(1.0 - 4.0 * lam * a ** 2, 0.0)
        b = (1.0 - np.sqrt(ayirtac)) / (2.0 * lam * guvenli)

    return xu * (b / guvenli)[:, None] * olcek + merkez


def azamiGecerliYaricap(lam: float) -> float:
    """Ters donusumun tanimli oldugu azami ideal yaricap (normalize).

    lam > 0 icin ayirtac 1 - 4*lam*a^2 negatif olunca ters donusum tanimsizdir;
    bu, o ideal noktanin hicbir bozuk piksele karsilik gelmedigi anlamina gelir.
    Dogrulama izgarasi cizilirken bu sinirin disina cikilmamalidir.
    """
    if lam <= 0:
        return np.inf
    return float(1.0 / (2.0 * np.sqrt(lam)))


# ----------------------------------------------------------------- selftest

def selftest() -> None:
    genislik, yukseklik = 1920, 1080
    rng = np.random.default_rng(0)

    # 1) Ileri-geri donusum tutarli olmali (her iki yonde)
    for lam in (-0.5028, -0.3, -0.05, 0.0, 0.05, 0.22):
        noktalar = rng.uniform([0, 0], [genislik, yukseklik], (400, 2))
        ideal = duzeltNokta(noktalar, lam, genislik, yukseklik)
        geri = bozNokta(ideal, lam, genislik, yukseklik)
        enBuyukSapma = float(np.abs(geri - noktalar).max())
        assert enBuyukSapma < 1e-6, (lam, enBuyukSapma)

    # 2) Merkez sabit kalmali: bozulma merkezde etkisizdir
    for lam in (-0.5, 0.0, 0.3):
        merkez = np.array([[genislik / 2.0, yukseklik / 2.0]])
        assert np.abs(duzeltNokta(merkez, lam, genislik, yukseklik) - merkez).max() < 1e-9
        assert np.abs(bozNokta(merkez, lam, genislik, yukseklik) - merkez).max() < 1e-9

    # 3) lam = 0 hicbir sey yapmamali
    noktalar = rng.uniform([0, 0], [genislik, yukseklik], (100, 2))
    assert np.allclose(duzeltNokta(noktalar, 0.0, genislik, yukseklik), noktalar)

    # 4) Negatif lam (varil bozulmasi, balik gozu) noktalari merkezden UZAKLASTIRIR.
    #    Gercek kameralarda olculen deger lam ~ -0,50; yani duzeltilmis goruntu
    #    orijinalden daha genistir. Bu, warp etmenin neden kenarlari yok ettiginin
    #    de aciklamasi: duzeltme kenarlari sonsuza dogru esnetir.
    kose = np.array([[genislik * 0.95, yukseklik * 0.95]])
    _, merkez = olcekVeMerkez(genislik, yukseklik)
    r0 = np.linalg.norm(kose - merkez)
    r1 = np.linalg.norm(duzeltNokta(kose, -0.5028, genislik, yukseklik) - merkez)
    assert r1 > r0 * 1.4, (r0, r1)

    # 5) Bozulma RADYAL olmali: yon degismemeli, yalnizca yaricap degismeli
    for lam in (-0.5028, 0.22):
        noktalar = rng.uniform([1, 1], [genislik, yukseklik], (200, 2))
        v0 = noktalar - merkez
        v1 = duzeltNokta(noktalar, lam, genislik, yukseklik) - merkez
        capraz = np.abs(v0[:, 0] * v1[:, 1] - v0[:, 1] * v1[:, 0])
        assert capraz.max() < 1e-6, (lam, capraz.max())

    # 6) Monotonluk: yaricap arttikca duzeltilmis yaricap da artmali. Aksi halde
    #    iki farkli piksel ayni ideal noktaya duser ve donusum tersinemez olur.
    for lam in (-0.6, -0.5028, -0.1, 0.1, 0.3):
        yariCaplar = np.linspace(0, 0.99, 200)
        p = merkez + np.stack([yariCaplar * olcekVeMerkez(genislik, yukseklik)[0],
                               np.zeros_like(yariCaplar)], axis=1)
        r = np.linalg.norm(duzeltNokta(p, lam, genislik, yukseklik) - merkez, axis=1)
        assert np.all(np.diff(r) > 0), lam

    # 7) Cozunurlukten bagimsizlik: ayni goreli konum, ayni goreli sonuc
    for lam in (-0.5028, 0.22):
        for g, y in ((1920, 1080), (3840, 2160), (1280, 720)):
            olcek, mrk = olcekVeMerkez(g, y)
            p = mrk + np.array([[0.4 * olcek, 0.2 * olcek]])
            d = (duzeltNokta(p, lam, g, y) - mrk) / olcek
            if g == 1920:
                referans = d
            else:
                assert np.abs(d - referans).max() < 1e-9, (lam, g, d, referans)

    # 8) Pozitif lam'de gecerlilik siniri dogru hesaplanmali
    lam = 0.22
    sinir = azamiGecerliYaricap(lam)
    olcek, mrk = olcekVeMerkez(genislik, yukseklik)
    icerde = mrk + np.array([[sinir * 0.9 * olcek, 0.0]])
    assert np.isfinite(bozNokta(icerde, lam, genislik, yukseklik)).all()
    assert azamiGecerliYaricap(-0.5) == np.inf

    print("selftest ok  (ileri-geri tutarlilik <1e-6 px, radyallik, monotonluk, "
          "cozunurluk bagimsizligi; lam=-0,5028'de kose %.2f kat disari itiliyor)"
          % (r1 / r0))


if __name__ == "__main__":
    selftest()
