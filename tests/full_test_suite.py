"""Full test suite: ontology queries, KQL telemetry, semantic model star schema, data agent."""
import base64, json, time, urllib.request, urllib.error, requests
from azure.identity import DefaultAzureCredential

with open("ontologies/SaintGobain/config.json") as f:
    config = json.load(f)

ws_id = config["workspace"]["id"]
lh_id = config["lakehouse"]["id"]
ont_id = config["ontology"]["id"]
sm_id = config["semanticModel"]["id"]
kql_uri = config["kqlDatabase"]["queryServiceUri"]
db_name = config["kqlDatabase"]["name"]
API = "https://api.fabric.microsoft.com/v1"

cred = DefaultAzureCredential()
fabric_token = cred.get_token("https://api.fabric.microsoft.com/.default").token
kusto_token = cred.get_token("https://kusto.kusto.windows.net/.default").token
pbi_token = cred.get_token("https://analysis.windows.net/powerbi/api/.default").token

h = {"Authorization": f"Bearer {fabric_token}", "Content-Type": "application/json"}
kh = {"Authorization": f"Bearer {kusto_token}", "Content-Type": "application/json"}
ph = {"Authorization": f"Bearer {pbi_token}", "Content-Type": "application/json"}

passed = failed = 0

def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}" + (f" -> {detail}" if detail else ""))
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f" -> {detail}" if detail else ""))

def dax(q):
    body = json.dumps({"queries": [{"query": q}], "serializerSettings": {"includeNulls": True}}).encode()
    req = urllib.request.Request(f"https://api.powerbi.com/v1.0/myorg/groups/{ws_id}/datasets/{sm_id}/executeQueries",
        data=body, headers=ph)
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read())
        err = res.get("results", [{}])[0].get("error")
        if err: return None, err.get("message","")
        return res.get("results", [{}])[0].get("tables", [{}])[0].get("rows", []), None

def kql(q):
    body = json.dumps({"db": db_name, "csl": q}).encode()
    req = urllib.request.Request(f"{kql_uri}/v2/rest/query", data=body, headers=kh, method="POST")
    with urllib.request.urlopen(req) as resp:
        for f in json.loads(resp.read()):
            if f.get("FrameType") == "DataTable" and f.get("TableKind") == "PrimaryResult":
                return f.get("Rows", [])
    return []

print("=" * 65)
print("  COMPLETE TEST SUITE - ONTOLOGY + STAR SCHEMA + KQL + AGENT")
print("=" * 65)

# ═══════════════ 1. ONTOLOGY STRUCTURE ═══════════════
print("\n--- TEST 1: Ontology Structure ---")
req = urllib.request.Request(f"{API}/workspaces/{ws_id}/ontologies/{ont_id}/getDefinition", headers=h, method="POST")
try:
    with urllib.request.urlopen(req) as resp:
        loc = resp.headers.get("Location",""); ra = int(resp.headers.get("Retry-After","10"))
except urllib.error.HTTPError as exc:
    loc = exc.headers.get("Location",""); ra = int(exc.headers.get("Retry-After","10"))

parts = []
if loc:
    time.sleep(ra)
    with urllib.request.urlopen(urllib.request.Request(loc, headers=h)) as pr:
        op = json.loads(pr.read())
        if op.get("status") == "Succeeded":
            with urllib.request.urlopen(urllib.request.Request(loc+"/result", headers=h)) as rr:
                parts = json.loads(rr.read()).get("definition",{}).get("parts",[])

et_count = sum(1 for p in parts if p["path"].startswith("EntityTypes/") and p["path"].endswith("/definition.json"))
rel_count = sum(1 for p in parts if p["path"].startswith("RelationshipTypes/") and p["path"].endswith("/definition.json"))
nts_count = sum(1 for p in parts if "/DataBindings/" in p["path"] and "NonTimeSeries" in base64.b64decode(p["payload"]).decode())
ts_count = sum(1 for p in parts if "/DataBindings/" in p["path"] and "TimeSeries" in base64.b64decode(p["payload"]).decode() and "NonTimeSeries" not in base64.b64decode(p["payload"]).decode())
ctx_count = sum(1 for p in parts if "/Contextualizations/" in p["path"])

check("Ontology non-empty", len(parts) > 0, f"total parts={len(parts)}")
check("6 entity types (Plant, Line, Equipment, Sensor, Product, WorkOrder)", et_count == 6, f"got={et_count}")
check("5 relationships (Has_Line, Has_Equipment, Has_Sensor, Assigned_To, Produces)", rel_count == 5, f"got={rel_count}")
check("6 NonTimeSeries bindings to Lakehouse DIMs", nts_count == 6, f"got={nts_count}")
check("3 TimeSeries bindings to KQL (Sensor, Equipment, Line)", ts_count == 3, f"got={ts_count}")
check("5 contextualizations for relationship joins", ctx_count == 5, f"got={ctx_count}")

# Validate entity type structure
et_names = []
for p in parts:
    if p["path"].startswith("EntityTypes/") and p["path"].endswith("/definition.json"):
        et = json.loads(base64.b64decode(p["payload"]))
        et_names.append(et["name"])
        for prop in et.get("properties", []):
            vt = prop.get("valueType", "")
            check(f"  {et['name']}.{prop['name']} valueType valid", vt in ("String","Boolean","DateTime","Object","BigInt","Double"), f"valueType={vt}")

# Validate NTS bindings point to existing Lakehouse tables
lh_tables = {t["name"] for t in requests.get(f"{API}/workspaces/{ws_id}/lakehouses/{lh_id}/tables", headers=h).json().get("data", [])}
for p in parts:
    if "/DataBindings/" in p["path"]:
        db = json.loads(base64.b64decode(p["payload"]))
        cfg = db["dataBindingConfiguration"]
        src = cfg["sourceTableProperties"]
        if src.get("sourceType") == "LakehouseTable":
            tn = src["sourceTableName"]
            check(f"  NTS binding table '{tn}' exists in Lakehouse", tn in lh_tables)
        elif src.get("sourceType") == "KustoTable":
            # KQL tables are accessed via mgmt endpoint, not query
            tn = src["sourceTableName"]
            try:
                mgmt_body = json.dumps({"db": db_name, "csl": ".show tables"}).encode()
                mgmt_req = urllib.request.Request(f"{kql_uri}/v1/rest/mgmt", data=mgmt_body, headers=kh, method="POST")
                with urllib.request.urlopen(mgmt_req) as mr:
                    mgmt_data = json.loads(mr.read())
                    kql_tables = [r[0] for r in mgmt_data.get("Tables", [{}])[0].get("Rows", [])]
                    check(f"  TS binding table '{tn}' exists in KQL", tn in kql_tables)
            except Exception as e:
                check(f"  TS binding table '{tn}' check", False, str(e)[:80])

# ═══════════════ 2. KQL TELEMETRY ═══════════════
print("\n--- TEST 2: KQL Telemetry Tables (Real-Time) ---")
for table in ["SensorTelemetry", "EquipmentStatus", "ProductionMetrics", "Alerts"]:
    rows = kql(f"{table} | count")
    count = rows[0][0] if rows else 0
    check(f"KQL table {table} accessible", count >= 0, f"rows={count}")

# Ingest and query test
kql_mgmt = f"{kql_uri}/v1/rest/mgmt"
import datetime, random
now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
ingest = f".ingest inline into table SensorTelemetry <| 'SG-SN-001',datetime({now}),{round(random.uniform(1050,1120),1)},'Good'"
body = json.dumps({"db": db_name, "csl": ingest}).encode()
urllib.request.urlopen(urllib.request.Request(kql_mgmt, data=body, headers=kh, method="POST"))
rows = kql("SensorTelemetry | where SensorId == 'SG-SN-001' | count")
check("KQL ingest + query works", rows and rows[0][0] > 0, f"SG-SN-001 readings={rows[0][0] if rows else 0}")

# ═══════════════ 3. SEMANTIC MODEL STAR SCHEMA ═══════════════
print("\n--- TEST 3: Semantic Model Star Schema ---")

# Dimension tables
for dim, expected in [("DIM_PLANT", 5), ("DIM_LINE", 12), ("DIM_EQUIPMENT", 18), ("DIM_SENSOR", 20), ("DIM_PRODUCT", 10), ("DIM_DATE", 17)]:
    rows, err = dax(f'EVALUATE ROW("c", COUNTROWS({dim}))')
    count = rows[0].get("[c]", 0) if rows else 0
    check(f"Dim {dim} rows={expected}", count == expected, f"got={count}")

# Fact tables
for fact, min_rows in [("FACT_PRODUCTION", 20), ("FACT_WORK_ORDER", 5), ("FACT_EQUIPMENT_OEE", 15)]:
    rows, err = dax(f'EVALUATE ROW("c", COUNTROWS({fact}))')
    if err:
        check(f"Fact {fact}", False, err[:100])
    else:
        count = rows[0].get("[c]", 0) if rows else 0
        check(f"Fact {fact} has data", count >= min_rows, f"rows={count}")

# Star schema relationships (fact -> dim traversal)
print("\n  Star Schema Relationships:")
rows, err = dax('EVALUATE ADDCOLUMNS(VALUES(DIM_PLANT[Name]), "Produced", CALCULATE([Total Produced])) ORDER BY [Produced] DESC')
check("FACT_PRODUCTION -> DIM_PLANT traversal", rows and not err, f"plants={len(rows) if rows else 0}")

rows, err = dax('EVALUATE ADDCOLUMNS(VALUES(DIM_PRODUCT[Name]), "Produced", CALCULATE([Total Produced])) ORDER BY [Produced] DESC')
check("FACT_PRODUCTION -> DIM_PRODUCT traversal", rows and not err, f"products={len(rows) if rows else 0}")

rows, err = dax('EVALUATE ADDCOLUMNS(VALUES(DIM_DATE[MonthName]), "Produced", CALCULATE([Total Produced]))')
check("FACT_PRODUCTION -> DIM_DATE traversal", rows and not err, f"months={len(rows) if rows else 0}")

rows, err = dax('EVALUATE ADDCOLUMNS(VALUES(DIM_EQUIPMENT[Name]), "OEE", CALCULATE([Avg OEE %])) ORDER BY [OEE] DESC')
check("FACT_EQUIPMENT_OEE -> DIM_EQUIPMENT traversal", rows and not err, f"equipment={len(rows) if rows else 0}")

rows, err = dax('EVALUATE ADDCOLUMNS(VALUES(DIM_LINE[Name]), "Orders", CALCULATE([Order Count]))')
check("FACT_WORK_ORDER -> DIM_LINE traversal", rows and not err, f"lines={len(rows) if rows else 0}")

# Measures validation
print("\n  Measures:")
measures = [
    ("[Total Produced]", "Total Produced"),
    ("[Yield %]", "Yield %"),
    ("[Plan Achievement %]", "Plan Achievement"),
    ("[Avg Cycle Time (s)]", "Avg Cycle Time"),
    ("[Availability %]", "Availability"),
    ("[Avg OEE %]", "Avg OEE"),
    ("[Total Breakdown Min]", "Total Breakdown"),
    ("[Equipment Utilization %]", "Equipment Utilization"),
    ("[Order Count]", "Order Count"),
    ("[Total Order Value]", "Total Order Value"),
    ("[Completion %]", "Completion"),
    ("[Open Orders]", "Open Orders"),
    ("[Total Scrap (kg)]", "Total Scrap"),
    ("[Total Defective]", "Total Defective"),
    ("[Avg Availability %]", "Avg Availability"),
]
for measure, label in measures:
    rows, err = dax(f'EVALUATE ROW("v", {measure})')
    if err:
        check(f"Measure: {label}", False, err[:80])
    else:
        val = rows[0].get("[v]", "null") if rows else "null"
        check(f"Measure: {label}", val is not None, f"value={val}")

# ═══════════════ 4. DATA AGENT ═══════════════
print("\n--- TEST 4: Data Agent ---")
items = requests.get(f"{API}/workspaces/{ws_id}/items", headers=h).json().get("value", [])
agent = next((i for i in items if i["type"] == "DataAgent"), None)
check("Data Agent exists", agent is not None, f"name={agent['displayName']}" if agent else "")
if agent:
    check("Data Agent item accessible", requests.get(f"{API}/workspaces/{ws_id}/items/{agent['id']}", headers=h).status_code == 200)

# ═══════════════ 5. GRAPH & ONTOLOGY ITEMS ═══════════════
print("\n--- TEST 5: Supporting Items ---")
graph_api = next((i for i in items if i["type"] == "GraphQLApi"), None)
graph_model = next((i for i in items if i["type"] == "GraphModel"), None)
check("GraphQL API exists", graph_api is not None, f"name={graph_api['displayName']}" if graph_api else "")
check("Graph Model exists", graph_model is not None, f"name={graph_model['displayName']}" if graph_model else "")

# ═══════════════ SUMMARY ═══════════════
total = passed + failed
print("\n" + "=" * 65)
print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
if failed == 0:
    print("  ALL TESTS PASSED!")
else:
    print(f"  {failed} TEST(S) FAILED")
print("=" * 65)
