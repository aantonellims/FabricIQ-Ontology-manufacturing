<#
.SYNOPSIS
    Deploy Fabric workspace, Lakehouse, and Eventhouse infrastructure.

.DESCRIPTION
    Creates the SG-Manufacturing-Ontology workspace on the configured capacity,
    then provisions a Lakehouse for master data and an Eventhouse with KQL Database
    for real-time telemetry. Updates config.json with all resource IDs.

    Idempotent: re-running reuses existing resources.

.EXAMPLE
    .\deploy\Deploy-Infrastructure.ps1
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$OntologyPath
)

$ErrorActionPreference = "Stop"

# Import shared helpers
Import-Module (Join-Path $PSScriptRoot "FabricHelpers.psm1") -Force

$configPath = Join-Path $OntologyPath "config.json"
$config     = Get-Config -ConfigPath $configPath
$apiBase    = $config.apiBase
$headers    = Get-FabricHeaders

Write-Host "=== SG Manufacturing Ontology - Infrastructure ===" -ForegroundColor Cyan

# --- 1) Find capacity ---
Write-Host "`n[1] Looking up capacity '$($config.capacity.name)'..." -ForegroundColor White
$capacities = (Invoke-FabricApi -Uri "$apiBase/capacities" -Headers $headers).value
$capacity   = $capacities | Where-Object { $_.displayName -eq $config.capacity.name }
if (-not $capacity) {
    Write-Error "Capacity '$($config.capacity.name)' not found. Update config.json capacity.name."
    exit 1
}
$capacityId = $capacity.id
$capacitySku = $capacity.sku
$capacityRegion = $capacity.region
Write-Host "  Capacity: $capacityId (sku=$capacitySku, region=$capacityRegion)" -ForegroundColor DarkGray

# Check if capacity is paused / suspended
$state = $capacity.state
if ($state -and $state -ne "Active") {
    Write-Error "Capacity '$($config.capacity.name)' is in '$state' state. Resume the capacity in the Azure portal before deploying."
    exit 1
}

# --- 2) Find or create workspace ---
Write-Host "`n[2] Workspace '$($config.workspace.name)'..." -ForegroundColor White
$workspaces = (Invoke-FabricApi -Uri "$apiBase/workspaces" -Headers $headers).value
$ws = $workspaces | Where-Object { $_.displayName -eq $config.workspace.name }
if ($ws) {
    Write-Host "  [EXISTS] Workspace = $($ws.id)" -ForegroundColor Yellow
} else {
    $wsBody = @{
        displayName = $config.workspace.name
        capacityId  = $capacityId
        description = "Saint-Gobain Manufacturing Ontology - RTI Demo"
    }
    $ws = Invoke-FabricApi -Uri "$apiBase/workspaces" -Method POST -Headers $headers -Body $wsBody
    Write-Host "  [CREATED] Workspace = $($ws.id)" -ForegroundColor Green
}
$workspaceId = $ws.id

# --- 3) Lakehouse ---
Write-Host "`n[3] Lakehouse '$($config.lakehouse.name)'..." -ForegroundColor White
$lh = Find-OrCreateItem -WorkspaceId $workspaceId -DisplayName $config.lakehouse.name `
        -ItemType "Lakehouse" -Description "Master data for SG manufacturing entities" `
        -Headers $headers -ApiBase $apiBase
$lakehouseId = $lh.id

# --- 4) Eventhouse ---
Write-Host "`n[4] Eventhouse '$($config.eventhouse.name)'..." -ForegroundColor White
$eh = Find-OrCreateItem -WorkspaceId $workspaceId -DisplayName $config.eventhouse.name `
        -ItemType "Eventhouse" -Description "Real-time telemetry for SG manufacturing" `
        -Headers $headers -ApiBase $apiBase
$eventhouseId = $eh.id

# --- 5) Wait for KQL Database auto-provisioning ---
Write-Host "`n[5] Waiting for KQL Database..." -ForegroundColor White
$maxRetries = 12
$kqlDb = $null
for ($i = 0; $i -lt $maxRetries; $i++) {
    $items = (Invoke-FabricApi -Uri "$apiBase/workspaces/$workspaceId/items" -Headers $headers).value
    $kqlDb = $items | Where-Object { $_.type -eq "KQLDatabase" }
    if ($kqlDb) { break }
    Write-Host "  Waiting for KQL Database... ($($i+1)/$maxRetries)" -ForegroundColor DarkGray
    Start-Sleep -Seconds 10
}
if (-not $kqlDb) {
    Write-Error "KQL Database was not auto-created with Eventhouse after $($maxRetries * 10)s."
    exit 1
}
$kqlDatabaseId = $kqlDb.id
Write-Host "  [READY] KQL Database = $kqlDatabaseId" -ForegroundColor Green

# Get KQL query service URI
$kqlDetails      = Invoke-FabricApi -Uri "$apiBase/workspaces/$workspaceId/kqlDatabases/$kqlDatabaseId" -Headers $headers
$queryServiceUri = $kqlDetails.properties.queryServiceUri

# --- 6) Update config.json ---
Write-Host "`n[6] Updating config.json..." -ForegroundColor White
$config.workspace.id                = $workspaceId
$config.lakehouse.id                = $lakehouseId
$config.eventhouse.id               = $eventhouseId
$config.kqlDatabase.id              = $kqlDatabaseId
$config.kqlDatabase.name            = $kqlDb.displayName
$config.kqlDatabase.queryServiceUri = $queryServiceUri
Save-Config -Config $config -ConfigPath $configPath

# --- 7) Post-deploy validation ---
Write-Host "`n[7] Validating deployed resources..." -ForegroundColor White
$valid = $true

try {
    $null = Invoke-FabricApi -Uri "$apiBase/workspaces/$workspaceId" -Headers $headers
    Write-Host "  [OK] Workspace reachable" -ForegroundColor Green
} catch {
    Write-Warning "  Workspace validation failed: $_"
    $valid = $false
}

try {
    $null = Invoke-FabricApi -Uri "$apiBase/workspaces/$workspaceId/lakehouses/$lakehouseId" -Headers $headers
    Write-Host "  [OK] Lakehouse reachable" -ForegroundColor Green
} catch {
    Write-Warning "  Lakehouse validation failed: $_"
    $valid = $false
}

try {
    $null = Invoke-FabricApi -Uri "$apiBase/workspaces/$workspaceId/kqlDatabases/$kqlDatabaseId" -Headers $headers
    Write-Host "  [OK] KQL Database reachable" -ForegroundColor Green
} catch {
    Write-Warning "  KQL Database validation failed: $_"
    $valid = $false
}

if (-not $valid) {
    Write-Error "Post-deploy validation failed. Check errors above."
    exit 1
}

# --- Summary ---
Write-Host "`n=== Infrastructure Ready ===" -ForegroundColor Green
Write-Host "  Workspace:    $workspaceId"    -ForegroundColor White
Write-Host "  Lakehouse:    $lakehouseId"    -ForegroundColor White
Write-Host "  Eventhouse:   $eventhouseId"   -ForegroundColor White
Write-Host "  KQL Database: $kqlDatabaseId"  -ForegroundColor White
Write-Host "  Query URI:    $queryServiceUri" -ForegroundColor White
