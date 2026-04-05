<#
.SYNOPSIS
    Deploy Graph Model for ontology visualization.

.DESCRIPTION
    Creates a Graph Model item that enables visual exploration of the ontology
    hierarchy in the Fabric portal.

.EXAMPLE
    .\deploy\Deploy-GraphModel.ps1 -OntologyPath "ontologies\SaintGobain"
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
if (-not $config.ontology.id) {
    Write-Error "ontology.id must be set. Run Deploy-OntologyModel.ps1 first."
    exit 1
}

$workspaceId = $config.workspace.id
$ontologyId  = $config.ontology.id
$headers     = Get-FabricHeaders

Write-Host "=== Deploy Graph Model ===" -ForegroundColor Cyan

# Create Graph Model linked to ontology
$graphModelName = "SG-Manufacturing-Graph"
Write-Host "`n[1] Creating Graph Model '$graphModelName'..." -ForegroundColor White

$graphModel = Find-OrCreateItem -WorkspaceId $workspaceId -DisplayName $graphModelName `
    -ItemType "GraphModel" -Description "Visual hierarchy for Saint-Gobain Manufacturing Ontology" `
    -Headers $headers -ApiBase $apiBase

Write-Host "`n=== Graph Model Ready ===" -ForegroundColor Green
Write-Host "  Graph Model ID: $($graphModel.id)" -ForegroundColor White
