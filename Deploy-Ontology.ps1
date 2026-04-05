<#
.SYNOPSIS
    Main orchestrator for Saint-Gobain Manufacturing Ontology deployment.

.DESCRIPTION
    Deploys a complete Microsoft Fabric RTI Ontology for a manufacturing
    hierarchy. Use switches to run individual steps or omit all switches
    to run everything.

.PARAMETER StepInfrastructure
    Deploy Fabric workspace, Lakehouse, Eventhouse, KQL Database.
.PARAMETER StepData
    Load sample CSV master data into Lakehouse Delta tables.
.PARAMETER StepKqlTables
    Create KQL telemetry tables with caching/retention policies.
.PARAMETER StepOntology
    Deploy the ontology model (entity types, relationships, bindings).
.PARAMETER StepSimulator
    Start the real-time telemetry simulator.
.PARAMETER StepGraph
    Deploy Graph Model for hierarchy visualisation.
.PARAMETER StepAgent
    Deploy Data Agent for natural language queries.

.EXAMPLE
    # Deploy everything
    .\Deploy-Ontology.ps1

.EXAMPLE
    # Deploy only infrastructure
    .\Deploy-Ontology.ps1 -StepInfrastructure

.EXAMPLE
    # Deploy data + KQL tables
    .\Deploy-Ontology.ps1 -StepData -StepKqlTables
#>

[CmdletBinding()]
param(
    [string]$OntologyPath = "ontologies\SaintGobain",
    [switch]$StepInfrastructure,
    [switch]$StepData,
    [switch]$StepKqlTables,
    [switch]$StepOntology,
    [switch]$StepSemanticModel,
    [switch]$StepSimulator,
    [switch]$StepGraph,
    [switch]$StepAgent
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
$OntologyPath = Join-Path $repoRoot $OntologyPath
if (-not (Test-Path (Join-Path $OntologyPath "config.json"))) {
    Write-Error "Ontology path '$OntologyPath' does not contain config.json. Use -OntologyPath to specify the ontology folder."
    exit 1
}
$deployDir = Join-Path $repoRoot "deploy"

# If no switches specified, run all P1 steps (infra → data → KQL → ontology)
$noSwitches = -not ($StepInfrastructure -or $StepData -or $StepKqlTables -or $StepOntology `
                     -or $StepSemanticModel -or $StepSimulator -or $StepGraph -or $StepAgent)

$ontologyName = Split-Path $OntologyPath -Leaf
Write-Host "============================================="  -ForegroundColor Cyan
Write-Host " Ontology Deployment: $ontologyName"              -ForegroundColor Cyan
Write-Host "============================================="  -ForegroundColor Cyan
Write-Host "  Ontology path: $OntologyPath" -ForegroundColor DarkGray
Write-Host ""

# --- Step 1: Infrastructure ---
if ($StepInfrastructure -or $noSwitches) {
    Write-Host ">>> Step 1: Infrastructure <<<" -ForegroundColor Magenta
    & "$deployDir\Deploy-Infrastructure.ps1" -OntologyPath $OntologyPath
    Write-Host ""
}

# --- Step 2: Sample Data ---
if ($StepData -or $noSwitches) {
    Write-Host ">>> Step 2: Load Sample Data <<<" -ForegroundColor Magenta
    & "$deployDir\Load-SampleData.ps1" -OntologyPath $OntologyPath
    Write-Host ""
}

# --- Step 3: KQL Tables ---
if ($StepKqlTables -or $noSwitches) {
    Write-Host ">>> Step 3: KQL Telemetry Tables <<<" -ForegroundColor Magenta
    & "$deployDir\Deploy-KqlTables.ps1" -OntologyPath $OntologyPath
    Write-Host ""
}

# --- Step 4: Ontology Model ---
if ($StepOntology -or $noSwitches) {
    Write-Host ">>> Step 4: Ontology Model <<<" -ForegroundColor Magenta
    & "$deployDir\Deploy-OntologyModel.ps1" -OntologyPath $OntologyPath
    Write-Host ""
}

# --- Step 4b: Semantic Model ---
if ($StepSemanticModel -or $noSwitches) {
    Write-Host ">>> Step 4b: Semantic Model <<<" -ForegroundColor Magenta
    & "$deployDir\Deploy-SemanticModel.ps1" -OntologyPath $OntologyPath
    Write-Host ""
}

# --- Step 5: Telemetry Simulator (P2) ---
if ($StepSimulator) {
    Write-Host ">>> Step 5: Telemetry Simulator <<<" -ForegroundColor Magenta
    & "$deployDir\Start-TelemetrySimulator.ps1" -OntologyPath $OntologyPath
    Write-Host ""
}

# --- Step 6: Graph Model (P3) ---
if ($StepGraph) {
    Write-Host ">>> Step 6: Graph Model <<<" -ForegroundColor Magenta
    & "$deployDir\Deploy-GraphModel.ps1" -OntologyPath $OntologyPath
    Write-Host ""
}

# --- Step 7: Data Agent (P3) ---
if ($StepAgent) {
    Write-Host ">>> Step 7: Data Agent <<<" -ForegroundColor Magenta
    & "$deployDir\Deploy-DataAgent.ps1" -OntologyPath $OntologyPath
    Write-Host ""
}

Write-Host "=============================================" -ForegroundColor Green
Write-Host " Deployment Complete"                          -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
