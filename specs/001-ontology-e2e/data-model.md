# Data Model: Saint-Gobain Manufacturing Ontology

**Date**: 2026-04-01 | **Plan**: [plan.md](plan.md)

## Entity Types

### 1. Plant (DIM_PLANT)

| Property | Type | Key | Description |
|----------|------|-----|-------------|
| PlantId | string | PK | Unique plant identifier (e.g., `SG-PLT-001`) |
| Name | string | Display | Plant name (e.g., "Saint-Gobain Aachen Flat Glass") |
| Location | string | | City name |
| Country | string | | Country code |
| Division | string | | Business division (Flat Glass, Insulation, Construction Products, Automotive Glass) |
| Capacity | int | | Daily capacity in units |
| Status | string | | Active / Inactive |
| Latitude | double | | GPS latitude |
| Longitude | double | | GPS longitude |

**Source**: `data/plants.csv` → Lakehouse `DIM_PLANT` | **Row Count**: 5

---

### 2. ProductionLine (DIM_LINE)

| Property | Type | Key | Description |
|----------|------|-----|-------------|
| LineId | string | PK | Unique line identifier (e.g., `SG-LN-001`) |
| Name | string | Display | Line name (e.g., "Float Line 1") |
| PlantId | string | FK→Plant | Parent plant reference |
| LineType | string | | Float, Coating, Cutting, Laminating, Fiberizing, Packaging, Mixing, Bagging, Forming, Tempering |
| Capacity | int | | Line capacity in units/day |
| Status | string | | Active / Inactive |

**Source**: `data/lines.csv` → Lakehouse `DIM_LINE` | **Row Count**: 12

---

### 3. Equipment (DIM_EQUIPMENT)

| Property | Type | Key | Description |
|----------|------|-----|-------------|
| EquipmentId | string | PK | Unique equipment identifier (e.g., `SG-EQ-001`) |
| Name | string | Display | Equipment name (e.g., "Float Bath") |
| LineId | string | FK→Line | Parent production line reference |
| EquipmentType | string | | FloatBath, Lehr, Heater, Coater, Reactor, CuttingTable, Robot, etc. |
| Manufacturer | string | | e.g., Pilkington, Siemens, FANUC |
| Model | string | | Model number |
| InstallDate | string | | Installation date (YYYY-MM-DD) |
| Status | string | | Operating / Maintenance / Offline |

**Source**: `data/equipment.csv` → Lakehouse `DIM_EQUIPMENT` | **Row Count**: 18+

---

### 4. Sensor (DIM_SENSOR)

| Property | Type | Key | Description |
|----------|------|-----|-------------|
| SensorId | string | PK | Unique sensor identifier (e.g., `SG-SN-001`) |
| Name | string | Display | Sensor name (e.g., "Bath Temperature Top") |
| EquipmentId | string | FK→Equipment | Parent equipment reference |
| SensorType | string | | Temperature, Level, Speed, Thickness, Power, Pressure, Position, Torque |
| Unit | string | | Measurement unit (Celsius, mm, m/min, kW, mbar, nm, RPM, Nm, Bar) |
| MinValue | double | | Expected minimum value |
| MaxValue | double | | Expected maximum value |
| Status | string | | Active / Inactive |

**Source**: `data/sensors.csv` → Lakehouse `DIM_SENSOR` | **Row Count**: 20

---

### 5. Product (DIM_PRODUCT)

| Property | Type | Key | Description |
|----------|------|-----|-------------|
| ProductId | string | PK | Unique product identifier (e.g., `SG-PRD-001`) |
| SKU | string | | Product SKU code |
| Name | string | Display | Product name (e.g., "PLANILUX Clear Float 4mm") |
| Category | string | | Product category |
| Division | string | | Business division |
| UnitCost | double | | Cost per unit |
| UnitPrice | double | | Sell price per unit |
| Weight | double | | Weight in kg |
| Status | string | | Active / Discontinued |

**Source**: `data/products.csv` → Lakehouse `DIM_PRODUCT` | **Row Count**: 10

---

### 6. WorkOrder (DIM_WORKORDER)

| Property | Type | Key | Description |
|----------|------|-----|-------------|
| WorkOrderId | string | PK | Unique work order identifier (e.g., `SG-WO-001`) |
| ProductId | string | FK→Product | Product being produced |
| LineId | string | FK→Line | Production line assigned |
| Quantity | int | | Order quantity |
| StartDate | string | | Planned start date |
| DueDate | string | | Due date |
| Status | string | | Scheduled / InProgress / Complete |
| Priority | string | | High / Medium / Low |

**Source**: `data/workorders.csv` → Lakehouse `DIM_WORKORDER` | **Row Count**: 8

---

## Relationships

| # | Name | From Entity | To Entity | Cardinality | Description |
|---|------|-------------|-----------|-------------|-------------|
| 1 | Has_Line | Plant | ProductionLine | One-to-Many | Plant.PlantId → Line.PlantId |
| 2 | Has_Equipment | ProductionLine | Equipment | One-to-Many | Line.LineId → Equipment.LineId |
| 3 | Has_Sensor | Equipment | Sensor | One-to-Many | Equipment.EquipmentId → Sensor.EquipmentId |
| 4 | Assigned_To | WorkOrder | ProductionLine | Many-to-One | WorkOrder.LineId → Line.LineId |
| 5 | Produces | WorkOrder | Product | Many-to-One | WorkOrder.ProductId → Product.ProductId |

### Relationship Graph

```
Plant ──[Has_Line (1:N)]──> ProductionLine ──[Has_Equipment (1:N)]──> Equipment ──[Has_Sensor (1:N)]──> Sensor
                            ProductionLine <──[Assigned_To (N:1)]── WorkOrder ──[Produces (N:1)]──> Product
```

---

## Data Bindings

### NonTimeSeries Bindings (Lakehouse → Entity)

Each entity type gets a NonTimeSeries binding that maps its ontology properties to Lakehouse Delta table columns. The binding references the Lakehouse item ID and the Delta table name.

| Entity Type | Lakehouse Table | Primary Key Column | Display Name Column |
|-------------|-----------------|-------------------|-------------------|
| Plant | DIM_PLANT | PlantId | Name |
| ProductionLine | DIM_LINE | LineId | Name |
| Equipment | DIM_EQUIPMENT | EquipmentId | Name |
| Sensor | DIM_SENSOR | SensorId | Name |
| Product | DIM_PRODUCT | ProductId | Name |
| WorkOrder | DIM_WORKORDER | WorkOrderId | WorkOrderId |

### TimeSeries Bindings (KQL → Entity)

TimeSeries bindings connect entity types to their KQL telemetry tables, enabling time-range queries on entities.

| Entity Type | KQL Table | Key Column | Timestamp Column | Metric Columns |
|-------------|-----------|------------|------------------|---------------|
| Sensor | SensorTelemetry | SensorId | Timestamp | Value, Unit, Quality |
| Equipment | EquipmentStatus | EquipmentId | Timestamp | Status, RunHours, CycleCount |
| ProductionLine | ProductionMetrics | LineId | Timestamp | OutputUnits, DefectRate, OEE |

---

## KQL Telemetry Tables

### SensorTelemetry

```kql
.create-merge table SensorTelemetry (
    SensorId: string,
    Timestamp: datetime,
    Value: real,
    Unit: string,
    Quality: string
)
```

### EquipmentStatus

```kql
.create-merge table EquipmentStatus (
    EquipmentId: string,
    Timestamp: datetime,
    Status: string,
    RunHours: real,
    CycleCount: long
)
```

### ProductionMetrics

```kql
.create-merge table ProductionMetrics (
    LineId: string,
    Timestamp: datetime,
    OutputUnits: long,
    DefectRate: real,
    OEE: real
)
```

### Alerts

```kql
.create-merge table Alerts (
    AlertId: string,
    EntityId: string,
    EntityType: string,
    Timestamp: datetime,
    Severity: string,
    Message: string,
    IsResolved: bool
)
```

---

## Validation Rules

### Foreign Key Integrity

| Child Table | FK Column | Parent Table | PK Column |
|-------------|-----------|-------------|-----------|
| DIM_LINE | PlantId | DIM_PLANT | PlantId |
| DIM_EQUIPMENT | LineId | DIM_LINE | LineId |
| DIM_SENSOR | EquipmentId | DIM_EQUIPMENT | EquipmentId |
| DIM_WORKORDER | ProductId | DIM_PRODUCT | ProductId |
| DIM_WORKORDER | LineId | DIM_LINE | LineId |

### Data Quality Rules

- All ID fields must match pattern `SG-{TYPE}-{NNN}`
- Status values are constrained to defined enums per entity
- Sensor MinValue < MaxValue
- WorkOrder StartDate ≤ DueDate
- All FK references must resolve (no orphan records)
