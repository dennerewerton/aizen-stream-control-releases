$ErrorActionPreference = 'Stop'

python -m pip install -r requirements.txt

$pyInstallerArgs = @(
  "-m", "PyInstaller",
  "--noconfirm",
  "--clean",
  "--onefile",
  "--windowed",
  "--noupx",
  "--name", "AizenStreamControl",
  "--icon", "assets/app_icon.ico",
  "--exclude-module", "cv2",
  "--exclude-module", "numpy",
  "--collect-data", "selenium",
  "--collect-data", "customtkinter",
  "--add-data", "assets;assets",
  "--add-data", "config.example.json;."
)

$pyInstallerArgs += "freefire_kill_sender.py"

python @pyInstallerArgs

Write-Host ""
Write-Host "Executavel gerado em: $((Resolve-Path 'dist\AizenStreamControl.exe').Path)"
