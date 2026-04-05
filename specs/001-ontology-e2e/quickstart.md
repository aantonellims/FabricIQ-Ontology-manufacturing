# Quickstart: Saint-Gobain Manufacturing Ontology

## Prerequisites

- **PowerShell 7+**: `winget install Microsoft.PowerShell`
- **Python 3.11+**: `winget install Python.Python.3.11`
- **Azure CLI**: `winget install Microsoft.AzureCLI`
- **Fabric Capacity**: Access to `msfabric001` capacity (or update `config.json`)
- **Azure Login**: `az login` with account that has Fabric Contributor role

## Quick Deploy (All Steps)

```powershell
# 1. Clone the repository
git clone <repo-url>
cd Ontology-Manuf

# 2. Login to Azure
az login

# 3. Deploy everything
.\Deploy-Ontology.ps1
```

## Step-by-Step Deploy

```powershell
# Step 1: Infrastructure (workspace, lakehouse, eventhouse)
.\Deploy-Ontology.ps1 -StepInfrastructure

# Step 2: Load sample master data into Lakehouse
.\Deploy-Ontology.ps1 -StepData

# Step 3: Create KQL telemetry tables
.\Deploy-Ontology.ps1 -StepKqlTables

# Step 4: Deploy ontology model
.\Deploy-Ontology.ps1 -StepOntology

# Step 5: Deploy semantic model (optional — for Power BI dashboards)
.\Deploy-Ontology.ps1 -StepSemanticModel

# Step 6: Ingest sample telemetry into KQL (24h of data)
python deploy/ingest_sample_telemetry.py

# Step 7: Deploy Data Agent (ontology-only source)
python deploy/deploy_data_agent.py

# Step 8: Start telemetry simulator (optional — live data)
.\Deploy-Ontology.ps1 -StepSimulator

# Step 9: Deploy graph model (optional)
.\Deploy-Ontology.ps1 -StepGraph
```

## Verify Deployment

### Check Infrastructure
```powershell
# Verify config.json has all resource IDs populated
Get-Content config.json | ConvertFrom-Json | Format-List
```

### Check Master Data
```powershell
# Query a Lakehouse table
$token = az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv
$config = Get-Content config.json | ConvertFrom-Json
# Verify tables exist via Fabric API
Invoke-RestMethod -Uri "$($config.apiBase)/workspaces/$($config.workspace.id)/lakehouses/$($config.lakehouse.id)/tables" `
  -Headers @{ Authorization = "Bearer $token" }
```

### Check KQL Tables
```kql
// Run in KQL Database query editor
.show tables
| project TableName, TotalRowCount

SensorTelemetry | count
EquipmentStatus | count
ProductionMetrics | count
Alerts | count
```

### Check Ontology
```powershell
# Verify ontology exists
$token = az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv
$config = Get-Content config.json | ConvertFrom-Json
Invoke-RestMethod -Uri "$($config.apiBase)/workspaces/$($config.workspace.id)/items?type=Ontology" `
  -Headers @{ Authorization = "Bearer $token" }
```

## Configuration

All resource IDs are stored in `config.json`. The file is auto-populated by deployment scripts:

| Key | Description | Populated By |
|-----|-------------|-------------|
| `workspace.id` | Fabric workspace GUID | Deploy-Infrastructure.ps1 |
| `lakehouse.id` | Lakehouse item GUID | Deploy-Infrastructure.ps1 |
| `eventhouse.id` | Eventhouse item GUID | Deploy-Infrastructure.ps1 |
| `kqlDatabase.id` | KQL Database GUID | Deploy-Infrastructure.ps1 |
| `kqlDatabase.queryServiceUri` | KQL query endpoint URL | Deploy-Infrastructure.ps1 |
| `ontology.id` | Ontology item GUID | Deploy-OntologyModel.ps1 |
| `semanticModel.id` | Semantic model GUID | deploy_semantic_model.py |

## Verify Data Agent

```powershell
# Inspect deployed agent definition
python tools/inspect_agent.py

# Should show:
#   Draft datasources (1): ontology-SG_ManufacturingOntology
```

### Test Queries for Data Agent (in Fabric Portal)

```
"Which production lines does the Aachen plant have?"
"For each plant, show any equipment that ever had a downtime greater than 150 minutes."
"Show all equipment at the Chemille plant that was ever in Maintenance status."
"How many pieces of equipment does each plant have?"
"List all sensors attached to the Float Bath equipment."
```

## Troubleshooting

| Issue | Resolution |
|-------|-----------|
| `az login` fails | Ensure Azure CLI is installed and you have Fabric access |
| Capacity not found | Update `config.json` capacity name to match your Fabric capacity |
| KQL Database timeout | Eventhouse auto-creates KQL DB; script polls for up to 2 minutes |
| Table load fails | Ensure CSV files exist in `data/` folder and match expected schemas |
| Token expires | Scripts refresh tokens per step; for long runs, re-run `az login` |
| KQL data has quotes in IDs | Re-run `ingest_sample_telemetry.py` — never quote strings in `.ingest inline` CSV |
| Data Agent can't find data | Verify KQL values have no embedded quotes; run `python tools/check_timestamps.py` |
| Agent shows stale sources | `updateDefinition` replaces entirely — re-run `deploy_data_agent.py` |

## Data Overview

| Entity | File | Table | Rows |
|--------|------|-------|------|
| Plants | data/plants.csv | DIM_PLANT | 5 |
| Lines | data/lines.csv | DIM_LINE | 12 |
| Equipment | data/equipment.csv | DIM_EQUIPMENT | 18+ |
| Sensors | data/sensors.csv | DIM_SENSOR | 19 |
| Products | data/products.csv | DIM_PRODUCT | 9 |
| Work Orders | data/workorders.csv | DIM_WORKORDER | 8 |
