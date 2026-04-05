# Research: Saint-Gobain Manufacturing Ontology

**Date**: 2026-04-01 | **Plan**: [plan.md](plan.md) | **Spec**: [../001-ontology-e2e.md](../001-ontology-e2e.md)

## Research Topics

### 1. Fabric Ontology REST API — Entity Types, Relationships, and Data Bindings

**Decision**: Use Fabric REST API v1 endpoints under `/workspaces/{workspaceId}/ontologies` for all ontology operations.

**Rationale**: The Fabric Ontology API provides create/update/delete operations for ontology models, entity types, relationships, and data bindings. This is the only programmatic path — no SDK exists for ontology management.

**Key Findings**:
- **Create Ontology**: `POST /workspaces/{wsId}/items` with `type: "Ontology"` and `displayName`
- **Entity Types**: Managed via ontology definition payload — each entity type defines `properties` (name, type), `primaryKey`, `displayName`, `foreignKeys`
- **Relationships**: Defined between entity types using `fromEntityType` / `toEntityType` with cardinality (One-to-Many)
- **Data Bindings**:
  - `NonTimeSeries`: Binds entity type to a Lakehouse Delta table — maps entity properties to table columns
  - `TimeSeries`: Binds entity type to a KQL table — maps timestamp column plus metric columns
- **Ontology Definition Format**: JSON payload submitted via `POST /workspaces/{wsId}/ontologies/{ontologyId}/definition` with complete entity graph

**Alternatives Considered**:
- Fabric portal UI → Rejected: not scriptable, violates Constitution Principle II
- Semantic Link SDK → Rejected: no ontology support currently

---

### 2. Lakehouse Data Loading via REST API (no Spark)

**Decision**: Use the Fabric Lakehouse Tables API (`POST /workspaces/{wsId}/lakehouses/{lhId}/tables/{tableName}/load`) to load CSV data directly into Delta tables.

**Rationale**: Avoids dependency on Spark notebooks or livy sessions. The Tables API accepts CSV files uploaded to the Lakehouse Files area, then converts them to Delta format.

**Key Findings**:
- **Step 1**: Upload CSV to Lakehouse Files via OneLake DFS API (`PUT https://onelake.dfs.fabric.microsoft.com/{wsId}/{lhId}/Files/{filename}`)
- **Step 2**: Call Lakehouse Table Load API to convert file to Delta table
- **Table naming**: Use uppercase with prefix: `DIM_PLANT`, `DIM_LINE`, `DIM_EQUIPMENT`, `DIM_SENSOR`, `DIM_PRODUCT`, `DIM_WORKORDER`
- **Overwrite behavior**: Specify `mode: "overwrite"` for idempotency
- **CSV encoding**: UTF-8 without BOM, comma delimiter

**Alternatives Considered**:
- Spark Notebooks / Livy API → Rejected: heavy dependency, slow startup, overkill for small reference data
- Direct Delta file write → Rejected: complex, requires Parquet libraries in PowerShell

---

### 3. KQL Table Creation via Management Commands

**Decision**: Use `.create-merge table` KQL management commands executed via the KQL REST API.

**Rationale**: `.create-merge` is idempotent — creates the table if it doesn't exist, merges schema if it does. This matches Constitution Principle IV (validate before deploy) and NFR-2 (idempotent).

**Key Findings**:
- **Endpoint**: `POST https://{queryServiceUri}/v1/rest/mgmt` with `{ "csl": ".create-merge table ...", "db": "{dbName}" }`
- **Auth**: Bearer token from `az account get-access-token --resource https://kusto.kusto.windows.net`
- **4 Tables**:
  - `SensorTelemetry` — SensorId:string, Timestamp:datetime, Value:real, Unit:string, Quality:string
  - `EquipmentStatus` — EquipmentId:string, Timestamp:datetime, Status:string, RunHours:real, CycleCount:long
  - `ProductionMetrics` — LineId:string, Timestamp:datetime, OutputUnits:long, DefectRate:real, OEE:real
  - `Alerts` — AlertId:string, EntityId:string, EntityType:string, Timestamp:datetime, Severity:string, Message:string
- **Retention/Caching**: 365 days retention, 31 days hot cache (`.alter table ... policy caching`)

**Alternatives Considered**:
- `.create table` → Rejected: not idempotent, fails if table exists
- One-time notebook → Rejected: not re-runnable from command line

---

### 4. Telemetry Simulator Design

**Decision**: Python script using `azure-kusto-ingest` SDK for batched ingestion with realistic value generation based on sensor min/max ranges from CSV.

**Rationale**: Python has mature Kusto ingestion libraries. Reading sensor ranges from `sensors.csv` ensures simulated values are realistic. 10-second interval matches spec requirement.

**Key Findings**:
- **Library**: `azure-kusto-ingest` (queued ingestion) or direct REST streaming ingestion
- **Value generation**: For each sensor, generate random float in `[MinValue, MaxValue]` range with Gaussian noise
- **Equipment status**: Cycle between Operating/Idle/Maintenance with weighted probabilities
- **Production metrics**: OEE typically 0.65-0.90, defect rate 0.5-5%
- **Alerts**: Random generation at ~5% probability per interval with severity distribution
- **Auth**: Azure CLI token (`az account get-access-token --resource https://kusto.kusto.windows.net`)

**Alternatives Considered**:
- PowerShell direct REST ingestion → Rejected: clumsy for continuous loop with timing
- .NET console app → Rejected: heavier toolchain, Python is simpler for data generation
- Eventstream/EventHub → Rejected: adds infrastructure components, direct KQL ingestion is simpler for demo

---

### 5. OneLake DFS API for File Upload

**Decision**: Use OneLake DFS-compatible API for uploading CSV files to Lakehouse Files area.

**Rationale**: Standard Azure Data Lake Storage Gen2 API works with OneLake. PowerShell `Invoke-RestMethod` can upload small files (<100MB) directly.

**Key Findings**:
- **Create file**: `PUT https://onelake.dfs.fabric.microsoft.com/{wsName}/{lhName}.Lakehouse/Files/{filename}?resource=file`
- **Append data**: `PATCH https://onelake.dfs.fabric.microsoft.com/{wsName}/{lhName}.Lakehouse/Files/{filename}?action=append&position=0`
- **Flush**: `PATCH https://onelake.dfs.fabric.microsoft.com/{wsName}/{lhName}.Lakehouse/Files/{filename}?action=flush&position={length}`
- **Auth**: Bearer token from `az account get-access-token --resource https://storage.azure.com`

**Alternatives Considered**:
- Fabric REST file upload API → More limited, DFS is more flexible
- azcopy → Works but adds external dependency

---

### 6. Graph Model & Data Agent APIs (P3)

**Decision**: Defer detailed implementation research until P1/P2 items are complete. Use Fabric REST API for GraphQL API item creation and Data Agent configuration.

**Rationale**: These are P3 priority items. The spec acknowledges they are "nice-to-have for demo polish." Core ontology works without them.

**Key Findings**:
- **Graph Model**: Created as a Fabric item type via workspace items API
- **Data Agent**: Created as a Fabric item with ontology reference and natural language configuration
- Both require ontology to be fully deployed first

**Alternatives Considered**: N/A — only one path available via Fabric API

---

## Resolved Clarifications

| Item | Resolution |
|------|-----------|
| Lakehouse data load mechanism | REST API (no Spark) — OneLake DFS upload + Table Load API |
| KQL auth resource scope | `https://kusto.kusto.windows.net` (not `https://api.fabric.microsoft.com`) |
| Ontology definition format | Single JSON payload with full entity graph, submitted to ontology definition endpoint |
| Simulator language | Python 3.11+ with `azure-kusto-ingest` |
| Table naming convention | Uppercase with prefix: `DIM_PLANT`, `DIM_LINE`, etc. |
| KQL table idempotency | `.create-merge table` management command |
| CSV upload to Lakehouse | OneLake DFS API (ADLS Gen2 compatible) |
