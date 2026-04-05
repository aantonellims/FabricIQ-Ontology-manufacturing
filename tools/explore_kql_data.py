"""Explore KQL data to find realistic query thresholds."""
import json, urllib.request
from azure.identity import DefaultAzureCredential

with open("ontologies/SaintGobain/config.json") as f:
    config = json.load(f)

QUERY_URI = config["kqlDatabase"]["queryServiceUri"]
DB_NAME = config["kqlDatabase"]["name"]
token = DefaultAzureCredential().get_token("https://api.kusto.windows.net/.default").token
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def kql_query(q):
    body = json.dumps({"db": DB_NAME, "csl": q}).encode()
    req = urllib.request.Request(f"{QUERY_URI}/v1/rest/query", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req) as r:
        result = json.loads(r.read())
    cols = [c["ColumnName"] for c in result["Tables"][0]["Columns"]]
    rows = result["Tables"][0]["Rows"]
    return cols, rows

# 1. Equipment downtime
print("=== EquipmentStatus: Downtime summary per equipment ===")
cols, rows = kql_query("""
EquipmentStatus
| summarize MaxDown=max(DownTimeMinutes), AvgDown=round(avg(DownTimeMinutes),1), Records=count() by EquipmentId
| order by MaxDown desc
""")
print(f"  {cols}")
for row in rows:
    print(f"  {row}")

# 2. SensorTelemetry - value ranges
print("\n=== SensorTelemetry: Value ranges per sensor ===")
cols, rows = kql_query("""
SensorTelemetry
| summarize MinVal=round(min(Value),2), MaxVal=round(max(Value),2), AvgVal=round(avg(Value),2), Records=count() by SensorId
| order by SensorId asc
""")
print(f"  {cols}")
for row in rows:
    print(f"  {row}")

# 3. Equipment non-Operating statuses
print("\n=== EquipmentStatus: Non-Operating events ===")
cols, rows = kql_query("""
EquipmentStatus
| where OperatingStatus != "Operating"
| summarize Records=count() by EquipmentId, OperatingStatus
| order by EquipmentId asc
""")
print(f"  {cols}")
for row in rows:
    print(f"  {row}")

# 4. ProductionMetrics - efficiency ranges
print("\n=== ProductionMetrics: Efficiency per line ===")
cols, rows = kql_query("""
ProductionMetrics
| summarize MinEff=round(min(Efficiency),2), MaxEff=round(max(Efficiency),2), AvgEff=round(avg(Efficiency),2), Records=count() by LineId
| order by LineId asc
""")
print(f"  {cols}")
for row in rows:
    print(f"  {row}")

# 5. Sensor details (what type is each sensor?)
print("\n=== Lakehouse: Sensor types (from ontology data) ===")
# We can't query lakehouse from KQL, but we know from ingest script:
sensor_info = [
    ("SG-SN-001", "SG-EQ-001", "Temperature", "°C", 1050, 1120),
    ("SG-SN-002", "SG-EQ-001", "Temperature", "°C", 1040, 1110),
    ("SG-SN-003", "SG-EQ-001", "Pressure", "bar", 5, 12),
    ("SG-SN-004", "SG-EQ-001", "Vibration", "mm/s", 8, 25),
    ("SG-SN-005", "SG-EQ-002", "Temperature", "°C", 550, 620),
    ("SG-SN-006", "SG-EQ-002", "Speed", "m/min", 200, 300),
    ("SG-SN-007", "SG-EQ-002", "Vibration", "mm/s", 2, 19),
    ("SG-SN-008", "SG-EQ-003", "Power", "kW", 100, 500),
    ("SG-SN-009", "SG-EQ-004", "Pressure", "mbar", 0.001, 0.01),
    ("SG-SN-010", "SG-EQ-004", "Power", "kW", 10, 200),
    ("SG-SN-011", "SG-EQ-005", "Temperature", "°C", 400, 650),
    ("SG-SN-012", "SG-EQ-006", "Speed", "RPM", 0, 6000),
    ("SG-SN-013", "SG-EQ-006", "Position", "mm", 0, 3210),
    ("SG-SN-014", "SG-EQ-008", "Pressure", "bar", 8, 14),
    ("SG-SN-015", "SG-EQ-008", "Temperature", "°C", 120, 145),
    ("SG-SN-016", "SG-EQ-012", "Temperature", "°C", 1300, 1500),
    ("SG-SN-017", "SG-EQ-013", "Speed", "RPM", 2000, 4000),
    ("SG-SN-018", "SG-EQ-015", "Power", "kW", 500, 2000),
    ("SG-SN-019", "SG-EQ-017", "Temperature", "°C", 580, 680),
    ("SG-SN-020", "SG-EQ-018", "Vibration", "mm/s", 2, 8),
]
for s in sensor_info:
    print(f"  {s[0]} on {s[1]}: {s[2]} ({s[3]}) range [{s[4]}-{s[5]}]")
