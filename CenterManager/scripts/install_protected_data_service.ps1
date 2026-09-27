param(
    [string]$PythonExe = "python",
    [switch]$Start
)

$ErrorActionPreference = "Stop"
$ServiceName = "AnTechKidsData"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Administrator privileges are required."
    }
}

Assert-Administrator

# pywin32 registers the ServiceFramework host. Registration alone does not move
# database access out of the GUI; SEC-02 enforced mode remains blocked until the
# broker implementation is complete.
& $PythonExe -m centermanager.platform.protected_data_service.service_host install --startup auto
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install $ServiceName."
}

# Use the per-service virtual account rather than an employee account. This is
# the identity that receives NTFS access to protected Database/Key/Backup paths.
& sc.exe config $ServiceName obj= "NT SERVICE\$ServiceName" password= ""
if ($LASTEXITCODE -ne 0) {
    throw "Failed to configure the virtual service account."
}

# Ensure the service SID is present in the process token so ACLs can grant access
# specifically to NT SERVICE\AnTechKidsData.
& sc.exe sidtype $ServiceName unrestricted
if ($LASTEXITCODE -ne 0) {
    throw "Failed to enable the service SID."
}

if ($Start) {
    Start-Service -Name $ServiceName
    $service = Get-Service -Name $ServiceName
    if ($service.Status -ne "Running") {
        throw "$ServiceName did not reach Running state."
    }
}

Write-Host "$ServiceName installed with virtual service identity."
Write-Host "Next: validate the broker, then run prepare_protected_storage_acl.ps1 -Apply."
