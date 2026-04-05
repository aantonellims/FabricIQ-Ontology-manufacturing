<#
.SYNOPSIS
    Start the real-time telemetry simulator.

.DESCRIPTION
    Launches the Python simulator that generates and ingests telemetry data
    into the KQL Database tables (SensorTelemetry, EquipmentEvents, LineProduction).

.EXAMPLE
    .\deploy\Start-TelemetrySimulator.ps1 -OntologyPath "ontologies\SaintGobain"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$OntologyPath
)

$ErrorActionPreference = "Stop"

Import-Module (Join-Path $PSScriptRoot "FabricHelpers.psm1") -Force

$configPath = Join-Path $OntologyPath "config.json"
$config     = Get-Config -ConfigPath $configPath

if (-not $config.kqlDatabase.queryServiceUri) {
    Write-Error "kqlDatabase.queryServiceUri must be set. Run Deploy-Infrastructure.ps1 first."
    exit 1
}

$simulatorScript = Join-Path $OntologyPath "simulator\telemetry_simulator.py"
if (-not (Test-Path $simulatorScript)) {
    Write-Error "Simulator script not found: $simulatorScript"
    exit 1
}

Write-Host "=== Starting Telemetry Simulator ===" -ForegroundColor Cyan
Write-Host "  KQL Endpoint: $($config.kqlDatabase.queryServiceUri)" -ForegroundColor DarkGray
Write-Host "  Database: $($config.kqlDatabase.name)" -ForegroundColor DarkGray

# Set environment variables for the simulator
$env:KUSTO_CLUSTER = $config.kqlDatabase.queryServiceUri
$env:KUSTO_DATABASE = $config.kqlDatabase.name

Write-Host "`nLaunching simulator..." -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop`n" -ForegroundColor DarkGray

python $simulatorScript
