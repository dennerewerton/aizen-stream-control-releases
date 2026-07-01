$ErrorActionPreference = 'Stop'

.\build_exe.ps1

if (!(Test-Path "dist\AizenStreamControl.exe")) {
  throw "dist\AizenStreamControl.exe nao encontrado. Execute build_exe.ps1 primeiro."
}

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
  "--name", "AizenStreamControlSetup",
  "--icon", "assets/app_icon.ico",
  "--add-binary", "dist/AizenStreamControl.exe;.",
  "--add-data", "assets;assets"
)

foreach ($binary in $runtimeBinaries) {
  $pyInstallerArgs += @("--add-binary", "$binary;.")
}

$pyInstallerArgs += "installer.py"

python @pyInstallerArgs

Write-Host ""
Write-Host "Instalador gerado em: $((Resolve-Path 'dist\AizenStreamControlSetup.exe').Path)"
