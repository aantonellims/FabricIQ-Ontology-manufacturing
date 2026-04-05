<#
.SYNOPSIS
    Deploy the RTI Ontology model via the Fabric updateDefinition API.

.DESCRIPTION
    Thin PowerShell wrapper that delegates to deploy/deploy_ontology_definition.py.
    The Python script reads entity types, relationships, bindings, and
    contextualizations from ontology/, injects runtime IDs from config.json,
    Base64-encodes each part, and pushes via updateDefinition API.

.EXAMPLE
    .\deploy\Deploy-OntologyModel.ps1 -OntologyPath "ontologies\SaintGobain"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$OntologyPath
)

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot

Write-Host "=== Deploy Ontology Model ===" -ForegroundColor Cyan
Write-Host "  Delegating to Python script..." -ForegroundColor DarkGray

$pythonScript = Join-Path $scriptDir "deploy_ontology_definition.py"
if (-not (Test-Path $pythonScript)) {
    Write-Error "Python script not found: $pythonScript"
    exit 1
}

python $pythonScript --ontology-path $OntologyPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "Ontology definition deployment failed (exit code $LASTEXITCODE)"
    exit $LASTEXITCODE
}

Write-Host "  Ontology definition deployment complete." -ForegroundColor Green
