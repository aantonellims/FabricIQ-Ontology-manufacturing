# Feature Specification: Saint-Gobain Manufacturing Ontology - End-to-End Deployment

**Feature Branch**: `001-ontology-e2e`  
**Created**: 2026-04-01  
**Updated**: 2026-04-03  
**Status**: Implemented & Validated — All user stories complete  
**Input**: Fabric RTI Ontology for Saint-Gobain manufacturing operations demo

## Architecture Overview

This solution deploys two complementary layers on Microsoft Fabric:

1. **Ontology (Digital Twin)**: Models the physical manufacturing hierarchy — plants, lines, equipment, sensors, products, and work orders — with entity types, relationships, bindings to Lakehouse (master data) and KQL (telemetry). The ontology defines *what exists* and *how it's connected*.

2. **Star Schema Semantic Model (Analytics)**: A proper star schema with 6 dimension tables, 3 fact tables, 15 relationships, and 15 DAX measures. The semantic model provides the *analytics layer* for Power BI dashboards — production output, OEE metrics, work order tracking.

These layers are complementary: the ontology does NOT contain analytics measures, and the semantic model does NOT model IoT telemetry.

## User Scenarios & Testing

### User Story 1 - Deploy Fabric Workspace & Infrastructure (Priority: P1)

As a demo engineer, I can run a single script that creates a Fabric workspace on `msfabric001` capacity with a Lakehouse for master data and an Eventhouse with KQL Database for telemetry.

**Why this priority**: Without infrastructure, nothing else can be deployed.

**Independent Test**: Run `Deploy-Ontology.ps1 -StepInfrastructure` and verify workspace, lakehouse, eventhouse, and KQL database exist via Fabric API.

**Acceptance Scenarios**:

1. **Given** no workspace exists, **When** I run the infrastructure script, **Then** workspace "SG-Manufacturing-Ontology" is created on msfabric001 capacity with Lakehouse and Eventhouse.
2. **Given** workspace already exists, **When** I run the script again, **Then** it reuses existing resources without errors (idempotent).
3. **Given** deployment succeeds, **Then** `config.json` is updated with all resource IDs.

---

### User Story 2 - Load Star Schema Master & Fact Data (Priority: P1)

As a demo engineer, I can load sample data representing Saint-Gobain's manufacturing operations into a star schema: 6 dimension tables (Plants, Lines, Equipment, Sensors, Products, Date) and 3 fact tables (Production, Work Orders, Equipment OEE).

**Why this priority**: Master and fact data are required for ontology entity bindings and for the semantic model analytics.

**Independent Test**: Run data load script and verify all 9 Delta tables exist with correct row counts via SQL Analytics Endpoint.

**Acceptance Scenarios**:

1. **Given** Lakehouse exists, **When** I run the data load, **Then** 9 Delta tables are created:
   - 6 dimensions: DIM_PLANT, DIM_LINE, DIM_EQUIPMENT, DIM_SENSOR, DIM_PRODUCT, DIM_DATE
   - 3 fact tables: FACT_PRODUCTION, FACT_WORK_ORDER, FACT_EQUIPMENT_OEE
2. **Given** tables already exist, **When** I run again, **Then** tables are overwritten with fresh data.
3. **Given** data is loaded, **Then** all foreign key references are valid (e.g., every FACT_PRODUCTION.PlantId exists in DIM_PLANT, every FACT_PRODUCTION.DateKey exists in DIM_DATE).
4. **Given** data is loaded, **Then** DIM_DATE covers a contiguous date range sufficient for all fact table DateKey references.

---

### User Story 3 - Create KQL Telemetry Tables (Priority: P1)

As a demo engineer, I can create KQL tables for real-time telemetry: SensorTelemetry, EquipmentStatus, ProductionMetrics, and Alerts.

**Why this priority**: Timeseries bindings require KQL tables to exist.

**Independent Test**: Run KQL table deployment and verify tables via `.show tables` command.

**Acceptance Scenarios**:

1. **Given** KQL Database exists, **When** I run Deploy-KqlTables.ps1, **Then** 4 tables with correct schemas are created.
2. **Given** tables exist, **When** script runs again, **Then** `.create-merge` ensures idempotent creation.
3. **Given** tables are created, **Then** test ingestion succeeds and data is queryable.

---

### User Story 4 - Deploy Star Schema Semantic Model (Priority: P1)

As a demo engineer, I can deploy a Power BI DirectLake semantic model with a proper star schema design — 6 dimension tables, 3 fact tables, 15 relationships (12 active, 3 inactive snowflake), and 15 DAX measures — so that stakeholders can explore manufacturing KPIs in interactive dashboards.

**Why this priority**: Saint-Gobain stakeholders expect interactive dashboards for production output, OEE analysis, and work order tracking. A properly designed star schema is required for performant Power BI reporting.

**Independent Test**: Run `Deploy-SemanticModel.ps1` (which invokes `deploy_semantic_model.py`) and verify the semantic model item exists in the workspace, all 9 tables are present, all 15 relationships are active/inactive as expected, and all 15 measures return valid results via DAX queries.

**Acceptance Scenarios**:

1. **Given** Lakehouse exists with 9 Delta tables, **When** I run the semantic model deployment, **Then** a DirectLake semantic model "SG-Manufacturing" is created in the workspace using `model.bim` with `compatibilityLevel` 1604.
2. **Given** semantic model is deployed, **Then** it contains exactly 9 tables: DIM_PLANT, DIM_LINE, DIM_EQUIPMENT, DIM_SENSOR, DIM_PRODUCT, DIM_DATE, FACT_PRODUCTION, FACT_WORK_ORDER, FACT_EQUIPMENT_OEE.
3. **Given** semantic model is deployed, **Then** 15 relationships exist:
   - 12 active star-schema relationships (each fact table to its relevant dimensions)
   - 3 inactive snowflake relationships: DIM_LINE→DIM_PLANT, DIM_EQUIPMENT→DIM_LINE, DIM_SENSOR→DIM_EQUIPMENT (inactive to prevent ambiguous filter paths)
4. **Given** semantic model is deployed, **Then** 15 DAX measures are defined across 3 fact tables:
   - FACT_PRODUCTION (7): Total Produced, Total Defective, Yield %, Plan Achievement %, Total Scrap, Avg Cycle Time, Availability %
   - FACT_EQUIPMENT_OEE (4): Avg OEE %, Avg Availability %, Total Breakdown Min, Equipment Utilization %
   - FACT_WORK_ORDER (4): Order Count, Total Order Value, Completion %, Open Orders
5. **Given** semantic model exists, **When** I query `EVALUATE ROW("Plants", COUNTROWS(DIM_PLANT))` via DAX, **Then** the correct plant count is returned.
6. **Given** semantic model has star schema relationships, **When** I query production by plant through the fact table, **Then** results correctly aggregate via the active dimension relationships.
7. **Given** semantic model already exists, **When** I run the deploy script again, **Then** it updates the definition without duplicating items (idempotent).
8. **Given** semantic model is deployed, **When** I open it in Power BI, **Then** all 9 tables, 15 relationships, and 15 measures are visible.
9. **Given** the model definition, **Then** partition mode is `"directLake"` only in partition objects, NEVER at table or model level.
10. **Given** the model definition, **Then** `defaultPowerBIDataSourceVersion` is `"powerBI_V3"`.

---

### User Story 5 - Deploy Ontology via Fabric Item Definition API (Priority: P1)

As a demo engineer, I can deploy the complete ontology to Fabric by pushing the Ontology Item Definition via the `updateDefinition` API (endpoint: `/ontologies/{id}/updateDefinition`) with Base64-encoded JSON parts. The definition includes 6 entity types (with positive 64-bit integer IDs, e.g., 296482030633), 5 relationship types, 6 NonTimeSeries data bindings to Lakehouse, 3 TimeSeries data bindings to KQL, and 5 contextualizations.

**Why this priority**: The ontology is the core deliverable. Without pushing the definition via the Item Definition API, the ontology item is empty.

**Independent Test**: After deployment, call `getDefinition` (LRO — result at `operation_url + "/result"`) on the ontology item and verify the response contains all 27 parts: 6 entity types, 5 relationship types, 9 data bindings, 5 contextualizations, plus metadata parts.

**Acceptance Scenarios**:

1. **Given** master data and KQL tables exist, **When** I run the ontology deployment (Python script `deploy_ontology_definition.py`), **Then** ontology "SaintGobainManufacturing" is created via the Fabric REST API.
2. **Given** ontology item exists, **When** the script calls `/ontologies/{id}/updateDefinition`, **Then** it pushes Base64-encoded JSON parts for EntityTypes, DataBindings, RelationshipTypes, and Contextualizations.
3. **Given** definition is pushed, **When** I call `getDefinition` on the ontology item (LRO, result at `operation_url + "/result"`), **Then** the response includes all 6 entity types with correct `valueType` properties (String, Boolean, DateTime, Object, BigInt, Double — not "dataType").
4. **Given** definition is pushed, **When** I call `getDefinition`, **Then** entity type IDs are positive 64-bit integers (e.g., 296482030633), not simple string identifiers or small numbers.
5. **Given** definition is pushed, **When** I verify DataBindings, **Then** 6 NonTimeSeries bindings exist (one per entity type, pointing to Lakehouse Delta tables) and 3 TimeSeries bindings exist (Sensor→SensorTelemetry, Equipment→EquipmentStatus, ProductionLine→ProductionMetrics in KQL).
6. **Given** definition is pushed, **When** I verify contextualizations, **Then** 5 contextualizations exist, one for each relationship type, providing the join-table mappings.
7. **Given** ontology exists, **When** I query entity store, **Then** entities from Lakehouse tables are resolved correctly.
8. **Given** telemetry is flowing, **When** I query timeseries bindings, **Then** sensor data is associated with correct entities.
9. **Given** ontology already exists, **When** I re-run the deploy script, **Then** the definition is updated in-place without creating a duplicate item.

---

### User Story 6 - Start Telemetry Simulator (Priority: P2)

As a demo presenter, I can start a telemetry simulator that generates realistic sensor readings, equipment status updates, and production metrics every 10 seconds.

**Why this priority**: Live data makes the demo compelling but isn't required for ontology structure.

**Independent Test**: Run simulator for 1 minute, then query KQL for recent records.

**Acceptance Scenarios**:

1. **Given** KQL tables exist, **When** I start the simulator, **Then** data flows into all 3 telemetry tables every 10s.
2. **Given** simulator is running, **When** I query `SensorTelemetry | where Timestamp > ago(1m)`, **Then** I get 10+ sensor readings per interval.

---

### User Story 7 - Deploy Graph Model & Data Agent (Priority: P3)

As a demo presenter, I can visualize the manufacturing hierarchy as a graph and ask natural language questions about the plant.

**Why this priority**: Nice-to-have for demo polish; ontology works without these.

**Independent Test**: Verify GraphQL API item exists and Data Agent responds to queries.

**Acceptance Scenarios**:

1. **Given** ontology is deployed, **When** I create graph model, **Then** hierarchy visualization is available.
2. **Given** data agent is deployed, **When** I ask "How many sensors are on Robot Arm A1?", **Then** agent returns correct answer.

---

### User Story 8 - Configure Data Agent with Ontology-Only Source & Comprehensive Instructions (Priority: P1)

As a demo presenter, I can deploy a Data Agent that uses the ontology as its **single data source**, with AI instructions that guide GQL queries including entity traversal, relationship navigation, time-series selectors, and entity name resolution — so the agent can answer questions about plants, equipment, sensors, and real-time telemetry using only the ontology.

**Why this priority**: The Data Agent is the primary user-facing interface for the demo. Using ontology-only as the source simplifies the architecture — the ontology's data bindings abstract the underlying Lakehouse (master data) and KQL (telemetry) resources.

**Independent Test**: Deploy the agent via `deploy_data_agent.py`, then ask questions in the Fabric portal agent chat. Queries must traverse ontology relationships AND access time-series data from underlying KQL tables.

**Acceptance Scenarios**:

1. **Given** ontology is deployed with data bindings, **When** I run `deploy_data_agent.py`, **Then** the Data Agent is updated with exactly 1 data source (ontology) and comprehensive AI instructions.
2. **Given** agent is deployed, **When** I ask "Which production lines does the Aachen plant have?", **Then** the agent returns Float Line 1, Coating Line A, Cutting & Sorting, Laminating Line.
3. **Given** agent is deployed, **When** I ask "For each plant, show any equipment that ever had a downtime greater than 150 minutes", **Then** the agent traverses Plant→Line→Equipment relationships and queries DownTimeMinutes time-series property, returning matching equipment with their plant context.
4. **Given** agent is deployed, **When** I ask "Show all equipment at the Chemille plant that was ever in Maintenance status", **Then** the agent resolves "Chemille" → "Isover Chemille Insulation" and queries Equipment.OperatingStatus time-series.
5. **Given** agent is deployed, **When** I use short plant names ("Aachen", "Seremange"), **Then** the agent resolves them to full names using the entity name resolution rules in the instructions.
6. **Given** agent is deployed, **Then** the agent instructions include: entity model (6 types with properties), relationships (5 edges), GQL query patterns (6 patterns including time-series selectors), underlying resource explanation, entity name resolution, and "Support group by" for aggregation.
7. **Given** agent is deployed, **Then** the datasource element descriptions include time-series property annotations (e.g., "TIME-SERIES: Efficiency, UnitCount, CycleTime" on ProductionLine).
8. **Given** the definition, **Then** there are no stale datasources — only the ontology source exists.
9. **Given** KQL tables have data, **When** I ask time-series queries, **Then** data values match correctly (no embedded single quotes in KQL string values).

---

### User Story 9 - Ingest Sample Telemetry Data into KQL (Priority: P2)

As a demo engineer, I can populate the KQL tables (SensorTelemetry, EquipmentStatus, ProductionMetrics, Alerts) with 24 hours of realistic sample data so the Data Agent can answer time-series queries immediately without waiting for a live simulator.

**Why this priority**: Without sample data, time-series queries return empty results, making the demo ineffective.

**Independent Test**: Run `ingest_sample_telemetry.py` and verify KQL tables have data via count queries.

**Acceptance Scenarios**:

1. **Given** KQL tables exist, **When** I run `ingest_sample_telemetry.py`, **Then** ~960 SensorTelemetry, ~864 EquipmentStatus, ~576 ProductionMetrics, and ~30 Alerts rows are ingested.
2. **Given** data is ingested, **Then** timestamps span the last 24 hours from ingestion time.
3. **Given** data is ingested, **Then** string values (SensorId, EquipmentId, OperatingStatus, etc.) do NOT contain embedded single quotes — Kusto inline ingest CSV values must NOT be quoted.
4. **Given** data is ingested, **Then** EquipmentId values match ontology entity IDs (e.g., `SG-EQ-001` not `'SG-EQ-001'`).
5. **Given** data is ingested, **Then** the Data Agent can resolve time-series queries because the ontology's TimeSeries bindings can match KQL rows by ID.

---

### Edge Cases

- What happens when Fabric capacity is paused? → Script should detect and report error before attempting creation.
- What happens when auth token expires mid-deployment? → Token refresh at each deployment step.
- What happens when KQL Database hasn't finished provisioning? → Poll for readiness with retry.
- What happens when the ontology definition is pushed with empty entity types? → Validation must fail with a clear error listing which entity types are missing.
- What happens when the Lakehouse SQL endpoint is not yet available for DirectLake? → Script should poll endpoint readiness before creating the semantic model.
- What happens when a semantic model with the same name already exists? → Script should update the existing definition, not create a duplicate.
- What happens when dim-to-dim relationships are all active? → Ambiguous filter paths cause DAX errors. Snowflake dim-to-dim relationships (LINE→PLANT, EQUIPMENT→LINE, SENSOR→EQUIPMENT) must be `isActive: false`.
- What happens when KQL inline ingest uses single-quoted string values? → Quotes become embedded in the data (e.g., `'SG-EQ-001'` instead of `SG-EQ-001`). Ontology time-series bindings fail to match. **Fix**: Never quote string values in `.ingest inline` CSV rows.
- What happens when Data Agent has multiple sources (ontology + semantic model + KQL)? → Agent must perform cross-source joins manually, which requires complex instructions. **Simplified**: Use ontology as single source — it abstracts both Lakehouse and KQL via data bindings.
- What happens when the Data Agent `updateDefinition` API is called with fewer datasources? → The API replaces the entire definition — stale sources are automatically removed.
- What happens when `az cli` hangs during PowerShell REST calls? → Use Python deploy scripts (`deploy_semantic_model.py`, `deploy_ontology_definition.py`) to avoid WMI timeout issues in `az rest` on Windows.
- What happens when `getDefinition` is called on an ontology? → It returns an LRO (Long Running Operation); the actual result is at `operation_url + "/result"`, not the initial response.
- What happens when partition mode is set at the table level? → DirectLake model deployment fails. Mode must ONLY be set in partition objects, never at table or model level.

### Validation Tests

#### Ontology Definition Validation (27 parts)

1. **VT-ONT-1**: After ontology deployment, call `POST /ontologies/{ontologyId}/getDefinition` (LRO) and verify the response contains exactly 6 entity type parts.
2. **VT-ONT-2**: Parse each entity type part (Base64-decode the payload) and verify `properties` array uses `valueType` (not `dataType`) with values in {String, Boolean, DateTime, Object, BigInt, Double}.
3. **VT-ONT-3**: Verify all entity type IDs are positive 64-bit integers (e.g., 296482030633).
4. **VT-ONT-4**: Verify 5 RelationshipType parts exist with correct source/target `entityTypeId` references.
5. **VT-ONT-5**: Verify 6 NonTimeSeries DataBinding parts exist under the correct `EntityTypes/{id}/DataBindings/` paths, each pointing to the corresponding Lakehouse Delta table.
6. **VT-ONT-6**: Verify 3 TimeSeries DataBinding parts exist (Sensor→SensorTelemetry, Equipment→EquipmentStatus, ProductionLine→ProductionMetrics).
7. **VT-ONT-7**: Verify 5 Contextualization parts exist, one for each relationship, providing the join-table mapping.

#### Star Schema Semantic Model Validation (9 tables, 15 relationships, 15 measures)

1. **VT-SM-1**: After semantic model deployment, call `GET /workspaces/{wsId}/items?type=SemanticModel` and verify an item named "SG-Manufacturing" exists.
2. **VT-SM-2**: Execute DAX query `EVALUATE ROW("Plants", COUNTROWS(DIM_PLANT))` and verify a non-zero result is returned.
3. **VT-SM-3**: Verify all 9 tables are present in the model (6 dimensions + 3 fact tables) via DAX.
4. **VT-SM-4**: Verify 15 relationships exist: 12 active (fact-to-dim) and 3 inactive (dim-to-dim snowflake: DIM_LINE→DIM_PLANT, DIM_EQUIPMENT→DIM_LINE, DIM_SENSOR→DIM_EQUIPMENT).
5. **VT-SM-5**: Verify all 15 DAX measures return valid results:
   - FACT_PRODUCTION: Total Produced, Total Defective, Yield %, Plan Achievement %, Total Scrap, Avg Cycle Time, Availability %
   - FACT_EQUIPMENT_OEE: Avg OEE %, Avg Availability %, Total Breakdown Min, Equipment Utilization %
   - FACT_WORK_ORDER: Order Count, Total Order Value, Completion %, Open Orders
6. **VT-SM-6**: Verify the model uses DirectLake mode by confirming `"mode": "directLake"` appears only in partition objects and `defaultPowerBIDataSourceVersion` is `"powerBI_V3"`.
7. **VT-SM-7**: Verify `compatibilityLevel` is 1604 in the model definition.
8. **VT-SM-8**: Verify star schema queries work: aggregating fact data (e.g., Total Produced) sliced by dimension attributes (e.g., by Plant, by Date) returns correct results.

#### Infrastructure & Integration Validation

1. **VT-INFRA-1**: Verify KQL Database has 4 accessible tables (SensorTelemetry, EquipmentStatus, ProductionMetrics, Alerts).
2. **VT-INFRA-2**: Verify KQL test ingestion succeeds and ingested data is queryable.
3. **VT-INFRA-3**: Verify Data Agent item exists in workspace.
4. **VT-INFRA-4**: Verify GraphQL API item exists in workspace.
5. **VT-INFRA-5**: Verify Graph Model item exists in workspace.

## Requirements

### Functional Requirements

#### Ontology (Digital Twin Layer)

1. **FR-1**: 6 entity types defined (Plant, ProductionLine, Equipment, Sensor, Product, WorkOrder) with proper primary keys, display names, and properties using `valueType` (not `dataType`)
2. **FR-2**: 5 relationships connecting the manufacturing hierarchy: Has_Line, Has_Equipment, Has_Sensor, Assigned_To, Produces
3. **FR-3**: 6 NonTimeSeries data bindings connect each entity type to its corresponding Lakehouse Delta table (DIM_PLANT, DIM_LINE, DIM_EQUIPMENT, DIM_SENSOR, DIM_PRODUCT, and the work order source)
4. **FR-4**: 3 TimeSeries data bindings connect Equipment→EquipmentStatus, Sensor→SensorTelemetry, and ProductionLine→ProductionMetrics to their KQL telemetry tables
5. **FR-5**: 5 contextualizations provide join-table mappings for each relationship type
6. **FR-6**: Ontology Item Definition pushed via `/ontologies/{id}/updateDefinition` API with Base64-encoded JSON parts; entity type IDs are positive 64-bit integers (e.g., 296482030633); DataBindings structured under `EntityTypes/{id}/DataBindings/`; RelationshipTypes reference source/target by `entityTypeId`
7. **FR-7**: After pushing ontology definition, `getDefinition` (LRO — result at `operation_url + "/result"`) returns a non-empty payload with all 27 parts: 6 entity types, 5 relationship types, 9 data bindings, 5 contextualizations, plus metadata

#### Star Schema Semantic Model (Analytics Layer)

8. **FR-8**: DirectLake semantic model "SG-Manufacturing" connects to the Lakehouse SQL endpoint and includes 9 tables: 6 dimensions (DIM_PLANT, DIM_LINE, DIM_EQUIPMENT, DIM_SENSOR, DIM_PRODUCT, DIM_DATE) and 3 fact tables (FACT_PRODUCTION, FACT_WORK_ORDER, FACT_EQUIPMENT_OEE)
9. **FR-9**: Semantic model defines 15 star schema relationships — 12 active relationships connecting each fact table to its relevant dimensions, and 3 inactive snowflake relationships (DIM_LINE→DIM_PLANT, DIM_EQUIPMENT→DIM_LINE, DIM_SENSOR→DIM_EQUIPMENT) to prevent ambiguous filter paths
10. **FR-10**: Semantic model includes 15 DAX measures distributed across 3 fact tables:
    - FACT_PRODUCTION (7): Total Produced, Total Defective, Yield %, Plan Achievement %, Total Scrap, Avg Cycle Time, Availability %
    - FACT_EQUIPMENT_OEE (4): Avg OEE %, Avg Availability %, Total Breakdown Min, Equipment Utilization %
    - FACT_WORK_ORDER (4): Order Count, Total Order Value, Completion %, Open Orders
11. **FR-11**: Semantic model deployed via Fabric Item Definition API using `model.bim` (TMSL) format with `compatibilityLevel` 1604, `defaultPowerBIDataSourceVersion` `"powerBI_V3"`, and partition mode `"directLake"` only in partition objects (never at table or model level)

#### Data & Telemetry

12. **FR-12**: Sample data uses Saint-Gobain domain terminology (glass types, building materials, etc.)
13. **FR-13**: 9 Lakehouse Delta tables loaded from CSV: 6 dimensions (plants, lines, equipment, sensors, products, dates) and 3 fact tables (production, work orders, equipment OEE)
14. **FR-14**: 4 KQL tables created for telemetry (SensorTelemetry, EquipmentStatus, ProductionMetrics, Alerts)
15. **FR-15**: Telemetry simulator generates realistic values within sensor-defined min/max ranges

#### Deployment

16. **FR-16**: Deploy scripts are Python-based (`deploy_ontology_definition.py`, `deploy_semantic_model.py`) to avoid `az cli` WMI timeout issues; PowerShell scripts serve as orchestrators calling Python
17. **FR-17**: DIM_WORKORDER was removed from the dimension tables; work order data is modeled as FACT_WORK_ORDER with cost, completion, and status metrics

### Non-Functional Requirements

1. **NFR-1**: Full deployment completes in under 10 minutes
2. **NFR-2**: All scripts are idempotent (safe to re-run)
3. **NFR-3**: No credentials stored in files (use `az account get-access-token`)
4. **NFR-4**: Resource IDs centralized in `config.json`
5. **NFR-5**: Ontology definition validated as non-empty after each push (deployment script verifies via `getDefinition`)
6. **NFR-6**: Semantic model deployment verifies Lakehouse SQL endpoint availability before pushing the definition
7. **NFR-7**: Validation suite achieves ≥99% pass rate (target: 100/101 tests)

## Success Criteria

### Measurable Outcomes

- **SC-1**: Full end-to-end deployment completes successfully from a single `Deploy-Ontology.ps1` invocation
- **SC-2**: Ontology `getDefinition` returns all 27 parts with correct structure (6 entity types, 5 relationships, 9 bindings, 5 contextualizations)
- **SC-3**: All 15 DAX measures return valid, non-error results when queried via the Fabric API
- **SC-4**: Validation suite passes ≥99% of tests (achieved: 100/101)
- **SC-5**: Star schema queries correctly aggregate fact data sliced by any dimension (e.g., Total Produced by Plant by Month)
- **SC-6**: KQL telemetry ingestion succeeds and data is queryable within 30 seconds
- **SC-7**: Re-running deployment on an existing workspace completes without errors (idempotent)

## Assumptions

- Target Fabric capacity `msfabric001` is available and running (not paused)
- User has Fabric admin or contributor permissions on the target capacity
- `az cli` is installed and authenticated (`az login` completed)
- Python 3.11+ is available for deployment scripts (Python used instead of PowerShell for REST calls due to `az rest` WMI timeout issues on Windows)
- Power BI Desktop March 2026+ supports compatibilityLevel 1604 for DirectLake models
- DIM_WORKORDER was intentionally removed; work order analytics are served by FACT_WORK_ORDER with additive measures

## Saint-Gobain Manufacturing Domain Model

### Ontology Entity Types (Digital Twin)

| Entity | Description | Saint-Gobain Context |
|--------|-------------|---------------------|
| Plant | Manufacturing facility | Flat Glass (Aachen), HPM (Cavaillon), Construction Products (Aubervilliers) |
| ProductionLine | Production/assembly line | Float Line, Coating Line, Laminating Line, Insulation Line |
| Equipment | Machines & devices | Float Bath, Annealing Lehr, Cutting Table, Mixing Station |
| Sensor | IoT sensors | Temperature, Thickness, Pressure, Speed, Humidity |
| Product | Manufactured goods | SGG PLANILUX, ISOVER, WEBER, GYPROC, SEKURIT |
| WorkOrder | Production orders | Batch production runs linked to product and line |

### Ontology Relationships

```
Plant ──[Has_Line]──> ProductionLine ──[Has_Equipment]──> Equipment ──[Has_Sensor]──> Sensor
                      ProductionLine <──[Assigned_To]── WorkOrder ──[Produces]──> Product
```

### Ontology Bindings

| Binding Type | Count | Targets |
|-------------|-------|---------|
| NonTimeSeries | 6 | Lakehouse DIMs: Plant, Line, Equipment, Sensor, Product, WorkOrder |
| TimeSeries | 3 | KQL: SensorTelemetry, EquipmentStatus, ProductionMetrics |

### Star Schema Semantic Model (Analytics)

#### Lakehouse Tables (9)

| Table | Type | Description |
|-------|------|-------------|
| DIM_PLANT | Dimension | Manufacturing facilities |
| DIM_LINE | Dimension | Production lines |
| DIM_EQUIPMENT | Dimension | Machines and devices |
| DIM_SENSOR | Dimension | IoT sensors |
| DIM_PRODUCT | Dimension | Manufactured goods |
| DIM_DATE | Dimension | Calendar date dimension |
| FACT_PRODUCTION | Fact | Daily output per production line (qty produced, defective, scrap, cycle time) |
| FACT_WORK_ORDER | Fact | Work orders with cost, completion status, and duration |
| FACT_EQUIPMENT_OEE | Fact | OEE metrics per equipment (availability, performance, quality) |

#### Star Schema Relationships (15)

| # | Type | Relationship | Active |
|---|------|-------------|--------|
| 1-12 | Fact→Dim | Each fact table connects to its relevant dimensions (Date, Plant, Line, Product, Equipment) | Yes |
| 13 | Dim→Dim (snowflake) | DIM_LINE → DIM_PLANT | No (inactive) |
| 14 | Dim→Dim (snowflake) | DIM_EQUIPMENT → DIM_LINE | No (inactive) |
| 15 | Dim→Dim (snowflake) | DIM_SENSOR → DIM_EQUIPMENT | No (inactive) |

Dim-to-dim relationships are inactive to prevent ambiguous filter paths in DAX.

#### DAX Measures (15)

| Fact Table | Measure | Description |
|-----------|---------|-------------|
| FACT_PRODUCTION | Total Produced | Sum of quantity produced |
| FACT_PRODUCTION | Total Defective | Sum of defective units |
| FACT_PRODUCTION | Yield % | (Produced - Defective) / Produced |
| FACT_PRODUCTION | Plan Achievement % | Actual vs planned production |
| FACT_PRODUCTION | Total Scrap | Sum of scrap units |
| FACT_PRODUCTION | Avg Cycle Time | Average cycle time |
| FACT_PRODUCTION | Availability % | Uptime percentage |
| FACT_EQUIPMENT_OEE | Avg OEE % | Average Overall Equipment Effectiveness |
| FACT_EQUIPMENT_OEE | Avg Availability % | Average equipment availability |
| FACT_EQUIPMENT_OEE | Total Breakdown Min | Total breakdown minutes |
| FACT_EQUIPMENT_OEE | Equipment Utilization % | Utilization rate |
| FACT_WORK_ORDER | Order Count | Count of work orders |
| FACT_WORK_ORDER | Total Order Value | Sum of order values |
| FACT_WORK_ORDER | Completion % | Completed / Total orders |
| FACT_WORK_ORDER | Open Orders | Count of non-completed orders |

### Key Technical Constraints

- `model.bim` uses `compatibilityLevel` 1604 (required for DirectLake)
- Partition mode `"directLake"` must ONLY appear in partition objects, never at table or model level
- `defaultPowerBIDataSourceVersion` must be `"powerBI_V3"`
- Ontology entity type IDs are positive 64-bit integers (e.g., 296482030633)
- Ontology API endpoint: `/ontologies/{id}/updateDefinition` (not `/items/{id}/...`)
- `getDefinition` is an LRO; actual result is at `operation_url + "/result"`
- Dim-to-dim relationships must be `isActive: false` to prevent ambiguous DAX paths
- Python deploy scripts used (not PowerShell `az rest`) due to WMI timeout issues on Windows

## Project Structure

```
Ontology-Manuf/
├── .specify/                    # Spec-kit framework
├── .github/agents/              # Copilot agents
├── specs/                       # Feature specifications
├── Deploy-Ontology.ps1          # Main deployment orchestrator
├── deploy/
│   ├── Deploy-Infrastructure.ps1
│   ├── Load-SampleData.ps1
│   ├── Deploy-KqlTables.ps1
│   ├── Deploy-SemanticModel.ps1 # NEW: DirectLake semantic model deployment
│   ├── Deploy-OntologyModel.ps1 # UPDATED: pushes definition via updateDefinition API
│   ├── Deploy-GraphModel.ps1
│   ├── Deploy-DataAgent.ps1
│   └── Start-TelemetrySimulator.ps1
├── ontologies/SaintGobain/
│   ├── config.json              # Fabric resource IDs
│   ├── data/                    # Sample CSV data
│   ├── ontology/                # Entity types & relationship definitions (Fabric API schema)
│   ├── semantic-model/          # TMDL/model.bim for DirectLake semantic model
│   ├── kql/                     # KQL table schemas & queries
│   ├── queries/                 # Graph query examples
│   └── simulator/               # Telemetry simulator (Python)
└── tests/
    └── Validate-Ontology.ps1    # UPDATED: includes ontology non-empty + semantic model checks
```

## Ontology Definition API Format

The Fabric Ontology uses the **Item Definition API** (`updateDefinition` / `getDefinition`). The definition payload consists of Base64-encoded JSON parts organized by path:

| Part Path | Content |
|-----------|--------|
| `EntityTypes/{id}/EntityType.json` | Entity type definition (id = positive Int64, properties use `valueType`) |
| `EntityTypes/{id}/DataBindings/{bindingName}.json` | Data binding (NonTimeSeries or TimeSeries) |
| `RelationshipTypes/{name}.json` | Relationship type (source/target by `entityTypeId`) |
| `Contextualizations/{name}.json` | Join-table mapping for a relationship |

The current ontology JSON files in `ontology/` use a simplified schema (`dataType` instead of `valueType`, string IDs, flat bindings directory). These must be restructured to match the Fabric API schema before deployment.
