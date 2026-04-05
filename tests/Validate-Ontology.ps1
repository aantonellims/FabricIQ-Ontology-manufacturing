<#
.SYNOPSIS
    Validate ontology files for cross-reference consistency.
#>
$ErrorActionPreference = "Stop"
$base = Join-Path $PSScriptRoot "..\ontologies\SaintGobain"
$issues = [System.Collections.Generic.List[string]]::new()

$entityDir = Join-Path $base "ontology\entity-types"
$dataDir   = Join-Path $base "data"
$ntsDir    = Join-Path $base "ontology\bindings\nontimeseries"
$tsDir     = Join-Path $base "ontology\bindings\timeseries"
$relDir    = Join-Path $base "ontology\relationships"

$map = [ordered]@{
    "plant"           = "plants.csv"
    "production-line" = "lines.csv"
    "equipment"       = "equipment.csv"
    "sensor"          = "sensors.csv"
    "product"         = "products.csv"
    "workorder"       = "workorders.csv"
}

Write-Host "`n=== 1. JSON Syntax ===" -ForegroundColor Cyan
Get-ChildItem (Join-Path $base "ontology") -Recurse -Filter "*.json" | ForEach-Object {
    try { $null = Get-Content $_.FullName -Raw | ConvertFrom-Json; Write-Host "  [OK] $($_.Name)" -ForegroundColor Green }
    catch { $issues.Add("JSON: $($_.Name) invalid"); Write-Host "  [FAIL] $($_.Name)" -ForegroundColor Red }
}

Write-Host "`n=== 2. Entity Properties vs CSV Headers ===" -ForegroundColor Cyan
foreach ($k in $map.Keys) {
    $entity = Get-Content (Join-Path $entityDir "$k.json") -Raw | ConvertFrom-Json
    $csvHeaders = (Get-Content (Join-Path $dataDir $map[$k]) -First 1).Split(",")
    $ok = $true
    foreach ($prop in $entity.properties) {
        if ($csvHeaders -notcontains $prop.name) {
            $issues.Add("ENTITY-CSV: $($entity.name).$($prop.name) not in $($map[$k]) headers")
            Write-Host "  [FAIL] $($entity.name).$($prop.name) missing from $($map[$k])" -ForegroundColor Red
            $ok = $false
        }
    }
    if ($ok) { Write-Host "  [OK] $($entity.name) -> $($map[$k])" -ForegroundColor Green }
}

Write-Host "`n=== 3. NonTimeSeries Binding Columns vs CSV Headers ===" -ForegroundColor Cyan
foreach ($k in $map.Keys) {
    $binding = Get-Content (Join-Path $ntsDir "$k.json") -Raw | ConvertFrom-Json
    $csvHeaders = (Get-Content (Join-Path $dataDir $map[$k]) -First 1).Split(",")
    $ok = $true
    foreach ($m in $binding.propertyMappings) {
        if ($csvHeaders -notcontains $m.columnName) {
            $issues.Add("BIND-CSV: $($binding.entityTypeName).$($m.columnName) not in $($map[$k]) headers")
            Write-Host "  [FAIL] $($binding.entityTypeName) column '$($m.columnName)' missing from $($map[$k])" -ForegroundColor Red
            $ok = $false
        }
    }
    if ($ok) { Write-Host "  [OK] $($binding.entityTypeName) binding -> $($map[$k])" -ForegroundColor Green }
}

Write-Host "`n=== 4. Entity Properties vs Binding PropertyNames ===" -ForegroundColor Cyan
foreach ($k in $map.Keys) {
    $entity = Get-Content (Join-Path $entityDir "$k.json") -Raw | ConvertFrom-Json
    $binding = Get-Content (Join-Path $ntsDir "$k.json") -Raw | ConvertFrom-Json
    $entityPropNames = $entity.properties | ForEach-Object { $_.name }
    $ok = $true
    foreach ($m in $binding.propertyMappings) {
        if ($entityPropNames -notcontains $m.propertyName) {
            $issues.Add("BIND-ENTITY: $($binding.entityTypeName) maps '$($m.propertyName)' which is not an entity property")
            Write-Host "  [FAIL] $($binding.entityTypeName) binding property '$($m.propertyName)' not in entity" -ForegroundColor Red
            $ok = $false
        }
    }
    if ($ok) { Write-Host "  [OK] $($entity.name) binding properties match entity" -ForegroundColor Green }
}

Write-Host "`n=== 5. Relationship Key Properties ===" -ForegroundColor Cyan
$entityNameFileMap = @{ "Plant"="plant"; "ProductionLine"="production-line"; "Equipment"="equipment"; "Sensor"="sensor"; "Product"="product"; "WorkOrder"="workorder" }
Get-ChildItem $relDir -Filter "*.json" | ForEach-Object {
    $rel = Get-Content $_.FullName -Raw | ConvertFrom-Json
    $fromFile = $entityNameFileMap[$rel.fromEntityType]
    $toFile   = $entityNameFileMap[$rel.toEntityType]
    $ok = $true

    if ($fromFile) {
        $fromEntity = Get-Content (Join-Path $entityDir "$fromFile.json") -Raw | ConvertFrom-Json
        $fromProps = $fromEntity.properties | ForEach-Object { $_.name }
        if ($fromProps -notcontains $rel.fromKeyProperty) {
            $issues.Add("REL: $($rel.name) fromKey '$($rel.fromKeyProperty)' not in $($rel.fromEntityType)")
            Write-Host "  [FAIL] $($rel.name): fromKey '$($rel.fromKeyProperty)' not in $($rel.fromEntityType) [$($fromProps -join ',')]" -ForegroundColor Red
            $ok = $false
        }
    }
    if ($toFile) {
        $toEntity = Get-Content (Join-Path $entityDir "$toFile.json") -Raw | ConvertFrom-Json
        $toProps = $toEntity.properties | ForEach-Object { $_.name }
        if ($toProps -notcontains $rel.toKeyProperty) {
            $issues.Add("REL: $($rel.name) toKey '$($rel.toKeyProperty)' not in $($rel.toEntityType)")
            Write-Host "  [FAIL] $($rel.name): toKey '$($rel.toKeyProperty)' not in $($rel.toEntityType) [$($toProps -join ',')]" -ForegroundColor Red
            $ok = $false
        }
    }
    if ($ok) { Write-Host "  [OK] $($rel.name): $($rel.fromEntityType).$($rel.fromKeyProperty) -> $($rel.toEntityType).$($rel.toKeyProperty)" -ForegroundColor Green }
}

Write-Host "`n=== 6. TimeSeries Binding Tables vs KQL Deploy Script ===" -ForegroundColor Cyan
$deployKql = Get-Content (Join-Path $PSScriptRoot "..\deploy\Deploy-KqlTables.ps1") -Raw
Get-ChildItem $tsDir -Filter "*.json" | ForEach-Object {
    $tsBinding = Get-Content $_.FullName -Raw | ConvertFrom-Json
    $tblName = $tsBinding.dataSource.tableName
    if ($deployKql -match [regex]::Escape($tblName)) {
        Write-Host "  [OK] $($tsBinding.entityTypeName) -> table '$tblName' in Deploy-KqlTables.ps1" -ForegroundColor Green
    } else {
        $issues.Add("TS-KQL: $($tsBinding.entityTypeName) references '$tblName' not in Deploy-KqlTables.ps1")
        Write-Host "  [FAIL] $($tsBinding.entityTypeName) -> table '$tblName' NOT in Deploy-KqlTables.ps1" -ForegroundColor Red
    }
}

Write-Host "`n=== 7. Simulator Table Names ===" -ForegroundColor Cyan
$simPy = Get-Content (Join-Path $base "simulator\telemetry_simulator.py") -Raw
foreach ($expectedTable in @("SensorTelemetry","EquipmentEvents","LineProduction")) {
    if ($simPy -match [regex]::Escape($expectedTable)) {
        Write-Host "  [OK] Simulator uses '$expectedTable'" -ForegroundColor Green
    } else {
        $issues.Add("SIM: Missing expected table '$expectedTable'")
        Write-Host "  [FAIL] Simulator missing table '$expectedTable'" -ForegroundColor Red
    }
}
foreach ($wrongTable in @("EquipmentStatus","ProductionMetrics")) {
    if ($simPy -match [regex]::Escape($wrongTable)) {
        $issues.Add("SIM: Uses wrong table name '$wrongTable'")
        Write-Host "  [FAIL] Simulator uses wrong table '$wrongTable'" -ForegroundColor Red
    }
}

Write-Host "`n=== 8. KQL create-tables.kql Consistency ===" -ForegroundColor Cyan
$kqlFile = Get-Content (Join-Path $base "kql\create-tables.kql") -Raw
foreach ($wrongTable in @("EquipmentStatus","ProductionMetrics")) {
    if ($kqlFile -match [regex]::Escape($wrongTable)) {
        $issues.Add("KQL-FILE: create-tables.kql has wrong table '$wrongTable'")
        Write-Host "  [FAIL] create-tables.kql uses wrong table '$wrongTable'" -ForegroundColor Red
    }
}

Write-Host "`n=== 9. FK Integrity: CSV Foreign Keys ===" -ForegroundColor Cyan
$plants = Import-Csv (Join-Path $dataDir "plants.csv")
$lines  = Import-Csv (Join-Path $dataDir "lines.csv")
$equip  = Import-Csv (Join-Path $dataDir "equipment.csv")
$sensors = Import-Csv (Join-Path $dataDir "sensors.csv")
$products = Import-Csv (Join-Path $dataDir "products.csv")
$workorders = Import-Csv (Join-Path $dataDir "workorders.csv")

$plantIds = $plants | ForEach-Object { $_.PlantId }
$lineIds  = $lines  | ForEach-Object { $_.LineId }
$equipIds = $equip  | ForEach-Object { $_.EquipmentId }
$productIds = $products | ForEach-Object { $_.ProductId }

# Lines -> Plants
$ok = $true
foreach ($l in $lines) {
    if ($plantIds -notcontains $l.PlantId) { $issues.Add("FK: Line $($l.LineId) -> PlantId $($l.PlantId) not found"); $ok = $false }
}
if ($ok) { Write-Host "  [OK] Lines.PlantId -> Plants.PlantId" -ForegroundColor Green }

# Equipment -> Lines
$ok = $true
foreach ($e in $equip) {
    if ($lineIds -notcontains $e.LineId) { $issues.Add("FK: Equipment $($e.EquipmentId) -> LineId $($e.LineId) not found"); $ok = $false }
}
if ($ok) { Write-Host "  [OK] Equipment.LineId -> Lines.LineId" -ForegroundColor Green }

# Sensors -> Equipment
$ok = $true
foreach ($s in $sensors) {
    if ($equipIds -notcontains $s.EquipmentId) { $issues.Add("FK: Sensor $($s.SensorId) -> EquipmentId $($s.EquipmentId) not found"); $ok = $false }
}
if ($ok) { Write-Host "  [OK] Sensors.EquipmentId -> Equipment.EquipmentId" -ForegroundColor Green }

# WorkOrders -> Products
$ok = $true
foreach ($wo in $workorders) {
    if ($productIds -notcontains $wo.ProductId) { $issues.Add("FK: WO $($wo.WorkOrderId) -> ProductId $($wo.ProductId) not found"); $ok = $false }
}
if ($ok) { Write-Host "  [OK] WorkOrders.ProductId -> Products.ProductId" -ForegroundColor Green }

# WorkOrders -> Lines
$ok = $true
foreach ($wo in $workorders) {
    if ($lineIds -notcontains $wo.LineId) { $issues.Add("FK: WO $($wo.WorkOrderId) -> LineId $($wo.LineId) not found"); $ok = $false }
}
if ($ok) { Write-Host "  [OK] WorkOrders.LineId -> Lines.LineId" -ForegroundColor Green }

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  TOTAL ISSUES: $($issues.Count)" -ForegroundColor $(if($issues.Count -gt 0){"Red"}else{"Green"})
Write-Host "========================================" -ForegroundColor Cyan
if ($issues.Count -gt 0) {
    Write-Host "`nIssue Summary:" -ForegroundColor Yellow
    $issues | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
}
