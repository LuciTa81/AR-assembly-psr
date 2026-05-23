$ErrorActionPreference = "Stop"

Write-Host "=== Setup Python virtual environment for Vision Assembly PSR v2 ==="

if (!(Test-Path ".venv_mp")) {
    py -3 -m venv .venv_mp
}

.\.venv_mp\Scripts\python.exe -m pip install --upgrade pip
.\.venv_mp\Scripts\python.exe -m pip install -r server\requirements.txt

Write-Host ""
Write-Host "[DONE] Environment is ready."
