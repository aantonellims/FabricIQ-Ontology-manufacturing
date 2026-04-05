"""Query the ontology graph directly via GQL API to verify relationships."""
import json, urllib.request, ssl, socket
from azure.identity import DefaultAzureCredential

# Set timeout
socket.setdefaulttimeout(60)

with open("ontologies/SaintGobain/config.json") as f:
    config = json.load(f)

ws_id = config["workspace"]["id"]
API = "https://api.fabric.microsoft.com/v1"
token = DefaultAzureCredential().get_token("https://api.fabric.microsoft.com/.default").token
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Ontology's graph model
graph_model_id = "85c58951-6eff-4506-8dbe-98264e7f52ba"
gql_url = f"{API}/workspaces/{ws_id}/GraphModels/{graph_model_id}/executeQuery?preview=true"

queries = [
    ("All Equipment", "MATCH (e:Equipment) RETURN e.Name AS EquipmentName, e.EquipmentType ORDER BY e.Name"),
    ("All Sensors", "MATCH (s:Sensor) RETURN s.Name AS SensorName, s.SensorType, s.EquipmentId ORDER BY s.Name"),
    ("Equipment with CNC", "MATCH (e:Equipment) WHERE e.Name CONTAINS 'CNC' RETURN e.Name, e.EquipmentType"),
    ("Equipment→Sensor", "MATCH (e:Equipment)-[:Has_Sensor]->(s:Sensor) RETURN e.Name AS Equipment, s.Name AS Sensor LIMIT 15"),
]

for label, query in queries:
    print(f"\n{'='*60}")
    print(f"GQL: {label}")
    print(f"{'='*60}")
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(gql_url, data=body, headers=h, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read())
        if result.get("status", {}).get("code") == "00000":
            data = result.get("result", {}).get("data", [])
            print(f"Rows: {len(data)}")
            for row in data:
                print(f"  {row}")
        else:
            print(f"Error: {result.get('status', {}).get('description')}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else ""
        print(f"HTTP {e.code}: {err_body[:500]}")
    except socket.timeout:
        print("TIMEOUT (60s)")
    except Exception as ex:
        print(f"Error: {type(ex).__name__}: {ex}")
