$ErrorActionPreference = 'Stop'

python -m pip install -r requirements.txt

$pyInstallerArgs = @(
  "-m", "PyInstaller",
  "--noconfirm",
  "--clean",
  "--onefile",
  "--windowed",
  "--noupx",
  "--runtime-tmpdir", ".",
  "--name", "AizenStreamControl",
  "--icon", "assets/app_icon.ico",
  "--collect-data", "selenium",
  "--collect-data", "customtkinter",
  "--add-data", "scripts/windows_ocr.ps1;scripts",
  "--add-data", "assets;assets",
  "--add-data", "config.example.json;."
)

$pyInstallerArgs += "freefire_kill_sender.py"

python @pyInstallerArgs

Write-Host ""
Write-Host "Executavel gerado em: $((Resolve-Path 'dist\AizenStreamControl.exe').Path)"
