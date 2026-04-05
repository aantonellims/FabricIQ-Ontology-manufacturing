"""Push a single minimal entity type - diagnostic test.

Usage:
    python deploy/test_single_entity.py --ontology-path ontologies/SaintGobain
"""

import argparse
import base64
import json
import logging
import sys
from pathlib import Path

from azure.identity import DefaultAzureCredential

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

API_BASE = "https://api.fabric.microsoft.com/v1"


def get_token(scope: str = "https://api.fabric.microsoft.com/.default") -> str:
    credential = DefaultAzureCredential()
    return credential.get_token(scope).token


def fabric_post(path: str, body: dict | None, token: str, follow_result: bool = False) -> dict | None:
    """POST to Fabric API with LRO handling."""
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
                    log.error("LRO failed: %s", json.dumps(poll_data, indent=2))
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
        log.error("HTTP %d on POST %s: %s", exc.code, path, err_body[:2000])
        raise


def b64(obj: dict) -> str:
    return base64.b64encode(json.dumps(obj, indent=2).encode()).decode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ontology-path", required=True)
    args = parser.parse_args()

    ontology_path = Path(args.ontology_path)
    config_path = ontology_path / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    
    workspace_id = config["workspace"]["id"]
    ontology_id = config["ontology"]["id"]
    ontology_name = config["ontology"]["name"]
    
    token = get_token()
    
    # Minimal entity type - use IDs from documentation example range
    minimal_entity = {
        "id": "8813598896083",  # From docs example
        "namespace": "usertypes",
        "baseEntityTypeId": None,
        "name": "TestPlant",
        "entityIdParts": ["3117068036374594013"],
        "displayNamePropertyId": "3117068036374594013",
        "namespaceType": "Custom",
        "visibility": "Visible",
        "properties": [
            {
                "id": "3117068036374594013",
                "name": "PlantId",
                "redefines": None,
                "baseTypeNamespaceType": None,
                "valueType": "String"
            }
        ],
        "timeseriesProperties": []
    }
    
    # Build parts
    parts = []
    
    # .platform
    platform = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Ontology", "displayName": ontology_name},
        "config": {"version": "2.0", "logicalId": "00000000-0000-0000-0000-000000000000"},
    }
    parts.append({"path": ".platform", "payload": b64(platform), "payloadType": "InlineBase64"})
    
    # definition.json (empty)
    parts.append({"path": "definition.json", "payload": b64({}), "payloadType": "InlineBase64"})
    
    # Single entity type
    parts.append({
        "path": f"EntityTypes/{minimal_entity['id']}/definition.json",
        "payload": b64(minimal_entity),
        "payloadType": "InlineBase64",
    })
    
    log.info("Payload parts:")
    for p in parts:
        decoded = json.loads(base64.b64decode(p["payload"]).decode())
        log.info("  %s: %s", p["path"], json.dumps(decoded, indent=2)[:200])
    
    # Push
    payload = {"definition": {"parts": parts}}
    log.info("Pushing definition...")
    
    result = fabric_post(f"/workspaces/{workspace_id}/ontologies/{ontology_id}/updateDefinition", payload, token)
    log.info("Push result: %s", json.dumps(result, indent=2) if result else None)
    
    # Validate
    log.info("Validating...")
    definition = fabric_post(
        f"/workspaces/{workspace_id}/ontologies/{ontology_id}/getDefinition",
        None,
        token,
        follow_result=True,
    )
    
    if definition:
        num_parts = len(definition.get("definition", {}).get("parts", []))
        log.info("getDefinition returned %d parts", num_parts)
    else:
        log.error("getDefinition returned nothing")


if __name__ == "__main__":
    main()
