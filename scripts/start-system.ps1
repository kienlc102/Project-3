# One startup command: publish live host LAN metadata and start Docker Compose.
# This is the system launcher, not an additional HTTP discovery service.
[CmdletBinding()]
param([switch]$BackendOnly, [switch]$NoBuild, [switch]$NetworkOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$runtimeDirectory = Join-Path $projectRoot '.runtime'
$metadataFile = Join-Path $runtimeDirectory 'host-network.json'
New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null

function Publish-HostNetwork {
    # Only connected interfaces with a default gateway; ignore Docker/WSL adapters.
    $interfaces = @(Get-NetIPConfiguration | Where-Object {
        $_.NetAdapter.Status -eq 'Up' -and $_.IPv4DefaultGateway -and
        $_.InterfaceAlias -notmatch 'vEthernet|Docker|WSL|VMware|VirtualBox|Loopback'
    } | ForEach-Object {
        $configuration = $_
        foreach ($address in $configuration.IPv4Address) {
            if ($address.IPAddress -notmatch '^(127\.|169\.254\.)') {
                @{ name = $configuration.InterfaceAlias; address = $address.IPAddress;
                   netmask = [string]$address.PrefixLength }
            }
        }
    })
    $payload = @{ interfaces = $interfaces; updated_at = [DateTime]::UtcNow.ToString('o') }
    $temporaryFile = Join-Path $runtimeDirectory 'host-network.tmp'
    [IO.File]::WriteAllText($temporaryFile, ($payload | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporaryFile -Destination $metadataFile -Force
    return (($interfaces | ForEach-Object { "$($_.address)/$($_.netmask)" }) -join ', ')
}

Push-Location $projectRoot
try {
    $lastNetwork = Publish-HostNetwork
    Write-Host "Host LAN: $lastNetwork"
    if (-not $NetworkOnly) {
        $composeArgs = @('compose', 'up', '-d')
        if (-not $NoBuild) { $composeArgs += '--build' }
        if ($BackendOnly) { $composeArgs += 'backend' }
        & docker @composeArgs
        if ($LASTEXITCODE -ne 0) { throw 'Docker Compose startup failed' }
    } else {
        Write-Host 'Network-only mode: Docker containers are unchanged.'
    }
    Write-Host 'Monitoring host LAN. Keep this terminal open. Ctrl+C stops host-network updates.'
    while ($true) {
        Start-Sleep -Seconds 10
        try {
            $currentNetwork = Publish-HostNetwork
            if ($currentNetwork -ne $lastNetwork) {
                Write-Host "Host LAN changed: $currentNetwork"
                $lastNetwork = $currentNetwork
            }
        } catch {
            Write-Warning "Cannot update host network: $($_.Exception.Message)"
        }
    }
} finally {
    Pop-Location
}
