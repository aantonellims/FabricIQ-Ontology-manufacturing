"""End-to-end validation of the Saint-Gobain Manufacturing Ontology deployment."""
import base64
import json
import time
import urllib.request
import urllib.error
from azure.identity import DefaultAzureCredential

API = "https://api.fabric.microsoft.com/v1"
PBI_API = "https://api.powerbi.com/v1.0/myorg"

with open("ontologies/SaintGobain/config.json") as f:
    config = json.load(f)

ws_id = config["workspace"]["id"]
lh_id = config["lakehouse"]["id"]
kql_id = config["kqlDatabase"]["id"]
ont_id = config["ontology"]["id"]
sm_id = config["semanticModel"]["id"]
query_uri = config["kqlDatabase"]["queryServiceUri"]
db_name = config["kqlDatabase"]["name"]

cred = DefaultAzureCredential()
token = cred.get_token("https://api.fabric.microsoft.com/.default").token
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

passed = 0
failed = 0
total = 0

def check(name, condition, detail=""):
    global passed, failed, total
    total += 1
    if condition:
        passed += 1
        print(f"  PASS  {name}" + (f" ({detail})" if detail else ""))
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f" ({detail})" if detail else ""))


print("=" * 60)
print("  SAINT-GOBAIN MANUFACTURING ONTOLOGY - E2E VALIDATION")
print("=" * 60)

# ── 1. WORKSPACE ITEMS ──
print("\n--- 1. Workspace Items ---")
items_resp = urllib.request.urlopen(
    urllib.request.Request(f"{API}/workspaces/{ws_id}/items", headers=headers)
)
items = json.loads(items_resp.read()).get("value", [])
item_types = {i["type"]: i for i in items}

check("Lakehouse exists", "Lakehouse" in item_types)
check("Eventhouse exists", "Eventhouse" in item_types)
check("KQLDatabase exists", "KQLDatabase" in item_types)
check("Ontology exists", "Ontology" in item_types)
check("SemanticModel exists", "SemanticModel" in item_types)
check("DataAgent exists", "DataAgent" in item_types)
check("GraphQLApi exists", "GraphQLApi" in item_types)
print(f"  Total items in workspace: {len(items)}")

# ── 2. LAKEHOUSE TABLES ──
print("\n--- 2. Lakehouse Delta Tables ---")
tables_resp = urllib.request.urlopen(
    urllib.request.Request(f"{API}/workspaces/{ws_id}/lakehouses/{lh_id}/tables", headers=headers)
)
tables = json.loads(tables_resp.read()).get("data", [])
table_names = [t["name"] for t in tables]
expected_tables = ["DIM_PLANT", "DIM_LINE", "DIM_EQUIPMENT", "DIM_SENSOR", "DIM_PRODUCT", "DIM_WORKORDER"]
for t in expected_tables:
    check(f"Table {t}", t in table_names)

# ── 3. KQL TABLES ──
print("\n--- 3. KQL Telemetry Tables ---")
kusto_token = cred.get_token("https://kusto.kusto.windows.net/.default").token
kusto_headers = {"Authorization": f"Bearer {kusto_token}", "Content-Type": "application/json"}
show_tables = json.dumps({"db": db_name, "csl": ".show tables"}).encode()
kql_resp = urllib.request.urlopen(
    urllib.request.Request(f"{query_uri}/v1/rest/mgmt", data=show_tables, headers=kusto_headers, method="POST")
)
kql_data = json.loads(kql_resp.read())
kql_table_names = [r[0] for r in kql_data.get("Tables", [{}])[0].get("Rows", [])]
for t in ["SensorTelemetry", "EquipmentStatus", "ProductionMetrics", "Alerts"]:
    check(f"KQL Table {t}", t in kql_table_names)

# ── 4. KQL DATA QUERY ──
print("\n--- 4. KQL Data Query ---")
# Ingest a test record
ingest = json.dumps({"db": db_name, "csl": ".ingest inline into table SensorTelemetry <| 'SG-SN-001', datetime(2026-04-02T12:00:00Z), 1092.3, 'Good'"}).encode()
urllib.request.urlopen(urllib.request.Request(f"{query_uri}/v1/rest/mgmt", data=ingest, headers=kusto_headers, method="POST"))

query = json.dumps({"db": db_name, "csl": "SensorTelemetry | count"}).encode()
q_resp = urllib.request.urlopen(
    urllib.request.Request(f"{query_uri}/v2/rest/query", data=query, headers=kusto_headers, method="POST")
)
q_data = json.loads(q_resp.read())
count = 0
for frame in q_data:
    if frame.get("FrameType") == "DataTable" and frame.get("TableKind") == "PrimaryResult":
        count = frame.get("Rows", [[0]])[0][0]
check("SensorTelemetry has data", count > 0, f"rows={count}")

# ── 5. ONTOLOGY DEFINITION ──
print("\n--- 5. Ontology Definition ---")
def get_definition():
    req = urllib.request.Request(
        f"{API}/workspaces/{ws_id}/ontologies/{ont_id}/getDefinition",
        headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status == 202:
                loc = resp.headers.get("Location", "")
                ra = int(resp.headers.get("Retry-After", "10"))
                time.sleep(ra)
                with urllib.request.urlopen(urllib.request.Request(loc, headers=headers)) as pr:
                    op = json.loads(pr.read().decode())
                    if op.get("status") == "Succeeded":
                        with urllib.request.urlopen(urllib.request.Request(loc + "/result", headers=headers)) as rr:
                            return json.loads(rr.read().decode())
            else:
                return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 202:
            loc = exc.headers.get("Location", "")
            ra = int(exc.headers.get("Retry-After", "10"))
            time.sleep(ra)
            with urllib.request.urlopen(urllib.request.Request(loc, headers=headers)) as pr:
                op = json.loads(pr.read().decode())
                if op.get("status") == "Succeeded":
                    with urllib.request.urlopen(urllib.request.Request(loc + "/result", headers=headers)) as rr:
                        return json.loads(rr.read().decode())
    return None

defn = get_definition()
parts = defn.get("definition", {}).get("parts", []) if defn else []
et_count = sum(1 for p in parts if p["path"].startswith("EntityTypes/") and p["path"].endswith("/definition.json"))
rel_count = sum(1 for p in parts if p["path"].startswith("RelationshipTypes/") and p["path"].endswith("/definition.json"))
db_count = sum(1 for p in parts if "/DataBindings/" in p["path"])
ctx_count = sum(1 for p in parts if "/Contextualizations/" in p["path"])

check("Ontology has parts", len(parts) > 0, f"total={len(parts)}")
check("6 Entity Types", et_count == 6, f"got={et_count}")
check("5 Relationships", rel_count == 5, f"got={rel_count}")
check("9 Data Bindings (6 NTS + 3 TS)", db_count == 9, f"got={db_count}")
check("5 Contextualizations", ctx_count == 5, f"got={ctx_count}")

# Validate entity type names
et_names = []
for p in parts:
    if p["path"].startswith("EntityTypes/") and p["path"].endswith("/definition.json"):
        decoded = json.loads(base64.b64decode(p["payload"]))
        et_names.append(decoded["name"])
        # Check valueType correctness
        for prop in decoded.get("properties", []):
            if prop.get("valueType") not in ("String", "Boolean", "DateTime", "Object", "BigInt", "Double"):
                check(f"Entity {decoded['name']} prop {prop['name']} valueType", False, f"invalid: {prop.get('valueType')}")
for expected_name in ["Plant", "ProductionLine", "Equipment", "Sensor", "Product", "WorkOrder"]:
    check(f"Entity type '{expected_name}' defined", expected_name in et_names)

# ── 6. SEMANTIC MODEL ──
print("\n--- 6. Semantic Model (DAX Queries) ---")
dax_token = cred.get_token("https://analysis.windows.net/powerbi/api/.default").token

def run_dax(query_text):
    body = json.dumps({
        "queries": [{"query": query_text}],
        "serializerSettings": {"includeNulls": True},
    }).encode()
    req = urllib.request.Request(
        f"{PBI_API}/groups/{ws_id}/datasets/{sm_id}/executeQueries",
        data=body,
        headers={"Authorization": f"Bearer {dax_token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

# Test 1: Plant count
try:
    result = run_dax('EVALUATE ROW("Plants", COUNTROWS(DIM_PLANT))')
    rows = result.get("results", [{}])[0].get("tables", [{}])[0].get("rows", [])
    plant_count = rows[0].get("[Plants]", 0) if rows else 0
    check("DAX: Plant count = 5", plant_count == 5, f"got={plant_count}")
except Exception as e:
    check("DAX: Plant count", False, str(e))

# Test 2: Equipment count
try:
    result = run_dax('EVALUATE ROW("Equipment", COUNTROWS(DIM_EQUIPMENT))')
    rows = result.get("results", [{}])[0].get("tables", [{}])[0].get("rows", [])
    eq_count = rows[0].get("[Equipment]", 0) if rows else 0
    check("DAX: Equipment count = 18", eq_count == 18, f"got={eq_count}")
except Exception as e:
    check("DAX: Equipment count", False, str(e))

# Test 3: Sensor count
try:
    result = run_dax('EVALUATE ROW("Sensors", COUNTROWS(DIM_SENSOR))')
    rows = result.get("results", [{}])[0].get("tables", [{}])[0].get("rows", [])
    sensor_count = rows[0].get("[Sensors]", 0) if rows else 0
    check("DAX: Sensor count = 20", sensor_count == 20, f"got={sensor_count}")
except Exception as e:
    check("DAX: Sensor count", False, str(e))

# Test 4: Cross-table query (relationship traversal)
try:
    result = run_dax('''
        EVALUATE
        SUMMARIZECOLUMNS(
            DIM_PLANT[Name],
            "Lines", COUNTROWS(DIM_LINE)
        )
    ''')
    rows = result.get("results", [{}])[0].get("tables", [{}])[0].get("rows", [])
    check("DAX: Plant-Line relationship traversal", len(rows) > 0, f"plants with lines={len(rows)}")
except Exception as e:
    check("DAX: Relationship traversal", False, str(e))

# Test 5: Measures
try:
    result = run_dax('EVALUATE ROW("PlantCount", [Plant Count])')
    rows = result.get("results", [{}])[0].get("tables", [{}])[0].get("rows", [])
    check("DAX: Plant Count measure works", len(rows) > 0, f"value={rows[0] if rows else 'none'}")
except Exception as e:
    check("DAX: Plant Count measure", False, str(e))

# ── SUMMARY ──
print("\n" + "=" * 60)
print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
if failed == 0:
    print("  ALL TESTS PASSED!")
else:
    print(f"  {failed} TESTS FAILED - review above")
print("=" * 60)
