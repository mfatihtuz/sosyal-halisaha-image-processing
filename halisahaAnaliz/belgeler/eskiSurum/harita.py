"""birlesik.csv -> isi haritalari ve saha gorselleri.

    python harita.py                       # birlesik.csv okur
    python harita.py birlesik.csv --cikti isi.png

Takim isi haritasi kimlige ihtiyac duymaz: birkac kimlik karissa bile
"hangi bolgede ne kadar duruldu" dogru cikar. Oyuncu bazli haritalar
kimlik kalitesine baglidir, o yuzden ayri dosyaya yazilir.
"""
import csv
import sys


def _takimda(ad, takim):
    """--takim x / y / ikisi  ->  ciktiya hangi takim girsin."""
    if takim == "ikisi" or ad.startswith("P"):     # P: takim henuz belirlenmemis
        return True
    return (takim == "x" and ad.startswith("X")) or (takim == "y" and ad.startswith("Y"))


def _bayrak():
    return sys.argv[sys.argv.index("--takim") + 1] if "--takim" in sys.argv else "ikisi"
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter

from metrik import hiz_profili, rol_bul

UZUNLUK, GENISLIK = 50.0, 30.0
HUCRE = 0.5          # metre
YUMUSATMA = 2.5      # hucre


def oku(yol, takim="ikisi"):
    r = [x for x in csv.DictReader(open(yol)) if _takimda(x["oyuncu"], takim)]
    return {"t": np.array([float(x["t_s"]) for x in r]),
            "no": np.array([x["oyuncu"] for x in r]),
            "x": np.array([float(x["x_m"]) for x in r]),
            "y": np.array([float(x["y_m"]) for x in r]),
            "takim": np.array([int(x["takim"]) for x in r])}


def saha_ciz(ax):
    ax.add_patch(plt.Rectangle((0, 0), UZUNLUK, GENISLIK, fill=False, ec="w", lw=1.6))
    ax.plot([UZUNLUK / 2] * 2, [0, GENISLIK], "w-", lw=1.4)
    ax.add_patch(plt.Circle((UZUNLUK / 2, GENISLIK / 2), 5.0, fill=False, ec="w", lw=1.4))
    for x0, gen in ((0, 8.0), (UZUNLUK - 8.0, 8.0)):
        ax.add_patch(plt.Rectangle((x0, GENISLIK / 2 - 8.0), gen, 16.0,
                                   fill=False, ec="w", lw=1.2))
    ax.set_xlim(-2, UZUNLUK + 2)
    ax.set_ylim(GENISLIK + 2, -2)
    ax.set_aspect("equal")
    ax.axis("off")


def isi(x, y):
    nx, ny = int(UZUNLUK / HUCRE), int(GENISLIK / HUCRE)
    H, _, _ = np.histogram2d(x, y, bins=[nx, ny],
                             range=[[0, UZUNLUK], [0, GENISLIK]])
    return gaussian_filter(H.T, YUMUSATMA)


def panel(ax, x, y, baslik):
    ax.imshow(isi(x, y), extent=[0, UZUNLUK, GENISLIK, 0],
              cmap="inferno", interpolation="bilinear", aspect="equal")
    saha_ciz(ax)
    ax.set_title(baslik, color="w", fontsize=11, pad=8)


def _aralik(d):
    def mmss(x):
        return "%d:%02d" % (int(x) // 60, int(x) % 60)
    return "%s - %s" % (mmss(d["t"].min()), mmss(d["t"].max()))


def _izler(d):
    iz = defaultdict(list)
    for i in range(len(d["t"])):
        iz[d["no"][i]].append((d["t"][i], d["x"][i], d["y"][i], d["takim"][i], 0))
    for v in iz.values():
        v.sort()
    return iz


def takim_haritasi(d, cikti):
    takimlar = sorted(set(d["takim"]))
    fig, axes = plt.subplots(1, len(takimlar) + 1, figsize=(6.2 * (len(takimlar) + 1), 4.6))
    fig.patch.set_facecolor("#111")
    panel(axes[0], d["x"], d["y"], "Iki takim birlikte")
    isim = {1: "Yelekli takim (X)", 0: "Serbest takim (Y)", -1: "Takim belirsiz"}
    for ax, tk in zip(axes[1:], takimlar):
        m = d["takim"] == tk
        panel(ax, d["x"][m], d["y"][m], isim.get(tk, "Takim %d" % tk))
    fig.suptitle("TAKIM ISI HARITASI   ·   mac dakikasi %s   ·   parlak bolge = orada daha cok "
                 "zaman gecirildi   ·   soldaki kale x=0, sagdaki x=50" % _aralik(d),
                 color="w", fontsize=12, y=0.985)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(cikti, dpi=140, facecolor=fig.get_facecolor())
    print("Yazildi:", cikti)


def oyuncu_haritasi(d, cikti, en_fazla=14):
    adli = [no for no in set(d["no"]) if not no.startswith("?")]
    iz = _izler(d)
    rol = rol_bul({a: iz[a] for a in adli})
    yol = {}
    for a in adli:
        _, _, _, v, dt = hiz_profili(iz[a])
        yol[a] = float((v * dt).sum())
    secili = sorted(adli, key=lambda n: (n[0], int(n[1:])))[:en_fazla]
    sut = 4
    sat = int(np.ceil(len(secili) / sut))
    fig, axes = plt.subplots(sat, sut, figsize=(4.6 * sut, 3.4 * sat))
    fig.patch.set_facecolor("#111")
    for ax, no in zip(np.ravel(axes), secili):
        m = d["no"] == no
        tk = "yelekli" if d["takim"][m][0] == 1 else "serbest"
        panel(ax, d["x"][m], d["y"][m],
              "%s   %s   ·   %s   ·   %.0f m kostu" % (no, tk, rol.get(no, "-"), yol[no]))
    for ax in np.ravel(axes)[len(secili):]:
        ax.axis("off")
    fig.suptitle("OYUNCU ISI HARITALARI   ·   mac dakikasi %s   ·   her kutu bir oyuncunun "
                 "sahada gecirdigi zamanin dagilimi   ·   parlak = orada uzun durdu" % _aralik(d),
                 color="w", fontsize=12.5, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(cikti, dpi=130, facecolor=fig.get_facecolor())
    print("Yazildi:", cikti)


def selftest():
    rng = np.random.default_rng(0)
    n = 4000
    d = {"t": np.linspace(0, 60, n), "no": rng.integers(1, 5, n),
         "x": np.clip(rng.normal(15, 8, n), 0, UZUNLUK),
         "y": np.clip(rng.normal(15, 6, n), 0, GENISLIK),
         "takim": rng.integers(0, 2, n)}
    H = isi(d["x"], d["y"])
    assert H.shape == (int(GENISLIK / HUCRE), int(UZUNLUK / HUCRE)), H.shape
    # yogunluk gercekten sol yariya kaymis mi (x ortalamasi 15)
    sol = H[:, :H.shape[1] // 2].sum()
    assert sol > 1.5 * H[:, H.shape[1] // 2:].sum(), (sol, H.sum())
    print("selftest ok  (izgara boyutu ve yogunluk dagilimi dogru)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        raise SystemExit
    kaynak = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith(".csv") else "birlesik.csv"
    d = oku(kaynak, _bayrak())
    takim_haritasi(d, "isi_takim.png")
    oyuncu_haritasi(d, "isi_oyuncu.png")
