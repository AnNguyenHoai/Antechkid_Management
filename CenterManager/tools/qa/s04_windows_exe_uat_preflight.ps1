# S04 Windows EXE UAT — read-only preflight of a disposable clone.
# This script NEVER starts or kills the EXE, changes a Git remote, or writes DB.
param(
  [Parameter(Mandatory=$true)][string]$CloneRoot,
  [Parameter(Mandatory=$true)][string]$ExeRelativePath
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $CloneRoot).Path
$runtime = Join-Path $root "runtime"
$repo = Join-Path $runtime "repository"
$db = Join-Path $runtime "Database\center.db"
$exe = Join-Path $root $ExeRelativePath
$flag = Join-Path $root "S04_UAT_DISPOSABLE_CLONE.txt"

if (-not (Test-Path -LiteralPath $flag -PathType Leaf)) {
  throw "Missing explicit S04_UAT_DISPOSABLE_CLONE.txt. Refusing to inspect an operational workspace."
}
if (-not (Test-Path -LiteralPath $db -PathType Leaf)) { throw "Missing cloned SQLCipher database." }
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Missing cloned Windows executable." }
if (-not (Test-Path -LiteralPath (Join-Path $repo ".git"))) { throw "Cloned local Git repo missing." }
if (-not $exe.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
  throw "EXE is outside the disposable clone."
}
$origin = (& git -C $repo remote get-url origin 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw "Cannot read cloned Git remote." }
if ($origin -match 'github\.com|https?://|git@|Antechkid_CenterManager_DatabaseOfficial') {
  throw "Remote is not isolated; NEVER run UAT against GitHub/production origin."
}
if (-not ((Test-Path -LiteralPath $origin) -or $origin.StartsWith("file:///"))) {
  throw "Expected an isolated local file-based Git remote; observed remote is not an accessible local path."
}

# Enumerate only names, lengths, checksums. Do NOT emit SQLCipher keys or content.
$observed = @(
  $db,
  ($db + "-wal"),
  ($db + "-shm"),
  ($db + "-journal"),
  (Join-Path $runtime "manifest.json"),
  (Join-Path $runtime "metadata\version.json")
)
$evidence = @()
foreach ($path in $observed) {
  if (Test-Path -LiteralPath $path -PathType Leaf) {
    $item = Get-Item -LiteralPath $path
    $evidence += [PSCustomObject]@{
      RelativePath = $path.Substring($root.Length).TrimStart('\\', '/')
      Bytes = $item.Length
      SHA256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    }
  }
}
$employees = Join-Path $runtime "Attachments\Employees"
if (Test-Path -LiteralPath $employees) {
  foreach ($item in (Get-ChildItem -LiteralPath $employees -File -Recurse)) {
    $evidence += [PSCustomObject]@{
      RelativePath = $item.FullName.Substring($root.Length).TrimStart('\\', '/')
      Bytes = $item.Length
      SHA256 = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash
    }
  }
}
[PSCustomObject]@{
  Verification = "DISPOSABLE_CLONE_PREFLIGHT_ONLY"
  CloneRoot = $root
  ExePath = $exe
  LocalGitOrigin = $origin
  ClonedFiles = $evidence
  CheckedAtUtc = [DateTime]::UtcNow.ToString("o")
} | ConvertTo-Json -Depth 6
