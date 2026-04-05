"""List all items in the workspace."""
import json, urllib.request
from azure.identity import DefaultAzureCredential

with open("ontologies/SaintGobain/config.json") as f:
    config = json.load(f)

ws_id = config["workspace"]["id"]
API = "https://api.fabric.microsoft.com/v1"
token = DefaultAzureCredential().get_token("https://api.fabric.microsoft.com/.default").token
h = {"Authorization": f"Bearer {token}"}

items = json.loads(urllib.request.urlopen(urllib.request.Request(f"{API}/workspaces/{ws_id}/items", headers=h)).read())
print(f"All items in workspace ({len(items['value'])}):\n")
for i in sorted(items["value"], key=lambda x: x["type"]):
    print(f"  [{i['type']:20s}] {i['displayName']}")
