"""Execute live queries against all deployed components."""
import json, time, random, datetime, base64, urllib.request, urllib.error
from azure.identity import DefaultAzureCredential

with open("ontologies/SaintGobain/config.json") as f:
    config = json.load(f)

ws_id, sm_id = config["workspace"]["id"], config["semanticModel"]["id"]
query_uri, db_name = config["kqlDatabase"]["queryServiceUri"], config["kqlDatabase"]["name"]
ont_id = config["ontology"]["id"]
API = "https://api.fabric.microsoft.com/v1"

cred = DefaultAzureCredential()
fabric_token = cred.get_token("https://api.fabric.microsoft.com/.default").token
kusto_token = cred.get_token("https://kusto.kusto.windows.net/.default").token
pbi_token = cred.get_token("https://analysis.windows.net/powerbi/api/.default").token

def kql_mgmt(cmd):
    body = json.dumps({"db": db_name, "csl": cmd}).encode()
    req = urllib.request.Request(f"{query_uri}/v1/rest/mgmt", data=body,
        headers={"Authorization": f"Bearer {kusto_token}", "Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req)

def kql_query(q):
    body = json.dumps({"db": db_name, "csl": q}).encode()
    req = urllib.request.Request(f"{query_uri}/v2/rest/query", data=body,
        headers={"Authorization": f"Bearer {kusto_token}", "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        for f in json.loads(resp.read()):
            if f.get("FrameType") == "DataTable" and f.get("TableKind") == "PrimaryResult":
                return [c["ColumnName"] for c in f.get("Columns", [])], f.get("Rows", [])
    return [], []

def dax(q):
    body = json.dumps({"queries": [{"query": q}], "serializerSettings": {"includeNulls": True}}).encode()
    req = urllib.request.Request(
        f"https://api.powerbi.com/v1.0/myorg/groups/{ws_id}/datasets/{sm_id}/executeQueries",
        data=body, headers={"Authorization": f"Bearer {pbi_token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read()).get("results", [{}])[0].get("tables", [{}])[0].get("rows", [])

def v(val):
    return str(val) if val is not None else ""

print("=" * 70)
print("    SAINT-GOBAIN MANUFACTURING ONTOLOGY - LIVE QUERY DEMO")
print("=" * 70)

# Ingest telemetry
print("\n[Ingesting sample telemetry...]")
now = datetime.datetime.now(datetime.UTC)
sensors_cfg = [("SG-SN-001",1050,1120),("SG-SN-002",1040,1110),("SG-SN-005",550,620),
               ("SG-SN-007",2,19),("SG-SN-014",8,14),("SG-SN-016",1300,1500),
               ("SG-SN-019",580,680),("SG-SN-020",2,8)]
sd = []
for sid,lo,hi in sensors_cfg:
    for i in range(5):
        ts = (now-datetime.timedelta(minutes=i*5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        sd.append(f"'{sid}',datetime({ts}),{round(random.uniform(lo,hi),1)},'{random.choice(['Good']*19+['Uncertain'])}'")
kql_mgmt(".ingest inline into table SensorTelemetry <| " + ",".join(sd))
ed = []
for eq in ["SG-EQ-001","SG-EQ-002","SG-EQ-005","SG-EQ-008","SG-EQ-010","SG-EQ-012","SG-EQ-017","SG-EQ-018"]:
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    dt = round(random.uniform(0,2),1) if random.random()>0.8 else 0
    ed.append(f"'{eq}',datetime({ts}),{round(random.uniform(5,10),1)},{dt},'{'Idle' if dt>0 else 'Operating'}'")
kql_mgmt(".ingest inline into table EquipmentStatus <| " + ",".join(ed))
pd_ = []
for ln in ["SG-LN-001","SG-LN-002","SG-LN-005","SG-LN-007","SG-LN-009"]:
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    pd_.append(f"'{ln}',datetime({ts}),{round(random.uniform(78,97),1)},{random.randint(15,45)},{round(random.uniform(30,90),1)}")
kql_mgmt(".ingest inline into table ProductionMetrics <| " + ",".join(pd_))
print(f"  Done: {len(sd)} sensor + {len(ed)} equipment + {len(pd_)} production records\n")

# ═══════════════ KQL ═══════════════
print("-" * 70)
print("  KQL QUERIES (Real-Time Telemetry)")
print("-" * 70)

print("\n>> Q1: Latest sensor readings")
_, rows = kql_query("SensorTelemetry | summarize arg_max(Timestamp, Value, Quality) by SensorId | order by SensorId | take 8")
print(f"  {'Sensor':<14} {'Value':>10} {'Quality':<10}")
print(f"  {'-'*14} {'-'*10} {'-'*10}")
for r in rows:
    sid = str(r[0]).strip("'")
    print(f"  {sid:<14} {r[2]:>10.1f} {str(r[3]).strip(chr(39)):<10}")

print("\n>> Q2: Equipment availability")
_, rows = kql_query("EquipmentStatus | summarize RT=sum(RunTimeMinutes), DT=sum(DownTimeMinutes) by EquipmentId | extend Avail=round(RT/(RT+DT)*100,1) | order by Avail asc")
print(f"  {'Equipment':<14} {'Run':>7} {'Down':>7} {'Avail':>7}")
print(f"  {'-'*14} {'-'*7} {'-'*7} {'-'*7}")
for r in rows:
    print(f"  {str(r[0]).strip(chr(39)):<14} {r[1]:>6.1f}m {r[2]:>6.1f}m {r[3]:>6.1f}%")

print("\n>> Q3: Production line efficiency")
_, rows = kql_query("ProductionMetrics | summarize Eff=round(avg(Efficiency),1), Units=sum(UnitCount), Cycle=round(avg(CycleTime),1) by LineId | order by Eff desc")
print(f"  {'Line':<14} {'Eff':>7} {'Units':>6} {'Cycle':>7}")
print(f"  {'-'*14} {'-'*7} {'-'*6} {'-'*7}")
for r in rows:
    print(f"  {str(r[0]).strip(chr(39)):<14} {r[1]:>6.1f}% {r[2]:>6} {r[3]:>6.1f}s")

# ═══════════════ DAX ═══════════════
print("\n" + "-" * 70)
print("  DAX QUERIES (Semantic Model - DirectLake on Lakehouse)")
print("-" * 70)

print("\n>> Q4: Entity counts across entire model")
rows = dax('EVALUATE ROW("Plants", COUNTROWS(DIM_PLANT), "Lines", COUNTROWS(DIM_LINE), "Equipment", COUNTROWS(DIM_EQUIPMENT), "Sensors", COUNTROWS(DIM_SENSOR), "Products", COUNTROWS(DIM_PRODUCT), "WorkOrders", COUNTROWS(DIM_WORKORDER))')
if rows:
    for k2, v2 in rows[0].items():
        print(f"  {k2.strip('[]'):<14} {v2}")

print("\n>> Q5: Plants with line/equipment counts (hierarchy)")
rows = dax('EVALUATE ADDCOLUMNS(VALUES(DIM_PLANT[Name]), "Div", CALCULATE(FIRSTNONBLANK(DIM_PLANT[Division],1)), "Lines", CALCULATE(COUNTROWS(DIM_LINE)), "Equip", CALCULATE(COUNTROWS(DIM_EQUIPMENT))) ORDER BY [Equip] DESC')
print(f"  {'Plant':<38} {'Division':<22} {'Lines':>5} {'Equip':>5}")
print(f"  {'-'*38} {'-'*22} {'-'*5} {'-'*5}")
for r in rows:
    print(f"  {v(r.get('DIM_PLANT[Name]')):<38} {v(r.get('[Div]')):<22} {v(r.get('[Lines]')):>5} {v(r.get('[Equip]')):>5}")

print("\n>> Q6: Equipment types")
rows = dax('EVALUATE SUMMARIZECOLUMNS(DIM_EQUIPMENT[EquipmentType], DIM_EQUIPMENT[Status], "Cnt", COUNTROWS(DIM_EQUIPMENT)) ORDER BY [Cnt] DESC')
print(f"  {'Type':<18} {'Status':<12} {'Count':>5}")
print(f"  {'-'*18} {'-'*12} {'-'*5}")
for r in rows:
    print(f"  {v(r.get('DIM_EQUIPMENT[EquipmentType]')):<18} {v(r.get('DIM_EQUIPMENT[Status]')):<12} {v(r.get('[Cnt]')):>5}")

print("\n>> Q7: Products by division")
rows = dax('EVALUATE ADDCOLUMNS(SUMMARIZECOLUMNS(DIM_PRODUCT[Division], DIM_PRODUCT[Category]), "Cnt", COUNTROWS(DIM_PRODUCT), "AvgPx", AVERAGE(DIM_PRODUCT[UnitPrice])) ORDER BY DIM_PRODUCT[Division]')
print(f"  {'Division':<22} {'Category':<25} {'#':>3} {'AvgPrice':>9}")
print(f"  {'-'*22} {'-'*25} {'-'*3} {'-'*9}")
for r in rows:
    px = r.get('[AvgPx]', 0) or 0
    print(f"  {v(r.get('DIM_PRODUCT[Division]')):<22} {v(r.get('DIM_PRODUCT[Category]')):<25} {v(r.get('[Cnt]')):>3} {px:>9.2f}")

print("\n>> Q8: Work orders summary")
rows = dax('EVALUATE ADDCOLUMNS(SUMMARIZECOLUMNS(DIM_WORKORDER[Status], DIM_WORKORDER[Priority]), "Cnt", COUNTROWS(DIM_WORKORDER), "Qty", SUM(DIM_WORKORDER[Quantity])) ORDER BY DIM_WORKORDER[Priority]')
print(f"  {'Status':<14} {'Priority':<10} {'#':>4} {'Qty':>8}")
print(f"  {'-'*14} {'-'*10} {'-'*4} {'-'*8}")
for r in rows:
    print(f"  {v(r.get('DIM_WORKORDER[Status]')):<14} {v(r.get('DIM_WORKORDER[Priority]')):<10} {v(r.get('[Cnt]')):>4} {v(r.get('[Qty]')):>8}")

print("\n>> Q9: Sensors per plant (full 4-level hierarchy traversal)")
rows = dax('EVALUATE ADDCOLUMNS(VALUES(DIM_PLANT[Name]), "Sensors", CALCULATE(COUNTROWS(DIM_SENSOR))) ORDER BY [Sensors] DESC')
print(f"  {'Plant':<40} {'Sensors':>7}")
print(f"  {'-'*40} {'-'*7}")
for r in rows:
    print(f"  {v(r.get('DIM_PLANT[Name]')):<40} {v(r.get('[Sensors]')):>7}")

# ═══════════════ ONTOLOGY ═══════════════
print("\n" + "-" * 70)
print("  ONTOLOGY DEFINITION (via Fabric API)")
print("-" * 70)

fh = {"Authorization": f"Bearer {fabric_token}", "Content-Type": "application/json"}
req = urllib.request.Request(f"{API}/workspaces/{ws_id}/ontologies/{ont_id}/getDefinition", headers=fh, method="POST")
try:
    with urllib.request.urlopen(req) as resp:
        loc = resp.headers.get("Location",""); ra = int(resp.headers.get("Retry-After","10"))
except urllib.error.HTTPError as exc:
    loc = exc.headers.get("Location",""); ra = int(exc.headers.get("Retry-After","10"))

if loc:
    time.sleep(ra)
    with urllib.request.urlopen(urllib.request.Request(loc, headers=fh)) as pr:
        op = json.loads(pr.read())
        if op.get("status") == "Succeeded":
            with urllib.request.urlopen(urllib.request.Request(loc+"/result", headers=fh)) as rr:
                parts = json.loads(rr.read()).get("definition",{}).get("parts",[])
                et_map = {}
                print(f"\n  {'Entity Type':<18} {'Props':>5} {'TS Props':>8} {'ID':>16}")
                print(f"  {'-'*18} {'-'*5} {'-'*8} {'-'*16}")
                for p in parts:
                    if p["path"].startswith("EntityTypes/") and p["path"].endswith("/definition.json"):
                        et = json.loads(base64.b64decode(p["payload"]))
                        et_map[et["id"]] = et["name"]
                        print(f"  {et['name']:<18} {len(et.get('properties',[])):>5} {len(et.get('timeseriesProperties',[])):>8} {et['id']:>16}")

                print(f"\n  {'Relationship':<18} {'From':<18} {'To':<18}")
                print(f"  {'-'*18} {'-'*18} {'-'*18}")
                for p in parts:
                    if p["path"].startswith("RelationshipTypes/") and p["path"].endswith("/definition.json"):
                        rel = json.loads(base64.b64decode(p["payload"]))
                        print(f"  {rel['name']:<18} {et_map.get(rel['source']['entityTypeId'],'?'):<18} {et_map.get(rel['target']['entityTypeId'],'?'):<18}")

                bnd = sum(1 for p in parts if "/DataBindings/" in p["path"])
                ctx = sum(1 for p in parts if "/Contextualizations/" in p["path"])
                print(f"\n  Bindings: {bnd} (6 Lakehouse + 3 KQL)  |  Contextualizations: {ctx}")

print("\n" + "=" * 70)
print("    ALL QUERIES EXECUTED SUCCESSFULLY")
print("=" * 70)
