<#
.SYNOPSIS
    Deploy DirectLake semantic model to Fabric workspace.
.DESCRIPTION
    Thin PowerShell wrapper that delegates to deploy/deploy_semantic_model.py.
.EXAMPLE
    .\deploy\Deploy-SemanticModel.ps1 -OntologyPath "ontologies\SaintGobain"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$OntologyPath
)

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot

Write-Host "=== Deploy Semantic Model ===" -ForegroundColor Cyan
Write-Host "  Delegating to Python script..." -ForegroundColor DarkGray

$pythonScript = Join-Path $scriptDir "deploy_semantic_model.py"
if (-not (Test-Path $pythonScript)) {
    Write-Error "Python script not found: $pythonScript"
    exit 1
}

python $pythonScript --ontology-path $OntologyPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "Semantic model deployment failed (exit code $LASTEXITCODE)"
    exit $LASTEXITCODE
}

Write-Host "  Semantic model deployment complete." -ForegroundColor Green
