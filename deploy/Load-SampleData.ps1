<#
.SYNOPSIS
    Upload CSV files to Lakehouse and load as Delta tables.

.DESCRIPTION
    Uploads 6 CSV files from data/ to the Lakehouse Files area via OneLake DFS API,
    then converts each to a Delta table using the Lakehouse Table Load API.

    Table mapping:
      plants.csv     -> DIM_PLANT
      lines.csv      -> DIM_LINE
      equipment.csv  -> DIM_EQUIPMENT
      sensors.csv    -> DIM_SENSOR
      products.csv   -> DIM_PRODUCT
      workorders.csv -> DIM_WORKORDER

.EXAMPLE
    .\deploy\Load-SampleData.ps1 -OntologyPath "ontologies\SaintGobain"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$OntologyPath
)

$ErrorActionPreference = "Stop"

Import-Module (Join-Path $PSScriptRoot "FabricHelpers.psm1") -Force

$configPath = Join-Path $OntologyPath "config.json"
$config     = Get-Config -ConfigPath $configPath
$apiBase    = $config.apiBase

if (-not $config.workspace.id) {
    Write-Error "workspace.id must be set. Run Deploy-Infrastructure.ps1 first."
    exit 1
}
if (-not $config.lakehouse.id) {
    Write-Error "lakehouse.id must be set. Run Deploy-Infrastructure.ps1 first."
    exit 1
}

$workspaceId   = $config.workspace.id
$workspaceName = $config.workspace.name
$lakehouseId   = $config.lakehouse.id
$lakehouseName = $config.lakehouse.name
$headers       = Get-FabricHeaders
$oneLakeHeaders = Get-FabricHeaders -Resource "https://storage.azure.com"

Write-Host "=== Load Sample Data ===" -ForegroundColor Cyan

# File to table mapping
$tableMap = @{
    "plants.csv"     = "DIM_PLANT"
    "lines.csv"      = "DIM_LINE"
    "equipment.csv"  = "DIM_EQUIPMENT"
    "sensors.csv"    = "DIM_SENSOR"
    "products.csv"   = "DIM_PRODUCT"
    "workorders.csv" = "DIM_WORKORDER"
}

$dataDir = Join-Path $OntologyPath "data"
$oneLakeBase = "https://onelake.dfs.fabric.microsoft.com"

# --- 1) Upload CSV files ---
Write-Host "`n[1] Uploading CSV files to Lakehouse..." -ForegroundColor White

foreach ($fileName in $tableMap.Keys) {
    $localPath = Join-Path $dataDir $fileName
    if (-not (Test-Path $localPath)) {
        Write-Warning "  File not found: $localPath - skipping"
        continue
    }

    $remotePath = "Files/staging/$fileName"
    $uploadUri  = "$oneLakeBase/$workspaceName/$lakehouseName/$remotePath`?resource=file"

    Write-Host "  Uploading: $fileName" -ForegroundColor DarkGray

    # Create file
    $null = Invoke-RestMethod -Uri $uploadUri -Method PUT -Headers $oneLakeHeaders -Body ""

    # Append content
    $content     = Get-Content $localPath -Raw -Encoding UTF8
    $contentBytes = [System.Text.Encoding]::UTF8.GetBytes($content)
    $appendUri   = "$oneLakeBase/$workspaceName/$lakehouseName/$remotePath`?action=append&position=0"
    $null = Invoke-RestMethod -Uri $appendUri -Method PATCH -Headers $oneLakeHeaders -Body $contentBytes -ContentType "application/octet-stream"

    # Flush
    $flushUri = "$oneLakeBase/$workspaceName/$lakehouseName/$remotePath`?action=flush&position=$($contentBytes.Length)"
    $null = Invoke-RestMethod -Uri $flushUri -Method PATCH -Headers $oneLakeHeaders

    Write-Host "  [OK] $fileName uploaded" -ForegroundColor Green
}

# --- 2) Load CSV to Delta tables ---
Write-Host "`n[2] Loading CSV files to Delta tables..." -ForegroundColor White

foreach ($fileName in $tableMap.Keys) {
    $tableName  = $tableMap[$fileName]
    $sourcePath = "Files/staging/$fileName"

    Write-Host "  Loading: $tableName from $sourcePath" -ForegroundColor DarkGray

    $loadUri = "$apiBase/workspaces/$workspaceId/lakehouses/$lakehouseId/tables/$tableName/load"
    $loadBody = @{
        relativePath  = $sourcePath
        pathType      = "File"
        mode          = "Overwrite"
        formatOptions = @{
            format   = "Csv"
            header   = $true
            delimiter = ","
        }
    }

    try {
        $response = Invoke-FabricApi -Uri $loadUri -Method POST -Headers $headers -Body $loadBody
        # Handle LRO if returned
        if ($response.StatusCode -eq 202 -or $response.operationId) {
            Write-Host "    Waiting for table load..." -ForegroundColor DarkGray
            Start-Sleep -Seconds 5
        }
        Write-Host "  [OK] $tableName loaded" -ForegroundColor Green
    }
    catch {
        Write-Warning "  Failed to load $tableName : $_"
    }
}

Write-Host "`n=== Sample Data Loaded ===" -ForegroundColor Green
