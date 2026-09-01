"""Tum veri tablolarinin TEK dogru kaynagi.

Onceki surumde su hata yasandi: `takip.py` satira sutun ekledi, basliga eklemedi;
`csv.DictReader` hicbir uyari vermeden sutunlari kaydirdi ve renk sutunundan kutu
genisligi okundu. Hata aylarca fark edilmedi -- teslim edilen `kamera1_izler.csv`
dosyasinda `g_px` ve `y_px` sutunlari hic yoktu, `birlestir.py` ise onlari
`.get("g_px", -1)` ile okuyup sessizce -1 aldi. Kimlik kartlarina ve isaretli
videoya bozuk kutu boyutu gitti.

Bu modul o hata sinifini yapisal olarak imkansiz kilar:

  1. Her tablo burada BIR KEZ tanimlanir. Yazan da okuyan da bu tanimi kullanir.
  2. Disk formati Parquet: sutun adlari ve tipleri dosyanin icinde gomulu. Sutun
     kaymasi diye bir sey olamaz, cunku sutunlar sirayla degil ADIYLA okunur.
  3. `yaz()` eksik veya fazla sutunu yazmayi REDDEDER. Sessiz kayma yerine
     gurultulu hata.

Kendi kendini test eder:

    python veriSemasi.py --selftest
"""
from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

# ----------------------------------------------------------------- tip esleme

# Kisa tip kodlari; modulun okunabilirligi icin pyarrow tipleri yerine bunlar
# kullanilir, pyarrow'a cevrim tek yerde yapilir.
TIPLER = {
    "f32": ("float32", np.float32),
    "f64": ("float64", np.float64),
    "i32": ("int32", np.int32),
    "i64": ("int64", np.int64),
    "bool": ("bool_", np.bool_),
    "str": ("string", object),
}


@dataclass(frozen=True)
class Sutun:
    """Bir tablo sutunu: adi, tipi ve ne anlama geldigi."""

    ad: str
    tip: str
    aciklama: str

    def __post_init__(self) -> None:
        if self.tip not in TIPLER:
            raise ValueError("Bilinmeyen tip %r (sutun %r)" % (self.tip, self.ad))

    @property
    def numpyTipi(self):
        return TIPLER[self.tip][1]


@dataclass(frozen=True)
class Tablo:
    """Bir veri tablosunun tam tanimi."""

    ad: str
    aciklama: str
    sutunlar: tuple[Sutun, ...]

    @property
    def adlar(self) -> tuple[str, ...]:
        return tuple(s.ad for s in self.sutunlar)

    def sutun(self, ad: str) -> Sutun:
        for s in self.sutunlar:
            if s.ad == ad:
                return s
        raise KeyError("%s tablosunda %r sutunu yok" % (self.ad, ad))

    def bosVeri(self) -> dict[str, list]:
        """Sutun adlariyla anahtarlanmis bos listeler; satir toplarken kullanilir."""
        return {s.ad: [] for s in self.sutunlar}

    def pyarrowSemasi(self):
        import pyarrow as pa

        return pa.schema([pa.field(s.ad, getattr(pa, TIPLER[s.tip][0])()) for s in self.sutunlar])

    # ------------------------------------------------------------- dogrulama

    def dogrula(self, veri: Mapping[str, Sequence]) -> None:
        """Sutun kumesinin BIREBIR ayni oldugunu ve uzunluklarin esit oldugunu dogrular.

        Eksik sutun da fazla sutun da hatadir. Onceki surumde eksik sutun sessizce
        varsayilan degere dusuyordu; burada yazma islemi durur.
        """
        beklenen, gelen = set(self.adlar), set(veri)
        eksik, fazla = sorted(beklenen - gelen), sorted(gelen - beklenen)
        if eksik or fazla:
            parcalar = []
            if eksik:
                parcalar.append("eksik sutun: %s" % ", ".join(eksik))
            if fazla:
                parcalar.append("taninmayan sutun: %s" % ", ".join(fazla))
            raise ValueError("%s tablosu semaya uymuyor -- %s" % (self.ad, "; ".join(parcalar)))

        uzunluklar = {ad: len(veri[ad]) for ad in self.adlar}
        benzersiz = set(uzunluklar.values())
        if len(benzersiz) > 1:
            bozuk = {a: n for a, n in uzunluklar.items() if n != max(benzersiz, key=list(uzunluklar.values()).count)}
            raise ValueError(
                "%s tablosunda sutun uzunluklari esit degil: %s" % (self.ad, bozuk or uzunluklar))


# ----------------------------------------------------------------- tablolar

TESPITLER = Tablo(
    ad="tespitler",
    aciklama="Kamera basina ham tespitler. Her satir bir karede bir kisi.",
    sutunlar=(
        Sutun("t_s", "f64", "Videonun mutlak zamani (saniye). Iki kamera bu eksende hizalanir."),
        Sutun("kareNo", "i64", "Videonun gercek kare indisi. Isaretli video tam bu kareye cizer."),
        Sutun("kamera", "i32", "1 veya 2."),
        Sutun("x_m", "f32", "Saha koordinati, kale A'dan uzunluk yonunde metre."),
        Sutun("y_m", "f32", "Saha koordinati, kenar 1'den genislik yonunde metre."),
        Sutun("guven", "f32", "Tespit guven skoru (0-1)."),
        Sutun("u_px", "f32", "Ayak noktasinin yatay pikseli."),
        Sutun("v_px", "f32", "Ayak noktasinin dikey pikseli."),
        Sutun("kutuSol", "f32", "Kutunun sol kenari (piksel)."),
        Sutun("kutuUst", "f32", "Kutunun ust kenari (piksel)."),
        Sutun("kutuGen", "f32", "Kutu genisligi (piksel)."),
        Sutun("kutuYuk", "f32", "Kutu yuksekligi (piksel)."),
        Sutun("maskeAlan", "i32", "Segmentasyon maskesindeki piksel sayisi; 0 ise maske yok."),
        Sutun("ton", "f32", "Maske piksellerinin medyan tonu, 0-360 derece."),
        Sutun("doygunluk", "f32", "Maske piksellerinin medyan doygunlugu, 0-255."),
        Sutun("parlaklik", "f32", "Maske piksellerinin medyan parlakligi, 0-255."),
        Sutun("siyahlik", "f32", "Koyu VE doygunlugu dusuk piksellerin orani (0-1). Takim ayrimi buna dayanir."),
        Sutun("gommeIz", "i32", "Gorunum gommesi dizisindeki satir indisi; -1 ise gomme yok."),
    ),
)

PARCALAR = Tablo(
    ad="parcalar",
    aciklama="Supheye yer birakmayan kisa takip parcalari (tracklet). Global baglama bunlari birlestirir.",
    sutunlar=(
        Sutun("parcaId", "i32", "Parca kimligi."),
        Sutun("baslaT", "f64", "Parcanin ilk ornegi (saniye)."),
        Sutun("bitisT", "f64", "Parcanin son ornegi (saniye)."),
        Sutun("ornekSayisi", "i32", "Parcadaki gozlem sayisi."),
        Sutun("baslaX", "f32", "Ilk ornegin x konumu (metre)."),
        Sutun("baslaY", "f32", "Ilk ornegin y konumu (metre)."),
        Sutun("bitisX", "f32", "Son ornegin x konumu (metre)."),
        Sutun("bitisY", "f32", "Son ornegin y konumu (metre)."),
        Sutun("baslaHx", "f32", "Parcanin basindaki hiz, x bileseni (m/s)."),
        Sutun("baslaHy", "f32", "Parcanin basindaki hiz, y bileseni (m/s)."),
        Sutun("bitisHx", "f32", "Parcanin sonundaki hiz, x bileseni (m/s)."),
        Sutun("bitisHy", "f32", "Parcanin sonundaki hiz, y bileseni (m/s)."),
        Sutun("ton", "f32", "Parca boyunca medyan ton (derece)."),
        Sutun("doygunluk", "f32", "Parca boyunca medyan doygunluk."),
        Sutun("parlaklik", "f32", "Parca boyunca medyan parlaklik."),
        Sutun("siyahlik", "f32", "Parca boyunca medyan siyahlik orani."),
        Sutun("kesilmeSebebi", "str", "Parcanin neden kesildigi: belirsizlik / gozlemYok / son."),
    ),
)

OYUNCU_IZLERI = Tablo(
    ad="oyuncuIzleri",
    aciklama="Hattin ana ciktisi. Her satir bir karede bir oyuncunun konumu ve iki kameradaki pikselleri.",
    sutunlar=(
        Sutun("t_s", "f64", "Mutlak video zamani (saniye)."),
        Sutun("kareNo", "i64", "Kamera 1'in kare indisi."),
        Sutun("oyuncuId", "i32", "Oyuncunun kalici sayisal kimligi."),
        Sutun("ad", "str", "Oyuncunun adi. Kadro girilmemisse O1..On."),
        Sutun("takim", "i32", "1 yelekli, 0 siyah forma, -1 bilinmiyor."),
        Sutun("x_m", "f32", "Saha konumu, uzunluk yonu (metre)."),
        Sutun("y_m", "f32", "Saha konumu, genislik yonu (metre)."),
        Sutun("kaynak", "i32", "12 iki kamera, 1 veya 2 tek kamera, 0 gozlem yok."),
        Sutun("dolgu", "bool", "True ise konum gozlemden degil duzlestiriciden geliyor."),
        Sutun("supheSkoru", "f32", "0-1. Yuksekse bu an duzeltme panelinde ust sirada gosterilir."),
        Sutun("parcaId", "i32", "Bu ornegin geldigi parca; duzeltme paneli parca butununu takaslar."),
        Sutun("k1_u", "f32", "Kamera 1 ayak noktasi, yatay piksel. Gozlem yoksa -1."),
        Sutun("k1_v", "f32", "Kamera 1 ayak noktasi, dikey piksel. Gozlem yoksa -1."),
        Sutun("k1_sol", "f32", "Kamera 1 kutu sol kenari. Gozlem yoksa -1."),
        Sutun("k1_ust", "f32", "Kamera 1 kutu ust kenari. Gozlem yoksa -1."),
        Sutun("k1_gen", "f32", "Kamera 1 kutu genisligi. Gozlem yoksa -1."),
        Sutun("k1_yuk", "f32", "Kamera 1 kutu yuksekligi. Gozlem yoksa -1."),
        Sutun("k2_u", "f32", "Kamera 2 ayak noktasi, yatay piksel. Gozlem yoksa -1."),
        Sutun("k2_v", "f32", "Kamera 2 ayak noktasi, dikey piksel. Gozlem yoksa -1."),
        Sutun("k2_sol", "f32", "Kamera 2 kutu sol kenari. Gozlem yoksa -1."),
        Sutun("k2_ust", "f32", "Kamera 2 kutu ust kenari. Gozlem yoksa -1."),
        Sutun("k2_gen", "f32", "Kamera 2 kutu genisligi. Gozlem yoksa -1."),
        Sutun("k2_yuk", "f32", "Kamera 2 kutu yuksekligi. Gozlem yoksa -1."),
    ),
)

OYUNCU_METRIKLERI = Tablo(
    ad="oyuncuMetrikleri",
    aciklama="Oyuncu basina tek satir ozet. Dashboard tablosu ve paylasim gorseli bunu okur.",
    sutunlar=(
        Sutun("ad", "str", "Oyuncu adi."),
        Sutun("takim", "i32", "1 yelekli, 0 siyah forma, -1 bilinmiyor."),
        Sutun("rol", "str", "kaleci / defans / orta saha / forvet."),
        Sutun("sureSn", "f32", "Analiz penceresinde sahada gecen sure."),
        Sutun("veriKalitesi", "f32", "Orneklerin gercek gozlemden gelme orani (0-1)."),
        Sutun("mesafeM", "f32", "Toplam kosu mesafesi (metre)."),
        Sutun("ortHizKmh", "f32", "Ortalama hiz (km/s)."),
        Sutun("maksHizKmh", "f32", "En yuksek hiz, 98. yuzdelik (km/s)."),
        Sutun("sprintSayisi", "i32", "Sprint esigini asip minimum sure koruyan olay sayisi."),
        Sutun("sprintMesafesiM", "f32", "Sprint hizinin ustunde katedilen toplam mesafe."),
        Sutun("enUzunSprintM", "f32", "Tek seferde en uzun sprint mesafesi."),
        Sutun("yuksekTempoSn", "f32", "Yuksek tempo esiginin ustunde gecen sure."),
        Sutun("mesafeYurumeM", "f32", "Yurume bolgesinde katedilen mesafe."),
        Sutun("mesafeKosuM", "f32", "Kosu bolgesinde katedilen mesafe."),
        Sutun("mesafeYuksekM", "f32", "Yuksek tempo bolgesinde katedilen mesafe."),
        Sutun("mesafeSprintM", "f32", "Sprint bolgesinde katedilen mesafe."),
        Sutun("hizlanma", "i32", "Ani hizlanma olayi sayisi."),
        Sutun("yavaslama", "i32", "Ani yavaslama olayi sayisi."),
        Sutun("ortX", "f32", "Ortalama x konumu (metre)."),
        Sutun("ortY", "f32", "Ortalama y konumu (metre)."),
        Sutun("solYuzde", "f32", "Sahanin sol ucte birinde gecen zaman orani."),
        Sutun("ortaYuzde", "f32", "Sahanin orta ucte birinde gecen zaman orani."),
        Sutun("sagYuzde", "f32", "Sahanin sag ucte birinde gecen zaman orani."),
    ),
)

REFERANS = Tablo(
    ad="referans",
    aciklama="Elle dogrulanmis kesit. puanla.py otomatik ciktiyi buna karsi puanlar.",
    sutunlar=(
        Sutun("t_s", "f64", "Mutlak video zamani (saniye)."),
        Sutun("ad", "str", "Dogru oyuncu adi."),
        Sutun("x_m", "f32", "Dogru saha konumu, uzunluk yonu."),
        Sutun("y_m", "f32", "Dogru saha konumu, genislik yonu."),
    ),
)

TUM_TABLOLAR = (TESPITLER, PARCALAR, OYUNCU_IZLERI, OYUNCU_METRIKLERI, REFERANS)


# ----------------------------------------------------------------- okuma / yazma

def yaz(tablo: Tablo, veri: Mapping[str, Sequence], yol: str | Path) -> Path:
    """Sutunlu veriyi Parquet olarak yazar. Sema uymuyorsa yazmaz, hata verir."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    tablo.dogrula(veri)
    yol = Path(yol)
    yol.parent.mkdir(parents=True, exist_ok=True)

    diziler = []
    for s in tablo.sutunlar:
        ham = veri[s.ad]
        if s.tip == "str":
            diziler.append(pa.array([("" if d is None else str(d)) for d in ham], type=pa.string()))
        else:
            diziler.append(pa.array(np.asarray(ham, dtype=s.numpyTipi)))
    pq.write_table(pa.Table.from_arrays(diziler, schema=tablo.pyarrowSemasi()), yol, compression="zstd")
    return yol


def oku(tablo: Tablo, yol: str | Path) -> dict[str, np.ndarray]:
    """Parquet dosyasini okur ve semaya uydugunu dogrular.

    Sutunlar ADIYLA okunur; dosyadaki sira onemsizdir. Bir sutun eksikse burada
    yuksek sesle patlar -- sessizce varsayilan deger uretmez.
    """
    import pyarrow.parquet as pq

    pat = pq.read_table(yol)
    mevcut = set(pat.column_names)
    eksik = [a for a in tablo.adlar if a not in mevcut]
    if eksik:
        raise ValueError("%s dosyasinda %s tablosunun su sutunlari yok: %s"
                         % (yol, tablo.ad, ", ".join(eksik)))

    cikti = {}
    for s in tablo.sutunlar:
        sutunVerisi = pat.column(s.ad).to_pylist()
        if s.tip == "str":
            cikti[s.ad] = np.array([("" if d is None else str(d)) for d in sutunVerisi], dtype=object)
        else:
            cikti[s.ad] = np.asarray(sutunVerisi, dtype=s.numpyTipi)
    return cikti


def csvDisaAktar(tablo: Tablo, veri: Mapping[str, Sequence], yol: str | Path) -> Path:
    """Kullanicinin Excel'de acabilmesi icin CSV disa aktarimi.

    Ic formatimiz degil, sadece disa aktarim. Baslik semadan uretilir, elle yazilmaz.
    """
    tablo.dogrula(veri)
    yol = Path(yol)
    yol.parent.mkdir(parents=True, exist_ok=True)
    n = len(veri[tablo.adlar[0]])
    with open(yol, "w", newline="", encoding="utf-8-sig") as fp:
        yazici = csv.writer(fp)
        yazici.writerow(tablo.adlar)
        for i in range(n):
            yazici.writerow([veri[a][i] for a in tablo.adlar])
    return yol


def satirlardanSutunlara(tablo: Tablo, satirlar: Iterable[Mapping[str, Any]]) -> dict[str, list]:
    """Sozluk listesini sutunlu bicime cevirir; eksik anahtari sessizce doldurmaz."""
    veri = tablo.bosVeri()
    for i, satir in enumerate(satirlar):
        eksik = [a for a in tablo.adlar if a not in satir]
        if eksik:
            raise ValueError("%d. satirda eksik alan: %s" % (i, ", ".join(eksik)))
        for a in tablo.adlar:
            veri[a].append(satir[a])
    return veri


def semaOzeti() -> str:
    """Belgeler icin okunabilir sema dokumu."""
    satirlar = []
    for t in TUM_TABLOLAR:
        satirlar.append("%s -- %s" % (t.ad, t.aciklama))
        for s in t.sutunlar:
            satirlar.append("    %-14s %-5s %s" % (s.ad, s.tip, s.aciklama))
        satirlar.append("")
    return "\n".join(satirlar)


# ----------------------------------------------------------------- selftest

def selftest() -> None:
    import tempfile

    rng = np.random.default_rng(0)

    # 1) Her tablo icin yazma -> okuma turu, deger ve tip korunuyor mu
    with tempfile.TemporaryDirectory() as klasor:
        for tablo in TUM_TABLOLAR:
            n = 20
            veri = {}
            for s in tablo.sutunlar:
                if s.tip == "str":
                    veri[s.ad] = ["deger%d" % i for i in range(n)]
                elif s.tip == "bool":
                    veri[s.ad] = list(rng.integers(0, 2, n).astype(bool))
                elif s.tip.startswith("i"):
                    veri[s.ad] = list(rng.integers(-50, 50, n))
                else:
                    veri[s.ad] = list(rng.normal(0, 10, n))

            yol = yaz(tablo, veri, Path(klasor) / (tablo.ad + ".parquet"))
            geri = oku(tablo, yol)

            assert set(geri) == set(tablo.adlar), tablo.ad
            for s in tablo.sutunlar:
                if s.tip == "str":
                    assert list(geri[s.ad]) == list(veri[s.ad]), (tablo.ad, s.ad)
                elif s.tip == "bool":
                    assert list(geri[s.ad]) == list(veri[s.ad]), (tablo.ad, s.ad)
                else:
                    beklenen = np.asarray(veri[s.ad], dtype=s.numpyTipi)
                    assert np.allclose(geri[s.ad], beklenen, rtol=1e-5), (tablo.ad, s.ad)

            csvYol = csvDisaAktar(tablo, veri, Path(klasor) / (tablo.ad + ".csv"))
            with open(csvYol, encoding="utf-8-sig") as fp:
                baslik = next(csv.reader(fp))
            assert baslik == list(tablo.adlar), (tablo.ad, baslik)

        # 2) ASIL TEST: eksik sutun yazilmayi reddetmeli
        veri = {s.ad: [0.0] * 3 for s in TESPITLER.sutunlar}
        veri.pop("kutuGen")
        try:
            yaz(TESPITLER, veri, Path(klasor) / "olmaz.parquet")
        except ValueError as e:
            assert "kutuGen" in str(e), e
        else:
            raise AssertionError("eksik sutun yazilmayi reddetmedi -- onceki surumun hatasi geri geldi")

        # 3) Fazla sutun da reddedilmeli (yazim hatasiyla eklenen sutun)
        veri = {s.ad: [0.0] * 3 for s in TESPITLER.sutunlar}
        veri["g_px"] = [0.0] * 3
        try:
            yaz(TESPITLER, veri, Path(klasor) / "olmaz2.parquet")
        except ValueError as e:
            assert "g_px" in str(e), e
        else:
            raise AssertionError("taninmayan sutun reddedilmedi")

        # 4) Sutun uzunluklari esit degilse reddedilmeli
        veri = {s.ad: [0.0] * 3 for s in TESPITLER.sutunlar}
        veri["ton"] = [0.0] * 2
        try:
            yaz(TESPITLER, veri, Path(klasor) / "olmaz3.parquet")
        except ValueError as e:
            assert "uzunluk" in str(e), e
        else:
            raise AssertionError("uzunluk uyusmazligi reddedilmedi")

        # 5) Sutun SIRASI degisse bile okuma dogru calismali (adiyla okunuyor)
        import pyarrow as pa
        import pyarrow.parquet as pq
        veri = {s.ad: ([1, 2, 3] if s.tip != "str" else ["a", "b", "c"]) for s in REFERANS.sutunlar}
        tersYol = Path(klasor) / "ters.parquet"
        tersAdlar = list(reversed(REFERANS.adlar))
        pat = pa.table({a: pa.array(veri[a]) for a in tersAdlar})
        pq.write_table(pat, tersYol)
        geri = oku(REFERANS, tersYol)
        assert list(geri["ad"]) == ["a", "b", "c"], geri["ad"]
        assert np.allclose(geri["x_m"], [1, 2, 3])

    toplamSutun = sum(len(t.sutunlar) for t in TUM_TABLOLAR)
    print("selftest ok  (%d tablo, %d sutun; eksik/fazla/uzunluk/sira testleri gecti)"
          % (len(TUM_TABLOLAR), toplamSutun))


if __name__ == "__main__":
    if "--sema" in sys.argv:
        print(semaOzeti())
    else:
        selftest()
