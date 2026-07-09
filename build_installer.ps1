$ErrorActionPreference = 'Stop'

.\build_exe.ps1

if (!(Test-Path "dist\AizenStreamControl.exe")) {
  throw "dist\AizenStreamControl.exe nao encontrado. Execute build_exe.ps1 primeiro."
}

$pyInstallerArgs = @(
  "-m", "PyInstaller",
  "--noconfirm",
  "--clean",
  "--onefile",
  "--windowed",
  "--noupx",
  "--runtime-tmpdir", ".",
  "--name", "AizenStreamControlSetup",
  "--icon", "assets/app_icon.ico",
  "--add-binary", "dist/AizenStreamControl.exe;.",
  "--add-data", "assets;assets"
)

$pyInstallerArgs += "installer.py"

python @pyInstallerArgs

Write-Host ""
Write-Host "Instalador gerado em: $((Resolve-Path 'dist\AizenStreamControlSetup.exe').Path)"
