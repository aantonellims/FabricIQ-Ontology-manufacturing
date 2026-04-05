# Ontology API Contracts

**Date**: 2026-04-01 | **Plan**: [../plan.md](../plan.md)

## Fabric REST API Endpoints Used

### Infrastructure

| Operation | Method | Endpoint | Auth Resource |
|-----------|--------|----------|---------------|
| List capacities | GET | `{apiBase}/capacities` | `https://api.fabric.microsoft.com` |
| List workspaces | GET | `{apiBase}/workspaces` | `https://api.fabric.microsoft.com` |
| Create workspace | POST | `{apiBase}/workspaces` | `https://api.fabric.microsoft.com` |
| Create item | POST | `{apiBase}/workspaces/{wsId}/items` | `https://api.fabric.microsoft.com` |
| List items | GET | `{apiBase}/workspaces/{wsId}/items` | `https://api.fabric.microsoft.com` |
| Get KQL Database | GET | `{apiBase}/workspaces/{wsId}/kqlDatabases/{dbId}` | `https://api.fabric.microsoft.com` |

### Data Loading

| Operation | Method | Endpoint | Auth Resource |
|-----------|--------|----------|---------------|
| Create file | PUT | `https://onelake.dfs.fabric.microsoft.com/{wsName}/{lhName}.Lakehouse/Files/{file}?resource=file` | `https://storage.azure.com` |
| Append data | PATCH | `https://onelake.dfs.fabric.microsoft.com/{wsName}/{lhName}.Lakehouse/Files/{file}?action=append&position=0` | `https://storage.azure.com` |
| Flush file | PATCH | `https://onelake.dfs.fabric.microsoft.com/{wsName}/{lhName}.Lakehouse/Files/{file}?action=flush&position={len}` | `https://storage.azure.com` |
| Load table | POST | `{apiBase}/workspaces/{wsId}/lakehouses/{lhId}/tables/{tableName}/load` | `https://api.fabric.microsoft.com` |

### KQL Management

| Operation | Method | Endpoint | Auth Resource |
|-----------|--------|----------|---------------|
| Execute mgmt command | POST | `https://{queryServiceUri}/v1/rest/mgmt` | `https://kusto.kusto.windows.net` |
| Execute query | POST | `https://{queryServiceUri}/v1/rest/query` | `https://kusto.kusto.windows.net` |

---

## Entity Type JSON Schema

Each entity type is defined with the following structure:

```json
{
  "name": "Plant",
  "displayNameProperty": "Name",
  "primaryKey": "PlantId",
  "properties": [
    { "name": "PlantId", "type": "String" },
    { "name": "Name", "type": "String" },
    { "name": "Location", "type": "String" },
    { "name": "Country", "type": "String" },
    { "name": "Division", "type": "String" },
    { "name": "Capacity", "type": "Int32" },
    { "name": "Status", "type": "String" },
    { "name": "Latitude", "type": "Double" },
    { "name": "Longitude", "type": "Double" }
  ],
  "foreignKeys": []
}
```

### Supported Property Types

| Ontology Type | Source CSV Type | Description |
|---------------|---------------|-------------|
| String | text | Any text value |
| Int32 | integer | 32-bit integer (Capacity, Quantity) |
| Double | decimal | Floating point (Latitude, UnitCost, MinValue) |
| DateTime | date string | ISO 8601 date (InstallDate, StartDate) |
| Boolean | true/false | Flag values |

---

## Relationship JSON Schema

```json
{
  "name": "Has_Line",
  "fromEntityType": "Plant",
  "toEntityType": "ProductionLine",
  "fromProperty": "PlantId",
  "toProperty": "PlantId",
  "cardinality": "OneToMany"
}
```

---

## NonTimeSeries Data Binding Schema

```json
{
  "entityTypeName": "Plant",
  "bindingType": "NonTimeSeries",
  "dataSource": {
    "type": "Lakehouse",
    "itemId": "{lakehouseId}",
    "tableName": "DIM_PLANT"
  },
  "propertyMappings": [
    { "entityProperty": "PlantId", "sourceColumn": "PlantId" },
    { "entityProperty": "Name", "sourceColumn": "Name" }
  ]
}
```

---

## TimeSeries Data Binding Schema

```json
{
  "entityTypeName": "Sensor",
  "bindingType": "TimeSeries",
  "dataSource": {
    "type": "KQLDatabase",
    "itemId": "{kqlDatabaseId}",
    "tableName": "SensorTelemetry"
  },
  "keyMapping": {
    "entityProperty": "SensorId",
    "sourceColumn": "SensorId"
  },
  "timestampColumn": "Timestamp",
  "metricMappings": [
    { "name": "Value", "sourceColumn": "Value", "type": "Double" },
    { "name": "Unit", "sourceColumn": "Unit", "type": "String" },
    { "name": "Quality", "sourceColumn": "Quality", "type": "String" }
  ]
}
```

---

## Table Load API Request Schema

```json
{
  "relativePath": "Files/{filename}.csv",
  "pathType": "File",
  "mode": "Overwrite",
  "formatOptions": {
    "format": "Csv",
    "header": true,
    "delimiter": ","
  }
}
```

---

## KQL Management Request Schema

```json
{
  "csl": ".create-merge table SensorTelemetry (SensorId: string, Timestamp: datetime, Value: real, Unit: string, Quality: string)",
  "db": "SG_ManufacturingEventhouse"
}
```

---

## config.json Schema

```json
{
  "workspace": { "id": "guid", "name": "string" },
  "capacity": { "name": "string" },
  "lakehouse": { "id": "guid", "name": "string" },
  "eventhouse": { "id": "guid", "name": "string" },
  "kqlDatabase": { "id": "guid", "name": "string", "queryServiceUri": "string" },
  "ontology": { "id": "guid", "name": "string" },
  "apiBase": "https://api.fabric.microsoft.com/v1"
}
```
