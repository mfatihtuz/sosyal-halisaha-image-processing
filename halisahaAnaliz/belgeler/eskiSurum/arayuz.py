"""Halisaha analizi - basit arayuz.

    python arayuz.py

Iki video, iki kalibrasyon ve bir dakika araligi secilir; takip, birlestirme,
isi haritasi ve oyuncu metrikleri sirayla calisir. Her kosu kendi klasorune
yazar, boylece farkli dakika araliklari birbirinin uzerine yazmaz.
"""
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, ttk

KOK = os.path.dirname(os.path.abspath(__file__))


def kalibrasyon_tahmin(video):
    aday = video.rsplit(".", 1)[0] + "_kalibrasyon.json"
    return aday if os.path.exists(aday) else ""


class Arayuz:
    def __init__(self, kok):
        kok.title("Halisaha Mac Analizi")
        kok.geometry("880x620")
        self.kuyruk = queue.Queue()
        self.alan = {}

        cerceve = ttk.Frame(kok, padding=12)
        cerceve.pack(fill="x")

        for i, (anahtar, etiket) in enumerate([
                ("video1", "Kamera 1 videosu"), ("kal1", "Kamera 1 kalibrasyon"),
                ("video2", "Kamera 2 videosu"), ("kal2", "Kamera 2 kalibrasyon")]):
            ttk.Label(cerceve, text=etiket).grid(row=i, column=0, sticky="w", pady=3)
            d = tk.StringVar()
            self.alan[anahtar] = d
            ttk.Entry(cerceve, textvariable=d, width=72).grid(row=i, column=1, padx=8)
            ttk.Button(cerceve, text="Sec...",
                       command=lambda a=anahtar: self.sec(a)).grid(row=i, column=2)

        alt = ttk.Frame(kok, padding=(12, 0))
        alt.pack(fill="x")
        self.basla = tk.StringVar(value="15")
        self.sure = tk.StringVar(value="60")
        self.saha = tk.StringVar(value="50x30")
        self.kadro = tk.StringVar(value="14")
        self.takim = tk.StringVar(value="Her ikisi")
        self.yelek = tk.StringVar(value="")
        self.video_cikti = tk.BooleanVar(value=True)
        for j, (etiket, degisken, gen) in enumerate([
                ("Baslangic (dakika)", self.basla, 8),
                ("Sure (saniye)", self.sure, 8),
                ("Saha olcusu (UxG metre)", self.saha, 10),
                ("Sahadaki kisi", self.kadro, 6)]):
            ttk.Label(alt, text=etiket).grid(row=0, column=j * 2, sticky="w", padx=(0, 6))
            ttk.Entry(alt, textvariable=degisken, width=gen).grid(row=0, column=j * 2 + 1, padx=(0, 18))

        ttk.Label(alt, text="Cikti takimi").grid(row=0, column=8, sticky="w", padx=(0, 6))
        ttk.Combobox(alt, textvariable=self.takim, width=20, state="readonly",
                     values=["Her ikisi", "Sadece X (yelekli)",
                             "Sadece Y (serbest)"]).grid(row=0, column=9)

        dugme = ttk.Frame(kok, padding=12)
        dugme.pack(fill="x")
        self.calistir_dugme = ttk.Button(dugme, text="Analizi baslat", command=self.baslat)
        self.calistir_dugme.pack(side="left")
        self.klasor_dugme = ttk.Button(dugme, text="Cikti klasorunu ac",
                                       command=self.klasoru_ac, state="disabled")
        self.klasor_dugme.pack(side="left", padx=8)
        self.durum = ttk.Label(dugme, text="hazir")
        self.durum.pack(side="left", padx=12)

        yl = ttk.Frame(kok, padding=(12, 0))
        yl.pack(fill="x")
        ttk.Label(yl, text="Yelekli oyuncu numaralari (once bos birak, kartlara bakip doldur)"
                  ).pack(side="left", padx=(0, 8))
        ttk.Entry(yl, textvariable=self.yelek, width=34).pack(side="left")
        ttk.Label(yl, text="orn: 3,5,7,9,11,13", foreground="#777").pack(side="left", padx=8)
        ttk.Checkbutton(yl, text="Isaretli video uret (yavas ama takibi izlemeni saglar)",
                        variable=self.video_cikti).pack(side="left", padx=16)

        self.gunluk = tk.Text(kok, height=22, bg="#111", fg="#ddd", insertbackground="#ddd")
        self.gunluk.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.hedef = None
        kok.after(120, self.kuyrugu_isle)

    def sec(self, anahtar):
        tur = [("Video", "*.mp4 *.mkv *.avi *.mov")] if "video" in anahtar else [("JSON", "*.json")]
        yol = filedialog.askopenfilename(filetypes=tur + [("Tumu", "*.*")])
        if not yol:
            return
        self.alan[anahtar].set(yol)
        if anahtar == "video1" and not self.alan["kal1"].get():
            self.alan["kal1"].set(kalibrasyon_tahmin(yol))
        if anahtar == "video2" and not self.alan["kal2"].get():
            self.alan["kal2"].set(kalibrasyon_tahmin(yol))

    def yaz(self, metin):
        self.gunluk.insert("end", metin)
        self.gunluk.see("end")

    def kuyrugu_isle(self):
        while not self.kuyruk.empty():
            tur, veri = self.kuyruk.get()
            if tur == "log":
                self.yaz(veri)
            elif tur == "durum":
                self.durum.config(text=veri)
            elif tur == "bitti":
                self.calistir_dugme.config(state="normal")
                self.klasor_dugme.config(state="normal")
        self.gunluk.after(120, self.kuyrugu_isle)

    def klasoru_ac(self):
        if not self.hedef:
            return
        if sys.platform == "win32":
            os.startfile(self.hedef)
        else:
            subprocess.Popen(["xdg-open", self.hedef])

    def baslat(self):
        eksik = [a for a in ("video1", "kal1", "video2", "kal2") if not self.alan[a].get()]
        if eksik:
            self.yaz("Eksik alan: %s\n" % ", ".join(eksik))
            return
        self.calistir_dugme.config(state="disabled")
        self.klasor_dugme.config(state="disabled")
        self.gunluk.delete("1.0", "end")
        threading.Thread(target=self.akis, daemon=True).start()

    def komut(self, argumanlar, klasor):
        self.kuyruk.put(("log", "\n$ %s\n" % " ".join(os.path.basename(a) for a in argumanlar)))
        p = subprocess.Popen([sys.executable] + argumanlar, cwd=klasor,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", bufsize=1)
        for satir in p.stdout:
            self.kuyruk.put(("log", satir))
        return p.wait()

    def akis(self):
        try:
            dk = float(self.basla.get())
            sure = float(self.sure.get())
        except ValueError:
            self.kuyruk.put(("log", "Baslangic ve sure sayi olmali.\n"))
            self.kuyruk.put(("bitti", None))
            return

        hedef = os.path.join(os.path.dirname(self.alan["video1"].get()),
                             "analiz_dk%g_%gs" % (dk, sure))
        os.makedirs(hedef, exist_ok=True)
        self.hedef = hedef
        self.kuyruk.put(("log", "Cikti klasoru: %s\n" % hedef))

        ortak = ["--basla", str(dk * 60), "--sure", str(sure), "--saha", self.saha.get()]
        tk_sec = {"Her ikisi": "ikisi", "Sadece X (yelekli)": "x",
                  "Sadece Y (serbest)": "y"}[self.takim.get()]
        adimlar = [
            ("Kamera 1 takip", [os.path.join(KOK, "takip.py"), self.alan["video1"].get(),
                                self.alan["kal1"].get(), "--cikti", "k1_izler.csv"] + ortak),
            ("Kamera 2 takip", [os.path.join(KOK, "takip.py"), self.alan["video2"].get(),
                                self.alan["kal2"].get(), "--cikti", "k2_izler.csv"] + ortak),
            ("Birlestirme ve kimlik", [os.path.join(KOK, "birlestir.py"),
                                       "k1_izler.csv", "k2_izler.csv",
                                       "--oyuncu", self.kadro.get()]
                                      + (["--yelek", self.yelek.get()]
                                         if self.yelek.get().strip() else [])),
            ("Isi haritalari", [os.path.join(KOK, "harita.py"), "birlesik.csv",
                                "--takim", tk_sec]),
            ("Oyuncu metrikleri", [os.path.join(KOK, "metrik.py"), "birlesik.csv",
                                   "--takim", tk_sec]),
            ("Metrik tablosu", [os.path.join(KOK, "tablo.py"), "oyuncu_metrik.csv"]),
            ("Kimlik kartlari", [os.path.join(KOK, "kimlik_kart.py"),
                                 self.alan["video1"].get(), self.alan["video2"].get(),
                                 "--takim", tk_sec]),
        ]
        if self.video_cikti.get():
            for kamera, anahtar in ((1, "video1"), (2, "video2")):
                adimlar.append(("Isaretli video - kamera %d" % kamera,
                                [os.path.join(KOK, "video_cikti.py"),
                                 self.alan[anahtar].get(), str(kamera), "--takim", tk_sec]))
        for ad, arg in adimlar:
            self.kuyruk.put(("durum", ad + "..."))
            if self.komut(arg, hedef) != 0:
                self.kuyruk.put(("log", "\n>>> '%s' adiminda hata. Durduruldu.\n" % ad))
                self.kuyruk.put(("durum", "hata"))
                self.kuyruk.put(("bitti", None))
                return
        self.kuyruk.put(("durum", "tamamlandi"))
        self.kuyruk.put(("log", "\nBitti. isi_takim.png, isi_oyuncu.png, oyuncu_tablo.png, "
                                 "kart_*.png, takip_*.mp4 ve oyuncu_metrik.csv hazir.\n"))
        self.kuyruk.put(("bitti", None))


if __name__ == "__main__":
    kok = tk.Tk()
    Arayuz(kok)
    kok.mainloop()
