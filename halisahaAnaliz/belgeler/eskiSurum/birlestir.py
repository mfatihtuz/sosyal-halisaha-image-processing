"""Iki kamerayi birlestirir ve saha uzerinde tek bir kimlik katmani kurar.

Kamera takip kimlikleri (iz_id) guvenilmez: oyuncular ust uste bininca kopar.
Burada onlar atilir. Her an iki kameranin tespitleri saha koordinatinda
birlestirilir, sonra hiz tahmini + forma rengi ile kalici oyuncu kimlikleri
yurutulur. Oyuncu goruntuden cikarsa kimligi SILINMEZ: tahminle devam eder ve
tekrar gorununce ayni kimlige baglanir.

    python birlestir.py kamera1_izler.csv kamera2_izler.csv
    python birlestir.py kamera1_izler.csv kamera2_izler.csv --oyuncu 14   # kadroyu sabitle
    python birlestir.py k1.csv k2.csv --oyuncu 14 --yelek 3,5,7,9,11,13   # yelekliler elle
    python birlestir.py --selftest

Cikti: birlesik.csv  ->  t_s, oyuncu, x_m, y_m, takim, kaynak, tahmin
  kaynak: 1, 2 veya 12 (iki kamera birden)      tahmin: 1 ise gozlem yok, kestirim
"""
import csv
import sys
from collections import defaultdict

import numpy as np
from scipy.optimize import linear_sum_assignment

ESLESME_M = 2.0      # iki kameranin ayni kisiyi gosterme esigi (olculen medyan 0.85 m)
KAPI_M = 1.8         # bir kimligin bir karede atlayabilecegi azami mesafe. KAPIYA renk KATILMAZ:
                     # ayni formali oyuncularda renk 0 oldugu icin kapiyi genisletir ve
                     # kimlik 4 m otedeki yanlis oyuncuyu kapardi.
KAYIP_SN = 8.0       # bu kadar sure gorunmezse kimlik pasife alinir
RENK_AGIRLIK = 1.0   # renk sadece kapi ICINDE ayirt edici olarak kullanilir
AZAMI_HIZ = 9.0      # m/s, hiz kestirimini gurultuye karsi sinirlar
DIK_SN = 12.0        # biten bir parca ile baslayan parca arasindaki azami bosluk
DIK_M = 14.0         # dikis icin azami konum sapmasi (ust sinir)
DOYGUN_ESIK = 60.0   # bu doygunlugun ustu "renkli forma", alti beyaz/gri/siyah sayilir
DIK_HIZ = 6.0        # dikisin ima ettigi azami hiz. Sabit mesafe esigi yerine bu kullanilir:
                     # 1 sn boslukta 14 m atlamak imkansiz, 12 sn boslukta gayet mumkun.


def oku(yol):
    kare = defaultdict(list)
    for s in csv.DictReader(open(yol)):
        kare[round(float(s["t_s"]), 2)].append(
            (float(s["x_m"]), float(s["y_m"]), int(float(s["h"])), int(float(s["s"])),
             float(s.get("u_px", -1)), float(s.get("v_px", -1)),
             float(s.get("g_px", -1)), float(s.get("y_px", -1))))
    return kare


def _renk_vek(h, s):
    """Ton dairesel; sat ile agirliklandirilmis birim vektor."""
    a = np.deg2rad(np.asarray(h, float) * 2.0)
    w = np.asarray(s, float) / 255.0
    return np.stack([np.cos(a) * w, np.sin(a) * w], axis=-1)


def kaynastir(a, b):
    """Ayni andaki iki kamera tespitini saha uzerinde tek listeye indirger.

    Her birlesik nokta, HANGI kameranin HANGI pikselinden geldigini yaninda tasir.
    Kimlik kartlari bu bilgiyi kullanir; kartta yeniden tespit yapip tahminle
    eslestirmek gerekmez, dolayisiyla iki kamerada ayni kisiye farkli etiket
    yazilmasi imkansiz hale gelir.
    """
    def kutu(p):
        return tuple(p[4:8]) if len(p) > 7 else (-1.0, -1.0, -1.0, -1.0)

    if not a:
        return [((p[0], p[1], p[2], p[3], (-1.0, -1.0, -1.0, -1.0), kutu(p)), 2) for p in b]
    if not b:
        return [((p[0], p[1], p[2], p[3], kutu(p), (-1.0, -1.0, -1.0, -1.0)), 1) for p in a]
    A, B = np.array(a, float), np.array(b, float)
    d = np.linalg.norm(A[:, None, :2] - B[None, :, :2], axis=2)
    ai, bi = linear_sum_assignment(d)
    cikti, kullanildi_a, kullanildi_b = [], set(), set()
    for i, j in zip(ai, bi):
        if d[i, j] <= ESLESME_M:
            orta = (A[i] + B[j]) / 2.0
            iyi = A[i] if A[i][3] >= B[j][3] else B[j]      # renk: doygun olani daha bilgili
            cikti.append(((orta[0], orta[1], iyi[2], iyi[3],
                           kutu(a[i]), kutu(b[j])), 12))
            kullanildi_a.add(i)
            kullanildi_b.add(j)
    cikti += [((A[i][0], A[i][1], A[i][2], A[i][3], kutu(a[i]), (-1.0, -1.0, -1.0, -1.0)), 1)
              for i in range(len(A)) if i not in kullanildi_a]
    cikti += [((B[j][0], B[j][1], B[j][2], B[j][3], (-1.0, -1.0, -1.0, -1.0), kutu(b[j])), 2)
              for j in range(len(B)) if j not in kullanildi_b]
    return cikti


class Kimlik:
    sayac = 0

    def __init__(self, p, t):
        Kimlik.sayac += 1
        self.no = Kimlik.sayac
        self.k = np.array(p[:2], float)
        self.h = np.zeros(2)
        self.renk = _renk_vek(p[2], p[3])
        self.son = t
        self.n = 1

    def tahmin(self, dt):
        return self.k + self.h * min(dt, 0.5)

    def guncelle(self, p, t, dt):
        yeni = np.array(p[:2], float)
        if dt > 0:
            ham = np.clip((yeni - self.k) / dt, -AZAMI_HIZ, AZAMI_HIZ)
            self.h = 0.8 * self.h + 0.2 * ham
        self.k = yeni
        self.renk = 0.95 * self.renk + 0.05 * _renk_vek(p[2], p[3])
        self.son = t
        self.n += 1


def yurut_sabit(kareler, n=None, kapi=3.5):
    """SABIT KADROLU takip: kimlik dogmaz, olmez, sadece atanir.

    Fuzyon her karede dogru sayida kisi buluyor (medyan 14). Sorun kimliklerin
    surekli yeniden dogmasi. Burada n yuva bir kez acilir ve her kare bu yuvalara
    atama yapilir; gozlem bulunamayan yuva tahminle yurur, fazla gozlem atilir.
    Sonuc: tam olarak n oyuncu, %100 zaman kapsamasi, sifir parcalanma.

    Takas riski kaybolmaz - ama parcalanma kaybolur, ki kisi bazli analizi
    imkansiz kilan asil sorun oydu.
    """
    zaman = sorted(kareler)
    sayilar = [len(kareler[t]) for t in zaman]
    if n is None:
        n = int(np.median(sayilar))
    baslangic = next((t for t in zaman if len(kareler[t]) >= n), zaman[0])

    yuva = [Kimlik(g[0], baslangic) for g in kareler[baslangic][:n]]
    for i, k in enumerate(yuva, 1):
        k.no = i

    satir, onceki = [], None
    for t in zaman:
        if t < baslangic:
            continue
        dt = (t - onceki) if onceki is not None else 0.1
        onceki = t
        gozlem = kareler[t]
        T = np.array([k.tahmin(t - k.son) for k in yuva])

        eslesen = {}
        if gozlem:
            G = np.array([g[0][:2] for g in gozlem], float)
            uzak = np.linalg.norm(T[:, None] - G[None], axis=2)
            gr = _renk_vek([g[0][2] for g in gozlem], [g[0][3] for g in gozlem])
            bedel = uzak + RENK_AGIRLIK * np.linalg.norm(
                np.array([k.renk for k in yuva])[:, None] - gr[None], axis=2)
            bedel[uzak > kapi] = 1e6
            for i, j in zip(*linear_sum_assignment(bedel)):
                if uzak[i, j] <= kapi:
                    eslesen[i] = j

        for i, k in enumerate(yuva):
            if i in eslesen:
                g = gozlem[eslesen[i]]
                k.guncelle(g[0], t, dt)
                bos = (-1.0, -1.0, -1.0, -1.0)
                px = (g[0][4], g[0][5]) if len(g[0]) > 5 else (bos, bos)
                satir.append([t, k.no, k.k[0], k.k[1], g[1], 0, g[0][2], g[0][3], *px])
            else:
                p = k.tahmin(t - k.son)
                k.k, k.h = p, k.h * 0.7          # gozlem yok: yavasla, savrulma
                bos = (-1.0, -1.0, -1.0, -1.0)
                satir.append([t, k.no, p[0], p[1], 0, 1, -1, -1, bos, bos])
    return satir


def takim_ata(satir, kareler=None, yaricap=45.0, denge=True):
    """Takim ayrimi: renk uzayinda YOGUN kumeyi bul.

    Yelekli takim tek bir renkte, yani renk uzayinda SIKI bir kume olusturur.
    Serbest takim ise dagiliktir (beyaz, gri, siyah, rastgele renkler). O yuzden
    esikle bolmek yerine en yogun kume aranir; icinde kalanlar yelekli sayilir.
    Ozellik: doygunlukla olceklenmis dairesel ton vektoru -> beyaz/gri merkeze
    yakin duser, renkli formalar cepere.
    """
    prof = defaultdict(list)
    for r in satir:
        if r[5] or len(r) < 8 or r[7] < 0:
            continue
        prof[r[1]].append((r[6], r[7]))
    ozet = {no: (float(np.median([h for h, _ in v])), float(np.median([s for _, s in v])))
            for no, v in prof.items() if len(v) >= 8}
    if len(ozet) < 4:
        return {no: -1 for no in prof}

    isim = list(ozet)
    aci = np.deg2rad(np.array([ozet[n][0] for n in isim]) * 2.0)
    doy = np.array([ozet[n][1] for n in isim])
    V = np.stack([doy * np.cos(aci), doy * np.sin(aci)], axis=1)

    # en yogun merkez: her adayin komsu sayisi, ardindan ortalama kaydirma
    komsu = [(np.linalg.norm(V - v, axis=1) <= yaricap).sum() for v in V]
    merkez = V[int(np.argmax(komsu))]
    for _ in range(20):
        icinde = np.linalg.norm(V - merkez, axis=1) <= yaricap
        if not icinde.any():
            break
        yeni_m = V[icinde].mean(axis=0)
        if np.allclose(yeni_m, merkez, atol=0.5):
            break
        merkez = yeni_m

    uzaklik = np.linalg.norm(V - merkez, axis=1)
    if denge:
        # Sabit kadroda takim buyuklukleri esittir. Renk bu goruntude 7/7 ayrimini
        # tek basina yapamiyor (beyaz forma salon isigindan maviye caliyor), o yuzden
        # yelek merkezine en yakin yarisi yelekli sayilir. Yanlis etiket olabilir ama
        # her oyuncu isimlendirilir; oyuncu bazli haritalar etiketleme hatasindan
        # etkilenmez, sadece takim gruplamasi etkilenir.
        sira = np.argsort(uzaklik)
        yelek = np.zeros(len(isim), bool)
        yelek[sira[:len(isim) // 2]] = True
    else:
        yelek = uzaklik <= yaricap
    sonuc = {n: (1 if y else 0) for n, y in zip(isim, yelek)}
    sonuc.update({n: -1 for n in prof if n not in ozet})
    return sonuc


def isimlendir(satir, takim, yelek=None):
    """Oyuncu etiketleri.

    Numaralandirma saha boyunca medyan konuma gore ve TAKIMDAN BAGIMSIZ yapilir,
    boylece takim atamasi degisince numaralar kaymaz.

    yelek verilmediyse etiketler P1..Pn olur: takim iddiasinda bulunulmaz, cunku
    otomatik takim ayrimi bu goruntude guvenilir degil (salon isigi beyaz formayi
    maviye caliyor). Kullanici --yelek ile yelekli oyuncularin numaralarini
    verdiginde etiketler X (yelekli) ve Y (serbest) olur.
    """
    konum = defaultdict(list)
    for r in satir:
        konum[r[1]].append(r[2])
    sira = sorted(konum, key=lambda n: np.median(konum[n]))
    no_of = {no: i + 1 for i, no in enumerate(sira)}

    if not yelek:
        return {no: "P%d" % i for no, i in no_of.items()}, {no: -1 for no in no_of}

    yelek = set(yelek)
    yeni_takim = {no: (1 if i in yelek else 0) for no, i in no_of.items()}
    ad, sayac = {}, {0: 0, 1: 0}
    for no in sira:
        t = yeni_takim[no]
        sayac[t] += 1
        ad[no] = "%s%d" % ("X" if t else "Y", sayac[t])
    return ad, yeni_takim


def renk_tablosu(satir, takim, ad):
    """Teshis icin: her kimligin ton/doygunluk profili ve takim karari."""
    prof = defaultdict(list)
    for r in satir:
        if not r[5] and len(r) > 7 and r[7] >= 0:
            prof[r[1]].append((r[6], r[7]))
    sure = defaultdict(list)
    for r in satir:
        sure[r[1]].append(r[0])
    sirali = sorted(prof, key=lambda n: -(max(sure[n]) - min(sure[n])))[:24]
    print("  ad   kimlik  sure  gozlem  ton(derece)  doygunluk  takim")
    for no in sirali:
        A = np.array(prof[no])
        print("  %-4s %5d  %4.0f  %6d  %10.0f  %9.0f  %5s"
              % (ad.get(no, "-"), no, max(sure[no]) - min(sure[no]), len(A),
                 np.median(A[:, 0]) * 2, np.median(A[:, 1]),
                 "yelek" if takim.get(no) == 1 else "serbest"))


def rapor(satir):
    sure = defaultdict(list)
    for t, no, *_ in satir:
        sure[no].append(t)
    uzun = sorted(((max(v) - min(v), no, len(v)) for no, v in sure.items()), reverse=True)
    toplam = max(t for t, *_ in satir) - min(t for t, *_ in satir)
    print("kimlik sayisi: %d   pencere: %.0f sn" % (len(sure), toplam))
    print("pencerenin %%90'indan fazlasini kapsayan kimlik: %d"
          % sum(1 for s, _, _ in uzun if s > 0.9 * toplam))
    print("en uzun 16 kimlik (sure sn / gozlem):")
    print("   " + "  ".join("%.0f/%d" % (s, n) for s, _, n in uzun[:16]))
    tahmin = sum(1 for r in satir if r[5])
    print("tahminle doldurulan satir orani: %.1f%%" % (100.0 * tahmin / len(satir)))


def selftest():
    # 14 kisi rastgele yuruyor; biri 20 sn boyunca hic gorunmuyor
    rng = np.random.default_rng(0)
    n, adim = 14, 0.1
    k = rng.uniform([2, 2], [48, 28], (n, 2))
    h = rng.normal(0, 1.2, (n, 2))
    renk = [(20, 200) if i < 7 else (100, 30) for i in range(n)]
    kareler = {}
    for s_ in range(600):
        t = round(900 + s_ * adim, 2)
        k = np.clip(k + h * adim, [0, 0], [50, 30])
        h += rng.normal(0, 0.25, (n, 2))
        bos = (-1.0, -1.0, -1.0, -1.0)
        kareler[t] = [((k[i, 0], k[i, 1], renk[i][0], renk[i][1], bos, bos), 12)
                      for i in range(n) if not (i == 3 and 100 <= s_ < 300)]

    sat = yurut_sabit(kareler, n)
    sure = defaultdict(list)
    for r in sat:
        sure[r[1]].append(r[0])
    assert len(sure) == n, len(sure)
    for v in sure.values():
        assert max(v) - min(v) > 59, max(v) - min(v)      # herkes tum pencereyi kapsamali

    tak = takim_ata(sat)
    kume = [sum(1 for v in tak.values() if v == c) for c in (0, 1)]
    assert min(kume) >= 5, tak                            # iki takim da makul buyuklukte
    print("selftest ok  (%d yuva, hepsi tam kapsama, takim ayrimi %d/%d)"
          % (len(sure), kume[0], kume[1]))


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        raise SystemExit

    n = int(sys.argv[sys.argv.index("--oyuncu") + 1]) if "--oyuncu" in sys.argv else None
    a, b = oku(sys.argv[1]), oku(sys.argv[2])
    kareler = {t: kaynastir(a.get(t, []), b.get(t, [])) for t in sorted(set(a) | set(b))}
    print("ortak zaman ekseni: %d kare, kare basina birlesik tespit: %.1f"
          % (len(kareler), np.mean([len(v) for v in kareler.values()])))

    satir = yurut_sabit(kareler, n)

    # Gercek gozlemi az olan yuva oyuncu degildir (kale arkasinda duran biri,
    # arada bir yakalanan bir yansima). Metriklerini uretmek yaniltici olur.
    gercek, toplam = defaultdict(int), defaultdict(int)
    for r in satir:
        toplam[r[1]] += 1
        gercek[r[1]] += 0 if r[5] else 1
    zayif = {k for k in toplam if gercek[k] / toplam[k] < 0.40}
    if zayif:
        print("elenen yuva: %d adet (gozleminin %%40'indan azi gercek tespit)" % len(zayif))
        satir = [r for r in satir if r[1] not in zayif]

    yelek = ([int(x) for x in sys.argv[sys.argv.index("--yelek") + 1].split(",")]
             if "--yelek" in sys.argv else None)
    takim = takim_ata(satir)
    ad, takim_son = isimlendir(satir, takim, yelek)
    if yelek:
        takim = takim_son
    rapor(satir)
    print("adlandirilan oyuncu: %d   isimli oyunculardaki gozlem orani: %.0f%%"
          % (len(ad), 100.0 * sum(1 for r in satir if r[1] in ad) / len(satir)))
    renk_tablosu(satir, takim, ad)
    if not yelek:
        print("\nTakim ayrimi otomatik yapilamiyor, etiketler P1..Pn olarak verildi.")
        print("Kimlik kartlarina bakip yelekli oyuncularin numaralarini soyle ver:")
        print("   --yelek 3,5,7,9,11,13   (P3, P5, ... yelekli demek)")
        print("Ondan sonra etiketler X (yelekli) ve Y (serbest) olur, numaralar kaymaz.")

    with open("birlesik.csv", "w", newline="") as fp:
        y = csv.writer(fp)
        y.writerow(["t_s", "oyuncu", "x_m", "y_m", "takim", "kaynak", "tahmin", "h", "s",
                    "u1", "v1", "g1", "y1", "u2", "v2", "g2", "y2"])
        for r in satir:
            t, no, x, yy, kay, tah = r[:6]
            h, sd = (r[6], r[7]) if len(r) > 7 else (-1, -1)
            k1 = r[8] if len(r) > 8 else (-1, -1, -1, -1)
            k2 = r[9] if len(r) > 9 else (-1, -1, -1, -1)
            y.writerow([round(t, 2), ad.get(no, "?%d" % no), round(x, 3), round(yy, 3),
                        takim.get(no, -1), kay, tah, h, sd,
                        *(round(v, 1) for v in k1), *(round(v, 1) for v in k2)])
    print("Yazildi: birlesik.csv")
