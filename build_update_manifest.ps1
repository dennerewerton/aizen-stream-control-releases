param(
  [Parameter(Mandatory = $true)]
  [string]$DownloadUrl,

  [string]$Version = "",

  [string]$Output = "dist\updates.json",

  [string]$Notes = ""
)

$ErrorActionPreference = 'Stop'

function Read-AppVersion {
  $source = Get-Content "freefire_kill_sender.py" -Raw
  $match = [regex]::Match($source, 'APP_VERSION\s*=\s*"([^"]+)"')
  if (!$match.Success) {
    throw "Nao consegui ler APP_VERSION em freefire_kill_sender.py."
  }
  return $match.Groups[1].Value
}

if (!$Version) {
  $Version = Read-AppVersion
}

if (!$Notes) {
  $Notes = "Atualizacao v$Version do Aizen Stream Control."
}

if (!(Test-Path "dist\AizenStreamControl.exe")) {
  .\build_exe.ps1
}

$hash = (Get-FileHash "dist\AizenStreamControl.exe" -Algorithm SHA256).Hash.ToLowerInvariant()
$manifest = [ordered]@{
  version = $Version
  notes = $Notes
  windows = [ordered]@{
    portable_url = $DownloadUrl
    sha256 = $hash
  }
}

$json = $manifest | ConvertTo-Json -Depth 5
$outputPath = Resolve-Path -Path (Split-Path $Output -Parent) -ErrorAction SilentlyContinue
if (!$outputPath) {
  New-Item -ItemType Directory -Force -Path (Split-Path $Output -Parent) | Out-Null
}
$resolvedOutput = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Output)
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($resolvedOutput, $json + [Environment]::NewLine, $utf8NoBom)

Write-Host "Manifesto gerado em: $((Resolve-Path $Output).Path)"
Write-Host "SHA256: $hash"
