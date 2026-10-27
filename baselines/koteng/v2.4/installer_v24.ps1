$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
Write-Host '============================================================='
Write-Host 'RBK KVINNER - KOTENG 2.4 - KOMPLETT FORSTEGANGSINSTALLASJON'
Write-Host '============================================================='

function New-KotengVenv {
    $venvDir = Join-Path $root '.venv'
    $pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        foreach ($version in @('-3.12', '-3.13', '-3.11', '-3')) {
            Write-Host ('Prover Python launcher ' + $version + ' ...')
            try {
                & py.exe $version -m venv $venvDir 2>$null
                if (($LASTEXITCODE -eq 0) -and (Test-Path -LiteralPath $venvPython)) { return $true }
            } catch { }
        }
    }
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
        (Join-Path $env:ProgramFiles 'Python312\python.exe'),
        (Join-Path $env:ProgramFiles 'Python313\python.exe')
    )
    foreach ($exe in $candidates) {
        if (-not (Test-Path -LiteralPath $exe)) { continue }
        try {
            & $exe -m venv $venvDir
            if (($LASTEXITCODE -eq 0) -and (Test-Path -LiteralPath $venvPython)) { return $true }
        } catch { }
    }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command) {
        try {
            & python.exe -m venv $venvDir
            if (($LASTEXITCODE -eq 0) -and (Test-Path -LiteralPath $venvPython)) { return $true }
        } catch { }
    }
    return $false
}

try {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        if (-not (New-KotengVenv)) {
            Write-Host 'Python mangler. Forsoker installasjon med Windows Package Manager (winget).'
            $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
            if (-not $winget) {
                throw 'Python ikke funnet, og winget er ikke installert. Installer Python 3.12 fra python.org/downloads/windows/ (husk py launcher), og kjor denne filen igjen.'
            }
            & winget.exe install --id Python.Python.3.12 --exact --source winget --accept-package-agreements --accept-source-agreements --silent
            if ($LASTEXITCODE -ne 0) { throw 'Windows kunne ikke installere Python. Installer Python 3.12 manuelt og prov igjen.' }
            if (-not (New-KotengVenv)) { throw 'Python installert, men denne terminalen finner den ikke. Lukk vinduet og start 01_INSTALLER.bat pa nytt.' }
        }
    }
    if (-not (Test-Path -LiteralPath $venvPython)) { throw 'Klarte ikke opprette privat Python-miljo.' }
    Write-Host 'Installerer avhengigheter i privat .venv ...'
    & $venvPython -m pip install --disable-pip-version-check --requirement (Join-Path $root 'requirements_v24.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Pip-installasjon feilet. Kontroller internett og prov igjen.' }
    Write-Host 'Verifiserer alle seks stadionfelt og SHA256-lasen ...'
    & $venvPython (Join-Path $root 'preflight_v24.py')
    if ($LASTEXITCODE -ne 0) { throw 'Forhandskontrollen feilet. Ingen sending er mulig.' }
    Write-Host ''
    Write-Host 'FERDIG! Ingen data er sendt. Fortsett med 02_TEST_EN_GANG.bat.' -ForegroundColor Green
    exit 0
}
catch {
    Write-Host ('STOPP: ' + $_.Exception.Message) -ForegroundColor Red
    exit 2
}
