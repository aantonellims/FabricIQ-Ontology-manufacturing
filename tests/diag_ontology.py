"""Diagnose ontology — check source data, companion lakehouse, and graph index."""
import json, urllib.request, base64, time
from azure.identity import DefaultAzureCredential

with open("ontologies/SaintGobain/config.json") as f:
    config = json.load(f)

ws_id = config["workspace"]["id"]
ont_id = config["ontology"]["id"]
lh_id = config["lakehouse"]["id"]
API = "https://api.fabric.microsoft.com/v1"
token = DefaultAzureCredential().get_token("https://api.fabric.microsoft.com/.default").token
h = {"Authorization": f"Bearer {token}"}

# 1. Source lakehouse tables
print("=== SOURCE LAKEHOUSE TABLES ===")
try:
    resp = urllib.request.urlopen(urllib.request.Request(f"{API}/workspaces/{ws_id}/lakehouses/{lh_id}/tables", headers=h))
    tables = json.loads(resp.read())
    for t in tables.get("data", []):
        print(f"  {t['name']:30s}  rows={t.get('rowCount','?')}")
except Exception as e:
    print(f"  Error: {e}")

# 2. Companion lakehouse
print("\n=== COMPANION LAKEHOUSE (OneLake) ===")
items_resp = urllib.request.urlopen(urllib.request.Request(f"{API}/workspaces/{ws_id}/items", headers=h))
items = json.loads(items_resp.read())
for item in items.get("value", []):
    if item["type"] == "Lakehouse" and "Ontology" in item.get("displayName", ""):
        comp_id = item["id"]
        print(f"Name: {item['displayName']}")
        print(f"ID:   {comp_id}")
        onelake = f"https://onelake.dfs.fabric.microsoft.com/{ws_id}/{comp_id}?resource=filesystem&recursive=true"
        try:
            ol_resp = urllib.request.urlopen(urllib.request.Request(onelake, headers=h))
            data = json.loads(ol_resp.read())
            paths = data.get("paths", [])
            print(f"Total paths: {len(paths)}")
            for p in paths:
                name = p.get("name", "")
                is_dir = p.get("isDirectory", "")
                size = p.get("contentLength", "")
                print(f"  {name}  (dir={is_dir}, size={size})")
        except Exception as ex:
            print(f"  OneLake error: {ex}")

# 3. Graph index
print("\n=== GRAPH INDEX ===")
for item in items.get("value", []):
    dn = item.get("displayName", "")
    if "graph" in dn.lower() or item["type"] == "GraphQLApi":
        print(f"  {dn} ({item['id']}) type={item['type']}")
        if item["type"] == "Lakehouse":
            gi_onelake = f"https://onelake.dfs.fabric.microsoft.com/{ws_id}/{item['id']}?resource=filesystem&recursive=true"
            try:
                gi_resp = urllib.request.urlopen(urllib.request.Request(gi_onelake, headers=h))
                gi_data = json.loads(gi_resp.read())
                for p in gi_data.get("paths", []):
                    print(f"    {p.get('name','')}  dir={p.get('isDirectory','')}  size={p.get('contentLength','')}")
            except Exception as ex:
                print(f"    OneLake error: {ex}")

# 4. Check the push script to see what was actually pushed
print("\n=== ONTOLOGY PUSH SCRIPT — RELATIONSHIPS ===")
import importlib.util, sys
# Just read the push script and extract relationship info
with open("deploy/push_ontology_v2.py") as f:
    content = f.read()
# Find relationship definitions
for line in content.split("\n"):
    if "Has_Line" in line or "Has_Equipment" in line or "Has_Sensor" in line or "Assigned_To" in line or "Produces" in line:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            print(f"  {stripped[:150]}")

