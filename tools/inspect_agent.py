"""Inspect current Data Agent definition — list all parts and datasource folders."""
import json, urllib.request, base64, time
from azure.identity import DefaultAzureCredential

with open("ontologies/SaintGobain/config.json") as f:
    config = json.load(f)

ws_id = config["workspace"]["id"]
API = "https://api.fabric.microsoft.com/v1"
token = DefaultAzureCredential().get_token("https://api.fabric.microsoft.com/.default").token
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

items = json.loads(urllib.request.urlopen(urllib.request.Request(f"{API}/workspaces/{ws_id}/items", headers=h)).read())
agent = next(i for i in items["value"] if i["type"] == "DataAgent")
agent_id = agent["id"]
print(f"Agent: {agent['displayName']} ({agent_id})")

req = urllib.request.Request(f"{API}/workspaces/{ws_id}/dataAgents/{agent_id}/getDefinition", data=b"{}", headers=h, method="POST")
result = None
try:
    with urllib.request.urlopen(req) as resp:
        body = resp.read()
        if resp.status == 202:
            loc = resp.headers.get("Location", "")
            ra = int(resp.headers.get("Retry-After", "5"))
            print(f"LRO started (202), polling...")
            time.sleep(ra)
            for attempt in range(20):
                with urllib.request.urlopen(urllib.request.Request(loc, headers=h)) as pr:
                    op = json.loads(pr.read())
                    st = op.get("status", "")
                    print(f"  Poll {attempt+1}: {st}")
                    if st == "Succeeded":
                        with urllib.request.urlopen(urllib.request.Request(loc + "/result", headers=h)) as rr:
                            result = json.loads(rr.read())
                        break
                    elif st == "Failed":
                        print(f"FAILED: {op}")
                        break
                time.sleep(3)
        else:
            result = json.loads(body)
except urllib.error.HTTPError as e:
    ebody = e.read().decode() if e.fp else ""
    print(f"HTTP {e.code}: {ebody[:300]}")
    if e.code == 202:
        loc = e.headers.get("Location", "")
        ra = int(e.headers.get("Retry-After", "5"))
        if loc:
            time.sleep(ra)
            for attempt in range(20):
                with urllib.request.urlopen(urllib.request.Request(loc, headers=h)) as pr:
                    op = json.loads(pr.read())
                    if op.get("status") == "Succeeded":
                        with urllib.request.urlopen(urllib.request.Request(loc + "/result", headers=h)) as rr:
                            result = json.loads(rr.read())
                        break
                time.sleep(3)

if not result:
    print("ERROR: Could not get definition")
    exit(1)

parts = result.get("definition", {}).get("parts", [])
print(f"\nAll {len(parts)} parts:")

draft_ds = []
published_ds = []
for p in parts:
    path = p["path"]
    print(f"  {path}")
    if "/datasource.json" in path:
        decoded = json.loads(base64.b64decode(p["payload"]))
        info = f"    type={decoded.get('type')}  displayName={decoded.get('displayName')}  artifactId={decoded.get('artifactId','')[:36]}"
        print(info)
        if "/draft/" in path:
            draft_ds.append(path)
        elif "/published/" in path:
            published_ds.append(path)

print(f"\n--- Summary ---")
print(f"Draft datasources ({len(draft_ds)}):")
for d in draft_ds:
    print(f"  {d}")
print(f"Published datasources ({len(published_ds)}):")
for d in published_ds:
    print(f"  {d}")
if not published_ds:
    print("  (none — agent not published yet)")
