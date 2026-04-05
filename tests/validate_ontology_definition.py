"""Validate ontology definition via Fabric getDefinition API.

Calls getDefinition on the deployed ontology item and validates:
  - 6 entity type parts with positive Int64 IDs
  - Properties use valueType (not dataType)
  - 5 relationship type parts
  - 6 NTS + 3 TS data binding parts
  - 5 contextualization parts

Usage:
    python tests/validate_ontology_definition.py --ontology-path ontologies/SaintGobain
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
VALID_VALUE_TYPES = {"String", "Boolean", "DateTime", "Object", "BigInt", "Double"}
EXPECTED_ENTITY_IDS = {"1001", "1002", "1003", "1004", "1005", "1006"}


def get_token() -> str:
    return DefaultAzureCredential().get_token("https://api.fabric.microsoft.com/.default").token


def fabric_post(path: str, body: dict | None, token: str) -> dict | None:
    import urllib.request
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ontology-path", required=True)
    args = parser.parse_args()

    config = json.loads((Path(args.ontology_path) / "config.json").read_text())
    workspace_id = config["workspace"]["id"]
    ontology_id = config["ontology"]["id"]
    token = get_token()
    errors = 0

    # Get definition
    result = fabric_post(f"/workspaces/{workspace_id}/items/{ontology_id}/getDefinition", None, token)
    if not result:
        log.error("FAIL: getDefinition returned empty")
        return 1

    parts = result.get("definition", {}).get("parts", [])
    if not parts:
        log.error("FAIL: No parts in definition")
        return 1

    # Classify parts
    et_parts, rel_parts, nts_parts, ts_parts, ctx_parts = [], [], [], [], []
    for part in parts:
        p = part.get("path", "")
        if p.startswith("EntityTypes/") and p.endswith("/definition.json"):
            et_parts.append(part)
        elif p.startswith("RelationshipTypes/") and p.endswith("/definition.json"):
            rel_parts.append(part)
        elif "/DataBindings/" in p:
            decoded = json.loads(base64.b64decode(part["payload"]).decode())
            bt = decoded.get("dataBindingConfiguration", {}).get("dataBindingType", "")
            if bt == "NonTimeSeries":
                nts_parts.append(part)
            elif bt == "TimeSeries":
                ts_parts.append(part)
        elif "/Contextualizations/" in p:
            ctx_parts.append(part)

    # VT-ONT-1: 6 entity types
    if len(et_parts) != 6:
        log.error("FAIL [VT-ONT-1]: Expected 6 entity types, got %d", len(et_parts))
        errors += 1
    else:
        log.info("PASS [VT-ONT-1]: 6 entity type parts")

    # VT-ONT-2 & VT-ONT-3: Property schema + IDs
    found_ids = set()
    for part in et_parts:
        decoded = json.loads(base64.b64decode(part["payload"]).decode())
        et_id = decoded.get("id", "")
        found_ids.add(et_id)

        try:
            if int(et_id) <= 0:
                log.error("FAIL [VT-ONT-3]: Entity '%s' has non-positive ID: %s", decoded.get("name"), et_id)
                errors += 1
        except (ValueError, TypeError):
            log.error("FAIL [VT-ONT-3]: Entity '%s' has non-integer ID: %s", decoded.get("name"), et_id)
            errors += 1

        for prop in decoded.get("properties", []):
            if "dataType" in prop:
                log.error("FAIL [VT-ONT-2]: Property '%s' on '%s' uses 'dataType'", prop["name"], decoded["name"])
                errors += 1
            vt = prop.get("valueType", "")
            if vt not in VALID_VALUE_TYPES:
                log.error("FAIL [VT-ONT-2]: Property '%s' invalid valueType '%s'", prop["name"], vt)
                errors += 1

    if found_ids != EXPECTED_ENTITY_IDS:
        log.error("FAIL [VT-ONT-3]: IDs mismatch. Expected %s, got %s", sorted(EXPECTED_ENTITY_IDS), sorted(found_ids))
        errors += 1
    else:
        log.info("PASS [VT-ONT-3]: All entity type IDs valid (1001-1006)")
        log.info("PASS [VT-ONT-2]: All properties use valid valueType")

    # VT-ONT-4: 5 relationships
    if len(rel_parts) != 5:
        log.error("FAIL [VT-ONT-4]: Expected 5 relationships, got %d", len(rel_parts))
        errors += 1
    else:
        log.info("PASS [VT-ONT-4]: 5 relationship type parts")
        for part in rel_parts:
            decoded = json.loads(base64.b64decode(part["payload"]).decode())
            src = decoded.get("source", {}).get("entityTypeId", "?")
            tgt = decoded.get("target", {}).get("entityTypeId", "?")
            log.info("  Relationship '%s': %s → %s", decoded.get("name"), src, tgt)

    # VT-ONT-5: 6 NTS bindings
    if len(nts_parts) != 6:
        log.error("FAIL [VT-ONT-5]: Expected 6 NTS bindings, got %d", len(nts_parts))
        errors += 1
    else:
        log.info("PASS [VT-ONT-5]: 6 NonTimeSeries binding parts")

    # VT-ONT-6: 3 TS bindings
    if len(ts_parts) != 3:
        log.error("FAIL [VT-ONT-6]: Expected 3 TS bindings, got %d", len(ts_parts))
        errors += 1
    else:
        log.info("PASS [VT-ONT-6]: 3 TimeSeries binding parts")

    # VT-ONT-7: 5 contextualizations
    if len(ctx_parts) != 5:
        log.error("FAIL [VT-ONT-7]: Expected 5 contextualizations, got %d", len(ctx_parts))
        errors += 1
    else:
        log.info("PASS [VT-ONT-7]: 5 contextualization parts")

    if errors == 0:
        log.info("ALL ONTOLOGY VALIDATION CHECKS PASSED")
        return 0
    else:
        log.error("%d validation errors found", errors)
        return 1


if __name__ == "__main__":
    sys.exit(main())
