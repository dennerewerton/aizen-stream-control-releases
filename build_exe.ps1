$ErrorActionPreference = 'Stop'

python -m pip install -r requirements.txt

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name "FreeFireKillSender" `
  --add-data "scripts/windows_ocr.ps1;scripts" `
  --add-data "config.example.json;." `
  "freefire_kill_sender.py"

Write-Host ""
Write-Host "Executavel gerado em: $((Resolve-Path 'dist\FreeFireKillSender.exe').Path)"
