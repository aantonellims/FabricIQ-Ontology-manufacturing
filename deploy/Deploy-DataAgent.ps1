<#
.SYNOPSIS
    Deploy Data Agent for natural language ontology queries.

.DESCRIPTION
    Creates a Data Agent item that enables natural language queries
    against the ontology via Copilot or API.

.EXAMPLE
    .\deploy\Deploy-DataAgent.ps1 -OntologyPath "ontologies\SaintGobain"
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

Write-Host "=== Deploy Data Agent ===" -ForegroundColor Cyan

# Create Data Agent linked to ontology
$agentName = "SG-Manufacturing-Agent"
Write-Host "`n[1] Creating Data Agent '$agentName'..." -ForegroundColor White

$agent = Find-OrCreateItem -WorkspaceId $workspaceId -DisplayName $agentName `
    -ItemType "DataAgent" -Description "Natural language queries for Saint-Gobain Manufacturing Ontology" `
    -Headers $headers -ApiBase $apiBase

# Configure agent to use ontology as data source
Write-Host "`n[2] Configuring agent data source..." -ForegroundColor White

$agentConfigUri = "$apiBase/workspaces/$workspaceId/dataAgents/$($agent.id)/configuration"
$agentConfig = @{
    dataSources = @(
        @{
            type = "Ontology"
            ontologyId = $ontologyId
        }
    )
    capabilities = @(
        "naturalLanguageQuery"
        "entityExploration"
        "relationshipNavigation"
    )
}

try {
    $null = Invoke-FabricApi -Uri $agentConfigUri -Method PUT -Headers $headers -Body $agentConfig
    Write-Host "  [OK] Agent configured" -ForegroundColor Green
}
catch {
    Write-Warning "  Agent configuration may need manual setup in portal: $_"
}

Write-Host "`n=== Data Agent Ready ===" -ForegroundColor Green
Write-Host "  Data Agent ID: $($agent.id)" -ForegroundColor White
Write-Host "  Linked Ontology: $ontologyId" -ForegroundColor White
