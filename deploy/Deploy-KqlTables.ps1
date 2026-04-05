<#
.SYNOPSIS
    Create KQL telemetry tables in the Eventhouse.

.DESCRIPTION
    Executes .create-or-alter table commands against the KQL Database
    to provision 3 telemetry tables with caching/retention policies:
      - SensorTelemetry
      - EquipmentEvents
      - LineProduction

.EXAMPLE
    .\deploy\Deploy-KqlTables.ps1 -OntologyPath "ontologies\SaintGobain"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$OntologyPath
)

$ErrorActionPreference = "Stop"

Import-Module (Join-Path $PSScriptRoot "FabricHelpers.psm1") -Force

$configPath = Join-Path $OntologyPath "config.json"
$config     = Get-Config -ConfigPath $configPath

if (-not $config.kqlDatabase.id) {
    Write-Error "kqlDatabase.id must be set. Run Deploy-Infrastructure.ps1 first."
    exit 1
}

$kqlDatabaseId   = $config.kqlDatabase.id
$queryServiceUri = $config.kqlDatabase.queryServiceUri

if (-not $queryServiceUri) {
    Write-Error "kqlDatabase.queryServiceUri not set. Run Deploy-Infrastructure.ps1 first."
    exit 1
}

$dbName = $config.kqlDatabase.name
$kqlHeaders = Get-FabricHeaders -Resource "https://kusto.kusto.windows.net"

Write-Host "=== Deploy KQL Tables ===" -ForegroundColor Cyan
Write-Host "  Database: $dbName" -ForegroundColor DarkGray
Write-Host "  Endpoint: $queryServiceUri" -ForegroundColor DarkGray

# KQL commands to create tables — aligned with ontology bindings + simulator
$kqlCommands = @"
// Create SensorTelemetry table (Sensor time-series binding)
.create-or-alter table SensorTelemetry (
    SensorId: string,
    Timestamp: datetime,
    Value: real,
    Unit: string,
    Quality: string
)

// Set retention policy
.alter table SensorTelemetry policy retention "{ \"SoftDeletePeriod\": \"365.00:00:00\", \"Recoverability\": \"Enabled\" }"

// Create EquipmentStatus table (Equipment time-series binding)
.create-or-alter table EquipmentStatus (
    EquipmentId: string,
    Timestamp: datetime,
    Status: string,
    RunHours: real,
    CycleCount: long
)

// Set retention policy
.alter table EquipmentStatus policy retention "{ \"SoftDeletePeriod\": \"365.00:00:00\", \"Recoverability\": \"Enabled\" }"

// Create ProductionMetrics table (ProductionLine time-series binding)
.create-or-alter table ProductionMetrics (
    LineId: string,
    Timestamp: datetime,
    OutputUnits: long,
    DefectRate: real,
    OEE: real
)

// Set retention policy
.alter table ProductionMetrics policy retention "{ \"SoftDeletePeriod\": \"365.00:00:00\", \"Recoverability\": \"Enabled\" }"

// Create Alerts table
.create-or-alter table Alerts (
    AlertId: string,
    EntityId: string,
    EntityType: string,
    Timestamp: datetime,
    Severity: string,
    Message: string,
    IsResolved: bool
)

// Set retention policy
.alter table Alerts policy retention "{ \"SoftDeletePeriod\": \"365.00:00:00\", \"Recoverability\": \"Enabled\" }"
"@

# Split into individual commands
$commands = $kqlCommands -split "(?=\.create-or-alter|\.alter)" | Where-Object { $_.Trim() }

Write-Host "`n[1] Creating KQL tables..." -ForegroundColor White

foreach ($cmd in $commands) {
    $cmd = $cmd.Trim()
    if (-not $cmd -or $cmd.StartsWith("//")) { continue }

    # Extract table name for logging
    if ($cmd -match "table\s+(\w+)") {
        $tableName = $matches[1]
        Write-Host "  Executing command for: $tableName" -ForegroundColor DarkGray
    }

    $mgmtUri = "$queryServiceUri/v1/rest/mgmt"
    $body = @{
        db  = $dbName
        csl = $cmd
    }

    try {
        $null = Invoke-RestMethod -Uri $mgmtUri -Method POST -Headers $kqlHeaders -Body ($body | ConvertTo-Json) -ContentType "application/json"
        Write-Host "  [OK] Command executed" -ForegroundColor Green
    }
    catch {
        Write-Warning "  Command failed: $_"
    }
}

Write-Host "`n=== KQL Tables Ready ===" -ForegroundColor Green
