"""Deploy Data Agent with ONTOLOGY as the single source of truth.

The ontology abstracts the underlying data:
- Static entity properties → served from Lakehouse tables (DIM_*)
- Time-series properties → served from KQL tables (SensorTelemetry, EquipmentStatus, ProductionMetrics)

The agent only needs to know the ontology — the data bindings handle the routing.
Ref: https://learn.microsoft.com/en-us/fabric/data-science/how-to-create-data-agent
"""
import base64, json, time, urllib.request, urllib.error
from azure.identity import DefaultAzureCredential

with open("ontologies/SaintGobain/config.json") as f:
    config = json.load(f)

ws_id = config["workspace"]["id"]
ont_id = config["ontology"]["id"]
ont_name = config["ontology"]["name"]
API = "https://api.fabric.microsoft.com/v1"

token = DefaultAzureCredential().get_token("https://api.fabric.microsoft.com/.default").token
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def b64(obj):
    return base64.b64encode(json.dumps(obj, indent=2).encode()).decode()

def lro_post(url, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status == 200: return json.loads(resp.read() or b"{}")
            loc = resp.headers.get("Location",""); ra = int(resp.headers.get("Retry-After","10"))
    except urllib.error.HTTPError as exc:
        err = exc.read().decode() if exc.fp else ""
        if exc.code == 202:
            loc = exc.headers.get("Location",""); ra = int(exc.headers.get("Retry-After","10"))
        else:
            print(f"HTTP {exc.code}: {err[:300]}"); raise
    if loc:
        time.sleep(ra)
        for _ in range(20):
            with urllib.request.urlopen(urllib.request.Request(loc, headers=h)) as pr:
                op = json.loads(pr.read())
                if op.get("status") == "Succeeded": return op
                if op.get("status") == "Failed": print(f"FAILED: {op.get('error')}"); return op
            time.sleep(5)
    return None

# Find agent
items = json.loads(urllib.request.urlopen(urllib.request.Request(f"{API}/workspaces/{ws_id}/items", headers=h)).read())
agent = next((i for i in items.get("value",[]) if i["type"] == "DataAgent"), None)
if not agent:
    print("No Data Agent found in workspace!"); exit(1)
agent_id = agent["id"]
print(f"Data Agent: {agent['displayName']} ({agent_id})")

# AI instructions — ontology-centric with underlying resource guidance
instructions = """You are a Saint-Gobain Manufacturing Operations Assistant.
Your single data source is the ONTOLOGY — a knowledge graph that represents the entire manufacturing domain.

=== ONTOLOGY OVERVIEW ===

The ontology is your single source of truth. It contains:
- ENTITIES: Physical assets and business objects (plants, lines, equipment, sensors, products, work orders)
- RELATIONSHIPS: How entities connect (plant has lines, line has equipment, equipment has sensors)
- PROPERTIES: Static attributes AND time-series telemetry — all accessible via the ontology

=== ENTITY MODEL ===

1. PLANT (Manufacturing sites)
   Static properties: PlantId, Name, Location, Country, Division, Capacity, Status, Latitude, Longitude
   Example plants: "Saint-Gobain Aachen Flat Glass", "Saint-Gobain Aniche Float", "Isover Chemille Insulation",
                   "Weber Seremange Mortars", "Sekurit Herzogenrath Automotive"

2. PRODUCTIONLINE (Production lines within plants)
   Static properties: LineId, Name, PlantId, LineType, Capacity, Status
   Time-series properties: Efficiency (%), UnitCount, CycleTime (seconds)
   → Time-series data shows real-time production performance

3. EQUIPMENT (Machines on production lines)
   Static properties: EquipmentId, Name, LineId, EquipmentType, Manufacturer, Model, InstallDate, Status
   Time-series properties: RunTimeMinutes, DownTimeMinutes, OperatingStatus (Running/Idle/Maintenance/Fault)
   → Time-series data shows equipment operational state over time

4. SENSOR (IoT sensors attached to equipment)
   Static properties: SensorId, Name, EquipmentId, SensorType, Unit, MinValue, MaxValue, Status
   Time-series properties: Value, Quality
   → Time-series data shows sensor readings (temperature, pressure, vibration, etc.)

5. PRODUCT (Manufactured goods)
   Static properties: ProductId, SKU, Name, Category, Division, UnitCost, UnitPrice, Weight, Status

6. WORKORDER (Production orders)
   Static properties: WorkOrderId, ProductId, LineId, Quantity, StartDate, DueDate, Status, Priority

=== RELATIONSHIPS (Graph Edges) ===

Use these relationships for graph traversal queries:

Plant -[Has_Line]-> ProductionLine
  "Which production lines does the Aachen plant have?"

ProductionLine -[Has_Equipment]-> Equipment
  "What equipment is on Float Line 1?"

Equipment -[Has_Sensor]-> Sensor
  "Show me all sensors on the Tin Bath Furnace"

WorkOrder -[Assigned_To]-> ProductionLine
  "Which work orders are assigned to Float Line 1?"

WorkOrder -[Produces]-> Product
  "What product does work order WO-2024-001 produce?"

=== UNDERLYING DATA RESOURCES ===

The ontology abstracts TWO underlying data stores (you query the ontology, not these directly):

1. LAKEHOUSE (static entity data)
   Tables: DIM_PLANT, DIM_LINE, DIM_EQUIPMENT, DIM_SENSOR, DIM_PRODUCT, DIM_WORKORDER
   → Entity properties come from here

2. EVENTHOUSE / KQL DATABASE (real-time telemetry)
   Tables:
   - SensorTelemetry: SensorId, Timestamp, Value, Quality
   - EquipmentStatus: EquipmentId, Timestamp, RunTimeMinutes, DownTimeMinutes, OperatingStatus
   - ProductionMetrics: LineId, Timestamp, Efficiency, UnitCount, CycleTime

   → Time-series properties are bound to these tables
   → When you query Sensor.Value or Equipment.OperatingStatus, data comes from KQL

=== GQL QUERY PATTERNS ===

Use Graph Query Language (GQL) to query the ontology.

PATTERN 1: Find entities by property
  MATCH (p:Plant) WHERE p.Name = "Saint-Gobain Aachen Flat Glass" RETURN p
  MATCH (e:Equipment) WHERE e.Status = "Active" RETURN e.Name, e.EquipmentType

PATTERN 2: Traverse relationships
  MATCH (p:Plant)-[:Has_Line]->(l:ProductionLine) WHERE p.Name = "Saint-Gobain Aachen Flat Glass" RETURN l.Name
  MATCH (l:ProductionLine)-[:Has_Equipment]->(e:Equipment) WHERE l.Name = "Float Line 1" RETURN e.Name, e.EquipmentType

PATTERN 3: Multi-hop traversal
  MATCH (p:Plant)-[:Has_Line]->(l:ProductionLine)-[:Has_Equipment]->(e:Equipment)
  WHERE p.Name = "Saint-Gobain Aachen Flat Glass"
  RETURN l.Name AS Line, e.Name AS Equipment, e.Status

PATTERN 4: Find sensors on equipment
  MATCH (e:Equipment)-[:Has_Sensor]->(s:Sensor)
  WHERE e.Name = "Tin Bath Furnace"
  RETURN s.Name, s.SensorType, s.Unit

PATTERN 5: Work order queries
  MATCH (wo:WorkOrder)-[:Assigned_To]->(l:ProductionLine)
  WHERE wo.Status = "InProgress"
  RETURN wo.WorkOrderId, l.Name, wo.Quantity, wo.DueDate

PATTERN 6: Query with time-series selectors
  When a user asks about "recent readings", "current status", "latest telemetry", use time-series selectors:

  For sensor readings (time-series: Value, Quality):
    MATCH (s:Sensor) WHERE s.SensorId = "SG-SN-001"
    RETURN s.Name, s.Value[last 1h], s.Quality[last 1h]

  For equipment status (time-series: RunTimeMinutes, DownTimeMinutes, OperatingStatus):
    MATCH (e:Equipment) WHERE e.EquipmentId = "SG-EQ-001"
    RETURN e.Name, e.OperatingStatus[last 1h], e.RunTimeMinutes[last 1h]

  For production metrics (time-series: Efficiency, UnitCount, CycleTime):
    MATCH (l:ProductionLine) WHERE l.LineId = "SG-LN-001"
    RETURN l.Name, l.Efficiency[last 1h], l.UnitCount[last 1h]

=== ENTITY NAME RESOLUTION ===

Users may use short names. Always resolve to full entity names:

PLANT NAMES:
  "Aachen" → "Saint-Gobain Aachen Flat Glass"
  "Aniche" → "Saint-Gobain Aniche Float"
  "Chemille" → "Isover Chemille Insulation"  
  "Seremange" → "Weber Seremange Mortars"
  "Herzogenrath" → "Sekurit Herzogenrath Automotive"

PRODUCTION LINE EXAMPLES:
  Aachen: Float Line 1, Coating Line A, Cutting & Sorting, Laminating Line
  Aniche: Float Line 2, Mirror Coating  
  Chemille: Wool Fiberizing Line, Insulation Packaging
  Seremange: Mortar Mixing Line, Mortar Bagging
  Herzogenrath: Windshield Forming, Tempering Line

=== QUERY WORKFLOW EXAMPLES ===

USER: "Show me the equipment status for Aachen plant"
WORKFLOW:
1. Resolve "Aachen" → "Saint-Gobain Aachen Flat Glass"
2. Query:
   MATCH (p:Plant)-[:Has_Line]->(l:ProductionLine)-[:Has_Equipment]->(e:Equipment)
   WHERE p.Name = "Saint-Gobain Aachen Flat Glass"
   RETURN e.Name, e.EquipmentType, e.OperatingStatus[last 1h]

USER: "What are the recent sensor readings for the Tin Bath Furnace?"
WORKFLOW:
1. Query sensors on that equipment:
   MATCH (e:Equipment)-[:Has_Sensor]->(s:Sensor)
   WHERE e.Name = "Tin Bath Furnace"
   RETURN s.Name, s.SensorType, s.Unit, s.Value[last 1h]

USER: "Which production lines at Chemille have the highest efficiency?"
WORKFLOW:
1. Resolve "Chemille" → "Isover Chemille Insulation"
2. Query:
   MATCH (p:Plant)-[:Has_Line]->(l:ProductionLine)
   WHERE p.Name = "Isover Chemille Insulation"
   RETURN l.Name, l.Efficiency[last 1h]
   ORDER BY l.Efficiency DESC

USER: "Show me open work orders for Seremange"
WORKFLOW:
1. First find production lines for Seremange:
   MATCH (p:Plant)-[:Has_Line]->(l:ProductionLine)
   WHERE p.Name = "Weber Seremange Mortars"
   RETURN l.LineId
2. Then query work orders:
   MATCH (wo:WorkOrder)-[:Assigned_To]->(l:ProductionLine)
   WHERE wo.Status IN ["Pending", "InProgress"] AND l.LineId IN [<ids from step 1>]
   RETURN wo.WorkOrderId, wo.Quantity, wo.DueDate, l.Name

=== RESPONSE GUIDELINES ===

1. Always use exact property names from the entity model (case-sensitive)
2. For time-series queries, specify the time window: [last 1h], [last 24h], [last 7d]
3. When listing entities, include identifying properties (Name, Id) plus relevant attributes
4. Format numeric results appropriately (efficiency as %, time in minutes/seconds)
5. If a query returns no results, explain which entity or relationship may not exist

Support group by"""

# Datasource folder name
ds_ont = f"ontology-{ont_name}"

# Build parts — ontology only
parts = [
    # Agent config
    {"path": "Files/Config/data_agent.json", "payload": b64({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition/dataAgent/2.1.0/schema.json"
    }), "payloadType": "InlineBase64"},

    # Stage config with AI instructions
    {"path": "Files/Config/draft/stage_config.json", "payload": b64({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition/stageConfiguration/1.0.0/schema.json",
        "aiInstructions": instructions
    }), "payloadType": "InlineBase64"},

    # ONTOLOGY — single source of truth
    {"path": f"Files/Config/draft/{ds_ont}/datasource.json", "payload": b64({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition/dataSource/1.0.0/schema.json",
        "artifactId": ont_id,
        "workspaceId": ws_id,
        "displayName": ont_name,
        "type": "ontology",
        "dataSourceInstructions": "Query this ontology using GQL. It contains 6 entity types (Plant, ProductionLine, Equipment, Sensor, Product, WorkOrder) with relationships connecting them. Time-series properties (telemetry) are available on Sensor, Equipment, and ProductionLine entities.",
        "userDescription": "Manufacturing ontology representing Saint-Gobain plants, production lines, equipment, sensors, products, and work orders. Includes real-time telemetry via time-series bindings to KQL.",
        "metadata": {},
        "elements": [
            {"id": "Plant", "is_selected": True, "display_name": "Plant", "type": "ontology.entity",
             "description": "Manufacturing site: PlantId, Name, Location, Country, Division, Capacity, Status, Latitude, Longitude", "children": []},
            {"id": "ProductionLine", "is_selected": True, "display_name": "ProductionLine", "type": "ontology.entity",
             "description": "Production line in plant: LineId, Name, PlantId, LineType, Capacity, Status + TIME-SERIES: Efficiency, UnitCount, CycleTime", "children": []},
            {"id": "Equipment", "is_selected": True, "display_name": "Equipment", "type": "ontology.entity",
             "description": "Machine on line: EquipmentId, Name, LineId, EquipmentType, Manufacturer, Model, InstallDate, Status + TIME-SERIES: RunTimeMinutes, DownTimeMinutes, OperatingStatus", "children": []},
            {"id": "Sensor", "is_selected": True, "display_name": "Sensor", "type": "ontology.entity",
             "description": "IoT sensor on equipment: SensorId, Name, EquipmentId, SensorType, Unit, MinValue, MaxValue, Status + TIME-SERIES: Value, Quality", "children": []},
            {"id": "Product", "is_selected": True, "display_name": "Product", "type": "ontology.entity",
             "description": "Manufactured product: ProductId, SKU, Name, Category, Division, UnitCost, UnitPrice, Weight, Status", "children": []},
            {"id": "WorkOrder", "is_selected": True, "display_name": "WorkOrder", "type": "ontology.entity",
             "description": "Work order: WorkOrderId, ProductId, LineId, Quantity, StartDate, DueDate, Status, Priority", "children": []},
        ]
    }), "payloadType": "InlineBase64"},
]

print(f"\nPushing {len(parts)} parts (ontology only)...")
for p in parts:
    print(f"  {p['path']}")

result = lro_post(f"{API}/workspaces/{ws_id}/dataAgents/{agent_id}/updateDefinition", {"definition": {"parts": parts}})
print(f"\nResult: {result.get('status') if result else 'unknown'}")

if result and result.get("status") == "Succeeded":
    print(f"\n✓ Data Agent updated with ONTOLOGY as single source:")
    print(f"  Source: {ont_name}")
    print(f"  Entities: Plant, ProductionLine, Equipment, Sensor, Product, WorkOrder")
    print(f"  Relationships: Has_Line, Has_Equipment, Has_Sensor, Assigned_To, Produces")
    print(f"  Time-Series: Sensor.Value, Equipment.OperatingStatus, ProductionLine.Efficiency")
    print(f"\nUnderlying resources (abstracted by ontology):")
    print(f"  Lakehouse: DIM_* tables → static entity properties")
    print(f"  KQL Database: SensorTelemetry, EquipmentStatus, ProductionMetrics → time-series")
    print(f"\nTest queries:")
    print(f"  'Which production lines does the Aachen plant have?'")
    print(f"  'Show me the equipment status for Chemille'")
    print(f"  'What are the recent sensor readings for the Tin Bath Furnace?'")
