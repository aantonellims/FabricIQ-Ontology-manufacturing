"""Monitor ontology backend: companion lakehouse ingestion, entity materialization, binding health."""
import json, time, urllib.request, urllib.error, base64, requests
from azure.identity import DefaultAzureCredential

with open("ontologies/SaintGobain/config.json") as f:
    config = json.load(f)

ws_id = config["workspace"]["id"]
lh_id = config["lakehouse"]["id"]
ont_id = config["ontology"]["id"]
kql_id = config["kqlDatabase"]["id"]
kql_uri = config["kqlDatabase"]["queryServiceUri"]
db_name = config["kqlDatabase"]["name"]
API = "https://api.fabric.microsoft.com/v1"

cred = DefaultAzureCredential()
token = cred.get_token("https://api.fabric.microsoft.com/.default").token
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
storage_token = cred.get_token("https://storage.azure.com/.default").token
sh = {"Authorization": f"Bearer {storage_token}"}
onelake = "https://onelake.dfs.fabric.microsoft.com"

print("=" * 70)
print("  ONTOLOGY BACKEND HEALTH CHECK")
print("=" * 70)

# ── 1. Source Lakehouse: verify tables and row counts ──
print("\n[1] SOURCE LAKEHOUSE (SG_ManufacturingLakehouse)")
print(f"    ID: {lh_id}")
tables = requests.get(f"{API}/workspaces/{ws_id}/lakehouses/{lh_id}/tables", headers=h).json().get("data", [])
print(f"    Tables: {len(tables)}")
for t in sorted(tables, key=lambda x: x["name"]):
    print(f"      {t['name']:<25s} format={t.get('format','?')}")

# Check table data via OneLake Files listing (check if Delta log exists)
print("\n    Checking Delta table health via OneLake:")
for table_name in ["DIM_PLANT","DIM_LINE","DIM_EQUIPMENT","DIM_SENSOR","DIM_PRODUCT","DIM_WORKORDER"]:
    try:
        url = f"{onelake}/{ws_id}/{lh_id}/Tables/{table_name}/_delta_log?resource=directory&recursive=false"
        req = urllib.request.Request(url, headers=sh)
        with urllib.request.urlopen(req) as resp:
            print(f"      {table_name}: Delta log exists (healthy)")
    except urllib.error.HTTPError as exc:
        print(f"      {table_name}: Delta log check = HTTP {exc.code}")

# ── 2. Companion Lakehouse ──
print("\n[2] COMPANION LAKEHOUSE (auto-created by ontology)")
items = requests.get(f"{API}/workspaces/{ws_id}/items", headers=h).json().get("value", [])
comp_lh = next((i for i in items if i["type"] == "Lakehouse" and i["id"] != lh_id), None)
if comp_lh:
    comp_id = comp_lh["id"]
    print(f"    Name: {comp_lh['displayName']}")
    print(f"    ID:   {comp_id}")
    
    # Check tables
    try:
        comp_tables = requests.get(f"{API}/workspaces/{ws_id}/lakehouses/{comp_id}/tables", headers=h)
        if comp_tables.status_code == 200:
            ct = comp_tables.json().get("data", [])
            print(f"    Tables: {len(ct)}")
            for t in ct:
                print(f"      {t['name']}")
            if not ct:
                print("    !! EMPTY - ontology has not materialized entities yet")
        else:
            print(f"    Tables API: HTTP {comp_tables.status_code}")
    except Exception as e:
        print(f"    Error: {e}")
    
    # Check Files directory in companion lakehouse
    print("\n    Checking companion OneLake directories:")
    for path in ["Tables", "Files"]:
        try:
            url = f"{onelake}/{ws_id}/{comp_id}/{path}?resource=directory&recursive=false"
            req = urllib.request.Request(url, headers=sh)
            with urllib.request.urlopen(req) as resp:
                data = resp.read().decode()
                # Count entries
                import re
                paths_found = re.findall(r'"name":"([^"]+)"', data)
                print(f"      /{path}: {len(paths_found)} entries")
                for pf in paths_found[:10]:
                    print(f"        {pf}")
        except urllib.error.HTTPError as exc:
            print(f"      /{path}: HTTP {exc.code}")
else:
    print("    NOT FOUND!")

# ── 3. KQL Database: check telemetry table health ──
print("\n[3] KQL DATABASE (telemetry)")
kusto_token = cred.get_token("https://kusto.kusto.windows.net/.default").token
kh = {"Authorization": f"Bearer {kusto_token}", "Content-Type": "application/json"}

body = json.dumps({"db": db_name, "csl": ".show tables details"}).encode()
req = urllib.request.Request(f"{kql_uri}/v1/rest/mgmt", data=body, headers=kh, method="POST")
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
        rows = data.get("Tables", [{}])[0].get("Rows", [])
        print(f"    Tables: {len(rows)}")
        for r in rows:
            print(f"      {r[0]:<25s} rows={r[3] if r[3] else 0}")
except Exception as e:
    print(f"    Error: {e}")

# ── 4. Ontology definition health ──
print("\n[4] ONTOLOGY DEFINITION")
req = urllib.request.Request(f"{API}/workspaces/{ws_id}/ontologies/{ont_id}/getDefinition", headers=h, method="POST")
try:
    with urllib.request.urlopen(req) as resp:
        loc = resp.headers.get("Location",""); ra = int(resp.headers.get("Retry-After","10"))
except urllib.error.HTTPError as exc:
    loc = exc.headers.get("Location",""); ra = int(exc.headers.get("Retry-After","10"))

parts = []
if loc:
    time.sleep(ra)
    for _ in range(15):
        with urllib.request.urlopen(urllib.request.Request(loc, headers=h)) as pr:
            op = json.loads(pr.read())
            if op.get("status") == "Succeeded":
                with urllib.request.urlopen(urllib.request.Request(loc+"/result", headers=h)) as rr:
                    parts = json.loads(rr.read()).get("definition",{}).get("parts",[])
                break
            if op.get("status") == "Failed":
                print(f"    getDefinition FAILED: {op.get('error')}")
                break
        time.sleep(5)

et_count = sum(1 for p in parts if p["path"].startswith("EntityTypes/") and p["path"].endswith("/definition.json"))
rel_count = sum(1 for p in parts if p["path"].startswith("RelationshipTypes/") and p["path"].endswith("/definition.json"))
db_count = sum(1 for p in parts if "/DataBindings/" in p["path"])
ctx_count = sum(1 for p in parts if "/Contextualizations/" in p["path"])
ov_count = sum(1 for p in parts if "/Overviews/" in p["path"])

print(f"    Total parts:          {len(parts)}")
print(f"    Entity types:         {et_count}")
print(f"    Relationships:        {rel_count}")
print(f"    Data bindings:        {db_count} (6 NTS + 3 TS)")
print(f"    Contextualizations:   {ctx_count}")
print(f"    Overviews:            {ov_count}")

# Check binding health: verify each binding's source is reachable
print("\n    Binding connectivity check:")
for p in parts:
    if "/DataBindings/" in p["path"]:
        db = json.loads(base64.b64decode(p["payload"]))
        cfg = db["dataBindingConfiguration"]
        src = cfg["sourceTableProperties"]
        bt = cfg["dataBindingType"]
        table = src.get("sourceTableName", "?")
        
        if src.get("sourceType") == "LakehouseTable":
            # Check table exists in source lakehouse
            exists = any(t["name"] == table for t in tables)
            status = "OK" if exists else "MISSING"
            print(f"      {bt:4s} {table:<25s} [{status}]")
        elif src.get("sourceType") == "KustoTable":
            # Already checked above
            print(f"      {bt:4s} {table:<25s} [KQL]")

# ── 5. GraphModel status ──
print("\n[5] GRAPH MODEL")
graph = next((i for i in items if i["type"] == "GraphModel"), None)
if graph:
    print(f"    Name: {graph['displayName']}")
    print(f"    ID:   {graph['id']}")
else:
    print("    NOT FOUND")

# ── 6. Summary ──
print("\n" + "=" * 70)
print("  SUMMARY")
print("=" * 70)
problems = []
if not tables:
    problems.append("Source lakehouse has NO tables")
if comp_lh:
    try:
        ct2 = requests.get(f"{API}/workspaces/{ws_id}/lakehouses/{comp_lh['id']}/tables", headers=h).json().get("data",[])
        if not ct2:
            problems.append("Companion lakehouse is EMPTY (ontology not materializing)")
    except:
        problems.append("Cannot check companion lakehouse")
if len(parts) < 27:
    problems.append(f"Ontology definition incomplete ({len(parts)} parts, expected 33)")
if ov_count == 0:
    problems.append("No Overviews defined (overview generation will be stuck)")

if problems:
    print("  ISSUES:")
    for p in problems:
        print(f"    - {p}")
    print()
    print("  POSSIBLE CAUSES FOR EMPTY COMPANION LAKEHOUSE:")
    print("    1. Ontology background processing is still running (wait 15-30 min)")
    print("    2. Capacity may be paused/throttled (check msfabric001 capacity)")
    print("    3. Binding column names don't match actual table columns (case-sensitive)")
    print("    4. sourceSchema='dbo' might not be recognized")
    print()
    print("  ACTIONS TO TRY:")
    print("    a. Wait 15 min and re-run this script")
    print("    b. In Fabric Portal: Ontology > ... > Refresh")
    print("    c. Check capacity status: Fabric Admin Portal > Capacities")
    print("    d. Re-create the ontology item from scratch")
else:
    print("  All checks passed!")

print("=" * 70)
