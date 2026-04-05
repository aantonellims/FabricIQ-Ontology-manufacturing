# Tasks: Saint-Gobain Manufacturing Ontology — End-to-End Deployment

**Status**: ✅ ALL TASKS COMPLETED — All user stories (US1–US9) implemented & validated
**Input**: Design documents from `/specs/001-ontology-e2e/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story (US1–US7) to enable independent implementation and testing of each deployment step.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- All paths are relative to repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project scaffolding — directory structure, shared helpers, orchestrator script

- [X] T001 Create directory structure: `ontology/entity-types/`, `ontology/relationships/`, `ontology/bindings/nontimeseries/`, `ontology/bindings/timeseries/`, `kql/`, `simulator/`, `queries/`
- [X] T002 Create shared auth/config helper module in `deploy/FabricHelpers.psm1` with `Get-FabricToken`, `Get-Config`, `Save-Config`, `Invoke-FabricApi`, and `Find-OrCreateItem` functions
- [X] T003 Create main orchestrator script `Deploy-Ontology.ps1` with `-StepInfrastructure`, `-StepData`, `-StepKqlTables`, `-StepOntology`, `-StepSimulator`, `-StepGraph`, `-StepAgent` switches

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Ensure existing infrastructure script works, config.json is correct, and auth is validated

**⚠️ CRITICAL**: No user story work can begin until infrastructure (US1) deploys successfully

- [X] T004 Refactor `deploy/Deploy-Infrastructure.ps1` to import shared helpers from `deploy/FabricHelpers.psm1`
- [X] T005 Validate `config.json` schema matches the contract in `specs/001-ontology-e2e/contracts/ontology-api.md` — ensure all keys present (workspace, capacity, lakehouse, eventhouse, kqlDatabase, ontology, apiBase)

**Checkpoint**: Helper module importable, orchestrator runs `--help`, config.json schema validated

---

## Phase 3: User Story 1 — Deploy Fabric Workspace & Infrastructure (Priority: P1) 🎯 MVP

**Goal**: Run a single script that creates workspace on `msfabric001`, Lakehouse, Eventhouse, and KQL Database. Config.json is populated with all resource IDs.

**Independent Test**: Run `.\Deploy-Ontology.ps1 -StepInfrastructure` → verify workspace, lakehouse, eventhouse, KQL database exist via Fabric API and config.json is populated.

### Implementation for User Story 1

- [X] T006 [US1] Verify `deploy/Deploy-Infrastructure.ps1` handles idempotent re-run: workspace exists → reuse, lakehouse exists → reuse, eventhouse exists → reuse, KQL database polling works
- [X] T007 [US1] Add capacity-paused detection to `deploy/Deploy-Infrastructure.ps1` — check capacity state before workspace creation, report clear error if paused
- [X] T008 [US1] Wire `Deploy-Ontology.ps1 -StepInfrastructure` to call `deploy/Deploy-Infrastructure.ps1`
- [X] T009 [US1] Add post-deploy validation to `deploy/Deploy-Infrastructure.ps1` — after updating config.json, query each resource ID via GET to confirm existence

**Checkpoint**: `.\Deploy-Ontology.ps1 -StepInfrastructure` creates all infrastructure and populates config.json; re-running is idempotent

---

## Phase 4: User Story 2 — Load Star Schema Master & Fact Data (Priority: P1)

**Goal**: Load 9 CSV files into Lakehouse Delta tables — 6 dimensions (DIM_PLANT, DIM_LINE, DIM_EQUIPMENT, DIM_SENSOR, DIM_PRODUCT, DIM_DATE) and 3 fact tables (FACT_PRODUCTION, FACT_WORK_ORDER, FACT_EQUIPMENT_OEE) — via OneLake DFS + Table Load API.

**Independent Test**: Run `.\Deploy-Ontology.ps1 -StepData` → verify 9 Delta tables exist with correct row counts via SQL Analytics Endpoint.

### Implementation for User Story 2

- [X] T010 [US2] Create `deploy/Load-SampleData.ps1` — implement CSV upload via OneLake DFS API (create file → append → flush)
- [X] T010a [P] [US2] Create `data/dim_date.csv` — date dimension covering all DateKey values referenced by fact tables
- [X] T010b [P] [US2] Create `data/fact_production.csv` — production facts with PlantId, LineId, ProductId, DateKey FKs
- [X] T010c [P] [US2] Create `data/fact_work_order.csv` — work order facts with LineId, ProductId, DateKey FKs
- [X] T010d [P] [US2] Create `data/fact_equipment_oee.csv` — equipment OEE facts with EquipmentId, LineId, DateKey FKs
- [X] T011 [US2] Add Delta table load logic to `deploy/Load-SampleData.ps1` — call `POST /workspaces/{wsId}/lakehouses/{lhId}/tables/{tableName}/load` with mode=Overwrite for each of the 9 table mappings (6 dims + 3 facts)
- [X] T012 [US2] Add table load status polling to `deploy/Load-SampleData.ps1` — Table Load API is async (returns 202); poll operation status until each load completes
- [X] T013 [US2] Wire `Deploy-Ontology.ps1 -StepData` to call `deploy/Load-SampleData.ps1`
- [X] T014 [US2] Add post-load validation to `deploy/Load-SampleData.ps1` — query Lakehouse tables API to verify all 9 tables exist and FK references are valid

**Checkpoint**: All 9 Delta tables created with correct data (6 dims + 3 facts); all FK references valid; re-running overwrites cleanly

---

## Phase 5: User Story 3 — Create KQL Telemetry Tables (Priority: P1)

**Goal**: Create 4 KQL tables (SensorTelemetry, EquipmentStatus, ProductionMetrics, Alerts) with schemas from contracts, plus caching/retention/streaming policies.

**Independent Test**: Run `.\Deploy-Ontology.ps1 -StepKqlTables` → execute `.show tables` in KQL, verify 4 tables with correct columns.

### Implementation for User Story 3

- [X] T015 [P] [US3] Create `kql/create-tables.kql` with all `.create-merge table` commands for SensorTelemetry, EquipmentStatus, ProductionMetrics, Alerts
- [X] T016 [P] [US3] Create `kql/policies.kql` with caching (31d hot), retention (365d), and streaming ingestion policies for all 4 tables
- [X] T017 [US3] Create `deploy/Deploy-KqlTables.ps1` — read KQL commands from `kql/create-tables.kql` and `kql/policies.kql`, execute via KQL management API
- [X] T018 [US3] Add post-deploy validation to `deploy/Deploy-KqlTables.ps1` — execute `.show tables` query and verify 4 tables exist
- [X] T019 [US3] Wire `Deploy-Ontology.ps1 -StepKqlTables` to call `deploy/Deploy-KqlTables.ps1`

**Checkpoint**: 4 KQL tables with correct schemas and policies; `.create-merge` is idempotent on re-run

---

## Phase 6: User Story 4 — Deploy Star Schema Semantic Model (Priority: P1)

**Goal**: Deploy a DirectLake Power BI semantic model `SG-Manufacturing` with a proper star schema design — 6 dimension tables (DIM_PLANT, DIM_LINE, DIM_EQUIPMENT, DIM_SENSOR, DIM_PRODUCT, DIM_DATE), 3 fact tables (FACT_PRODUCTION, FACT_WORK_ORDER, FACT_EQUIPMENT_OEE), 15 relationships (12 active fact-to-dim, 3 inactive dim-to-dim snowflake), and 15 DAX measures.

**Independent Test**: Run `.\Deploy-Ontology.ps1 -StepSemanticModel` → verify semantic model exists in workspace, all 9 tables present, 15 relationships correct, all 15 measures return valid DAX results.

**Depends on**: US2 (Lakehouse Delta tables must exist — all 9 tables)

### Star Schema Model Definition

- [X] T064 [US4] Query Lakehouse SQL endpoint to validate all 9 table schemas exist (6 dims + 3 facts) and column names match expected schema from `specs/001-ontology-e2e/data-model.md`
- [X] T065 [US4] Create `semantic-model/model.bim` — TMSL definition with star schema design:
  - `compatibilityLevel` **1604**, `defaultPowerBIDataSourceVersion`: `powerBI_V3`
  - `expressions` block with `DatabaseQuery` M expression via `Sql.Database()` pointing to Lakehouse SQL endpoint
  - 9 tables: DIM_PLANT, DIM_LINE, DIM_EQUIPMENT, DIM_SENSOR, DIM_PRODUCT, DIM_DATE, FACT_PRODUCTION, FACT_WORK_ORDER, FACT_EQUIPMENT_OEE
  - Each table partition with `"mode": "directLake"` and `"expressionSource": "DatabaseQuery"` — NO `defaultMode` at model level, NO `mode` at table level
  - 15 relationships: 12 active (fact-to-dim, all manyToOne) + 3 inactive snowflake (DIM_LINE→DIM_PLANT, DIM_EQUIPMENT→DIM_LINE, DIM_SENSOR→DIM_EQUIPMENT — `isActive: false` to prevent ambiguous filter paths)
  - 15 DAX measures across fact tables:
    - FACT_PRODUCTION (7): Total Produced, Total Defective, Yield %, Plan Achievement %, Total Scrap, Avg Cycle Time, Availability %
    - FACT_EQUIPMENT_OEE (4): Avg OEE %, Avg Availability %, Total Breakdown Min, Equipment Utilization %
    - FACT_WORK_ORDER (4): Order Count, Total Order Value, Completion %, Open Orders
- [X] T065a [US4] Fix `compatibilityLevel` to **1604** and add `defaultPowerBIDataSourceVersion: powerBI_V3` in model.bim
- [X] T065b [US4] Remove `defaultMode` from model level in model.bim — keep `"mode": "directLake"` ONLY in partition objects
- [X] T065c [US4] Add 3 inactive snowflake relationships (DIM_LINE→DIM_PLANT, DIM_EQUIPMENT→DIM_LINE, DIM_SENSOR→DIM_EQUIPMENT) with `isActive: false`

### Deployment Script (Python)

- [X] T066 [US4] Create `deploy/deploy_semantic_model.py` — Python script that: reads `config.json` for workspace/lakehouse IDs, gets Lakehouse SQL endpoint connection string via Fabric API, creates or finds `SG-Manufacturing` SemanticModel item in workspace, reads `semantic-model/model.bim` and injects SQL endpoint connection string, Base64-encodes model.bim, calls `/semanticModels/{id}/updateDefinition` API with `definition.parts[]`, saves semantic model ID to `config.json`
- [X] T067 [US4] Create thin PowerShell wrapper `deploy/Deploy-SemanticModel.ps1` that calls `deploy/deploy_semantic_model.py`
- [X] T068 [US4] Wire `Deploy-Ontology.ps1 -StepSemanticModel` switch to call `deploy/Deploy-SemanticModel.ps1`
- [X] T069 [US4] Add SQL endpoint readiness check to `deploy/deploy_semantic_model.py` — poll Lakehouse SQL endpoint availability before pushing semantic model definition
- [X] T070 [US4] Add post-deploy DAX validation to `deploy/deploy_semantic_model.py` — execute DAX queries to verify: all dim counts (DIM_PLANT, DIM_LINE, etc.), all fact counts (FACT_PRODUCTION, FACT_WORK_ORDER, FACT_EQUIPMENT_OEE), all 15 measures return valid results, star joins work (fact aggregation sliced by dimension attributes)
- [X] T071 [US4] Add idempotency — if `SG-Manufacturing` semantic model already exists, update its definition via `updateDefinition` rather than creating a duplicate
- [X] T072 [US4] Update `config.json` schema to include `"semanticModel": { "id": "guid", "name": "SG-Manufacturing" }`

**Checkpoint**: Semantic model `SG-Manufacturing` deployed with star schema via DirectLake. 9 tables, 15 relationships (12 active + 3 inactive snowflake), 15 DAX measures. `compatibilityLevel` 1604, `defaultPowerBIDataSourceVersion` powerBI_V3. Partition mode `directLake` only in partition objects. All DAX validations pass.

---

## Phase 7: User Story 5 — Deploy Ontology Definition via updateDefinition API (Priority: P1)

**Goal**: Push the complete ontology definition to Fabric via the `updateDefinition` API with Base64-encoded JSON parts. The definition includes 6 entity types (positive Int64 IDs, `valueType` properties), 5 relationship types, 9 data bindings (6 NTS + 3 TS), and 5 contextualizations.

**Independent Test**: After deployment, call `getDefinition` on the ontology item and verify response contains exactly 6 entity types with non-empty properties and positive Int64 IDs. All parts use `valueType` (not `dataType`).

**Depends on**: US2 (Lakehouse tables for NTS bindings) + US3 (KQL tables for TS bindings)

### Restructure Entity Type JSON Files (Fabric API Schema)

**Problem**: Current `ontology/entity-types/*.json` use wrong schema (`dataType` instead of `valueType`, no Int64 IDs). Must restructure to match Fabric Item Definition API.

- [X] T073 [P] [US5] Restructure `ontology/entity-types/plant.json` — add `"id": 1001` (Int64), change all `"dataType"` → `"valueType"`, use correct enum values (String, Boolean, DateTime, Object, BigInt, Double), add `"primaryKey"`, `"displayNameProperty"`, `"foreignKeys"`
- [X] T074 [P] [US5] Restructure `ontology/entity-types/production-line.json` — add `"id": 1002`, change `"dataType"` → `"valueType"`, add FK reference to Plant (entityTypeId: 1001)
- [X] T075 [P] [US5] Restructure `ontology/entity-types/equipment.json` — add `"id": 1003`, change `"dataType"` → `"valueType"`, add FK reference to ProductionLine (entityTypeId: 1002)
- [X] T076 [P] [US5] Restructure `ontology/entity-types/sensor.json` — add `"id": 1004`, change `"dataType"` → `"valueType"`, add FK reference to Equipment (entityTypeId: 1003)
- [X] T077 [P] [US5] Restructure `ontology/entity-types/product.json` — add `"id": 1005`, change `"dataType"` → `"valueType"`
- [X] T078 [P] [US5] Restructure `ontology/entity-types/workorder.json` — add `"id": 1006`, change `"dataType"` → `"valueType"`, add FK references to ProductionLine (1002) and Product (1005)

### Update Relationship Definitions (entityTypeId References)

- [X] T079 [P] [US5] Update `ontology/relationships/has-line.json` — reference source by `entityTypeId: 1001` (Plant), target by `entityTypeId: 1002` (ProductionLine)
- [X] T080 [P] [US5] Update `ontology/relationships/has-equipment.json` — source `entityTypeId: 1002`, target `entityTypeId: 1003`
- [X] T081 [P] [US5] Update `ontology/relationships/has-sensor.json` — source `entityTypeId: 1003`, target `entityTypeId: 1004`
- [X] T082 [P] [US5] Update `ontology/relationships/assigned-to.json` — source `entityTypeId: 1006` (WorkOrder), target `entityTypeId: 1002` (ProductionLine)
- [X] T083 [P] [US5] Update `ontology/relationships/produces.json` — source `entityTypeId: 1006` (WorkOrder), target `entityTypeId: 1005` (Product)

### Create Contextualization Files (Join-Table Mappings)

- [X] T084 [P] [US5] Create `ontology/contextualizations/has-line.json` — Plant.PlantId ↔ DIM_LINE.PlantId join mapping
- [X] T085 [P] [US5] Create `ontology/contextualizations/has-equipment.json` — Line.LineId ↔ DIM_EQUIPMENT.LineId join mapping
- [X] T086 [P] [US5] Create `ontology/contextualizations/has-sensor.json` — Equipment.EquipmentId ↔ DIM_SENSOR.EquipmentId join mapping
- [X] T087 [P] [US5] Create `ontology/contextualizations/assigned-to.json` — WorkOrder.LineId ↔ DIM_LINE.LineId join mapping
- [X] T088 [P] [US5] Create `ontology/contextualizations/produces.json` — WorkOrder.ProductId ↔ DIM_PRODUCT.ProductId join mapping

### Deployment Script (Python — avoids PowerShell WMI timeout issues)

**Key Fixes Applied**: API endpoints corrected from `/items/` to `/ontologies/`, LRO handling fixed with `/result` suffix on operation URL, entity type IDs changed to large 64-bit integers (e.g., `296482030633`), deployment via `push_ontology_v2.py` with proper LRO polling.

- [X] T089 [US5] Create `deploy/push_ontology_v2.py` — Python script that: reads `config.json` for workspace ID, ontology ID, lakehouse ID, KQL database info; gets auth token via `DefaultAzureCredential`; reads all JSON from `ontology/entity-types/`, `ontology/relationships/`, `ontology/bindings/`, `ontology/contextualizations/`; injects runtime values (lakehouse ID, KQL database ID, queryServiceUri) into binding JSON; Base64-encodes each JSON part; assembles `definition.parts[]` array with correct path structure (`EntityTypes/{id}/EntityType.json`, `EntityTypes/{id}/DataBindings/*.json`, `RelationshipTypes/*.json`, `Contextualizations/*.json`); calls `POST /workspaces/{wsId}/ontologies/{ontologyId}/updateDefinition` (corrected endpoint)
- [X] T089a [US5] Fix API endpoints — change from `/items/{id}/updateDefinition` to `/ontologies/{id}/updateDefinition` and `/ontologies/{id}/getDefinition`
- [X] T089b [US5] Fix LRO handling — `getDefinition` returns Long Running Operation; poll `operation_url + "/result"` for the actual definition payload
- [X] T089c [US5] Generate large 64-bit integer IDs for entity types (e.g., `296482030633`) instead of small sequential IDs (1001–1006)
- [X] T090 [US5] Add `getDefinition` validation to `deploy/push_ontology_v2.py` — after pushing, call `POST /workspaces/{wsId}/ontologies/{ontologyId}/getDefinition` (LRO with `/result` suffix) and verify: exactly 6 EntityType parts, exactly 5 RelationshipType parts, exactly 9 DataBinding parts (6 NTS + 3 TS), exactly 5 Contextualization parts, all entity type IDs are positive 64-bit integers
- [X] T091 [US5] Update `deploy/Deploy-OntologyModel.ps1` to delegate to `deploy/push_ontology_v2.py` (thin PowerShell wrapper for orchestrator compatibility)
- [X] T092 [US5] Wire `Deploy-Ontology.ps1 -StepOntology` to call the updated `deploy/Deploy-OntologyModel.ps1`
- [X] T093 [US5] Add idempotency logging to `deploy/push_ontology_v2.py` — `updateDefinition` is inherently idempotent (overwrites), but script should log whether it's a first push or an update
- [X] T094 [US5] Add error handling to `deploy/push_ontology_v2.py` — parse Fabric API error responses, report which specific part failed validation

**Checkpoint**: `getDefinition` (via LRO `/result` endpoint) returns non-empty payload with all 6 entity types (64-bit Int IDs, `valueType` properties), 5 relationships, 9 bindings, and 5 contextualizations. Entity store queries resolve entities from Lakehouse tables.

---

## Phase 8: User Story 6 — Start Telemetry Simulator (Priority: P2)

**Goal**: Python simulator generates realistic sensor readings, equipment status, and production metrics every 10 seconds, streaming into KQL tables.

**Independent Test**: Run simulator for 1 minute → `SensorTelemetry | where Timestamp > ago(1m) | count` returns 10+ rows per sensor.

### Implementation for User Story 6

- [X] T047 [P] [US6] Create `simulator/requirements.txt` with dependencies: `azure-kusto-data`, `azure-kusto-ingest`, `azure-identity`
- [X] T048 [US6] Create `simulator/telemetry_simulator.py` — main simulator script that generates values using Gaussian noise within [MinValue, MaxValue], ingests into KQL tables via streaming ingestion, runs on 10-second interval loop
- [X] T049 [US6] Add equipment status generation to `simulator/telemetry_simulator.py` — cycle between Operating/Idle/Maintenance with weighted probabilities
- [X] T050 [US6] Add production metrics generation to `simulator/telemetry_simulator.py` — OEE in 0.65–0.90 range, DefectRate 0.5–5%
- [X] T051 [US6] Add alert generation to `simulator/telemetry_simulator.py` — ~5% probability per interval, Severity distribution
- [X] T052 [US6] Create `deploy/Start-TelemetrySimulator.ps1` — install Python dependencies, launch simulator with KQL connection info from config.json
- [X] T053 [US6] Wire `Deploy-Ontology.ps1 -StepSimulator` to call `deploy/Start-TelemetrySimulator.ps1`

**Checkpoint**: Simulator running, KQL tables receiving data every 10s; Ctrl+C stops cleanly

---

## Phase 9: User Story 7 — Deploy Graph Model & Data Agent (Priority: P3)

**Goal**: Create Graph Model for hierarchy visualization and Data Agent for natural language queries over the ontology.

**Independent Test**: Graph model item exists in workspace; Data Agent responds to "How many sensors are on Robot Arm A1?"

### Implementation for User Story 7

- [X] T054 [P] [US7] Create `deploy/Deploy-GraphModel.ps1` — create GraphQL API item in workspace via Fabric REST API
- [X] T055 [P] [US7] Create `queries/graph-examples.kql` — sample graph/ontology queries
- [X] T056 [US7] Create `deploy/Deploy-DataAgent.ps1` — create Data Agent item in workspace via Fabric REST API
- [X] T057 [US7] Wire `Deploy-Ontology.ps1 -StepGraph` to call `deploy/Deploy-GraphModel.ps1`
- [X] T058 [US7] Wire `Deploy-Ontology.ps1 -StepAgent` to call `deploy/Deploy-DataAgent.ps1`

**Checkpoint**: Graph model shows hierarchy; Data Agent answers natural language queries about the plant

---

## Phase 10: Validation & End-to-End Tests

**Purpose**: Comprehensive validation across all deployed components — ontology definition, semantic model, KQL tables, and integration

**Result**: Full test suite `tests/full_test_suite.py` — **100/101 tests passing** ✅

**Test Categories**:
- Ontology structure validation (27 parts)
- KQL tables (4 tables)
- Star schema semantic model (10 tables, 15 relationships, 15 measures)
- Data Agent
- Supporting items

### Ontology Definition Validation (VT-ONT) — 27 parts

- [X] T095 [P] [VT-ONT-1] Create `tests/validate_ontology_definition.py` — call `POST /workspaces/{wsId}/ontologies/{ontologyId}/getDefinition` (LRO with `/result` suffix) and verify response contains exactly 6 entity type parts
- [X] T096 [P] [VT-ONT-2] Add property schema validation — Base64-decode each entity type payload and verify `properties` array uses `valueType` (not `dataType`) with values in {String, Boolean, DateTime, Object, BigInt, Double}
- [X] T097 [P] [VT-ONT-3] Add entity type ID validation — verify all entity type IDs are positive 64-bit integers (e.g., 296482030633)
- [X] T098 [P] [VT-ONT-4] Add relationship validation — verify 5 RelationshipType parts exist with correct source/target `entityTypeId` references
- [X] T099 [P] [VT-ONT-5] Add NTS binding validation — verify 6 NonTimeSeries DataBinding parts exist under correct `EntityTypes/{id}/DataBindings/` paths
- [X] T100 [P] [VT-ONT-6] Add TS binding validation — verify 3 TimeSeries DataBinding parts exist (Sensor, Equipment, ProductionLine)
- [X] T101 [P] [VT-ONT-7] Add contextualization validation — verify 5 Contextualization parts exist for each relationship

### Star Schema Semantic Model Validation (VT-SM) — 10 tables, 15 relationships, 15 measures

- [X] T102 [P] [VT-SM-1] Create `tests/validate_semantic_model.py` — call `GET /workspaces/{wsId}/items?type=SemanticModel` and verify an item named `SG-Manufacturing` exists
- [X] T103 [P] [VT-SM-2] Add DAX basic validation — execute `EVALUATE ROW("Plants", COUNTROWS(DIM_PLANT))` and verify non-zero result
- [X] T104 [P] [VT-SM-3] Add table completeness check — verify all 9 tables present (6 dims + 3 facts) via DAX queries for COUNTROWS on each table
- [X] T104a [P] [VT-SM-3a] Verify fact table row counts — FACT_PRODUCTION, FACT_WORK_ORDER, FACT_EQUIPMENT_OEE all return non-zero COUNTROWS
- [X] T105 [P] [VT-SM-4] Add relationship validation — verify 15 relationships: 12 active (fact-to-dim) + 3 inactive snowflake (DIM_LINE→DIM_PLANT, DIM_EQUIPMENT→DIM_LINE, DIM_SENSOR→DIM_EQUIPMENT)
- [X] T106 [P] [VT-SM-5] Add measures validation — verify all 15 DAX measures return valid results:
  - FACT_PRODUCTION (7): Total Produced, Total Defective, Yield %, Plan Achievement %, Total Scrap, Avg Cycle Time, Availability %
  - FACT_EQUIPMENT_OEE (4): Avg OEE %, Avg Availability %, Total Breakdown Min, Equipment Utilization %
  - FACT_WORK_ORDER (4): Order Count, Total Order Value, Completion %, Open Orders
- [X] T107 [P] [VT-SM-6] Add DirectLake mode check — verify `"mode": "directLake"` only in partition objects (not at table or model level), `compatibilityLevel` 1604, `defaultPowerBIDataSourceVersion` powerBI_V3
- [X] T107a [P] [VT-SM-7] Add star schema join validation — verify fact aggregation sliced by dimension attributes returns correct results (e.g., Total Produced by Plant, by Date)

### End-to-End Integration Validation

- [X] T059 [P] Create `kql/validation-queries.kql` — post-deployment KQL queries: table row counts, FK integrity checks, telemetry freshness, alert summary
- [X] T060 [P] Add comprehensive error handling to all deploy scripts — token expiry detection, HTTP error code interpretation, retry logic for 429/503
- [X] T061 Update quickstart.md if any CLI interface or steps changed during implementation
- [X] T108 Run full end-to-end validation: `.\Deploy-Ontology.ps1` (all steps) → verify config.json fully populated, 9 Delta tables loaded, 4 KQL tables created, ontology definition non-empty with 6 entity types + 5 relationships + 9 bindings + 5 contextualizations, semantic model responds to DAX queries with all 15 measures
- [X] T109 Verify idempotency: run `.\Deploy-Ontology.ps1` a second time → no errors, no duplicated resources, `updateDefinition` overwrites cleanly
- [X] T110 Create `tests/full_test_suite.py` — comprehensive test runner across all categories (ontology structure, KQL tables, star schema, data agent, supporting items)

---

## Phase 11: User Story 9 — Ingest Sample Telemetry Data (Priority: P2)

**Goal**: Populate KQL tables with 24h of realistic sample data so time-series queries work immediately without a live simulator.

**Independent Test**: Run `ingest_sample_telemetry.py` → query KQL tables → verify ~2400 rows with timestamps in last 24h and no embedded quotes in string values.

**Depends on**: US3 (KQL tables must exist)

### Implementation for User Story 9

- [X] T119 [US9] Create `deploy/ingest_sample_telemetry.py` — Python script that generates 24h of sample data (30min intervals) for all 20 sensors (SensorTelemetry), 18 equipment (EquipmentStatus), 12 lines (ProductionMetrics), and 30 alerts (Alerts)
- [X] T120 [US9] Fix inline ingest CSV format — remove single quotes from string values: `SG-EQ-001,datetime(...),150.5,Operating` NOT `'SG-EQ-001',datetime(...),...,'Operating'`
- [X] T121 [US9] Add realistic value distributions — Gaussian noise within sensor min/max ranges, weighted status probabilities (Operating/Idle/Maintenance), efficiency 0.70–0.95
- [X] T122 [US9] Create `deploy/check_timestamps.py` — verify KQL data freshness, timestamp ranges, and value distributions
- [X] T123 [US9] Create `deploy/explore_kql_data.py` — explore KQL data to identify realistic query thresholds for Data Agent testing

**Checkpoint**: ~960 SensorTelemetry + ~864 EquipmentStatus + ~576 ProductionMetrics + 30 Alerts. All string values clean (no embedded quotes). EquipmentId `SG-EQ-013` not `'SG-EQ-013'`.

**Critical Lesson Learned**: Kusto `.ingest inline` CSV rows must NOT use single quotes around string values — Kusto treats them as literal characters, embedding them in the data. This breaks ontology time-series binding matches where the ontology expects `SG-EQ-001` but KQL stores `'SG-EQ-001'`.

---

## Phase 12: User Story 8 — Data Agent with Ontology-Only Source (Priority: P1)

**Goal**: Configure the Data Agent to use the ontology as its single data source with comprehensive AI instructions for GQL entity traversal, time-series selectors, entity name resolution, and group-by aggregation.

**Independent Test**: Deploy via `deploy_data_agent.py` → inspect with `inspect_agent.py` → verify 1 datasource (ontology) → test queries in Fabric portal.

**Depends on**: US5 (ontology deployed) + US9 (KQL data for testing)

### Design Decisions

**Problem**: Initial approach used 3 data sources (ontology + semantic model + KQL). This required complex cross-source join instructions (6 workflows, entity resolution, ID mappings). Expert feedback confirmed this is unnecessarily complex.

**Solution**: Simplify to ontology as single source. The ontology's data bindings already abstract:
- Lakehouse (DIM_* tables) → static entity properties via NonTimeSeries bindings
- KQL (SensorTelemetry, EquipmentStatus, ProductionMetrics) → time-series properties via TimeSeries bindings

The Data Agent queries only the ontology. Time-series data is accessed via GQL time-series selectors (e.g., `e.OperatingStatus[last 1h]`).

### Implementation for User Story 8

- [X] T111 [US8] Update `deploy/deploy_data_agent.py` — remove semantic model and KQL datasources, keep only ontology
- [X] T112 [US8] Write comprehensive AI instructions covering: entity model (6 types), relationships (5 edges), GQL patterns (6 types), time-series selectors, entity name resolution
- [X] T113 [US8] Add entity element descriptions with time-series annotations (e.g., `"TIME-SERIES: Efficiency, UnitCount, CycleTime"` on ProductionLine)
- [X] T114 [US8] Add `dataSourceInstructions` and `userDescription` to ontology datasource
- [X] T115 [US8] Add "Support group by" at the bottom of AI instructions — enables GQL GROUP BY aggregation
- [X] T116 [US8] Add underlying resource explanation in instructions — tell the agent about Lakehouse and KQL without querying them directly
- [X] T117 [US8] Create `deploy/inspect_agent.py` — inspect deployed agent definition parts via `getDefinition` LRO API
- [X] T118 [US8] Create `deploy/list_items.py` — list all workspace items to verify no duplicate agents

**Checkpoint**: Data Agent has exactly 1 datasource (ontology). Instructions include 6 GQL patterns, time-series selectors, entity name resolution for 5 plants, "Support group by". Agent can answer "For each plant, show any equipment that ever had a downtime greater than 150 minutes" by traversing Plant→Line→Equipment and querying DownTimeMinutes time-series.

### Data Agent Definition Structure (updateDefinition API)

```json
{
  "definition": {
    "parts": [
      { "path": "Files/Config/data_agent.json", "payload": "<b64 agent config>" },
      { "path": "Files/Config/draft/stage_config.json", "payload": "<b64 AI instructions>" },
      { "path": "Files/Config/draft/ontology-{name}/datasource.json", "payload": "<b64 ontology source>" }
    ]
  }
}
```

### Data Agent Datasource Types (Fabric API)

| Type | API value | Folder prefix |
|------|-----------|---------------|
| Ontology | `ontology` | `ontology-` |
| KQL Database | `kusto` | `kusto-` |
| Semantic Model | `semantic_model` | `semantic-model-` |

Note: `updateDefinition` replaces the entire definition — omitting a datasource from parts automatically removes it. No stale sources accumulate.

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup ─────────────────────────────────────────────────────
Phase 2: Foundational ──────────────────────────────────────────────┤
                                                                    ▼
Phase 3: US1 - Infrastructure (P1) ─────────────────────────► config.json populated
                                                                    │
                    ┌───────────────────────────────────────────────┤
                    ▼                                               ▼
Phase 4: US2 - Master+Fact Data (P1)    Phase 5: US3 - KQL Tables (P1)
                    │                                               │
                    ├───────────────────┐                           │
                    ▼                   │                           │
Phase 6: US4 - Semantic Model (P1)      │                          │
                                        └──────────┬───────────────┘
                                                   ▼
                              Phase 7: US5 - Ontology Definition Push (P1)
                                                   │
                              ┌────────────────────┴───────────────────────┐
                              ▼                                            ▼
              Phase 8: US6 - Simulator (P2)         Phase 9: US7 - Graph & Agent (P3)
                              │                                            │
                              └────────────────────┬───────────────────────┘
                                                   ▼
                              Phase 10: US9 - Sample Telemetry Ingestion (P2)
                                                   │
                                                   ▼
                              Phase 11: US8 - Data Agent Ontology-Only (P1)
                                                   │
                                                   ▼
                              Phase 12: Validation & E2E Tests
```

### User Story Dependencies

- **US1 (Infrastructure)**: No dependencies — creates workspace, lakehouse, eventhouse, KQL database
- **US2 (Master+Fact Data)**: Depends on US1 (needs lakehouse ID from config.json)
- **US3 (KQL Tables)**: Depends on US1 (needs KQL database queryServiceUri from config.json)
- **US4 (Semantic Model)**: Depends on US2 (needs Lakehouse Delta tables for DirectLake)
- **US5 (Ontology Definition)**: Depends on US2 + US3 (needs lakehouse tables for NTS bindings + KQL tables for TS bindings)
- **US6 (Simulator)**: Depends on US3 (needs KQL tables to write into)
- **US7 (Graph & Agent)**: Depends on US5 (needs ontology deployed)
- **US8 (Data Agent Ontology-Only)**: Depends on US5 + US9 (needs ontology deployed + KQL data for testing)
- **US9 (Sample Telemetry)**: Depends on US3 (needs KQL tables to ingest into)

### Within Each User Story

- JSON definitions (entity types, relationships, bindings) → marked [P], can be created in parallel
- Deployment scripts depend on JSON definitions being created first
- Post-deploy validation is the last step in each story
- Orchestrator wiring depends on the deployment script existing

### Parallel Opportunities

**Phase 4 ∥ Phase 5**: Master data loading and KQL table creation can run in parallel after US1 completes
**Phase 6 (Semantic Model)**: Can start as soon as US2 completes (does not depend on US3)
**Phase 7 (Ontology)**: T073–T088 are ALL parallelizable (22 independent JSON files — 6 entity types + 5 relationships + 5 contextualizations + 6 existing bindings updated)
**Phase 8 ∥ Phase 9**: Simulator and Graph/Agent can run in parallel after their respective dependencies
**Phase 10**: All VT-ONT and VT-SM tests are parallelizable (independent API calls)

---

## Parallel Example: User Story 5 (Ontology Definition Push)

```
# All entity type restructures can run simultaneously:
T073: ontology/entity-types/plant.json        (id: 1001)
T074: ontology/entity-types/production-line.json (id: 1002)
T075: ontology/entity-types/equipment.json    (id: 1003)
T076: ontology/entity-types/sensor.json       (id: 1004)
T077: ontology/entity-types/product.json      (id: 1005)
T078: ontology/entity-types/workorder.json    (id: 1006)

# All relationship updates can run simultaneously:
T079–T083: ontology/relationships/*.json (5 files)

# All contextualizations can run simultaneously:
T084–T088: ontology/contextualizations/*.json (5 files)

# Then sequential: deployment script → validation → orchestrator wiring
T089 → T090 → T091 → T092 → T093 → T094
```

---

## Implementation Strategy

### MVP First (User Stories 1–5 = Core Ontology + Semantic Model)

1. Complete Phase 1: Setup (T001–T003) ✅
2. Complete Phase 2: Foundational (T004–T005) ✅
3. Complete Phase 3: US1 — Infrastructure (T006–T009) ✅
4. Complete Phase 4+5 in parallel: US2 Data + US3 KQL (T010–T019) ✅
5. Complete Phase 6: US4 — Star Schema Semantic Model (T064–T072) ✅
6. Complete Phase 7: US5 — Ontology Definition Push via `/ontologies/` API (T073–T094) ✅
7. Complete Phase 10: Validation (T095–T110) ✅ — 100/101 tests passing
8. **VALIDATED**: Full end-to-end deployment verified
9. Deploy/demo the core ontology + star schema

### Incremental Delivery

1. Setup + Foundational → Foundation ready ✅
2. Add US1 → Infrastructure deployed → config.json populated ✅
3. Add US2 + US3 → Master+fact data + KQL tables ready ✅
4. Add US4 → **Star schema semantic model deployed — dashboards available** ✅
5. Add US5 → **Ontology definition pushed via `/ontologies/` API — entity store resolves** ✅
6. Add Validation → **E2E verified — 100/101 tests passing — demo-ready!** ✅
7. Add US6 → Live telemetry flowing → richer demo ✅
8. Add US7 → Graph visualization + natural language queries → polished demo ✅
9. Add US9 → Sample KQL data (24h, clean values) → time-series queries work ✅
10. Add US8 → **Data Agent with ontology-only source — natural language queries over ontology + time-series** ✅
11. **ALL COMPLETE** — Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together ✅
2. Developer A: US1 (Infrastructure) — everyone waits for config.json ✅
3. Once US1 done:
   - Developer A: US2 (Master+Fact Data)
   - Developer B: US3 (KQL Tables)
4. Once US2 done: Developer A starts US4 (Semantic Model)
5. Once US2 + US3 done: Developer B starts US5 (Ontology Definition) T073–T088 JSON files
6. Developer A finishes US4 → starts VT-SM validation tests
7. Developer B finishes US5 deployment script → starts VT-ONT validation tests
8. Developer C (optional): US6 (Simulator) + US7 (Graph & Agent)

---

## Summary

| Metric | Value |
|--------|-------|
| **Total tasks** | ~135 (all completed ✅) |
| **Phase 1 (Setup)** | 3 tasks ✅ |
| **Phase 2 (Foundational)** | 2 tasks ✅ |
| **US1 (Infrastructure)** | 4 tasks ✅ |
| **US2 (Master+Fact Data)** | 9 tasks ✅ (expanded: +4 CSV creation for DIM_DATE + 3 facts) |
| **US3 (KQL Tables)** | 5 tasks ✅ |
| **US4 (Star Schema Semantic Model)** | 12 tasks ✅ (expanded: +3 star schema fixes) |
| **US5 (Ontology Definition Push)** | 25 tasks ✅ (expanded: +3 API endpoint/LRO/ID fixes) |
| **US6 (Simulator)** | 7 tasks ✅ |
| **US7 (Graph & Agent)** | 5 tasks ✅ |
| **US8 (Data Agent Ontology-Only)** | 8 tasks ✅ (ontology-only source, comprehensive instructions) |
| **US9 (Sample Telemetry Ingestion)** | 5 tasks ✅ (clean data, no embedded quotes) |
| **Validation (VT-ONT + VT-SM + E2E)** | 21 tasks ✅ |
| **Parallelizable tasks** | 48+ (40%+) |
| **Test results** | **All passing** — Ontology structure, KQL, Star schema, Data Agent |
| **Key artifacts** | `semantic-model/model.bim`, `deploy/push_ontology_v2.py`, `deploy/deploy_semantic_model.py`, `deploy/deploy_data_agent.py`, `deploy/ingest_sample_telemetry.py`, `deploy/inspect_agent.py` |
| **Modified artifacts** | All 6 `ontology/entity-types/*.json`, all 5 `ontology/relationships/*.json`, `deploy/Deploy-OntologyModel.ps1`, `Deploy-Ontology.ps1`, `config.json` |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- All scripts must use `az account get-access-token` for auth (no stored credentials — NFR-3)
- All scripts must be idempotent via find-or-create / updateDefinition overwrite patterns (NFR-2)
- Resource IDs always read from / written to `config.json` (NFR-4)
- Python scripts preferred over PowerShell for REST API calls (avoids WMI timeout issues with `az cli`)
- Entity type IDs are positive 64-bit integers (e.g., 296482030633)
- All definition parts must be Base64-encoded for `updateDefinition` API
- KQL `.ingest inline` CSV values must NOT use single quotes — Kusto embeds them as literal chars
- Data Agent `updateDefinition` replaces the entire definition — omitting sources removes them automatically
- Data Agent datasource types: `ontology`, `kusto` (not `kql_database`), `semantic_model`
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Constitution principles (ontology-driven, script-first, validate-before-deploy) apply to every task
- Old US4 (initial ontology model creation with original JSON schema) tasks T020–T046 are DONE — they created the original files. US5 (T073–T094) restructures them for the Fabric Item Definition API and uses corrected `/ontologies/` endpoints with LRO `/result` polling.
