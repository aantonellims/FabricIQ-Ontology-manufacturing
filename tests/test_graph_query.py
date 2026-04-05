"""Query the ontology graph directly via GraphQL API to verify relationships."""
import json, urllib.request
from azure.identity import DefaultAzureCredential

with open("ontologies/SaintGobain/config.json") as f:
    config = json.load(f)

ws_id = config["workspace"]["id"]
API = "https://api.fabric.microsoft.com/v1"
token = DefaultAzureCredential().get_token("https://api.fabric.microsoft.com/.default").token
h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

graphql_id = "d5fbd577-5753-455b-a209-d24428143e5f"

# First, get the GraphQL endpoint URL
graphql_url = f"{API}/workspaces/{ws_id}/graphqlapis/{graphql_id}/graphql"

# Test 1: List all Plants
queries = [
    ("All Plants", '{ plants(first: 10) { items { PlantId Name Location Country Status } } }'),
    ("All ProductionLines", '{ productionLines(first: 10) { items { LineId Name PlantId LineType Status } } }'),
    ("Plant→Lines (Seremange)", '{ plants(filter: { Name: { eq: "Seremange" } }) { items { PlantId Name has_Line { items { LineId Name LineType Status } } } } }'),
]

for label, query in queries:
    print(f"\n{'='*60}")
    print(f"QUERY: {label}")
    print(f"{'='*60}")
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(graphql_url, data=body, headers=h, method="POST")
    try:
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read())
        print(json.dumps(result, indent=2))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else ""
        print(f"HTTP {e.code}: {err_body[:500]}")
    except Exception as ex:
        print(f"Error: {ex}")
