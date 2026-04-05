"""Check timestamps in KQL tables."""
import json, urllib.request
from azure.identity import DefaultAzureCredential

with open("ontologies/SaintGobain/config.json") as f:
    config = json.load(f)

QUERY_URI = config["kqlDatabase"]["queryServiceUri"]
DB_NAME = config["kqlDatabase"]["name"]
token = DefaultAzureCredential().get_token("https://api.kusto.windows.net/.default").token
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def kql(q):
    body = json.dumps({"db": DB_NAME, "csl": q}).encode()
    req = urllib.request.Request(f"{QUERY_URI}/v1/rest/query", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req) as r:
        result = json.loads(r.read())
    return result["Tables"][0]

# Check timestamps ranges
for table in ["EquipmentStatus", "SensorTelemetry", "ProductionMetrics"]:
    t = kql(f"{table} | summarize MinTS=min(Timestamp), MaxTS=max(Timestamp), Records=count()")
    print(f"{table}: {t['Rows'][0]}")

print()

# Check KQL now()
t = kql("print now=now()")
print(f"KQL now(): {t['Rows'][0]}")

print()

# Show rows with high downtime
t = kql("EquipmentStatus | where DownTimeMinutes > 150 | take 5 | project EquipmentId, Timestamp, DownTimeMinutes, OperatingStatus")
print(f"EquipmentStatus with DownTimeMinutes > 150:")
for row in t["Rows"]:
    print(f"  {row}")

print()

# Check how old the data is
t = kql("EquipmentStatus | summarize MaxTS=max(Timestamp) | extend Age=now()-MaxTS")
print(f"Data age: {t['Rows'][0]}")
