param(
    [Parameter(Mandatory=$true)][string]$ReleaseRoot,
    [Parameter(Mandatory=$true)][string]$BackupPath,
    [Parameter(Mandatory=$true)][string]$Stage,
    [Parameter(Mandatory=$true)][string]$OutputPath
)

$ErrorActionPreference = 'Stop'

function Get-FileSha256OrNull([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Read-JsonFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Test-SqliteIntegrity([string]$DbPath) {
    if (-not (Test-Path -LiteralPath $DbPath -PathType Leaf)) { return 'missing' }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $python) { return 'not_checked' }
    $script = "import sqlite3,sys; c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro', uri=True); print(c.execute('PRAGMA integrity_check').fetchone()[0]); c.close()"
    try {
        return (& $python.Source -c $script $DbPath 2>$null | Select-Object -First 1).Trim()
    } catch {
        return 'error'
    }
}

$releaseRootResolved = (Resolve-Path -LiteralPath $ReleaseRoot).Path
$backupResolved = (Resolve-Path -LiteralPath $BackupPath).Path
$runtimeRoot = Join-Path $releaseRootResolved 'runtime'
$managedBackupRoot = Join-Path $runtimeRoot 'Backup\publish'
$runtimeDb = Join-Path $runtimeRoot 'Database\center.db'
$manifestPath = Join-Path $backupResolved 'manifest.json'
$backupDb = Join-Path $backupResolved 'center.db'
$metadataPath = Join-Path $backupResolved 'metadata'
$releaseManifestPath = Join-Path $releaseRootResolved 'RELEASE_MANIFEST.json'

$manifest = Read-JsonFile $manifestPath
$releaseManifest = Read-JsonFile $releaseManifestPath

$managedRootFull = [System.IO.Path]::GetFullPath($managedBackupRoot).TrimEnd('\') + '\'
$backupFull = [System.IO.Path]::GetFullPath($backupResolved).TrimEnd('\') + '\'
$isManaged = $backupFull.StartsWith($managedRootFull, [System.StringComparison]::OrdinalIgnoreCase)

$backupDbSha = Get-FileSha256OrNull $backupDb
$runtimeDbSha = Get-FileSha256OrNull $runtimeDb
$manifestChecksum = $null
if ($null -ne $manifest -and $null -ne $manifest.checksums) {
    $manifestChecksum = $manifest.checksums.'center.db'
    if ($null -ne $manifestChecksum) { $manifestChecksum = $manifestChecksum.ToString().ToLowerInvariant() }
}

$tempArtifacts = @()
if (Test-Path -LiteralPath (Join-Path $runtimeRoot 'Database')) {
    $tempArtifacts += Get-ChildItem -LiteralPath (Join-Path $runtimeRoot 'Database') -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like '.center.db.restore-*' } |
        ForEach-Object { $_.Name }
}
$tempArtifacts += Get-ChildItem -LiteralPath $runtimeRoot -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like '.metadata.restore-*' -or $_.Name -like '.metadata.previous-*' } |
    ForEach-Object { $_.Name }

$report = [ordered]@{
    schema_version = 1
    task = 'EP-PROD-06'
    captured_at_utc = [DateTime]::UtcNow.ToString('o')
    stage = $Stage
    release = [ordered]@{
        version = if ($null -ne $releaseManifest) { $releaseManifest.version } else { $null }
        source_commit = if ($null -ne $releaseManifest) { $releaseManifest.source_commit } else { $null }
    }
    backup = [ordered]@{
        managed_path = $isManaged
        format_version = if ($null -ne $manifest) { $manifest.format_version } else { $null }
        manifest_sha256 = Get-FileSha256OrNull $manifestPath
        database_sha256 = $backupDbSha
        manifest_database_sha256 = $manifestChecksum
        checksum_matches = ($null -ne $backupDbSha -and $null -ne $manifestChecksum -and $backupDbSha -eq $manifestChecksum)
        sqlite_integrity = Test-SqliteIntegrity $backupDb
        metadata_present = (Test-Path -LiteralPath $metadataPath -PathType Container)
    }
    runtime = [ordered]@{
        database_sha256 = $runtimeDbSha
        matches_selected_backup = ($null -ne $runtimeDbSha -and $null -ne $backupDbSha -and $runtimeDbSha -eq $backupDbSha)
        restore_temp_artifact_count = @($tempArtifacts).Count
    }
}

$outDir = Split-Path -Parent $OutputPath
if ($outDir) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Host "EP-PROD-06 evidence written: $OutputPath"
