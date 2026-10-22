#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'

# Allow only local-subnet traffic to the two development ports.
$ruleName = 'AnTang-Local-Development'
$ports = @(8000, 8081)
$wslCreator = '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}'

if (-not (Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name $ruleName -DisplayName 'AnTang local API and Metro' `
        -Direction Inbound -Action Allow -Protocol TCP -LocalPort $ports `
        -RemoteAddress LocalSubnet -Profile Any | Out-Null
}
if (-not (Get-NetFirewallHyperVRule -Name $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallHyperVRule -Name $ruleName -DisplayName 'AnTang WSL local API and Metro' `
        -Direction Inbound -Action Allow -VMCreatorId $wslCreator -Protocol TCP `
        -LocalPorts $ports -RemoteAddresses LocalSubnet | Out-Null
}

$state = [ordered]@{
    configured = $true
    rule = $ruleName
    ports = $ports
    remoteScope = 'LocalSubnet'
}
$state | ConvertTo-Json

