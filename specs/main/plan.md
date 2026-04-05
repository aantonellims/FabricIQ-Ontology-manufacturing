# Implementation Plan: Saint-Gobain Manufacturing Ontology - End-to-End Deployment

**Branch**: `main` | **Date**: 2026-04-01 | **Updated**: 2026-04-03 | **Spec**: [specs/001-ontology-e2e/spec.md](../001-ontology-e2e/spec.md)
**Input**: Feature specification from `/specs/001-ontology-e2e/spec.md`
**Status**: ✅ ALL COMPLETED — US1–US9 implemented & validated

## Summary

Deploy a complete Microsoft Fabric RTI Ontology representing Saint-Gobain's manufacturing hierarchy alongside a star schema semantic model and an ontology-driven Data Agent. The system deploys Fabric infrastructure (Workspace, Lakehouse, Eventhouse/KQL Database), loads 9 tables (6 dims + 3 facts) into Lakehouse Delta tables, creates 4 KQL telemetry tables, deploys a 6-entity ontology with 9 data bindings (6 NTS + 3 TS), a DirectLake star schema semantic model (15 relationships, 15 DAX measures), ingests 24h of sample telemetry data, and configures a Data Agent with ontology as its single source of truth. All deployment is via idempotent Python scripts using Fabric REST API and `DefaultAzureCredential` for auth, with resource IDs centralized in `config.json`.

## Technical Context

**Language/Version**: PowerShell 7+, Python 3.11+  
**Primary Dependencies**: Microsoft Fabric REST API, `az cli`, `azure-identity` (DefaultAzureCredential), Fabric Lakehouse API, KQL Management API, Ontology API (`/ontologies/` endpoints), Data Agent API (`/dataAgents/` endpoints)  
**Storage**: Fabric Lakehouse (Delta tables for master data), Fabric Eventhouse (KQL Database for telemetry)  
**Semantic Layer**: Power BI DirectLake semantic model (star schema)  
**AI Layer**: Fabric Data Agent (ontology-only source with GQL + time-series selectors)  
**Testing**: Python pytest (full test suite), manual Data Agent queries in Fabric portal  
**Target Platform**: Microsoft Fabric (capacity: `msfabric001`)  
**Project Type**: Infrastructure-as-code / deployment automation  
**Performance Goals**: Full deployment < 10 minutes (NFR-1)  
**Constraints**: No stored credentials (NFR-3), all scripts idempotent (NFR-2), resource IDs in config.json (NFR-4), Python for REST API calls  
**Scale/Scope**: 5 plants, 12 lines, 18+ equipment, 19 sensors, 9 products; 6 entity types, 5 relationships, 9 data bindings, 4 KQL telemetry tables, 1 semantic model, 1 Data Agent, ~2400 sample telemetry rows

## Constitution Check

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Ontology-Driven Architecture | ✅ PASS | 6 entity types map 1:1 to real-world objects; data bindings connect Lakehouse + KQL |
| II. Fabric-Native, Script-First | ✅ PASS | All deploy via Python scripts; config.json externalizes state |
| III. Separation of Master Data / Telemetry | ✅ PASS | Master → Lakehouse; telemetry → KQL; ontology binds both |
| IV. Validate Before Deploy | ✅ PASS | All scripts check existing resources; schema validation |
| V. Saint-Gobain Manufacturing Domain | ✅ PASS | SG plant names, products, glass manufacturing equipment |
| VI. Ontology-Centric Data Agent | ✅ PASS | Single ontology source; GQL entity traversal + time-series selectors |

## Deployment Order

```
US1: Infrastructure → config.json
US2: Master+Fact Data (9 Delta tables) ──┐
US3: KQL Tables (4 tables) ─────────────┤
US4: Star Schema Semantic Model ────────┤
US5: Ontology Definition Push ──────────┘
US6: Telemetry Simulator (optional)
US7: Graph Model (optional)
US9: Sample Telemetry Ingestion (24h of KQL data)
US8: Data Agent (ontology-only source, GQL instructions)
```

## Key Artifacts

| Artifact | Purpose |
|----------|---------|
| `deploy/deploy_data_agent.py` | Deploy Data Agent with ontology source + AI instructions |
| `deploy/deploy_semantic_model.py` | Deploy DirectLake star schema semantic model |
| `deploy/push_ontology_v2.py` | Push ontology definition via `/ontologies/` API |
| `deploy/ingest_sample_telemetry.py` | Populate KQL with 24h sample data |
| `deploy/inspect_agent.py` | Inspect deployed agent definition |
| `ontologies/SaintGobain/config.json` | All Fabric resource IDs |
specs/main/
├── plan.md              # This file
├── research.md          # Phase 0: Fabric API research findings
├── data-model.md        # Phase 1: Entity types, relationships, bindings
├── quickstart.md        # Phase 1: Getting started guide
└── contracts/
    ├── ontology-api.md  # Ontology entity type JSON schemas
    └── kql-tables.md    # KQL table schemas
```

### Source Code (repository root)

```text
Ontology-Manuf/
├── config.json                      # Fabric resource IDs (populated by deploy)
├── Deploy-Ontology.ps1              # Main orchestrator (calls all deploy scripts)
├── deploy/
│   ├── Deploy-Infrastructure.ps1    # [EXISTS] Workspace + Lakehouse + Eventhouse
│   ├── Load-SampleData.ps1          # Upload CSVs → Lakehouse Delta tables
│   ├── Deploy-KqlTables.ps1         # Create 4 KQL telemetry tables
│   ├── Deploy-OntologyModel.ps1     # Create ontology + entity types + relationships + bindings
│   ├── Deploy-GraphModel.ps1        # (P3) Graph visualization
│   ├── Deploy-DataAgent.ps1         # (P3) Natural language data agent
│   └── Start-TelemetrySimulator.ps1 # (P2) Real-time data generator
├── data/                            # [EXISTS] Sample CSV master data
│   ├── plants.csv                   # 5 plants
│   ├── lines.csv                    # 12 production lines
│   ├── equipment.csv                # 18 equipment items
│   ├── sensors.csv                  # 19 sensors
│   ├── products.csv                 # 9 products
│   └── workorders.csv               # 8 work orders
├── ontology/
│   ├── entity-types/                # Entity type JSON definitions
│   │   ├── plant.json
│   │   ├── production-line.json
│   │   ├── equipment.json
│   │   ├── sensor.json
│   │   ├── product.json
│   │   └── workorder.json
│   ├── relationships/               # Relationship JSON definitions
│   │   ├── has-line.json
│   │   ├── has-equipment.json
│   │   ├── has-sensor.json
│   │   ├── assigned-to.json
│   │   └── produces.json
│   └── bindings/                    # Data binding definitions
│       ├── nontimeseries/           # Lakehouse bindings per entity
│       └── timeseries/              # KQL bindings per entity
├── kql/
│   ├── create-tables.kql            # KQL .create-merge table commands
│   └── validation-queries.kql       # Post-deploy validation queries
├── simulator/
│   ├── requirements.txt             # Python dependencies
│   └── telemetry_simulator.py       # Generates realistic sensor data
└── queries/
    └── graph-examples.kql           # Sample graph/ontology queries
```

**Structure Decision**: Script-first deployment project — no `src/` needed. PowerShell scripts live in `deploy/`, ontology JSON definitions in `ontology/`, KQL schemas in `kql/`, Python simulator in `simulator/`.

## Complexity Tracking

No constitution violations — no entries needed.
