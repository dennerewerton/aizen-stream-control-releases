param(
  [string]$Version = "",

  [string]$Repository = "dennerewerton/aizen-stream-control-releases",

  [string]$ExePath = "dist\AizenStreamControl.exe",

  [string]$SetupPath = "dist\AizenStreamControlSetup.exe",

  [string]$ManifestPath = "dist\updates.json",

  [string]$Notes = "",

  [switch]$SkipBuild,

  [switch]$DryRun
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

function Invoke-GitHubJson {
  param(
    [string]$Method,
    [string]$Uri,
    [object]$Body = $null,
    [int[]]$OkStatus = @(200, 201)
  )

  $params = @{
    Method = $Method
    Uri = $Uri
    Headers = $script:GitHubHeaders
    UseBasicParsing = $true
  }
  if ($null -ne $Body) {
    $jsonBody = $Body | ConvertTo-Json -Depth 8 -Compress
    $params.ContentType = "application/json; charset=utf-8"
    $params.Body = [System.Text.Encoding]::UTF8.GetBytes($jsonBody)
  }

  try {
    $response = Invoke-WebRequest @params
  } catch {
    $response = $_.Exception.Response
    if ($null -eq $response) {
      throw
    }
    if ($OkStatus -notcontains [int]$response.StatusCode) {
      throw
    }
    return $null
  }

  if ($OkStatus -notcontains [int]$response.StatusCode) {
    throw "GitHub retornou HTTP $($response.StatusCode) para $Uri."
  }
  if ([string]::IsNullOrWhiteSpace($response.Content)) {
    return $null
  }
  return $response.Content | ConvertFrom-Json
}

if (!$Version) {
  $Version = Read-AppVersion
}
$tag = "v$Version"
$downloadUrl = "https://github.com/$Repository/releases/download/$tag/AizenStreamControl.exe"

if (!$Notes) {
  $Notes = "Atualizacao $tag do Aizen Stream Control."
}

if (!$SkipBuild) {
  if ($ExePath -ne "dist\AizenStreamControl.exe" -or $SetupPath -ne "dist\AizenStreamControlSetup.exe") {
    throw "Build automatico usa os caminhos padrao em dist. Use os caminhos padrao ou rode com -SkipBuild apos gerar os artefatos customizados."
  }
  .\build_installer.ps1
}

.\build_update_manifest.ps1 -Version $Version -DownloadUrl $downloadUrl -Output $ManifestPath -Notes $Notes -SkipBuild:$SkipBuild | Out-Host

if (!(Test-Path $ExePath)) {
  throw "Executavel nao encontrado: $ExePath"
}
if (!(Test-Path $ManifestPath)) {
  throw "Manifesto nao encontrado: $ManifestPath"
}

$exeHash = (Get-FileHash $ExePath -Algorithm SHA256).Hash.ToLowerInvariant()
$manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
if ($manifest.version -ne $Version) {
  throw "Manifesto esta em v$($manifest.version), esperado v$Version."
}
if ($manifest.windows.sha256 -ne $exeHash) {
  throw "Hash do manifesto nao bate com o executavel."
}

Write-Host "Release: $Repository $tag"
Write-Host "Exe: $((Resolve-Path $ExePath).Path)"
Write-Host "Manifesto: $((Resolve-Path $ManifestPath).Path)"
Write-Host "SHA256: $exeHash"

if ($DryRun) {
  Write-Host "Dry run concluido. Nenhum upload foi enviado."
  exit 0
}

$token = $env:GITHUB_TOKEN
if (!$token) {
  $token = $env:GH_TOKEN
}
if (!$token) {
  $token = [Environment]::GetEnvironmentVariable("GITHUB_TOKEN", "User")
}
if (!$token) {
  $token = [Environment]::GetEnvironmentVariable("GH_TOKEN", "User")
}
if (!$token) {
  $token = [Environment]::GetEnvironmentVariable("GITHUB_TOKEN", "Machine")
}
if (!$token) {
  $token = [Environment]::GetEnvironmentVariable("GH_TOKEN", "Machine")
}
if (!$token) {
  throw "Defina GITHUB_TOKEN ou GH_TOKEN com permissao de Contents/Release write antes de publicar."
}

$script:GitHubHeaders = @{
  Authorization = "Bearer $token"
  Accept = "application/vnd.github+json"
  "X-GitHub-Api-Version" = "2022-11-28"
  "User-Agent" = "AizenStreamControlPublisher"
}

$apiBase = "https://api.github.com/repos/$Repository"
$release = Invoke-GitHubJson -Method "GET" -Uri "$apiBase/releases/tags/$tag" -OkStatus @(200, 404)

if ($null -eq $release) {
  $release = Invoke-GitHubJson -Method "POST" -Uri "$apiBase/releases" -Body @{
    tag_name = $tag
    name = $tag
    body = $Notes
    draft = $false
    prerelease = $false
    make_latest = "true"
  } -OkStatus @(201)
  Write-Host "Release criada: $tag"
} else {
  $release = Invoke-GitHubJson -Method "PATCH" -Uri "$apiBase/releases/$($release.id)" -Body @{
    name = $tag
    body = $Notes
    draft = $false
    prerelease = $false
    make_latest = "true"
  } -OkStatus @(200)
  Write-Host "Release atualizada: $tag"
}

$assets = @($release.assets)
foreach ($asset in $assets) {
  if ($asset.name -in @("AizenStreamControl.exe", "AizenStreamControlSetup.exe", "updates.json")) {
    Invoke-GitHubJson -Method "DELETE" -Uri "$apiBase/releases/assets/$($asset.id)" -OkStatus @(204) | Out-Null
    Write-Host "Asset antigo removido: $($asset.name)"
  }
}

$uploadBase = [string]$release.upload_url
$uploadBase = $uploadBase -replace '\{.*$', ''
if (!$uploadBase.StartsWith("https://")) {
  throw "URL de upload invalida retornada pelo GitHub: $uploadBase"
}
$assetPaths = @($ExePath, $ManifestPath)
if (Test-Path $SetupPath) {
  $assetPaths += $SetupPath
}
foreach ($assetPath in $assetPaths) {
  $item = Get-Item $assetPath
  $assetName = [uri]::EscapeDataString($item.Name)
  $uploadUri = "${uploadBase}?name=$assetName"
  Invoke-RestMethod `
    -Method POST `
    -Uri $uploadUri `
    -Headers $script:GitHubHeaders `
    -ContentType "application/octet-stream" `
    -InFile $item.FullName `
    | Out-Null
  Write-Host "Asset enviado: $($item.Name)"
}

Write-Host "Publicado: https://github.com/$Repository/releases/tag/$tag"
