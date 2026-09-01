"""Butun esikler ve parametreler tek yerde.

Onceki surumde sabitler sekiz ayri dosyaya dagilmisti ve alti tanesi
(`KAPI_M`, `KAYIP_SN`, `DIK_SN`, `DIK_M`, `DOYGUN_ESIK`, `DIK_HIZ`) tanimlanip
hic kullanilmiyordu -- `birlestir.py` dosyanin basinda `KAPI_M = 1.8` yazip
fonksiyon imzasinda `kapi=3.5` varsayilanini kullaniyordu. Dosyada dogru deger
yaziliydi ama koda hic ulasmiyordu.

Burada her deger tek bir yerde tanimli, arayuzden degistirilebilir ve JSON'a
serilesir; bir kosunun hangi ayarlarla yapildigi cikti klasorunde saklanir.

Her esigin yaninda NEDEN o deger oldugu yaziyor. Olculerek bulunan degerlerde
olcumun kendisi de yazili.

    python ayarlar.py --selftest
    python ayarlar.py --yaz ayarlar.json
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, get_type_hints


@dataclass
class SahaAyarlari:
    """Saha geometrisi. Gercek olcu bilinmiyorsa varsayilan kullanilir."""

    uzunluk: float = 50.0
    """Kaleden kaleye mesafe (metre). VARSAYIM -- gercek olcu bilinmiyor.

    Kalibrasyon kisitlari "bu cizgi X=uzunluk/2'dir" bicimindedir, dolayisiyla
    gercek olcu ogrenildiginde kalibrasyonu tekrarlamak GEREKMEZ; sadece bu deger
    degistirilir ve tum konumlar oranla olceklenir.
    """

    genislik: float = 30.0
    """Kenar cizgileri arasi mesafe (metre). VARSAYIM."""

    cezaSahasiDerinlik: float = 8.0
    """Kale cizgisinden ceza sahasi cizgisine mesafe (metre)."""

    cezaSahasiGenislik: float = 16.0
    """Ceza sahasinin genisligi (metre)."""

    ortaDaireYaricap: float = 5.0
    """Orta daire yaricapi (metre). Kalibrasyonda daire kisiti olarak kullanilir."""

    kenarPayi: float = 3.0
    """Saha sinirinin bu kadar disindaki tespitler elenir (metre).

    Tribun, kenarda bekleyenler, cam/branda yansimalari.
    """


@dataclass
class TespitAyarlari:
    """YOLO tespit hatti."""

    model: str = "yolo11m-seg.pt"
    """Segmentasyon modeli.

    Maske SART: onceki surumde renk, kutunun bir diliminden olculuyordu ve o dilim
    cim + mavi duvar + yandaki oyuncu iceriyordu. Olculen sonuc: 60 sn yasayan 7
    izin doygunluklari 10-61 arasinda sikismis, tonlarin cogu 184-256 derece
    bandina (arkadaki mavi duvar panelleri) dusmustu. Maske arka plani tanim
    geregi disarida birakir.
    """

    orneklemeFps: float = 10.0
    """Saniyede kac kare islenecek (kaynak ~30 fps).

    Olculen: 10 fps'te oyuncu kare basina medyan 0,15 m / p90 0,44 m yer
    degistiriyor, en yakin komsu ise p10 2,23 m otede. 5 kat marj var, yani
    eslestirme icin fazlasiyla yeterli. Daha yuksek fps islem yukunu artirir,
    dogrulugu anlamli olcude artirmaz.
    """

    guvenEsigi: float = 0.25
    """Tespit guven esigi."""

    girdiCozunurlugu: int = 1920
    """Model girdi boyutu.

    Dusurulemez: uzak yaridaki oyuncular 15-40 piksel. Olculen guven yakin yarida
    0,856 iken uzak yarida 0,705'e dusuyor; cozunurluk dusurulurse uzak yari
    tamamen kaybolur.
    """

    yariHassasiyet: bool = True
    """FP16. Yaklasik 1,7 kat hiz, dogrulukta olculebilir kayip yok."""

    topluBoyut: int = 8
    """Ayni anda modele verilen kare sayisi. GPU'yu doyurur, ~1,5-2 kat hiz."""

    uzakYariKarolama: bool = True
    """Karenin uzak bolgesini ayrica ve tam cozunurlukte islemek.

    Hedef: kare basina tespit 12,66 -> 14. Sahada 14 kisi varken kamera basina
    ortalama 12,66 tespit dusuyor, yani her karede ~1,3 kisi kayip. Eksik tespit
    kimlik takasinin ikinci buyuk kaynagi.

    KAZANC OLCULMEDEN KALICILASTIRILMAZ: Faz 2'de acik/kapali kiyaslanacak.
    """

    karoOrtusme: float = 0.2
    """Karolar arasi ortusme orani; kenarda bolunen kisiyi kaybetmemek icin."""

    siyahlikParlaklikEsigi: float = 70.0
    """Bu parlakligin altindaki maske pikseli "koyu" sayilir (0-255)."""

    siyahlikDoygunlukEsigi: float = 60.0
    """Bu doygunlugun altindaki maske pikseli "renksiz" sayilir (0-255).

    Koyu VE renksiz piksellerin orani `siyahlik`. Siyah forma yuksek, yelek dusuk
    deger verir; takim ayrimi bu tek sayiya dayanir.
    """


@dataclass
class KalibrasyonAyarlari:
    """Lens + homografi cozumu."""

    lambdaTaramaAlt: float = -0.6
    lambdaTaramaUst: float = 0.6
    lambdaTaramaAdim: int = 241
    """Tek parametreli bolme modelinin kaba taramasi.

    Tek serbestlik derecesi oldugu icin yerel minimum riski yok. Brown-Conrady
    (k1,k2,k3) denendi ve elendi: asiri serbestlik k2=-5,2 / k3=8,5 gibi fiziksel
    anlami olmayan degerler bulup olcutu memnun etti, gercek geometriyi yakalamadi.
    """

    enAzNokta: int = 4
    """Homografi icin gereken asgari nokta sayisi."""

    kabulEdilebilirRms: float = 0.40
    """Bu metrenin ustundeki RMS arayuzde uyari verir. Olculen deger 0,31-0,36 m."""

    aynalamaSuphesiM: float = 4.0
    """Iki kameranin ima ettigi konumlar bu kadar ayrisiyorsa aynalama denetimi tetiklenir.

    Onceki surum bu tuzaga bir kez dustu: kamera 2 kalibre edilirken yakin kale
    yanlis kaleyle etiketlendi. Aynalama gecerli bir projektif donusum oldugu icin
    uyum hatasi 0,31 m gibi gayet iyi cikti ve hata kendini hic belli etmedi.
    """

    hataHaritasiHucre: float = 5.0
    """Capraz kamera hata haritasinin izgara adimi (metre)."""


@dataclass
class KimlikAyarlari:
    """Kimlik katmani -- projenin can alici noktasi."""

    vAzami: float = 8.0
    """Bir oyuncunun fiziksel azami hizi (m/s). Zamana uyarli kapinin egimi."""

    kapiTabani: float = 0.5
    """Kapinin sabit terimi (metre): konum olcum gurultusu."""

    def kapi(self, dt: float) -> float:
        """Bir kimligin `dt` saniyede atlayabilecegi azami mesafe.

        ONCEKI SURUMUN ANA HATASI SABIT 3,5 METRELIK KAPIYDI.

        Olculen gercek: oyuncu 0,1 sn'de medyan 0,15 m / p90 0,44 m hareket
        ediyor, en yakin komsu p10 2,23 m otede. Sabit 3,5 m kapi gerekenin 8 kati.
        Bir oyuncu bir karede tespit edilemedigin de (kare basina 12,66 tespit,
        14 kisi -> ~1,3 eksik) o yuva 3,5 m otedeki komsunun tespitini kapiyor,
        komsunun yuvasi bir baskasini kapiyor; cig.

        Zamana uyarli kapi bu sorunu kokten cozer: dt=0,1 sn'de 1,3 m, ama 2 sn
        boslukta 16,5 m. Kisa araliktaki komsu kapmasi imkansiz hale gelirken uzun
        boslukta yeniden baglanma mumkun kalir.
        """
        return self.vAzami * max(dt, 0.0) + self.kapiTabani

    belirsizlikMarji: float = 0.6
    """Parca uzatma icin en iyi ile ikinci aday arasinda gereken en az fark (metre).

    Fark bundan kucukse parca KESILIR. Tasarimin yonu bilincli olarak tersine
    cevrildi: parcalanma ucuz, takas pahali. Onceki surum tam tersini yapiyordu.
    """

    esitlemeM: float = 2.0
    """Iki kameranin ayni kisiyi gosterme esigi (metre). Olculen medyan fark 0,85 m."""

    renkAgirligi: float = 1.0
    """Renk farkinin eslestirme maliyetine katkisi.

    KAPIYA DAHIL DEGIL. Onceki surumde renk maliyeti kapi esigine dahil edilince,
    ayni formali oyuncularda renk farki sifir oldugu icin kapi fiilen genisledi ve
    kimlikler uzaktaki yanlis oyuncuyu kapti. Kapi yalnizca mesafeye bakar; renk
    kapi ICINDE ayirt edici olarak kullanilir.
    """

    baglamaAzamiHiz: float = 7.0
    """Iki parcayi baglamak icin ima edilen azami hiz (m/s).

    Sabit mesafe esigi yerine bu kullanilir: 1 sn boslukta 14 m atlamak imkansiz,
    12 sn boslukta gayet mumkun.
    """

    baglamaAzamiBosluk: float = 20.0
    """Iki parca arasinda kapatilabilecek azami zaman boslugu (saniye)."""

    zayifZincirEsigi: float = 0.40
    """Orneklerinin bu oranindan azi gercek gozlem olan zincir oyuncu sayilmaz.

    Kale arkasinda duran biri, arada bir yakalanan bir yansima. Metriklerini
    uretmek yaniltici olur.
    """

    supheYakinlikM: float = 1.5
    """Iki zincir bu mesafeden yakinsa o an "riskli" isaretlenir ve duzeltme
    panelinde ust siralarda gosterilir."""


@dataclass
class MetrikAyarlari:
    """Hareket metrikleri."""

    duzlestirmePencere: int = 9
    """Savitzky-Golay pencere uzunlugu (ornek). 10 fps'te ~0,9 sn.

    Futbolda yon degisimi ~1 sn olceginde; altindaki dalgalanma tespit gurultusudur.
    Hareketli ortalama YERINE Savitzky-Golay: hareketli ortalama tepe noktalarini
    sistematik olarak bastirir ve maksimum hizi oldugundan dusuk gosterir, sprint
    sayimi bundan dogrudan etkilenir.
    """

    duzlestirmeDerece: int = 2
    """Savitzky-Golay polinom derecesi."""

    turevTabani: int = 3
    """Hiz turevi +-bu kadar ornekten alinir. 10 fps'te 0,6 sn.

    Komsu kareden turev almak felaket: 0,3 m'lik konum gurultusu 10 fps'te 3 m/s
    sahte hiz uretir. Olculen: duran oyuncu 60 saniyede 62 m "kosmus" cikiyordu.
    """

    azamiHiz: float = 8.0
    """Bu hizin ustu tespit hatasi sayilir ve kirpilir (m/s)."""

    sprintHiz: float = 4.5
    """Sprint esigi (m/s). Halisaha olceginde sprint tanimi."""

    sprintSure: float = 0.4
    """Sprint sayilmasi icin esigin ustunde gecmesi gereken en az sure (saniye)."""

    yuksekTempoHiz: float = 3.0
    """Yuksek tempo esigi (m/s)."""

    kosuHiz: float = 2.0
    """Yurume/kosu ayrimi esigi (m/s)."""

    ivmeEsigi: float = 2.0
    """Ani hizlanma/yavaslama olayi esigi (m/s^2)."""

    enAzVeriKalitesi: float = 0.50
    """Bu oranin altinda veri kalitesi olan oyuncunun metrikleri uyarili gosterilir."""


@dataclass
class HaritaAyarlari:
    """Isi haritasi."""

    hucre: float = 0.5
    """Izgara cozunurlugu (metre)."""

    yumusatma: float = 2.5
    """Gauss yumusatma yaricapi (hucre)."""


@dataclass
class DogrulamaAyarlari:
    """Referans kesit ve puanlama."""

    referansSuresiSn: float = 60.0
    """Elle dogrulanacak kesitin uzunlugu (saniye). Kullanici degistirebilir."""

    eslesmeYaricapiM: float = 2.0
    """Puanlamada tahmin ile referansin ayni kisi sayilmasi icin azami mesafe."""


@dataclass
class Ayarlar:
    """Tum ayarlarin koku. JSON'a serilesir, arayuzden duzenlenir."""

    saha: SahaAyarlari = field(default_factory=SahaAyarlari)
    tespit: TespitAyarlari = field(default_factory=TespitAyarlari)
    kalibrasyon: KalibrasyonAyarlari = field(default_factory=KalibrasyonAyarlari)
    kimlik: KimlikAyarlari = field(default_factory=KimlikAyarlari)
    metrik: MetrikAyarlari = field(default_factory=MetrikAyarlari)
    harita: HaritaAyarlari = field(default_factory=HaritaAyarlari)
    dogrulama: DogrulamaAyarlari = field(default_factory=DogrulamaAyarlari)

    # ------------------------------------------------------------- serilestirme

    def sozluge(self) -> dict[str, Any]:
        return asdict(self)

    def jsonaYaz(self, yol: str | Path) -> Path:
        yol = Path(yol)
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(json.dumps(self.sozluge(), indent=2, ensure_ascii=False), encoding="utf-8")
        return yol

    @classmethod
    def sozluktenOku(cls, veri: dict[str, Any]) -> "Ayarlar":
        """Kismi sozlukten okur; verilmeyen alanlar varsayilanda kalir.

        Taninmayan anahtar sessizce yutulmaz, hata verir -- yazim hatasiyla
        girilmis bir ayarin fark edilmeden varsayilanda kalmasi tam olarak
        onceki surumun oldurucu hatasiydi.
        """
        return _sozluktenDataclass(cls, veri, kok=cls.__name__)

    @classmethod
    def jsondanOku(cls, yol: str | Path) -> "Ayarlar":
        return cls.sozluktenOku(json.loads(Path(yol).read_text(encoding="utf-8")))

    # ------------------------------------------------------------- belgeleme

    def ozet(self) -> str:
        satirlar = []
        for grup in fields(self):
            alt = getattr(self, grup.name)
            satirlar.append("[%s]" % grup.name)
            for f in fields(alt):
                satirlar.append("  %-26s %s" % (f.name, getattr(alt, f.name)))
            satirlar.append("")
        return "\n".join(satirlar)


def _sozluktenDataclass(tur, veri: dict[str, Any], kok: str):
    """Ic ice dataclass'lari sozlukten kurar, taninmayan anahtarda hata verir.

    `from __future__ import annotations` yuzunden `field.type` bir metin oldugu icin
    gercek tipler `get_type_hints` ile cozulur; aksi halde ic ice dataclass'lar
    taninmaz ve sozluk olarak atanip sessizce bozuk nesne uretilirdi.
    """
    if not isinstance(veri, dict):
        raise ValueError("%s icin sozluk bekleniyordu, %s geldi" % (kok, type(veri).__name__))

    gecerli = {f.name: f for f in fields(tur)}
    taninmayan = sorted(set(veri) - set(gecerli))
    if taninmayan:
        raise ValueError("%s icinde taninmayan ayar: %s (gecerli olanlar: %s)"
                         % (kok, ", ".join(taninmayan), ", ".join(sorted(gecerli))))

    ipuclari = get_type_hints(tur)
    kurulacak = {}
    for ad in gecerli:
        if ad not in veri:
            continue
        altTur = ipuclari.get(ad)
        if isinstance(altTur, type) and is_dataclass(altTur):
            kurulacak[ad] = _sozluktenDataclass(altTur, veri[ad], kok="%s.%s" % (kok, ad))
        else:
            kurulacak[ad] = veri[ad]
    return tur(**kurulacak)


VARSAYILAN = Ayarlar()


# ----------------------------------------------------------------- selftest

def selftest() -> None:
    import tempfile

    a = Ayarlar()

    # 1) Zamana uyarli kapi: kisa aralikta dar, uzun boslukta genis
    k = a.kimlik
    assert abs(k.kapi(0.1) - 1.3) < 1e-9, k.kapi(0.1)
    assert k.kapi(0.1) < 2.23, "kapi en yakin komsu mesafesinin p10'undan (2,23 m) kucuk olmali"
    assert k.kapi(0.1) > 1.13, "kapi olculen p99 kare basina hareketten (1,13 m) buyuk olmali"
    assert k.kapi(2.0) > 15.0, "2 sn boslukta yeniden baglanma mumkun kalmali"
    assert k.kapi(0.0) == k.kapiTabani

    # Eski surumun sabit kapisiyla kiyas: 0,1 sn'de kac kat dar
    assert 3.5 / k.kapi(0.1) > 2.5, "yeni kapi eski 3,5 m'den belirgin sekilde dar olmali"

    # 2) JSON turu: yaz -> oku -> ayni
    with tempfile.TemporaryDirectory() as klasor:
        yol = a.jsonaYaz(Path(klasor) / "ayarlar.json")
        geri = Ayarlar.jsondanOku(yol)
        assert geri.sozluge() == a.sozluge()

    # 3) Kismi sozluk: verilmeyen alanlar varsayilanda kalir
    kismi = Ayarlar.sozluktenOku({"saha": {"uzunluk": 45.0, "genislik": 28.0}})
    assert kismi.saha.uzunluk == 45.0 and kismi.saha.genislik == 28.0
    assert kismi.tespit.orneklemeFps == VARSAYILAN.tespit.orneklemeFps
    assert kismi.kimlik.vAzami == VARSAYILAN.kimlik.vAzami

    # 4) ASIL TEST: yazim hatasi sessizce yutulmamali
    try:
        Ayarlar.sozluktenOku({"saha": {"uzunlk": 45.0}})
    except ValueError as e:
        assert "uzunlk" in str(e) and "saha" in str(e), e
    else:
        raise AssertionError("taninmayan ayar anahtari sessizce yutuldu")

    try:
        Ayarlar.sozluktenOku({"kimlikk": {}})
    except ValueError as e:
        assert "kimlikk" in str(e), e
    else:
        raise AssertionError("taninmayan ayar grubu sessizce yutuldu")

    # 5) Metrik esikleri kendi icinde tutarli mi
    m = a.metrik
    assert m.kosuHiz < m.yuksekTempoHiz < m.sprintHiz < m.azamiHiz, "hiz bolgeleri artan sirada olmali"
    assert m.duzlestirmePencere % 2 == 1, "Savitzky-Golay penceresi tek sayi olmali"
    assert m.duzlestirmeDerece < m.duzlestirmePencere, "polinom derecesi pencereden kucuk olmali"

    # 6) Kimlik esikleri tutarli mi
    assert k.esitlemeM > 0.85, "iki kamera esitleme esigi olculen medyan farktan (0,85 m) buyuk olmali"
    assert k.supheYakinlikM > k.kapi(0.1), "suphe yaricapi kapidan genis olmali"

    print("selftest ok  (kapi 0,1 sn -> %.2f m [eski 3,50 m], 2,0 sn -> %.2f m; "
          "%d ayar grubu, yazim hatasi yakalaniyor)"
          % (k.kapi(0.1), k.kapi(2.0), len(fields(Ayarlar))))


if __name__ == "__main__":
    if "--yaz" in sys.argv:
        hedef = sys.argv[sys.argv.index("--yaz") + 1]
        print("Yazildi:", VARSAYILAN.jsonaYaz(hedef))
    elif "--ozet" in sys.argv:
        print(VARSAYILAN.ozet())
    else:
        selftest()
