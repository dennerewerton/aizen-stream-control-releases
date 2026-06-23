param(
  [Parameter(Mandatory = $true)]
  [string]$DownloadUrl,

  [string]$Version = "2.6.22",

  [string]$Output = "dist\updates.json",

  [string]$Notes = "Kills FF com acoes reais do Jarvis no ranking: +1/-1, definir, editar nome/ID, ignorar, reexibir e resetar."
)

$ErrorActionPreference = 'Stop'

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
