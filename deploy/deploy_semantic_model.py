"""Deploy DirectLake semantic model to Microsoft Fabric.

Reads model.bim from ontologies/<ontology>/semantic-model/, injects the
Lakehouse SQL endpoint connection string, and pushes via the Fabric
updateDefinition API.

Usage:
    python deploy/deploy_semantic_model.py --ontology-path ontologies/SaintGobain
"""

import argparse
import base64
import json
import logging
import sys
import time
from pathlib import Path

from azure.identity import DefaultAzureCredential

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

API_BASE = "https://api.fabric.microsoft.com/v1"
SEMANTIC_MODEL_NAME = "SG-Manufacturing"


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


def fabric_post(path: str, body: dict | None, token: str, method: str = "POST") -> dict | None:
    import urllib.request
    import urllib.error
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method,
    )

    def _handle_lro(location, retry_after):
        time.sleep(retry_after)
        for i in range(30):
            poll_req = urllib.request.Request(location, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(poll_req) as pr:
                poll_data = json.loads(pr.read().decode() or "{}")
                status = poll_data.get("status", "")
                if status == "Succeeded":
                    return poll_data
                elif status == "Failed":
                    log.error("LRO failed: %s", poll_data.get("error"))
                    return poll_data
                log.info("  Processing... (%s, attempt %d)", status, i + 1)
                time.sleep(5)
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
        log.error("HTTP %d on %s %s: %s", exc.code, method, path, err_body[:500])
        raise


def b64(payload: str | dict) -> str:
    text = json.dumps(payload, indent=2) if isinstance(payload, dict) else payload
    return base64.b64encode(text.encode()).decode()


# ── Lakehouse SQL endpoint discovery ──────────────────────────────
def get_sql_endpoint(workspace_id: str, lakehouse_id: str, token: str) -> tuple[str, str]:
    """Return (connection_string, endpoint_id) for the Lakehouse SQL endpoint."""
    log.info("Querying Lakehouse SQL endpoint...")
    max_attempts = 12
    for attempt in range(1, max_attempts + 1):
        info = fabric_get(f"/workspaces/{workspace_id}/lakehouses/{lakehouse_id}", token)
        props = info.get("properties", {})
        sql_ep = props.get("sqlEndpointProperties", {})
        conn = sql_ep.get("connectionString")
        ep_id = sql_ep.get("id")
        status = sql_ep.get("provisioningStatus", "")
        if conn and ep_id and status.lower() == "success":
            log.info("SQL endpoint ready: %s", conn)
            return conn, ep_id
        log.info("  Attempt %d/%d – endpoint status: %s", attempt, max_attempts, status)
        time.sleep(10)
    raise RuntimeError("Lakehouse SQL endpoint not ready after polling")


# ── Semantic model CRUD ───────────────────────────────────────────
def find_or_create_semantic_model(workspace_id: str, model_bim: str, token: str) -> str:
    """Find existing or create new SemanticModel item with definition. Returns item ID."""
    items = fabric_get(f"/workspaces/{workspace_id}/items?type=SemanticModel", token)
    for item in items.get("value", []):
        if item["displayName"] == SEMANTIC_MODEL_NAME:
            log.info("Found existing semantic model: %s", item["id"])
            return item["id"]

    log.info("Creating semantic model '%s' with definition...", SEMANTIC_MODEL_NAME)
    platform = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": SEMANTIC_MODEL_NAME},
        "config": {"version": "2.0", "logicalId": "00000000-0000-0000-0000-000000000000"},
    }
    pbism = {"version": "1.0"}
    create_body = {
        "displayName": SEMANTIC_MODEL_NAME,
        "type": "SemanticModel",
        "definition": {
            "parts": [
                {"path": ".platform", "payload": b64(platform), "payloadType": "InlineBase64"},
                {"path": "definition.pbism", "payload": b64(pbism), "payloadType": "InlineBase64"},
                {"path": "model.bim", "payload": b64(model_bim), "payloadType": "InlineBase64"},
            ]
        },
    }
    result = fabric_post(f"/workspaces/{workspace_id}/semanticModels", create_body, token)
    if result and "id" in result:
        sm_id = result["id"]
    elif result and result.get("status") == "Succeeded":
        # LRO completed - need to find the item
        items2 = fabric_get(f"/workspaces/{workspace_id}/items?type=SemanticModel", token)
        sm_item = next((i for i in items2.get("value", []) if i["displayName"] == SEMANTIC_MODEL_NAME), None)
        sm_id = sm_item["id"] if sm_item else None
        if not sm_id:
            raise RuntimeError("Semantic model created but not found after LRO")
    else:
        raise RuntimeError(f"Failed to create semantic model: {result}")
    log.info("Created semantic model: %s", sm_id)
    return sm_id


def push_definition(workspace_id: str, item_id: str, model_bim: str, token: str) -> None:
    """Push model.bim via updateDefinition API."""
    platform = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": SEMANTIC_MODEL_NAME},
        "config": {"version": "2.0", "logicalId": "00000000-0000-0000-0000-000000000000"},
    }
    pbism = {"version": "1.0"}

    payload = {
        "definition": {
            "parts": [
                {"path": ".platform", "payload": b64(platform), "payloadType": "InlineBase64"},
                {"path": "definition.pbism", "payload": b64(pbism), "payloadType": "InlineBase64"},
                {"path": "model.bim", "payload": b64(model_bim), "payloadType": "InlineBase64"},
            ]
        }
    }
    log.info("Pushing semantic model definition (%d bytes)...", len(model_bim))
    fabric_post(f"/workspaces/{workspace_id}/semanticModels/{item_id}/updateDefinition", payload, token)
    log.info("Definition pushed successfully.")


# ── DAX validation ────────────────────────────────────────────────
def validate_dax(workspace_id: str, dataset_id: str, token: str) -> None:
    """Execute a test DAX query to verify DirectLake connectivity."""
    dax_token = get_token("https://analysis.windows.net/powerbi/api/.default")
    import urllib.request
    body = json.dumps({
        "queries": [{"query": "EVALUATE ROW(\"Plants\", COUNTROWS(DIM_PLANT))"}],
        "serializerSettings": {"includeNulls": True},
    }).encode()
    req = urllib.request.Request(
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/executeQueries",
        data=body,
        headers={"Authorization": f"Bearer {dax_token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        rows = result.get("results", [{}])[0].get("tables", [{}])[0].get("rows", [])
        if rows:
            log.info("DAX validation result: %s", rows[0])
        else:
            log.warning("DAX returned no rows — model may still be initialising")
    except Exception as exc:
        log.warning("DAX validation skipped (model may need time to initialise): %s", exc)


# ── Main ──────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy DirectLake semantic model")
    parser.add_argument("--ontology-path", required=True, help="Path to ontology folder (e.g. ontologies/SaintGobain)")
    args = parser.parse_args()

    ontology_path = Path(args.ontology_path)
    config_path = ontology_path / "config.json"
    model_path = ontology_path / "semantic-model" / "model.bim"

    if not config_path.exists():
        log.error("config.json not found at %s", config_path)
        sys.exit(1)
    if not model_path.exists():
        log.error("model.bim not found at %s", model_path)
        sys.exit(1)

    config = json.loads(config_path.read_text())
    workspace_id = config["workspace"]["id"]
    lakehouse_id = config["lakehouse"]["id"]

    token = get_token()

    # 1) Get SQL endpoint
    sql_conn, sql_ep_id = get_sql_endpoint(workspace_id, lakehouse_id, token)

    # 2) Read and inject model.bim
    model_text = model_path.read_text(encoding="utf-8")
    model_text = model_text.replace("__SQL_ENDPOINT__", sql_conn)
    model_text = model_text.replace("__SQL_ENDPOINT_ID__", sql_ep_id)

    # 3) Find or create semantic model (with definition on first create)
    sm_id = find_or_create_semantic_model(workspace_id, model_text, token)

    # 4) If it already existed, push updated definition
    # (find_or_create already pushed definition on create)
    items_check = fabric_get(f"/workspaces/{workspace_id}/items?type=SemanticModel", token)
    existing = next((i for i in items_check.get("value", []) if i["id"] == sm_id), None)
    if existing:
        log.info("Updating definition for existing semantic model...")
        push_definition(workspace_id, sm_id, model_text, token)

    # 5) Save to config
    if "semanticModel" not in config:
        config["semanticModel"] = {}
    config["semanticModel"]["id"] = sm_id
    config["semanticModel"]["name"] = SEMANTIC_MODEL_NAME
    config_path.write_text(json.dumps(config, indent=4), encoding="utf-8")
    log.info("Saved semantic model ID to config.json")

    # 6) DAX validation (best-effort)
    validate_dax(workspace_id, sm_id, token)

    log.info("Semantic model deployment complete.")


if __name__ == "__main__":
    main()
