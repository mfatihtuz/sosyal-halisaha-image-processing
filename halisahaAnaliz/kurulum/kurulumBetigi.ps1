# Halisaha Analizi -- Windows kurulum betigi
#
#   powershell -ExecutionPolicy Bypass -File halisahaAnaliz\kurulum\kurulumBetigi.ps1
#
# Mevcut Python kurulumunuza dokunmaz; projeye ait ayri bir sanal ortam acar.

$ErrorActionPreference = "Stop"
$kok = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ortam = Join-Path $kok ".venv"

Write-Host ""
Write-Host "Halisaha Mac Analizi -- kurulum" -ForegroundColor Cyan
Write-Host "Proje koku: $kok"
Write-Host ""

# ---------------------------------------------------------------- 1) Python bul
#
# Rapordaki birinci kurulum sorunu: cu121 indeksinde Python 3.14 tekerlegi yok,
# "No matching distribution found for torch" hatasi geliyor. 3.10-3.13 araniyor.

function Bul-Python {
    # (dosya, ek argumanlar) ciftleri. py launcher'a -3.12 gibi arguman gerekir,
    # digerleri dogrudan cagrilir.
    $adaylar = @(
        @{ Dosya = "py";         Arg = @("-3.12") },
        @{ Dosya = "py";         Arg = @("-3.13") },
        @{ Dosya = "py";         Arg = @("-3.11") },
        @{ Dosya = "python3.12"; Arg = @() },
        @{ Dosya = "python3.11"; Arg = @() },
        @{ Dosya = "python";     Arg = @() }
    )
    foreach ($aday in $adaylar) {
        if (-not (Get-Command $aday.Dosya -ErrorAction SilentlyContinue)) { continue }
        try {
            $argumanlar = @($aday.Arg) + @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")
            $surum = & $aday.Dosya @argumanlar 2>$null
            if ($LASTEXITCODE -ne 0) { continue }
            if ($surum -match '^3\.(1[0-3])$') {
                $gosterim = (@($aday.Dosya) + $aday.Arg) -join " "
                Write-Host "Python $surum bulundu: $gosterim" -ForegroundColor Green
                return $aday
            }
        } catch { }
    }
    return $null
}

$py = Bul-Python
if (-not $py) {
    Write-Host "Python 3.10-3.13 bulunamadi." -ForegroundColor Red
    Write-Host ""
    Write-Host "  Indirme: https://www.python.org/downloads/release/python-31210/" -ForegroundColor Yellow
    Write-Host "  Kurarken 'Add python.exe to PATH' isaretli olsun." -ForegroundColor Yellow
    Write-Host "  3.14 kuruluysa DOKUNMAYIN; 3.12'yi yanina kurun, ikisi birlikte durur." -ForegroundColor Yellow
    exit 1
}

# ---------------------------------------------------------------- 2) Sanal ortam

if (Test-Path (Join-Path $ortam "Scripts\python.exe")) {
    Write-Host "Sanal ortam zaten var: $ortam"
} else {
    Write-Host "Sanal ortam aciliyor: $ortam"
    $argumanlar = @($py.Arg) + @("-m", "venv", $ortam)
    & $py.Dosya @argumanlar
    if ($LASTEXITCODE -ne 0) { Write-Host "Sanal ortam acilamadi." -ForegroundColor Red; exit 1 }
}

$vpy = Join-Path $ortam "Scripts\python.exe"
& $vpy -m pip install --upgrade pip --quiet

# ---------------------------------------------------------------- 3) torch
#
# Rapordaki ikinci kurulum sorunu: torch ve torchvision ayri komutlarla
# kurulunca surumler uyusmuyor ve "RuntimeError: operator torchvision::nms does
# not exist" ILK TESPITTE patliyor. Bu yuzden AYNI KOMUTTA ve ayni indeksten.

Write-Host ""
Write-Host "torch + torchvision kuruluyor (CUDA cu128, ayni komutta)..." -ForegroundColor Cyan
& $vpy -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) {
    Write-Host "torch kurulamadi. Internet baglantisini ve Python surumunu kontrol edin." -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------- 4) Digerleri

Write-Host ""
Write-Host "Diger paketler kuruluyor..." -ForegroundColor Cyan
& $vpy -m pip install -r (Join-Path $kok "kurulum\gereksinimler.txt")
if ($LASTEXITCODE -ne 0) { Write-Host "Paket kurulumu basarisiz." -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------- 5) Video klasoru

$videoKlasoru = Join-Path (Split-Path -Parent $kok) "videolar"
if (-not (Test-Path $videoKlasoru)) {
    New-Item -ItemType Directory -Path $videoKlasoru | Out-Null
}
Write-Host ""
Write-Host "Video klasoru hazir: $videoKlasoru" -ForegroundColor Green
Write-Host "  Mac kayitlarini buraya koyun. Depoya girmezler (.gitignore)." -ForegroundColor Gray

# ---------------------------------------------------------------- 6) Dogrulama

Write-Host ""
Write-Host "Ortam denetimi:" -ForegroundColor Cyan
& $vpy (Join-Path $kok "kurulum\ortamDogrula.py")

Write-Host ""
Write-Host "Kurulum bitti." -ForegroundColor Green
Write-Host "Sanal ortami acmak icin:  .\halisahaAnaliz\.venv\Scripts\Activate.ps1" -ForegroundColor Gray
