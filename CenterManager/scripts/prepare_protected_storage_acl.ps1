param(
    [string]$ServiceName = "AnTechKidsData",
    [string]$ProtectedRoot = "$env:ProgramData\AnTechKids\CenterManager\Protected",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Administrator privileges are required."
    }
}

function Assert-ServiceExists([string]$Name) {
    $service = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if ($null -eq $service) {
        throw "Windows service '$Name' is not installed. Refusing to apply service-only ACLs."
    }
}

Assert-Administrator
Assert-ServiceExists $ServiceName

$serviceSid = "NT SERVICE\$ServiceName"
$paths = @(
    $ProtectedRoot,
    (Join-Path $ProtectedRoot "Database"),
    (Join-Path $ProtectedRoot "Backup"),
    (Join-Path $ProtectedRoot "Key"),
    (Join-Path $ProtectedRoot "metadata")
)

Write-Host "SEC-02 protected storage ACL plan"
Write-Host "Root: $ProtectedRoot"
Write-Host "Service SID: $serviceSid"
Write-Host "Interactive users receive no direct ACL grant."

if (-not $Apply) {
    Write-Host "Dry run only. Re-run with -Apply after the DB broker service is installed and validated."
    exit 0
}

foreach ($path in $paths) {
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

# Remove inherited permissions, then grant only service, SYSTEM and local
# Administrators. No Users/Authenticated Users grant is added. This script is
# intentionally not run automatically by the desktop application.
icacls $ProtectedRoot /inheritance:r | Out-Null
icacls $ProtectedRoot /grant:r `
    "$serviceSid:(OI)(CI)F" `
    "SYSTEM:(OI)(CI)F" `
    "BUILTIN\Administrators:(OI)(CI)F" | Out-Null

# Re-apply recursively so pre-existing children cannot retain weaker ACLs.
icacls $ProtectedRoot /inheritance:r /T /C | Out-Null
icacls $ProtectedRoot /grant:r `
    "$serviceSid:(OI)(CI)F" `
    "SYSTEM:(OI)(CI)F" `
    "BUILTIN\Administrators:(OI)(CI)F" /T /C | Out-Null

Write-Host "Protected storage ACLs applied."
Write-Host "Do not enable ANTECHKIDS_PROTECTED_STORAGE_MODE=enforced until the service-backed DB broker is active."
