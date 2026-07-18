param(
  [Parameter(Mandatory = $true)]
  [string]$DownloadUrl,

  [string]$Version = "",

  [string]$Output = "dist\updates.json",

  [string]$Notes = "",

  [switch]$SkipBuild
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

function Test-BuildArtifactStale {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ArtifactPath
  )

  if (!(Test-Path $ArtifactPath)) {
    return $true
  }

  $artifactTime = (Get-Item $ArtifactPath).LastWriteTimeUtc
  $sourcePaths = @(
    "freefire_kill_sender.py",
    "config.example.json",
    "requirements.txt",
    "assets"
  )

  foreach ($sourcePath in $sourcePaths) {
    if (!(Test-Path $sourcePath)) {
      continue
    }
    $item = Get-Item $sourcePath
    if ($item.PSIsContainer) {
      $newerChild = Get-ChildItem $item.FullName -Recurse -File |
        Where-Object { $_.LastWriteTimeUtc -gt $artifactTime } |
        Select-Object -First 1
      if ($null -ne $newerChild) {
        return $true
      }
    } elseif ($item.LastWriteTimeUtc -gt $artifactTime) {
      return $true
    }
  }

  return $false
}

if (!$Version) {
  $Version = Read-AppVersion
}

if (!$Notes) {
  $Notes = "Atualizacao v$Version do Aizen Stream Control."
}

if (!$SkipBuild -and (Test-BuildArtifactStale "dist\AizenStreamControl.exe")) {
  .\build_exe.ps1
}

if ($SkipBuild -and (Test-BuildArtifactStale "dist\AizenStreamControl.exe")) {
  throw "dist\AizenStreamControl.exe esta ausente ou mais antigo que o codigo. Execute build_exe.ps1 ou remova -SkipBuild."
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
