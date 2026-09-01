# Halisaha Analizi -- Windows kurulum betigi
#
#   powershell -ExecutionPolicy Bypass -File kurulum\kurulumBetigi.ps1
#
# Mevcut Python kurulumunuza dokunmaz; projeye ait ayri bir sanal ortam acar.

$ErrorActionPreference = "Stop"
$kok = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ortam = Join-Path $kok ".venv"

Write-Host "Halisaha Analizi kurulumu" -ForegroundColor Cyan
Write-Host "Proje koku: $kok"

# 1) Python 3.12 bul. Rapordaki birinci kurulum sorunu: cu121 indeksinde
#    Python 3.14 tekerlegi yok, "No matching distribution found for torch" gelir.
$py = $null
foreach ($aday in @("py -3.12", "python3.12", "python")) {
    try {
        $parcalar = $aday.Split(" ")
        $surum = & $parcalar[0] $parcalar[1..($parcalar.Length-1)] -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null
        if ($surum -match "^3\.(1[0-3])$") { $py = $aday; Write-Host "Python $surum bulundu: $aday" -ForegroundColor Green; break }
    } catch { }
}
if (-not $py) {
    Write-Host "Python 3.10-3.13 bulunamadi. https://www.python.org/downloads/release/python-3128/" -ForegroundColor Red
    Write-Host "3.14 kuruluysa dokunmayin; 3.12'yi yanina kurun." -ForegroundColor Yellow
    exit 1
}

# 2) Sanal ortam
if (-not (Test-Path $ortam)) {
    Write-Host "Sanal ortam aciliyor: $ortam"
    $parcalar = $py.Split(" ")
    & $parcalar[0] $parcalar[1..($parcalar.Length-1)] -m venv $ortam
}
$vpy = Join-Path $ortam "Scripts\python.exe"
& $vpy -m pip install --upgrade pip --quiet

# 3) torch + torchvision AYNI KOMUTTA ve CUDA indeksinden.
#    Rapordaki ikinci kurulum sorunu: ayri kurulunca surumler uyusmuyor ve
#    "RuntimeError: operator torchvision::nms does not exist" ILK TESPITTE patliyor.
Write-Host "torch + torchvision kuruluyor (CUDA cu128)..." -ForegroundColor Cyan
& $vpy -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# 4) Kalan paketler
Write-Host "Diger paketler kuruluyor..." -ForegroundColor Cyan
& $vpy -m pip install -r (Join-Path $kok "kurulum\gereksinimler.txt")

# 5) Dogrulama
Write-Host "`nOrtam denetimi:" -ForegroundColor Cyan
& $vpy (Join-Path $kok "kurulum\ortamDogrula.py")

Write-Host "`nKullanim:" -ForegroundColor Green
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  python sunucu\uygulama.py"
