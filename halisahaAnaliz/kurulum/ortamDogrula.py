"""Ortam denetimi: her sey kurulu ve calisiyor mu, tek raporda.

Onceki surumde kurulum iki kez saatler kaybettirdi:
  * cu121 indeksinde Python 3.14 paketi yok -> "No matching distribution found for torch"
  * torch ve torchvision ayri komutlarla kurulunca
    "RuntimeError: operator torchvision::nms does not exist"

Ikisi de kurulumdan sonra degil, ILK ANALIZ KOSUSUNUN ORTASINDA patliyor. Bu
betik onlari bastan yakalar ve ne yapilmasi gerektigini soyler.

    python ortamDogrula.py
    python ortamDogrula.py --hizli    # model indirmeyi ve GPU olcumunu atla
"""
from __future__ import annotations

import importlib
import platform
import shutil
import subprocess
import sys
import time

# (icebalen ad, gorunen ad, zorunlu mu, eksikse ne yapmali)
PAKETLER = [
    ("numpy", "numpy", True, "pip install numpy"),
    ("scipy", "scipy", True, "pip install scipy"),
    ("pyarrow", "pyarrow", True, "pip install pyarrow"),
    ("networkx", "networkx", True, "pip install networkx"),
    ("cv2", "opencv-python", True, "pip install opencv-python"),
    ("matplotlib", "matplotlib", True, "pip install matplotlib"),
    ("torch", "torch", True, "kurulumBetigi.ps1 calistir (torch + torchvision AYNI komutta)"),
    ("torchvision", "torchvision", True, "kurulumBetigi.ps1 calistir"),
    ("ultralytics", "ultralytics", True, "pip install ultralytics"),
    ("fastapi", "fastapi", True, "pip install fastapi uvicorn"),
    ("uvicorn", "uvicorn", True, "pip install fastapi uvicorn"),
]

YESIL, SARI, KIRMIZI, SIFIRLA = "\033[92m", "\033[93m", "\033[91m", "\033[0m"
if platform.system() == "Windows":
    try:                                       # Windows 10+ ANSI destegi
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        YESIL = SARI = KIRMIZI = SIFIRLA = ""


class Rapor:
    def __init__(self) -> None:
        self.satirlar: list[tuple[str, str, str, str]] = []
        self.hata = 0
        self.uyari = 0

    def ekle(self, durum: str, baslik: str, deger: str, oneri: str = "") -> None:
        self.satirlar.append((durum, baslik, deger, oneri))
        if durum == "hata":
            self.hata += 1
        elif durum == "uyari":
            self.uyari += 1

    def yazdir(self) -> None:
        simge = {"ok": (YESIL, "OK  "), "uyari": (SARI, "DIKKAT"), "hata": (KIRMIZI, "HATA")}
        print()
        for durum, baslik, deger, oneri in self.satirlar:
            renk, etiket = simge[durum]
            print("  %s%-6s%s %-26s %s" % (renk, etiket, SIFIRLA, baslik, deger))
            if oneri:
                print("         %s-> %s%s" % (SARI, oneri, SIFIRLA))
        print()
        if self.hata:
            print("%s%d hata, %d uyari. Analiz calistirilamaz.%s" % (KIRMIZI, self.hata, self.uyari, SIFIRLA))
        elif self.uyari:
            print("%s%d uyari. Analiz calisir ama yavas olabilir.%s" % (SARI, self.uyari, SIFIRLA))
        else:
            print("%sOrtam hazir.%s" % (YESIL, SIFIRLA))


def _pythonDenetle(r: Rapor) -> None:
    s = sys.version_info
    metin = "%d.%d.%d (%s)" % (s.major, s.minor, s.micro, platform.python_implementation())
    if s < (3, 10):
        r.ekle("hata", "Python", metin, "Python 3.12 gerekli; 3.10 altinda calismaz.")
    elif s >= (3, 14):
        r.ekle("uyari", "Python", metin,
               "3.14 cok yeni; torch/ultralytics tekerlekleri gecikebilir. 3.12 onerilir.")
    else:
        r.ekle("ok", "Python", metin)


def _paketleriDenetle(r: Rapor) -> dict[str, object]:
    yuklenen: dict[str, object] = {}
    for icAd, gorunenAd, zorunlu, oneri in PAKETLER:
        try:
            m = importlib.import_module(icAd)
            yuklenen[icAd] = m
            r.ekle("ok", gorunenAd, getattr(m, "__version__", "kurulu"))
        except Exception as e:
            r.ekle("hata" if zorunlu else "uyari", gorunenAd, "KURULU DEGIL (%s)" % type(e).__name__, oneri)
    return yuklenen


def _torchDenetle(r: Rapor, yuklenen: dict, hizli: bool) -> None:
    torch = yuklenen.get("torch")
    if torch is None:
        return

    if not torch.cuda.is_available():
        r.ekle("hata", "CUDA", "kullanilamiyor",
               "GPU'suz tam mac ~40 kat yavas. cu128 indeksinden torch kur.")
        return

    ad = torch.cuda.get_device_name(0)
    bellek = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
    r.ekle("ok", "CUDA aygiti", "%s, %.1f GB" % (ad, bellek))
    if bellek < 6:
        r.ekle("uyari", "GPU bellegi", "%.1f GB" % bellek,
               "1920 cozunurlukte toplu isleme icin dar; ayarlar.tespit.topluBoyut dusurun.")

    # ASIL TEST: torchvision::nms gercekten cagrilabiliyor mu.
    # torch ile torchvision ayri surumlerden kurulursa import basarili olur ama
    # ILK TESPITTE patlar. Onceki surumde tam olarak bu yasandi.
    if "torchvision" in yuklenen:
        try:
            import torch as t
            import torchvision
            kutular = t.tensor([[0.0, 0.0, 10.0, 10.0], [1.0, 1.0, 11.0, 11.0]])
            skor = t.tensor([0.9, 0.8])
            torchvision.ops.nms(kutular, skor, 0.5)
            r.ekle("ok", "torchvision::nms", "calisiyor")
        except Exception as e:
            r.ekle("hata", "torchvision::nms", str(e)[:60],
                   "torch ve torchvision'i AYNI komutta ve ayni indeksten kurun.")

    if hizli:
        return

    try:
        import torch as t
        x = t.randn(2048, 2048, device="cuda", dtype=t.float16)
        t.cuda.synchronize()
        basla = time.perf_counter()
        for _ in range(30):
            x = x @ x.T / 100.0
        t.cuda.synchronize()
        sure = time.perf_counter() - basla
        tflops = 30 * 2 * 2048 ** 3 / sure / 1e12
        r.ekle("ok", "FP16 hesap", "%.1f TFLOPS" % tflops)
    except Exception as e:
        r.ekle("uyari", "FP16 hesap", "olculemedi: %s" % str(e)[:40])


def _ffmpegDenetle(r: Rapor) -> None:
    yol = shutil.which("ffmpeg")
    if not yol:
        r.ekle("uyari", "ffmpeg", "PATH'te yok",
               "Isaretli video ve klip uretimi icin gerekli. https://ffmpeg.org")
        return
    try:
        c = subprocess.run([yol, "-version"], capture_output=True, text=True, timeout=10)
        surum = c.stdout.split("\n")[0].replace("ffmpeg version ", "")[:40]
        nvenc = "h264_nvenc" in subprocess.run([yol, "-encoders"], capture_output=True,
                                               text=True, timeout=10).stdout
        r.ekle("ok", "ffmpeg", "%s%s" % (surum, "  [NVENC var]" if nvenc else ""))
        if not nvenc:
            r.ekle("uyari", "NVENC", "yok", "Video uretimi CPU'da kodlanir, yavas olur.")
    except Exception as e:
        r.ekle("uyari", "ffmpeg", "calistirilamadi: %s" % str(e)[:40])


# Selftest'i olan tum cekirdek modulleri. Yenisi eklendiginde buraya da eklenir.
SELFTEST_MODULLERI = [
    "cekirdek.veriSemasi",
    "cekirdek.ayarlar",
    "cekirdek.lensModeli",
    "cekirdek.kameraKaynastirma",
    "cekirdek.kimlikCozucu",
    "sentetikSahne",
    "puanla",
]


def _cekirdekDenetle(r: Rapor, hizli: bool) -> None:
    """Kendi modullerimizin selftest'leri geciyor mu.

    Bunlar GPU ve video gerektirmez; ortam bozuldugunda ilk burada belli olur.
    """
    import contextlib
    import io
    from pathlib import Path

    kok = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(kok))
    sys.path.insert(0, str(kok / "testler"))

    # Sentetik sahne uretimi birkac saniye surer; hizli modda atlanir.
    yavaslar = {"cekirdek.kameraKaynastirma", "cekirdek.kimlikCozucu",
                "sentetikSahne", "puanla"}

    for modulYolu in SELFTEST_MODULLERI:
        kisaAd = modulYolu.split(".")[-1]
        if hizli and modulYolu in yavaslar:
            r.ekle("ok", kisaAd, "atlandi (--hizli)")
            continue
        try:
            m = importlib.import_module(modulYolu)
            with contextlib.redirect_stdout(io.StringIO()):
                m.selftest()
            r.ekle("ok", kisaAd, "selftest gecti")
        except Exception as e:
            r.ekle("hata", kisaAd, "selftest BASARISIZ: %s" % str(e)[:60])


def calistir(hizli: bool = False) -> int:
    print("Halisaha Analizi -- ortam denetimi")
    print("%s %s" % (platform.system(), platform.release()))
    r = Rapor()
    _pythonDenetle(r)
    yuklenen = _paketleriDenetle(r)
    _torchDenetle(r, yuklenen, hizli)
    _ffmpegDenetle(r)
    _cekirdekDenetle(r, hizli)
    r.yazdir()
    return 1 if r.hata else 0


if __name__ == "__main__":
    raise SystemExit(calistir(hizli="--hizli" in sys.argv))
