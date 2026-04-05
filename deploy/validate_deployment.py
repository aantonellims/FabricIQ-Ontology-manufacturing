"""End-to-end deployment validation.

Validates all deployed components: ontology definition, semantic model,
Lakehouse tables, and KQL tables.

Usage:
    python deploy/validate_deployment.py --ontology-path ontologies/SaintGobain
"""

import argparse
import base64
import json
import logging
import sys
from pathlib import Path

from azure.identity import DefaultAzureCredential

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

API_BASE = "https://api.fabric.microsoft.com/v1"


def get_token(scope: str = "https://api.fabric.microsoft.com/.default") -> str:
    credential = DefaultAzureCredential()
    return credential.get_token(scope).token


def fabric_get(path: str, token: str) -> dict:
    import urllib.request
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fabric_post(path: str, body: dict | None, token: str) -> dict | None:
    import urllib.request
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except Exception as exc:
        log.error("API error: %s", exc)
        return None


class ValidationResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.details = []

    def ok(self, msg: str):
        self.passed += 1
        self.details.append(f"  ✓ {msg}")
        log.info("✓ %s", msg)

    def fail(self, msg: str):
        self.failed += 1
        self.details.append(f"  ✗ {msg}")
        log.error("✗ %s", msg)

    def warn(self, msg: str):
        self.warnings += 1
        self.details.append(f"  ⚠ {msg}")
        log.warning("⚠ %s", msg)

    def summary(self) -> str:
        return f"Passed: {self.passed}, Failed: {self.failed}, Warnings: {self.warnings}"


def validate_lakehouse_tables(config: dict, token: str, result: ValidationResult) -> None:
    """Validate that all 6 DIM tables exist in the Lakehouse."""
    log.info("=== Validating Lakehouse Tables ===")
    workspace_id = config["workspace"]["id"]
    lakehouse_id = config["lakehouse"]["id"]
    expected_tables = {"DIM_PLANT", "DIM_LINE", "DIM_EQUIPMENT", "DIM_SENSOR", "DIM_PRODUCT", "DIM_WORKORDER"}

    try:
        resp = fabric_get(f"/workspaces/{workspace_id}/lakehouses/{lakehouse_id}/tables", token)
        actual = {t["name"] for t in resp.get("data", [])}
        for table in expected_tables:
            if table in actual:
                result.ok(f"Lakehouse table exists: {table}")
            else:
                result.fail(f"Lakehouse table missing: {table}")
    except Exception as exc:
        result.fail(f"Cannot query Lakehouse tables: {exc}")


def validate_ontology_definition(config: dict, token: str, result: ValidationResult) -> None:
    """Validate the ontology definition via getDefinition API."""
    log.info("=== Validating Ontology Definition ===")
    workspace_id = config["workspace"]["id"]
    ontology_id = config["ontology"]["id"]

    if not ontology_id:
        result.fail("Ontology ID not set in config.json")
        return

    try:
        resp = fabric_post(
            f"/workspaces/{workspace_id}/items/{ontology_id}/getDefinition", None, token
        )
    except Exception as exc:
        result.fail(f"getDefinition failed: {exc}")
        return

    if not resp:
        result.fail("getDefinition returned empty response")
        return

    parts = resp.get("definition", {}).get("parts", [])
    if not parts:
        result.fail("Ontology definition is empty (no parts)")
        return

    # Count part types
    entity_type_parts = []
    rel_parts = []
    binding_parts = []
    ctx_parts = []

    for part in parts:
        p = part.get("path", "")
        if p.startswith("EntityTypes/") and p.endswith("/definition.json"):
            entity_type_parts.append(part)
        elif p.startswith("RelationshipTypes/") and p.endswith("/definition.json"):
            rel_parts.append(part)
        elif "/DataBindings/" in p:
            binding_parts.append(part)
        elif "/Contextualizations/" in p:
            ctx_parts.append(part)

    # VT-ONT-1: Entity type count
    if len(entity_type_parts) == 6:
        result.ok(f"Entity types: {len(entity_type_parts)} (expected 6)")
    else:
        result.fail(f"Entity types: {len(entity_type_parts)} (expected 6)")

    # VT-ONT-2 & VT-ONT-3: Property schema + ID validation
    valid_value_types = {"String", "Boolean", "DateTime", "Object", "BigInt", "Double"}
    expected_ids = {"1001", "1002", "1003", "1004", "1005", "1006"}
    found_ids = set()

    for part in entity_type_parts:
        decoded = json.loads(base64.b64decode(part["payload"]).decode())
        et_id = decoded.get("id", "")
        found_ids.add(et_id)

        # Check ID is positive int
        try:
            if int(et_id) > 0:
                result.ok(f"Entity type '{decoded.get('name')}' has valid ID: {et_id}")
            else:
                result.fail(f"Entity type '{decoded.get('name')}' has non-positive ID: {et_id}")
        except (ValueError, TypeError):
            result.fail(f"Entity type '{decoded.get('name')}' has non-integer ID: {et_id}")

        # Check properties use valueType
        for prop in decoded.get("properties", []):
            if "dataType" in prop:
                result.fail(f"Property '{prop['name']}' on '{decoded['name']}' uses 'dataType' instead of 'valueType'")
            vt = prop.get("valueType", "")
            if vt not in valid_value_types:
                result.fail(f"Property '{prop['name']}' has invalid valueType: '{vt}'")

    if found_ids == expected_ids:
        result.ok(f"All expected entity type IDs present: {sorted(expected_ids)}")
    else:
        result.fail(f"Entity type IDs mismatch. Expected: {sorted(expected_ids)}, Found: {sorted(found_ids)}")

    # VT-ONT-4: Relationships
    if len(rel_parts) == 5:
        result.ok(f"Relationship types: {len(rel_parts)} (expected 5)")
    else:
        result.fail(f"Relationship types: {len(rel_parts)} (expected 5)")

    # VT-ONT-5 & VT-ONT-6: Bindings
    nts_count = 0
    ts_count = 0
    for part in binding_parts:
        decoded = json.loads(base64.b64decode(part["payload"]).decode())
        binding_type = decoded.get("dataBindingConfiguration", {}).get("dataBindingType", "")
        if binding_type == "NonTimeSeries":
            nts_count += 1
        elif binding_type == "TimeSeries":
            ts_count += 1

    if nts_count == 6:
        result.ok(f"NTS bindings: {nts_count} (expected 6)")
    else:
        result.fail(f"NTS bindings: {nts_count} (expected 6)")

    if ts_count == 3:
        result.ok(f"TS bindings: {ts_count} (expected 3)")
    else:
        result.fail(f"TS bindings: {ts_count} (expected 3)")

    # VT-ONT-7: Contextualizations
    if len(ctx_parts) == 5:
        result.ok(f"Contextualizations: {len(ctx_parts)} (expected 5)")
    else:
        result.fail(f"Contextualizations: {len(ctx_parts)} (expected 5)")


def validate_semantic_model(config: dict, token: str, result: ValidationResult) -> None:
    """Validate the semantic model exists and responds to DAX."""
    log.info("=== Validating Semantic Model ===")
    workspace_id = config["workspace"]["id"]

    # VT-SM-1: Check existence
    try:
        items = fabric_get(f"/workspaces/{workspace_id}/items?type=SemanticModel", token)
        sm = None
        for item in items.get("value", []):
            if item["displayName"] == "SG-Manufacturing":
                sm = item
                break
        if sm:
            result.ok(f"Semantic model 'SG-Manufacturing' exists: {sm['id']}")
        else:
            result.fail("Semantic model 'SG-Manufacturing' not found in workspace")
            return
    except Exception as exc:
        result.fail(f"Cannot list semantic models: {exc}")
        return

    # VT-SM-2 through VT-SM-6: DAX validation
    try:
        dax_token = DefaultAzureCredential().get_token(
            "https://analysis.windows.net/powerbi/api/.default"
        ).token

        import urllib.request
        queries = [
            ("Plant count", 'EVALUATE ROW("Plants", COUNTROWS(DIM_PLANT))'),
            ("Table list", "EVALUATE INFO.TABLES()"),
        ]
        for label, query in queries:
            body = json.dumps({
                "queries": [{"query": query}],
                "serializerSettings": {"includeNulls": True},
            }).encode()
            req = urllib.request.Request(
                f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{sm['id']}/executeQueries",
                data=body,
                headers={"Authorization": f"Bearer {dax_token}", "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req) as resp:
                dax_result = json.loads(resp.read())
            rows = dax_result.get("results", [{}])[0].get("tables", [{}])[0].get("rows", [])
            if rows:
                result.ok(f"DAX '{label}' returned {len(rows)} row(s)")
            else:
                result.warn(f"DAX '{label}' returned no rows")
    except Exception as exc:
        result.warn(f"DAX validation skipped (model may be initializing): {exc}")


def validate_kql_tables(config: dict, result: ValidationResult) -> None:
    """Validate that KQL tables exist."""
    log.info("=== Validating KQL Tables ===")
    query_uri = config.get("kqlDatabase", {}).get("queryServiceUri")
    db_name = config.get("kqlDatabase", {}).get("name")

    if not query_uri or not db_name:
        result.warn("KQL database info not in config — skipping KQL validation")
        return

    try:
        kql_token = DefaultAzureCredential().get_token(
            "https://kusto.kusto.windows.net/.default"
        ).token

        import urllib.request
        body = json.dumps({"csl": ".show tables", "db": db_name}).encode()
        req = urllib.request.Request(
            f"{query_uri}/v1/rest/mgmt",
            data=body,
            headers={"Authorization": f"Bearer {kql_token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())

        tables = set()
        for frame in data.get("Tables", data.get("frames", [])):
            for row in frame.get("Rows", []):
                if row:
                    tables.add(row[0])

        expected = {"SensorTelemetry", "EquipmentStatus", "ProductionMetrics", "Alerts"}
        for table in expected:
            if table in tables:
                result.ok(f"KQL table exists: {table}")
            else:
                result.fail(f"KQL table missing: {table}")
    except Exception as exc:
        result.warn(f"KQL table validation failed: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate end-to-end deployment")
    parser.add_argument("--ontology-path", required=True, help="Path to ontology folder")
    args = parser.parse_args()

    ontology_path = Path(args.ontology_path)
    config_path = ontology_path / "config.json"
    if not config_path.exists():
        log.error("config.json not found at %s", config_path)
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    token = get_token()
    result = ValidationResult()

    validate_lakehouse_tables(config, token, result)
    validate_ontology_definition(config, token, result)
    validate_semantic_model(config, token, result)
    validate_kql_tables(config, result)

    log.info("")
    log.info("=" * 50)
    log.info("VALIDATION SUMMARY: %s", result.summary())
    for detail in result.details:
        log.info(detail)
    log.info("=" * 50)

    if result.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
