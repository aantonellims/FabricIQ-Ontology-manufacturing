"""Deploy ontology definition to Fabric via updateDefinition API.

Reads entity types, relationships, bindings, and contextualizations from
the ontology folder, injects runtime IDs from config.json, Base64-encodes
each part, and pushes the full definition in a single API call.

Usage:
    python deploy/deploy_ontology_definition.py --ontology-path ontologies/SaintGobain
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


def fabric_post(path: str, body: dict | None, token: str, follow_result: bool = False) -> dict | None:
    """POST to Fabric API with LRO handling. If follow_result=True, fetches /result after LRO."""
    import urllib.request
    import urllib.error
    import time as _time

    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )

    def _handle_lro(location, retry_after):
        log.info("LRO accepted, polling in %ds...", retry_after)
        _time.sleep(retry_after)
        for attempt in range(20):
            poll_req = urllib.request.Request(location, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(poll_req) as pr:
                poll_data = json.loads(pr.read().decode() or "{}")
                status = poll_data.get("status", "")
                if status == "Succeeded":
                    if follow_result:
                        rr_req = urllib.request.Request(location + "/result", headers={"Authorization": f"Bearer {token}"})
                        with urllib.request.urlopen(rr_req) as rr:
                            return json.loads(rr.read().decode() or "{}")
                    return poll_data
                elif status == "Failed":
                    log.error("LRO failed: %s", poll_data.get("error"))
                    return poll_data
                log.info("  Still processing (%s, attempt %d)...", status, attempt + 1)
                _time.sleep(5)
        return None

    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            if resp.status == 202:
                loc = resp.headers.get("Location", "")
                ra = int(resp.headers.get("Retry-After", "10"))
                if loc:
                    return _handle_lro(loc, ra)
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode() if exc.fp else ""
        if exc.code == 202:
            loc = exc.headers.get("Location", "")
            ra = int(exc.headers.get("Retry-After", "10"))
            if loc:
                return _handle_lro(loc, ra)
            return None
        log.error("HTTP %d on POST %s: %s", exc.code, path, err_body[:500])
        raise


def b64(obj: dict) -> str:
    return base64.b64encode(json.dumps(obj, indent=2).encode()).decode()


def inject_runtime_values(text: str, config: dict) -> str:
    """Replace placeholder tokens with actual IDs from config."""
    workspace_id = config["workspace"]["id"]
    lakehouse_id = config["lakehouse"]["id"]
    eventhouse_id = config["eventhouse"]["id"]
    kql_query_uri = config["kqlDatabase"]["queryServiceUri"]
    kql_db_name = config["kqlDatabase"]["name"]

    text = text.replace("__WORKSPACE_ID__", workspace_id)
    text = text.replace("__LAKEHOUSE_ID__", lakehouse_id)
    text = text.replace("__EVENTHOUSE_ID__", eventhouse_id)
    text = text.replace("__KQL_QUERY_URI__", kql_query_uri)
    text = text.replace("__KQL_DB_NAME__", kql_db_name)
    return text


def load_json_dir(directory: Path, config: dict) -> list[dict]:
    """Load all JSON files from a directory, injecting runtime values."""
    results = []
    if not directory.exists():
        return results
    for f in sorted(directory.glob("*.json")):
        raw = inject_runtime_values(f.read_text(encoding="utf-8"), config)
        results.append(json.loads(raw))
    return results


def build_definition_parts(ontology_path: Path, config: dict) -> list[dict]:
    """Build the definition.parts array for updateDefinition API."""
    parts = []

    # .platform
    platform = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Ontology", "displayName": config["ontology"]["name"]},
        "config": {"version": "2.0", "logicalId": "00000000-0000-0000-0000-000000000000"},
    }
    parts.append({"path": ".platform", "payload": b64(platform), "payloadType": "InlineBase64"})

    # definition.json (empty object)
    parts.append({"path": "definition.json", "payload": b64({}), "payloadType": "InlineBase64"})

    ont = ontology_path / "ontology"

    # Entity types + their data bindings
    entity_types = load_json_dir(ont / "entity-types", config)
    nts_bindings = load_json_dir(ont / "bindings" / "nontimeseries", config)
    ts_bindings = load_json_dir(ont / "bindings" / "timeseries", config)

    # Index bindings by entity type ID
    all_bindings: dict[str, list[dict]] = {}
    for binding in nts_bindings + ts_bindings:
        et_id = binding.get("entityTypeId", "unknown")
        all_bindings.setdefault(et_id, []).append(binding)

    for et in entity_types:
        et_id = et["id"]
        parts.append({
            "path": f"EntityTypes/{et_id}/definition.json",
            "payload": b64(et),
            "payloadType": "InlineBase64",
        })
        # Add data bindings for this entity type
        for binding in all_bindings.get(et_id, []):
            binding_id = binding["id"]
            # Strip entityTypeId from payload - it's determined by path, not JSON field
            binding_payload = {k: v for k, v in binding.items() if k != "entityTypeId"}
            parts.append({
                "path": f"EntityTypes/{et_id}/DataBindings/{binding_id}.json",
                "payload": b64(binding_payload),
                "payloadType": "InlineBase64",
            })

    # Relationship types
    relationships = load_json_dir(ont / "relationships", config)
    for rel in relationships:
        rel_id = rel["id"]
        parts.append({
            "path": f"RelationshipTypes/{rel_id}/definition.json",
            "payload": b64(rel),
            "payloadType": "InlineBase64",
        })

    # Contextualizations (under their relationship type)
    contextualizations = load_json_dir(ont / "contextualizations", config)
    for ctx in contextualizations:
        rel_id = ctx.get("relationshipTypeId", "unknown")
        ctx_id = ctx["id"]
        # Strip relationshipTypeId from payload - it's determined by path, not JSON field
        ctx_payload = {k: v for k, v in ctx.items() if k != "relationshipTypeId"}
        parts.append({
            "path": f"RelationshipTypes/{rel_id}/Contextualizations/{ctx_id}.json",
            "payload": b64(ctx_payload),
            "payloadType": "InlineBase64",
        })

    return parts


def push_definition(workspace_id: str, ontology_id: str, parts: list[dict], token: str) -> None:
    """Call updateDefinition API."""
    payload = {"definition": {"parts": parts}}
    log.info("Pushing ontology definition (%d parts)...", len(parts))
    fabric_post(f"/workspaces/{workspace_id}/ontologies/{ontology_id}/updateDefinition", payload, token)
    log.info("Ontology definition pushed successfully.")


def validate_definition(workspace_id: str, ontology_id: str, token: str) -> dict:
    """Call getDefinition and validate the response."""
    log.info("Validating via getDefinition...")
    result = fabric_post(f"/workspaces/{workspace_id}/ontologies/{ontology_id}/getDefinition", None, token, follow_result=True)
    if not result:
        log.warning("getDefinition returned empty response")
        return {}

    def_parts = result.get("definition", {}).get("parts", [])
    counts = {
        "entity_types": 0,
        "relationships": 0,
        "data_bindings": 0,
        "contextualizations": 0,
    }
    for part in def_parts:
        p = part.get("path", "")
        if "/definition.json" in p and p.startswith("EntityTypes/"):
            counts["entity_types"] += 1
        elif "/definition.json" in p and p.startswith("RelationshipTypes/"):
            counts["relationships"] += 1
        elif "/DataBindings/" in p:
            counts["data_bindings"] += 1
        elif "/Contextualizations/" in p:
            counts["contextualizations"] += 1

    log.info("getDefinition counts: %s", json.dumps(counts))

    # Validate entity type payloads
    for part in def_parts:
        p = part.get("path", "")
        if p.startswith("EntityTypes/") and p.endswith("/definition.json"):
            decoded = json.loads(base64.b64decode(part["payload"]).decode())
            et_id = decoded.get("id", "")
            if not et_id or int(et_id) <= 0:
                log.error("Entity type has invalid ID: %s", et_id)
            for prop in decoded.get("properties", []):
                if "dataType" in prop and "valueType" not in prop:
                    log.error("Property '%s' uses 'dataType' instead of 'valueType'", prop.get("name"))
                vt = prop.get("valueType", "")
                if vt not in ("String", "Boolean", "DateTime", "Object", "BigInt", "Double"):
                    log.error("Property '%s' has invalid valueType: '%s'", prop.get("name"), vt)

    expected = {"entity_types": 6, "relationships": 5, "data_bindings": 9, "contextualizations": 5}
    for key, expected_count in expected.items():
        if counts[key] != expected_count:
            log.warning("Expected %d %s, got %d", expected_count, key, counts[key])
        else:
            log.info("✓ %s: %d (expected %d)", key, counts[key], expected_count)

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy ontology definition via updateDefinition API")
    parser.add_argument("--ontology-path", required=True, help="Path to ontology folder")
    args = parser.parse_args()

    ontology_path = Path(args.ontology_path)
    config_path = ontology_path / "config.json"
    if not config_path.exists():
        log.error("config.json not found at %s", config_path)
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    workspace_id = config["workspace"]["id"]
    ontology_id = config["ontology"]["id"]

    if not ontology_id:
        log.error("ontology.id is empty in config.json")
        sys.exit(1)

    token = get_token()

    # Build definition parts
    parts = build_definition_parts(ontology_path, config)
    log.info("Built %d definition parts", len(parts))

    # Check if this is a first push or update
    try:
        existing = fabric_post(
            f"/workspaces/{workspace_id}/ontologies/{ontology_id}/getDefinition", None, token, follow_result=True
        )
        existing_parts = existing.get("definition", {}).get("parts", []) if existing else []
        if existing_parts:
            log.info("Ontology has existing definition (%d parts) — will overwrite", len(existing_parts))
        else:
            log.info("Ontology is empty — first push")
    except Exception:
        log.info("Ontology appears empty — first push")

    # Push
    push_definition(workspace_id, ontology_id, parts, token)

    # Validate
    validate_definition(workspace_id, ontology_id, token)

    log.info("Ontology definition deployment complete.")


if __name__ == "__main__":
    main()
