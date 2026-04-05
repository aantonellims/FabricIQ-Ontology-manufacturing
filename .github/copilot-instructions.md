# Ontology-Manuf Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-03

## Active Technologies

- PowerShell 7+, Python 3.11+ + Microsoft Fabric REST API, `az cli`, `azure-identity`, Fabric Lakehouse API, KQL Management API, Ontology API, Data Agent API (main)

## Project Structure

```text
deploy/          # Core deployment scripts (PowerShell + Python)
deploy/archive/  # One-time fix scripts (historical)
tools/           # Utility & inspection scripts
ontologies/      # SaintGobain ontology config, data, definitions
tests/           # Validation & test suites
specs/           # Feature specifications, plans, tasks
.specify/        # Spec-kit configuration & templates
.github/         # Copilot agents, prompts, instructions
```

## Commands

python deploy/deploy_data_agent.py; python deploy/ingest_sample_telemetry.py; python tools/inspect_agent.py; python tools/validate_deployment.py

## Code Style

PowerShell 7+, Python 3.11+: Follow standard conventions. Use DefaultAzureCredential for auth. No single quotes in KQL inline ingest CSV values.

## Recent Changes

- main: Ontology-only Data Agent with comprehensive GQL + time-series instructions
- main: Sample telemetry ingestion (24h, no embedded quotes in KQL values)
- main: Added PowerShell 7+, Python 3.11+ + Microsoft Fabric REST API, `az cli`, Fabric Lakehouse API, KQL Management API, Ontology API, Data Agent API

- main: Added PowerShell 7+, Python 3.11+ + Microsoft Fabric REST API, `az cli`, Fabric Lakehouse API, KQL Management API, Ontology API

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
