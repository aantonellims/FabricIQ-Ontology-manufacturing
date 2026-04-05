# Saint-Gobain Manufacturing Ontology Constitution

## Core Principles

### I. Ontology-Driven Architecture
Every feature models the physical manufacturing world as a digital twin. Entity types map 1:1 to real-world objects (Plants, Production Lines, Equipment, Sensors). Relationships capture the physical hierarchy and operational dependencies. All data bindings connect master data (Lakehouse) and telemetry (Eventhouse/KQL) to ontology entities. The ontology is the **single source of truth** for the Data Agent — underlying resources (Lakehouse, KQL) are abstracted via data bindings.

### II. Fabric-Native, Script-First Deployment
All infrastructure and ontology artifacts are deployed via Python scripts for Fabric REST API calls using DefaultAzureCredential, with PowerShell for deployment orchestration. No manual portal clicks required. Scripts must be re-runnable without side effects (create-or-update semantics). Config is externalized to `config.json`.

### III. Separation of Master Data and Telemetry
Static/slowly-changing master data (Plants, Equipment, Products) lives in Lakehouse Delta tables. High-frequency time-series data (sensor readings, equipment status, production metrics) flows through Eventhouse KQL tables. The Ontology binds both sources via NonTimeSeries and TimeSeries data bindings.

### IV. Validate Before Deploy
Every deployment step includes pre-validation: check for existing resources before creating, validate schemas match source tables, confirm API responses. Never assume resources exist or don't exist — always query first.

### V. Saint-Gobain Manufacturing Domain
The ontology models Saint-Gobain's glass & building materials manufacturing operations: Flat Glass plants, High Performance Materials facilities, and Construction Products factories. Entity types, properties, and telemetry streams reflect real Saint-Gobain operational concepts.

### VI. Ontology-Centric Data Agent
The Data Agent uses the ontology as its single data source. The agent instructions guide GQL queries for entity traversal and time-series selectors for telemetry. Cross-source joins are handled by the ontology's data bindings — the agent never queries Lakehouse or KQL directly.

## Technology Stack

- **Platform**: Microsoft Fabric (capacity: `msfabric001`)
- **Master Data**: Fabric Lakehouse (Delta tables: DIM_PLANT, DIM_LINE, DIM_EQUIPMENT, DIM_SENSOR, DIM_PRODUCT, DIM_DATE, DIM_WORKORDER + 3 fact tables)
- **Telemetry**: Fabric Eventhouse (KQL Database: SensorTelemetry, EquipmentStatus, ProductionMetrics, Alerts)
- **Ontology**: Fabric RTI Ontology (6 entity types, 5 relationships, 9 data bindings, 5 contextualizations)
- **Semantic Model**: Power BI DirectLake star schema (9 tables, 15 relationships, 15 DAX measures)
- **AI Queries**: Fabric Data Agent (ontology-only source, GQL + time-series selectors)
- **Scripts**: PowerShell 7+ with `az cli` for authentication
- **API Deployment**: Python 3.11+ with azure-identity for API deployment
- **Data Generation**: Python 3.11+ (sample data, telemetry ingestion)

## Development Workflow

1. **Spec first**: Define entity types and relationships in JSON before any deployment
2. **Data validation**: Verify sample data CSVs match entity property definitions
3. **Incremental deploy**: Deploy in order: Lakehouse → Data Load → KQL Tables → Ontology → Semantic Model → Data Agent
4. **Test with queries**: After each deployment step, run validation KQL/Graph/Agent queries
5. **Idempotent scripts**: All scripts support re-running without errors
6. **Agent instructions**: When updating Agent, test with queries that traverse ontology + time-series

## Governance

- Constitution supersedes ad-hoc decisions about architecture and deployment patterns
- Entity type changes require updating both ontology definitions and corresponding sample data
- All Fabric resource IDs stored in `config.json` — never hardcoded in scripts
- Credentials use `DefaultAzureCredential` or `az account get-access-token` — never stored in files
- KQL inline ingest: NEVER use single quotes around string values (they become embedded in the data)

**Version**: 2.0.0 | **Ratified**: 2026-04-01 | **Last Amended**: 2026-04-03
