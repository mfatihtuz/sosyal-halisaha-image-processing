"""Sabit kamera kalibrasyonu. Goruntu HIC dondurulmez, sadece nokta eslemesi kurulur.

Tek bozulma parametresi (bolme modeli) + homografi, hepsi tek seferde ve
DOGRUDAN metre hatasi kucultulerek cozulur. Cizgi tiklamalari da veri olarak
kullanilir: kenar cizgisindeki her nokta "Y=0", orta cizgideki her nokta "X=25"
diyen birer denklemdir. Boylece 7 nokta yerine onlarca kisitla calisilir.

    pip install opencv-python matplotlib numpy scipy

    python kalibrasyon.py kamera1.mp4          # 300. saniyeden kare alir
    python kalibrasyon.py kamera1.mp4 900      # 900. saniyeden
    python kalibrasyon.py --selftest

Cikti: <video>_kalibrasyon.json  +  dogrulama_<video>.png

ONEMLI - koordinat sistemi iki kamerada da AYNI olmali:
  Kale A  = kamera 1'in arkasinda durdugu kale (X=0).  Kamera 2'de sagda gorunur.
  Kale B  = karsi kale (X=50).
  Kenar 1 = kamera 1'in goruntusunde USTTE kalan kenar cizgisi (Y=0).
  Kenar 2 = kamera 1'in goruntusunde ALTTA kalan kenar cizgisi (Y=30).
"""
import json
import sys

import cv2
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import least_squares

# ponytail: saha olculeri tahmin (30x50). Gercek olcu ogrenilince degistir.
UZUNLUK, GENISLIK = 50.0, 30.0

# (ad, hangi eksen sabit, degeri)  ->  bu cizgideki her nokta bir denklem
CIZGILER = [
    ("Kenar 1  (ustteki kenar cizgisi)", "y", 0.0),
    ("Kenar 2  (alttaki kenar cizgisi)", "y", GENISLIK),
    ("Orta cizgi",                       "x", UZUNLUK / 2),
    ("Kale A cizgisi  (yakin kale)",     "x", 0.0),
    ("Kale B cizgisi  (uzak kale)",      "x", UZUNLUK),
]

NOKTALAR = [
    ("Kale A x Kenar 1", (0.0,         0.0)),
    ("Orta   x Kenar 1", (UZUNLUK / 2, 0.0)),
    ("Kale B x Kenar 1", (UZUNLUK,     0.0)),
    ("Kale B x Kenar 2", (UZUNLUK,     GENISLIK)),
    ("Orta   x Kenar 2", (UZUNLUK / 2, GENISLIK)),
    ("Kale A x Kenar 2", (0.0,         GENISLIK)),
    ("Orta nokta",       (UZUNLUK / 2, GENISLIK / 2)),
]


# ---------------------------------------------------------------- lens modeli

def _olcek(w, h):
    return np.hypot(w, h) / 2.0, np.array([w / 2.0, h / 2.0])


def duzelt_nokta(px, lam, w, h):
    """Bozuk piksel -> ideal piksel. Bolme modeli: xu = xd / (1 + lam*r^2)."""
    s, c = _olcek(w, h)
    xd = (np.asarray(px, float).reshape(-1, 2) - c) / s
    r2 = (xd ** 2).sum(axis=1, keepdims=True)
    return xd / (1.0 + lam * r2) * s + c


def boz_nokta(pu, lam, w, h):
    """Ideal piksel -> bozuk piksel. Bolme modelinin tersi (kok secimi: kucuk kok)."""
    s, c = _olcek(w, h)
    xu = (np.asarray(pu, float).reshape(-1, 2) - c) / s
    a = np.linalg.norm(xu, axis=1)
    guvenli = np.maximum(a, 1e-12)
    if abs(lam) < 1e-12:
        b = a
    else:
        disk = np.maximum(1.0 - 4.0 * lam * a ** 2, 0.0)
        b = (1.0 - np.sqrt(disk)) / (2.0 * lam * guvenli)
    return xu * (b / guvenli)[:, None] * s + c


# ---------------------------------------------------------------- cozum

def _uygula(H, pts):
    p = np.hstack([pts, np.ones((len(pts), 1))]) @ H.T
    return p[:, :2] / p[:, 2:3]


def _artiklar(par, n_px, n_m, c_px, c_kis, w, h):
    """Tum kisitlarin metre cinsinden artiklari. Optimize edilen sey = onemsedigimiz sey."""
    lam, H = par[0], np.append(par[1:9], 1.0).reshape(3, 3)
    r = []
    if len(n_px):
        r.append((_uygula(H, duzelt_nokta(n_px, lam, w, h)) - n_m).ravel())
    for px, (eksen, deger) in zip(c_px, c_kis):
        m = _uygula(H, duzelt_nokta(px, lam, w, h))
        r.append(m[:, 0 if eksen == "x" else 1] - deger)
    return np.concatenate(r) if r else np.zeros(1)


def coz(n_px, n_m, c_px, c_kis, w, h):
    if len(n_m) < 4:
        sys.exit("En az 4 nokta gerekli, %d verildi." % len(n_m))

    # 1) lam icin kaba tarama - tek parametre oldugu icin yerel minimum riski yok
    en_iyi = None
    for lam in np.linspace(-0.6, 0.6, 241):
        ideal = duzelt_nokta(n_px, lam, w, h)
        H, _ = cv2.findHomography(ideal.astype(np.float32), n_m.astype(np.float32))
        if H is None:
            continue
        par = np.concatenate([[lam], (H / H[2, 2]).ravel()[:8]])
        bedel = float((_artiklar(par, n_px, n_m, c_px, c_kis, w, h) ** 2).sum())
        if en_iyi is None or bedel < en_iyi[0]:
            en_iyi = (bedel, par)

    # 2) lam ve H birlikte ince ayar
    son = least_squares(_artiklar, en_iyi[1], args=(n_px, n_m, c_px, c_kis, w, h),
                        method="lm", max_nfev=20000)
    lam, H = son.x[0], np.append(son.x[1:9], 1.0).reshape(3, 3)
    art = _artiklar(son.x, n_px, n_m, c_px, c_kis, w, h)
    return lam, H, float(np.sqrt((art ** 2).mean())), np.sqrt(en_iyi[0] / max(len(art), 1))


# ---------------------------------------------------------------- girdi / cikti

def kare_al(video, saniye):
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        sys.exit("Video acilamadi: " + video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    print("%dx%d @ %.1f fps, %.1f dk"
          % (cap.get(3), cap.get(4), fps, cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps / 60))
    cap.set(cv2.CAP_PROP_POS_MSEC, saniye * 1000)
    ok, kare = cap.read()
    cap.release()
    if not ok:
        sys.exit("Kare okunamadi, baska bir saniye dene.")
    return cv2.cvtColor(kare, cv2.COLOR_BGR2RGB)


def tikla(kare):
    plt.figure(figsize=(16, 9))
    plt.imshow(kare)
    c_px, c_kis = [], []
    for ad, eksen, deger in CIZGILER:
        plt.title(ad + "  ->  uzerine 4-8 nokta tikla, sonra bir tusa bas. "
                       "Gorunmuyorsa hemen tusa bas.")
        pts = plt.ginput(12, timeout=0)
        if len(pts) >= 3:
            c_px.append(np.array(pts, float))
            c_kis.append((eksen, deger))
            plt.plot([p[0] for p in pts], [p[1] for p in pts], "y.-", linewidth=1)
            plt.draw()

    n_px, n_m = [], []
    for ad, xy in NOKTALAR:
        plt.title(ad + "  ->  tikla. Gormuyorsan bir tusa bas, atlanir.")
        secim = plt.ginput(1, timeout=0)
        if not secim:
            continue
        n_px.append(secim[0])
        n_m.append(xy)
        plt.plot(secim[0][0], secim[0][1], "r+", markersize=14)
        plt.draw()
    plt.close()
    return np.array(n_px, float).reshape(-1, 2), np.array(n_m, float).reshape(-1, 2), c_px, c_kis


def dogrulama_ciz(kare, lam, H, yol):
    h, w = kare.shape[:2]
    tuval, Hi = kare.copy(), np.linalg.inv(H)
    for x in np.arange(0.0, UZUNLUK + 0.01, 5.0):
        m = np.array([(x, y) for y in np.linspace(0, GENISLIK, 80)])
        cv2.polylines(tuval, [np.int32(boz_nokta(_uygula(Hi, m), lam, w, h))],
                      False, (255, 0, 0), 2)
    for y in np.arange(0.0, GENISLIK + 0.01, 5.0):
        m = np.array([(x, y) for x in np.linspace(0, UZUNLUK, 120)])
        cv2.polylines(tuval, [np.int32(boz_nokta(_uygula(Hi, m), lam, w, h))],
                      False, (0, 255, 255), 2)
    cv2.imwrite(yol, cv2.cvtColor(tuval, cv2.COLOR_RGB2BGR))


def selftest():
    w, h, lam_g = 1920, 1080, 0.22
    M = np.array([[26.0, 6.0, 300.0], [3.0, 27.0, 180.0], [0.0009, 0.0016, 1.0]])  # metre -> ideal px

    n_m = np.array([p[1] for p in NOKTALAR])
    n_px = boz_nokta(_uygula(M, n_m), lam_g, w, h)

    c_px, c_kis = [], []
    for _, eksen, deger in CIZGILER:
        t = np.linspace(0, GENISLIK if eksen == "x" else UZUNLUK, 7)
        m = np.stack([np.full(7, deger), t], 1) if eksen == "x" else np.stack([t, np.full(7, deger)], 1)
        c_px.append(boz_nokta(_uygula(M, m), lam_g, w, h))
        c_kis.append((eksen, deger))

    # ileri/geri donusum tutarli mi
    assert np.abs(duzelt_nokta(n_px, lam_g, w, h) - _uygula(M, n_m)).max() < 1e-6

    rng = np.random.default_rng(0)
    lam, H, rms, kaba = coz(n_px + rng.normal(0, 1.0, n_px.shape), n_m,
                            [c + rng.normal(0, 1.0, c.shape) for c in c_px], c_kis, w, h)
    assert rms < 0.25, rms
    assert abs(lam - lam_g) < 0.03, (lam, lam_g)
    print("selftest ok  (lam %.3f/%.3f, kaba %.2f m -> ince %.3f m)" % (lam, lam_g, kaba, rms))


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        raise SystemExit

    video = sys.argv[1]
    kare = kare_al(video, float(sys.argv[2]) if len(sys.argv) > 2 else 300.0)
    h, w = kare.shape[:2]

    n_px, n_m, c_px, c_kis = tikla(kare)
    lam, H, rms, kaba = coz(n_px, n_m, c_px, c_kis, w, h)

    print("lam=%.4f   kisit sayisi=%d   RMS hata: %.2f m"
          % (lam, 2 * len(n_m) + sum(len(c) for c in c_px), rms))
    if rms > 1.0:
        print("UYARI: 1 m ustu. Dogrulama resmine bak, kayan bolgeyi yeniden tikla.")

    taban = video.rsplit(".", 1)[0]
    dogrulama_ciz(kare, lam, H, "dogrulama_" + taban + ".png")
    with open(taban + "_kalibrasyon.json", "w") as fp:
        json.dump({"lam": lam, "H": H.tolist(), "px": [w, h], "rms_m": rms,
                   "uzunluk": UZUNLUK, "genislik": GENISLIK}, fp, indent=2)
    print("Yazildi:", taban + "_kalibrasyon.json", "ve dogrulama_" + taban + ".png")
