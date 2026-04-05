"""Ingest sample telemetry data into KQL tables for all equipment, sensors, lines.

Creates realistic time-series data covering the last 24 hours so the Data Agent
can answer time-series queries against the Eventhouse.
"""
import json, random, urllib.request
from datetime import datetime, timezone, timedelta
from azure.identity import DefaultAzureCredential

with open("ontologies/SaintGobain/config.json") as f:
    config = json.load(f)

QUERY_URI = config["kqlDatabase"]["queryServiceUri"]
DB_NAME = config["kqlDatabase"]["name"]

token = DefaultAzureCredential().get_token("https://api.kusto.windows.net/.default").token
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def kql_mgmt(csl):
    body = json.dumps({"db": DB_NAME, "csl": csl}).encode()
    req = urllib.request.Request(f"{QUERY_URI}/v1/rest/mgmt", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status
    except Exception as e:
        print(f"  WARN: {e}")
        return None


# Equipment IDs and their characteristics
equipment = [
    ("SG-EQ-001", "Float Bath"),       ("SG-EQ-002", "Annealing Lehr"),
    ("SG-EQ-003", "Tin Bath Heater"),   ("SG-EQ-004", "Magnetron Sputter"),
    ("SG-EQ-005", "CVD Reactor"),       ("SG-EQ-006", "Cutting Table CNC"),
    ("SG-EQ-007", "Sorting Robot"),     ("SG-EQ-008", "Autoclave Unit"),
    ("SG-EQ-009", "PVB Applicator"),    ("SG-EQ-010", "Float Bath 2"),
    ("SG-EQ-011", "Mirror Coating"),    ("SG-EQ-012", "Cupola Furnace"),
    ("SG-EQ-013", "Fiberizing Spinner"),("SG-EQ-014", "Packaging Robot"),
    ("SG-EQ-015", "Mortar Mixer"),      ("SG-EQ-016", "Bagging Machine"),
    ("SG-EQ-017", "Bending Furnace"),   ("SG-EQ-018", "Tempering Furnace"),
]

# Sensor config: (id, equipment_id, min, max)
sensors = [
    ("SG-SN-001", "SG-EQ-001", 1050, 1120), ("SG-SN-002", "SG-EQ-001", 1040, 1110),
    ("SG-SN-003", "SG-EQ-001", 5, 12),      ("SG-SN-004", "SG-EQ-001", 8, 25),
    ("SG-SN-005", "SG-EQ-002", 550, 620),   ("SG-SN-006", "SG-EQ-002", 200, 300),
    ("SG-SN-007", "SG-EQ-002", 2, 19),      ("SG-SN-008", "SG-EQ-003", 100, 500),
    ("SG-SN-009", "SG-EQ-004", 0.001, 0.01),("SG-SN-010", "SG-EQ-004", 10, 200),
    ("SG-SN-011", "SG-EQ-005", 400, 650),   ("SG-SN-012", "SG-EQ-006", 0, 6000),
    ("SG-SN-013", "SG-EQ-006", 0, 3210),    ("SG-SN-014", "SG-EQ-008", 8, 14),
    ("SG-SN-015", "SG-EQ-008", 120, 145),   ("SG-SN-016", "SG-EQ-012", 1300, 1500),
    ("SG-SN-017", "SG-EQ-013", 2000, 4000), ("SG-SN-018", "SG-EQ-015", 500, 2000),
    ("SG-SN-019", "SG-EQ-017", 580, 680),   ("SG-SN-020", "SG-EQ-018", 2, 8),
]

lines = [f"SG-LN-{i:03d}" for i in range(1, 13)]

now = datetime.now(timezone.utc)
statuses = ["Operating", "Operating", "Operating", "Operating", "Idle", "Maintenance"]
qualities = ["Good", "Good", "Good", "Fair", "Poor"]
severities = ["Low", "Medium", "High", "Critical"]

print("=== Ingesting Sample Telemetry ===")

# Generate 24h of data, one reading per 30 min = 48 points per entity
intervals = 48
dt = timedelta(minutes=30)

# --- SensorTelemetry ---
print(f"\n[1/4] SensorTelemetry — {len(sensors)} sensors x {intervals} readings...")
batch_size = 5  # sensors per ingest command
for batch_start in range(0, len(sensors), batch_size):
    batch_sensors = sensors[batch_start:batch_start + batch_size]
    rows = []
    for sid, _eid, mn, mx in batch_sensors:
        mid = (mn + mx) / 2
        std = (mx - mn) / 6
        for i in range(intervals):
            ts = (now - timedelta(minutes=30 * (intervals - i))).strftime("%Y-%m-%dT%H:%M:%SZ")
            val = round(random.gauss(mid, std), 2)
            val = max(mn * 0.95, min(mx * 1.05, val))
            q = random.choice(qualities)
            rows.append(f"{sid},datetime({ts}),{val},{q}")
    cmd = ".ingest inline into table SensorTelemetry <|\n" + "\n".join(rows)
    kql_mgmt(cmd)
    print(f"  Batch {batch_start // batch_size + 1}: {len(rows)} rows")

# --- EquipmentStatus ---
print(f"\n[2/4] EquipmentStatus — {len(equipment)} equipment x {intervals} readings...")
for batch_start in range(0, len(equipment), 6):
    batch_eq = equipment[batch_start:batch_start + 6]
    rows = []
    for eid, _name in batch_eq:
        run_base = random.uniform(5000, 20000)
        down_base = random.uniform(10, 200)
        for i in range(intervals):
            ts = (now - timedelta(minutes=30 * (intervals - i))).strftime("%Y-%m-%dT%H:%M:%SZ")
            st = random.choice(statuses)
            run_min = round(run_base + i * 0.5 + random.uniform(-2, 2), 1)
            down_min = round(down_base + (random.uniform(0, 5) if st != "Operating" else 0), 1)
            rows.append(f"{eid},datetime({ts}),{run_min},{down_min},{st}")
    cmd = ".ingest inline into table EquipmentStatus <|\n" + "\n".join(rows)
    kql_mgmt(cmd)
    print(f"  Batch {batch_start // 6 + 1}: {len(rows)} rows")

# --- ProductionMetrics ---
print(f"\n[3/4] ProductionMetrics — {len(lines)} lines x {intervals} readings...")
rows = []
for lid in lines:
    cap = random.randint(1000, 3000)
    for i in range(intervals):
        ts = (now - timedelta(minutes=30 * (intervals - i))).strftime("%Y-%m-%dT%H:%M:%SZ")
        eff = round(random.uniform(0.7, 0.95), 3)
        units = random.randint(int(cap * 0.01), int(cap * 0.04))
        cycle = round(random.uniform(15, 60), 1)
        rows.append(f"{lid},datetime({ts}),{eff},{units},{cycle}")
cmd = ".ingest inline into table ProductionMetrics <|\n" + "\n".join(rows)
kql_mgmt(cmd)
print(f"  {len(rows)} rows")

# --- Alerts ---
print(f"\n[4/4] Alerts — generating sample alerts...")
rows = []
for i in range(30):
    ts = (now - timedelta(minutes=random.randint(1, 1440))).strftime("%Y-%m-%dT%H:%M:%SZ")
    entity = random.choice(["SG-EQ-" + f"{random.randint(1,18):03d}", "SG-SN-" + f"{random.randint(1,20):03d}"])
    etype = "Equipment" if entity.startswith("SG-EQ") else "Sensor"
    sev = random.choice(severities)
    resolved = "true" if random.random() > 0.3 else "false"
    rows.append(f"ALT-{i+1:04d},{entity},{etype},datetime({ts}),{sev},Threshold exceeded on {etype} {entity},{resolved}")
cmd = ".ingest inline into table Alerts <|\n" + "\n".join(rows)
kql_mgmt(cmd)
print(f"  {len(rows)} rows")

print("\n=== Ingestion Complete ===")
print(f"  SensorTelemetry:   {len(sensors) * intervals} rows")
print(f"  EquipmentStatus:   {len(equipment) * intervals} rows")
print(f"  ProductionMetrics: {len(lines) * intervals} rows")
print(f"  Alerts:            30 rows")
