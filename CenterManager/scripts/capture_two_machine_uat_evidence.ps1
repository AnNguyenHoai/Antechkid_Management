param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("A", "B")]
    [string]$Role,

    [Parameter(Mandatory = $true)]
    [string]$Stage,

    [Parameter(Mandatory = $true)]
    [string]$ReleaseRoot,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

function Get-Sha256Text([string]$Value) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
        return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Get-FileSha256OrNull([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Invoke-BundledGit([string[]]$Arguments) {
    $output = & $script:GitExe @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    if ($null -eq $output) {
        return ""
    }
    return (($output | Out-String).Trim())
}

function Read-JsonOrNull([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    try {
        return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

$root = (Resolve-Path -LiteralPath $ReleaseRoot).Path
$manifestPath = Join-Path $root "RELEASE_MANIFEST.json"
$script:GitExe = Join-Path $root "git\cmd\git.exe"
$runtimeDb = Join-Path $root "runtime\Database\center.db"
$repoRoot = Join-Path $root "runtime\repository"
$repoDb = Join-Path $repoRoot "database\center.db"
$lockPath = Join-Path $root "runtime\collaboration\lock.json"
$snapshotRoot = Join-Path $root "runtime\snapshots"

if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "RELEASE_MANIFEST.json not found under release root: $root"
}
if (-not (Test-Path -LiteralPath $script:GitExe -PathType Leaf)) {
    throw "Bundled Git not found: $script:GitExe"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$machineName = if ([string]::IsNullOrWhiteSpace($env:COMPUTERNAME)) { "unknown-machine" } else { $env:COMPUTERNAME }
$machineFingerprint = Get-Sha256Text $machineName

$repoHead = $null
$remoteFingerprint = $null
$changedCount = $null
$repositoryAvailable = Test-Path -LiteralPath (Join-Path $repoRoot ".git")
if ($repositoryAvailable) {
    $repoHead = Invoke-BundledGit @("-C", $repoRoot, "rev-parse", "HEAD")
    $remoteUrl = Invoke-BundledGit @("-C", $repoRoot, "remote", "get-url", "origin")
    if (-not [string]::IsNullOrWhiteSpace($remoteUrl)) {
        # Never write the remote URL to evidence because it may contain credentials.
        $remoteFingerprint = Get-Sha256Text $remoteUrl
    }
    $status = Invoke-BundledGit @("-C", $repoRoot, "status", "--porcelain")
    if ($null -ne $status) {
        if ([string]::IsNullOrWhiteSpace($status)) {
            $changedCount = 0
        }
        else {
            $changedCount = @($status -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }).Count
        }
    }
}

$runtimeSha = Get-FileSha256OrNull $runtimeDb
$authoritativeSha = Get-FileSha256OrNull $repoDb
$dbMatches = ($null -ne $runtimeSha) -and ($null -ne $authoritativeSha) -and ($runtimeSha -eq $authoritativeSha)

$lock = Read-JsonOrNull $lockPath
$lockEvidence = [ordered]@{
    present = ($null -ne $lock)
    locked = if ($null -ne $lock) { [bool]$lock.locked } else { $false }
    lease_expires_at = if ($null -ne $lock) { $lock.lease_expires_at } else { $null }
    finishing_deadline = if ($null -ne $lock) { $lock.finishing_deadline } else { $null }
    publish_intent = if ($null -ne $lock) { [bool]$lock.publish_intent } else { $false }
}

$snapshotFiles = @()
if (Test-Path -LiteralPath $snapshotRoot -PathType Container) {
    $snapshotFiles = @(Get-ChildItem -LiteralPath $snapshotRoot -File -Recurse -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc)
}
$latestSnapshotSha = $null
if ($snapshotFiles.Count -gt 0) {
    $latestSnapshotSha = Get-FileSha256OrNull $snapshotFiles[-1].FullName
}

$report = [ordered]@{
    schema_version = 1
    task = "EP-PROD-05"
    captured_at_utc = [DateTime]::UtcNow.ToString("o")
    role = $Role
    stage = $Stage
    machine_fingerprint = $machineFingerprint
    release = [ordered]@{
        application = $manifest.application
        version = $manifest.version
        release_channel = $manifest.release_channel
        source_commit = $manifest.source_commit
        platform = $manifest.platform
    }
    repository = [ordered]@{
        available = [bool]$repositoryAvailable
        head = $repoHead
        remote_fingerprint = $remoteFingerprint
        changed_entry_count = $changedCount
        clean = ($null -ne $changedCount -and $changedCount -eq 0)
    }
    database = [ordered]@{
        runtime_sha256 = $runtimeSha
        authoritative_sha256 = $authoritativeSha
        authoritative_matches_runtime = [bool]$dbMatches
    }
    collaboration = $lockEvidence
    recovery = [ordered]@{
        snapshot_count = $snapshotFiles.Count
        latest_snapshot_sha256 = $latestSnapshotSha
    }
}

$outputParent = Split-Path -Parent $OutputPath
if (-not [string]::IsNullOrWhiteSpace($outputParent)) {
    New-Item -ItemType Directory -Path $outputParent -Force | Out-Null
}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Host "EP-PROD-05 evidence captured: $OutputPath"
Write-Host "Role=$Role Stage=$Stage Release=$($manifest.version) Source=$($manifest.source_commit)"
Write-Host "Repository HEAD=$repoHead DB converged=$dbMatches Snapshots=$($snapshotFiles.Count)"
