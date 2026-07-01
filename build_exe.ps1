$ErrorActionPreference = 'Stop'

python -m pip install -r requirements.txt

$pythonRoot = Split-Path (Get-Command python).Source -Parent
$runtimeBinaries = @()
$runtimeBinaries += Get-ChildItem $pythonRoot -Filter "python*.dll" | Select-Object -ExpandProperty FullName
$runtimeBinaries += @(
  (Join-Path $pythonRoot "vcruntime140.dll"),
  (Join-Path $pythonRoot "vcruntime140_1.dll"),
  (Join-Path $env:WINDIR "System32\ucrtbase.dll")
) | Where-Object { Test-Path $_ }

$downlevelDir = Join-Path $env:WINDIR "System32\downlevel"
if (Test-Path $downlevelDir) {
  $runtimeBinaries += Get-ChildItem $downlevelDir -Filter "api-ms-win-crt-*.dll" | Select-Object -ExpandProperty FullName
}

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

foreach ($binary in $runtimeBinaries) {
  $pyInstallerArgs += @("--add-binary", "$binary;.")
}

$pyInstallerArgs += "freefire_kill_sender.py"

python @pyInstallerArgs

Write-Host ""
Write-Host "Executavel gerado em: $((Resolve-Path 'dist\AizenStreamControl.exe').Path)"
