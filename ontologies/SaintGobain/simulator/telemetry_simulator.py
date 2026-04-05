"""
Saint-Gobain Manufacturing Ontology — Telemetry Simulator

Generates realistic sensor readings, equipment status, production metrics,
and alerts every 10 seconds, streaming into KQL tables via Kusto ingestion.

Usage:
    python simulator/telemetry_simulator.py --cluster <queryServiceUri> --database <dbName>

Auth: Uses Azure CLI credential (run 'az login' first).
"""

import argparse
import csv
import json
import os
import random
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from azure.identity import AzureCliCredential
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.kusto.ingest import (
    IngestionProperties,
    QueuedIngestClient,
    ReportLevel,
)

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------
INTERVAL_SECONDS = 10
RUNNING = True

QUALITY_CHOICES = ["Good"] * 90 + ["Uncertain"] * 8 + ["Bad"] * 2
EQUIPMENT_STATUS_WEIGHTS = {"Operating": 75, "Idle": 15, "Maintenance": 10}
ALERT_PROBABILITY = 0.05
SEVERITY_WEIGHTS = {"Critical": 10, "Warning": 40, "Info": 50}


def _weighted_choice(weights: dict) -> str:
    population = list(weights.keys())
    w = list(weights.values())
    return random.choices(population, weights=w, k=1)[0]


def signal_handler(_sig, _frame):
    global RUNNING
    print("\n[Ctrl+C] Stopping simulator...")
    RUNNING = False


signal.signal(signal.SIGINT, signal_handler)

# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_csv(filepath: str) -> list[dict]:
    with open(filepath, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_metadata(data_dir: str):
    sensors = load_csv(os.path.join(data_dir, "sensors.csv"))
    equipment = load_csv(os.path.join(data_dir, "equipment.csv"))
    lines = load_csv(os.path.join(data_dir, "lines.csv"))
    return sensors, equipment, lines

# ---------------------------------------------------------------------------
# Value generators
# ---------------------------------------------------------------------------

def generate_sensor_reading(sensor: dict) -> dict:
    min_val = float(sensor["MinValue"])
    max_val = float(sensor["MaxValue"])
    mid = (min_val + max_val) / 2.0
    std = (max_val - min_val) / 6.0  # 99.7% within range
    value = random.gauss(mid, std)
    value = max(min_val * 0.95, min(max_val * 1.05, value))  # slight overshoot ok
    return {
        "SensorId": sensor["SensorId"],
        "Timestamp": datetime.now(timezone.utc).isoformat(),
        "Value": round(value, 2),
        "Unit": sensor["Unit"],
        "Quality": random.choice(QUALITY_CHOICES),
    }


# Per-equipment state kept across intervals
_equipment_state: dict[str, dict] = {}


def generate_equipment_status(equip: dict) -> dict:
    eid = equip["EquipmentId"]
    if eid not in _equipment_state:
        _equipment_state[eid] = {
            "RunHours": round(random.uniform(5000, 20000), 1),
            "CycleCount": random.randint(10000, 100000),
        }
    state = _equipment_state[eid]
    status = _weighted_choice(EQUIPMENT_STATUS_WEIGHTS)
    if status == "Operating":
        state["RunHours"] = round(state["RunHours"] + INTERVAL_SECONDS / 3600, 2)
        state["CycleCount"] += random.randint(0, 3)
    return {
        "EquipmentId": eid,
        "Timestamp": datetime.now(timezone.utc).isoformat(),
        "Status": status,
        "RunHours": state["RunHours"],
        "CycleCount": state["CycleCount"],
    }


def generate_production_metrics(line: dict) -> dict:
    capacity = int(line.get("Capacity", 1000))
    output_units = random.randint(
        int(capacity * 0.005), int(capacity * 0.02)
    )  # per 10s slice
    return {
        "LineId": line["LineId"],
        "Timestamp": datetime.now(timezone.utc).isoformat(),
        "OutputUnits": output_units,
        "DefectRate": round(random.uniform(0.005, 0.05), 4),
        "OEE": round(random.uniform(0.65, 0.92), 3),
    }


_alert_counter = 0


def maybe_generate_alert(entity_id: str, entity_type: str) -> dict | None:
    global _alert_counter
    if random.random() > ALERT_PROBABILITY:
        return None
    _alert_counter += 1
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    return {
        "AlertId": f"ALT-{date_str}-{_alert_counter:04d}",
        "EntityId": entity_id,
        "EntityType": entity_type,
        "Timestamp": datetime.now(timezone.utc).isoformat(),
        "Severity": _weighted_choice(SEVERITY_WEIGHTS),
        "Message": f"Threshold exceeded on {entity_type} {entity_id}",
        "IsResolved": False,
    }

# ---------------------------------------------------------------------------
# Ingestion helpers
# ---------------------------------------------------------------------------

def dict_to_csv_line(d: dict) -> str:
    """Convert a dict to a CSV row string (values only)."""
    return ",".join(str(v) for v in d.values())


def build_csv_payload(rows: list[dict]) -> str:
    if not rows:
        return ""
    header = ",".join(rows[0].keys())
    lines = [header] + [dict_to_csv_line(r) for r in rows]
    return "\n".join(lines)


def ingest_via_streaming(
    client: KustoClient, database: str, table: str, rows: list[dict]
):
    """Ingest rows into a KQL table via streaming ingestion REST call."""
    if not rows:
        return
    # Build a JSON array payload for streaming ingestion
    payload = json.dumps(rows)
    try:
        client.execute_streaming_ingest(database, table, payload, "json")
    except Exception as e:
        print(f"  [WARN] Streaming ingest to {table} failed: {e}")

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SG Manufacturing Telemetry Simulator")
    parser.add_argument("--cluster", required=True, help="KQL query service URI")
    parser.add_argument("--database", required=True, help="KQL database name")
    parser.add_argument(
        "--data-dir",
        default=str(Path(__file__).resolve().parent.parent / "data"),
        help="Path to CSV data directory",
    )
    parser.add_argument(
        "--interval", type=int, default=INTERVAL_SECONDS, help="Seconds between readings"
    )
    args = parser.parse_args()

    print("=== SG Manufacturing Telemetry Simulator ===")
    print(f"  Cluster:  {args.cluster}")
    print(f"  Database: {args.database}")
    print(f"  Interval: {args.interval}s")
    print(f"  Data dir: {args.data_dir}")

    # Load metadata
    sensors, equipment, lines = load_metadata(args.data_dir)
    print(f"  Sensors:    {len(sensors)}")
    print(f"  Equipment:  {len(equipment)}")
    print(f"  Lines:      {len(lines)}")

    # Build Kusto client with Azure CLI auth
    credential = AzureCliCredential()
    kcsb = KustoConnectionStringBuilder.with_azure_token_credential(
        args.cluster, credential
    )
    client = KustoClient(kcsb)

    print("\nStreaming telemetry... Press Ctrl+C to stop.\n")

    tick = 0
    while RUNNING:
        tick += 1
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")

        # Generate sensor telemetry
        sensor_rows = [generate_sensor_reading(s) for s in sensors if s.get("Status") == "Active"]
        ingest_via_streaming(client, args.database, "SensorTelemetry", sensor_rows)

        # Generate equipment status
        equip_rows = [generate_equipment_status(e) for e in equipment]
        ingest_via_streaming(client, args.database, "EquipmentStatus", equip_rows)

        # Generate production metrics
        line_rows = [generate_production_metrics(ln) for ln in lines if ln.get("Status") == "Active"]
        ingest_via_streaming(client, args.database, "ProductionMetrics", line_rows)

        # Generate alerts
        alerts = []
        for s in sensors:
            alert = maybe_generate_alert(s["SensorId"], "Sensor")
            if alert:
                alerts.append(alert)
        for e in equipment:
            alert = maybe_generate_alert(e["EquipmentId"], "Equipment")
            if alert:
                alerts.append(alert)
        for ln in lines:
            alert = maybe_generate_alert(ln["LineId"], "Line")
            if alert:
                alerts.append(alert)
        if alerts:
            ingest_via_streaming(client, args.database, "Alerts", alerts)

        print(
            f"[{ts}] Tick {tick}: "
            f"{len(sensor_rows)} sensors, {len(equip_rows)} equipment, "
            f"{len(line_rows)} lines, {len(alerts)} alerts"
        )

        time.sleep(args.interval)

    print("\nSimulator stopped.")
    client.close()


if __name__ == "__main__":
    main()
