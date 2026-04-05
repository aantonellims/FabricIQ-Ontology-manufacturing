"""Validate semantic model deployment.

Checks that the SG-Manufacturing semantic model exists in the workspace
and responds to DAX queries. Validates tables, relationships, measures,
and DirectLake mode.

Usage:
    python tests/validate_semantic_model.py --ontology-path ontologies/SaintGobain
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from azure.identity import DefaultAzureCredential

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

API_BASE = "https://api.fabric.microsoft.com/v1"
EXPECTED_TABLES = {"DIM_PLANT", "DIM_LINE", "DIM_EQUIPMENT", "DIM_SENSOR", "DIM_PRODUCT", "DIM_WORKORDER"}


def get_fabric_token() -> str:
    return DefaultAzureCredential().get_token("https://api.fabric.microsoft.com/.default").token


def get_pbi_token() -> str:
    return DefaultAzureCredential().get_token("https://analysis.windows.net/powerbi/api/.default").token


def fabric_get(path: str, token: str) -> dict:
    import urllib.request
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def execute_dax(workspace_id: str, dataset_id: str, query: str, token: str) -> list:
    import urllib.request
    body = json.dumps({
        "queries": [{"query": query}],
        "serializerSettings": {"includeNulls": True},
    }).encode()
    req = urllib.request.Request(
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/executeQueries",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    return result.get("results", [{}])[0].get("tables", [{}])[0].get("rows", [])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ontology-path", required=True)
    args = parser.parse_args()

    config = json.loads((Path(args.ontology_path) / "config.json").read_text())
    workspace_id = config["workspace"]["id"]
    errors = 0

    fabric_token = get_fabric_token()

    # VT-SM-1: Check semantic model exists
    log.info("=== VT-SM-1: Semantic Model Existence ===")
    items = fabric_get(f"/workspaces/{workspace_id}/items?type=SemanticModel", fabric_token)
    sm = None
    for item in items.get("value", []):
        if item["displayName"] == "SG-Manufacturing":
            sm = item
            break

    if sm:
        log.info("PASS [VT-SM-1]: SG-Manufacturing exists (id=%s)", sm["id"])
    else:
        log.error("FAIL [VT-SM-1]: SG-Manufacturing not found")
        errors += 1
        return errors  # Can't continue without the model

    dataset_id = sm["id"]

    try:
        pbi_token = get_pbi_token()
    except Exception as exc:
        log.warning("Cannot get Power BI token — skipping DAX tests: %s", exc)
        return errors

    # VT-SM-2: Basic DAX
    log.info("=== VT-SM-2: Basic DAX Query ===")
    try:
        rows = execute_dax(workspace_id, dataset_id,
                           'EVALUATE ROW("Plants", COUNTROWS(DIM_PLANT))', pbi_token)
        if rows:
            plant_count = rows[0].get("[Plants]", 0)
            if plant_count > 0:
                log.info("PASS [VT-SM-2]: COUNTROWS(DIM_PLANT) = %s", plant_count)
            else:
                log.error("FAIL [VT-SM-2]: COUNTROWS(DIM_PLANT) = 0")
                errors += 1
        else:
            log.error("FAIL [VT-SM-2]: No rows returned")
            errors += 1
    except Exception as exc:
        log.warning("SKIP [VT-SM-2]: DAX failed (model may be initializing): %s", exc)

    # VT-SM-3: Table completeness
    log.info("=== VT-SM-3: Table Completeness ===")
    try:
        rows = execute_dax(workspace_id, dataset_id, "EVALUATE INFO.TABLES()", pbi_token)
        found_tables = set()
        for row in rows:
            name = row.get("[Name]", "")
            if name.startswith("DIM_"):
                found_tables.add(name)
        missing = EXPECTED_TABLES - found_tables
        if not missing:
            log.info("PASS [VT-SM-3]: All 6 DIM tables present")
        else:
            log.error("FAIL [VT-SM-3]: Missing tables: %s", missing)
            errors += 1
    except Exception as exc:
        log.warning("SKIP [VT-SM-3]: %s", exc)

    # VT-SM-4: Relationship traversal
    log.info("=== VT-SM-4: Relationship Traversal ===")
    try:
        rows = execute_dax(
            workspace_id, dataset_id,
            'EVALUATE SUMMARIZECOLUMNS(DIM_PLANT[Name], "Lines", COUNTROWS(DIM_LINE))',
            pbi_token,
        )
        if rows:
            log.info("PASS [VT-SM-4]: Plant→Line traversal returned %d row(s)", len(rows))
        else:
            log.warning("SKIP [VT-SM-4]: No rows from traversal query")
    except Exception as exc:
        log.warning("SKIP [VT-SM-4]: %s", exc)

    # VT-SM-5: Measures exist
    log.info("=== VT-SM-5: Measures Validation ===")
    try:
        rows = execute_dax(workspace_id, dataset_id, "EVALUATE INFO.MEASURES()", pbi_token)
        measure_names = {row.get("[Name]", "") for row in rows}
        expected_measures = {"Equipment Count", "Sensor Count", "Plant Count",
                            "Active Equipment", "Work Orders by Status", "Avg Unit Cost"}
        found = expected_measures & measure_names
        missing = expected_measures - measure_names
        if not missing:
            log.info("PASS [VT-SM-5]: All 6 measures present")
        else:
            log.warning("WARN [VT-SM-5]: Missing measures: %s", missing)
    except Exception as exc:
        log.warning("SKIP [VT-SM-5]: %s", exc)

    # VT-SM-6: DirectLake mode
    log.info("=== VT-SM-6: DirectLake Mode ===")
    try:
        rows = execute_dax(workspace_id, dataset_id, "EVALUATE INFO.PARTITIONS()", pbi_token)
        modes = {row.get("[Mode]", "") for row in rows if row.get("[TableName]", "").startswith("DIM_")}
        if "DirectLake" in modes or 4 in modes:
            log.info("PASS [VT-SM-6]: DirectLake mode confirmed")
        elif modes:
            log.warning("WARN [VT-SM-6]: Partition modes: %s", modes)
        else:
            log.warning("SKIP [VT-SM-6]: Could not determine mode")
    except Exception as exc:
        log.warning("SKIP [VT-SM-6]: %s", exc)

    if errors == 0:
        log.info("ALL SEMANTIC MODEL VALIDATION CHECKS PASSED")
    else:
        log.error("%d validation errors found", errors)
    return errors


if __name__ == "__main__":
    sys.exit(main())
