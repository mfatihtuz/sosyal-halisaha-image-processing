# Halisaha Mac Analizi -- Windows kurulum betigi
#
#   powershell -ExecutionPolicy Bypass -File halisahaAnaliz\kurulum\kurulumBetigi.ps1
#
# Ne yapar:
#   1. Python 3.10-3.13 arar; yoksa 3.12'yi KENDISI KURAR
#   2. Projeye ait ayri bir sanal ortam acar (mevcut Python'unuza dokunmaz)
#   3. torch + torchvision'i CUDA cu128 indeksinden AYNI KOMUTTA kurar
#   4. Kalan paketleri kurar, videolar\ klasorunu acar, ortami dogrular

$ErrorActionPreference = "Stop"
$kok = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$projeKoku = Split-Path -Parent $kok
$ortam = Join-Path $kok ".venv"

# Python 3.12'nin sabitlenmis surumu. winget calismazsa dogrudan bu indirilir.
$PY_SURUM = "3.12.10"
$PY_URL = "https://www.python.org/ftp/python/$PY_SURUM/python-$PY_SURUM-amd64.exe"

Write-Host ""
Write-Host "Halisaha Mac Analizi -- kurulum" -ForegroundColor Cyan
Write-Host "Proje koku: $kok"
Write-Host ""

# ---------------------------------------------------------------- yardimcilar

function Yenile-Path {
    # winget/installer PATH'i degistirir ama MEVCUT oturuma yansimaz.
    # Kayit defterinden okuyup bu oturumun PATH'ini tazeliyoruz.
    $makine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $kullanici = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = ($makine, $kullanici | Where-Object { $_ }) -join ";"
}

function Test-PythonSurumu {
    param([string]$Dosya, [string[]]$Arg)
    try {
        $argumanlar = @($Arg) + @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")
        $surum = & $Dosya @argumanlar 2>$null
        if ($LASTEXITCODE -ne 0) { return $null }
        if ($surum -match '^3\.(1[0-3])$') { return $surum }
    } catch { }
    return $null
}

function Bul-Python {
    # Once py launcher (surum secebiliyor), sonra dogrudan calistirilabilirler,
    # en son bilinen kurulum yollari. Her aday icin surum dogrulaniyor.
    $adaylar = @(
        @{ Dosya = "py";         Arg = @("-3.12") },
        @{ Dosya = "py";         Arg = @("-3.13") },
        @{ Dosya = "py";         Arg = @("-3.11") },
        @{ Dosya = "py";         Arg = @("-3.10") },
        @{ Dosya = "python3.12"; Arg = @() },
        @{ Dosya = "python3.11"; Arg = @() },
        @{ Dosya = "python";     Arg = @() }
    )
    foreach ($aday in $adaylar) {
        if (-not (Get-Command $aday.Dosya -ErrorAction SilentlyContinue)) { continue }
        $surum = Test-PythonSurumu -Dosya $aday.Dosya -Arg $aday.Arg
        if ($surum) {
            $gosterim = (@($aday.Dosya) + $aday.Arg) -join " "
            Write-Host "Python $surum bulundu: $gosterim" -ForegroundColor Green
            return $aday
        }
    }
    # PATH'te yoksa bilinen kurulum yollarina bak
    $yollar = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "C:\Program Files\Python312\python.exe",
        "C:\Program Files\Python311\python.exe"
    )
    foreach ($yol in $yollar) {
        if (-not (Test-Path $yol)) { continue }
        $surum = Test-PythonSurumu -Dosya $yol -Arg @()
        if ($surum) {
            Write-Host "Python $surum bulundu: $yol" -ForegroundColor Green
            return @{ Dosya = $yol; Arg = @() }
        }
    }
    return $null
}

function Kur-Python312 {
    Write-Host "Uygun Python bulunamadi. Python $PY_SURUM kuruluyor..." -ForegroundColor Yellow
    Write-Host "  (Mevcut Python kurulumlariniza DOKUNULMAZ, yanlarina kurulur.)" -ForegroundColor Gray
    Write-Host ""

    # 1) winget -- Windows 10 1809+ ve 11'de var, en temiz yol
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "winget ile deneniyor..." -ForegroundColor Cyan
        try {
            winget install --id Python.Python.3.12 -e --source winget `
                   --accept-package-agreements --accept-source-agreements --silent
            Yenile-Path
            $bulunan = Bul-Python
            if ($bulunan) { return $bulunan }
            Write-Host "winget kurdu ama Python bulunamadi, dogrudan indirmeye geciliyor." -ForegroundColor Yellow
        } catch {
            Write-Host "winget basarisiz oldu, dogrudan indirmeye geciliyor." -ForegroundColor Yellow
        }
    }

    # 2) Dogrudan indirip sessiz kurulum
    $kurucu = Join-Path $env:TEMP "python-$PY_SURUM-amd64.exe"
    Write-Host "Indiriliyor: $PY_URL" -ForegroundColor Cyan
    try {
        $ilerlemeEski = $ProgressPreference
        $ProgressPreference = "SilentlyContinue"   # cok daha hizli indirir
        Invoke-WebRequest -Uri $PY_URL -OutFile $kurucu -UseBasicParsing
        $ProgressPreference = $ilerlemeEski
    } catch {
        Write-Host "Indirme basarisiz: $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }

    Write-Host "Kuruluyor (sessiz, yalnizca bu kullanici icin)..." -ForegroundColor Cyan
    # InstallAllUsers=0 -> yonetici gerektirmez
    # PrependPath=1     -> PATH'e ekler
    # Include_launcher=1-> py launcher gelir, surum secimi kolaylasir
    $arg = "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=1 Include_test=0"
    $islem = Start-Process -FilePath $kurucu -ArgumentList $arg -Wait -PassThru
    Remove-Item $kurucu -ErrorAction SilentlyContinue

    if ($islem.ExitCode -ne 0) {
        Write-Host "Kurucu $($islem.ExitCode) koduyla dondu." -ForegroundColor Red
        return $null
    }

    Yenile-Path
    return Bul-Python
}

# ---------------------------------------------------------------- 1) Python

$py = Bul-Python
if (-not $py) {
    $py = Kur-Python312
}
if (-not $py) {
    Write-Host ""
    Write-Host "Python kurulamadi. Elle kurun:" -ForegroundColor Red
    Write-Host "  $PY_URL" -ForegroundColor Yellow
    Write-Host "  Kurarken 'Add python.exe to PATH' isaretli olsun." -ForegroundColor Yellow
    Write-Host "  Sonra bu betigi YENI bir PowerShell penceresinde tekrar calistirin." -ForegroundColor Yellow
    exit 1
}

# ---------------------------------------------------------------- 2) Sanal ortam

$vpy = Join-Path $ortam "Scripts\python.exe"
if (Test-Path $vpy) {
    Write-Host "Sanal ortam zaten var: $ortam"
} else {
    Write-Host "Sanal ortam aciliyor: $ortam"
    $argumanlar = @($py.Arg) + @("-m", "venv", $ortam)
    & $py.Dosya @argumanlar
    if (-not (Test-Path $vpy)) {
        Write-Host "Sanal ortam acilamadi." -ForegroundColor Red
        exit 1
    }
}
& $vpy -m pip install --upgrade pip --quiet

# ---------------------------------------------------------------- 3) torch
#
# Rapordaki kurulum sorunu: torch ve torchvision ayri komutlarla kurulunca
# surumler uyusmuyor ve "RuntimeError: operator torchvision::nms does not exist"
# ILK TESPITTE patliyor. Bu yuzden AYNI KOMUTTA ve ayni indeksten.

Write-Host ""
Write-Host "torch + torchvision kuruluyor (CUDA cu128, ayni komutta)..." -ForegroundColor Cyan
Write-Host "  ~2,5 GB, birkac dakika surebilir." -ForegroundColor Gray
& $vpy -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) {
    Write-Host "torch kurulamadi." -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------- 4) Digerleri

Write-Host ""
Write-Host "Diger paketler kuruluyor..." -ForegroundColor Cyan
& $vpy -m pip install -r (Join-Path $kok "kurulum\gereksinimler.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Host "Paket kurulumu basarisiz." -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------- 5) videolar\

$videoKlasoru = Join-Path $projeKoku "videolar"
if (-not (Test-Path $videoKlasoru)) { New-Item -ItemType Directory -Path $videoKlasoru | Out-Null }
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
