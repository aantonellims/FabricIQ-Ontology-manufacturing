"""Sync local ontology files with IDs from the deployed definition.

Downloads the current definition from Fabric and updates local files to match.

Usage:
    python deploy/sync_from_deployed.py --ontology-path ontologies/SaintGobain
"""

import argparse
import base64
import json
import sys
from pathlib import Path

from azure.identity import DefaultAzureCredential

API_BASE = "https://api.fabric.microsoft.com/v1"


def get_token():
    credential = DefaultAzureCredential()
    return credential.get_token("https://api.fabric.microsoft.com/.default").token


def api_post(path: str, body: dict | None, token: str, follow_result: bool = False) -> dict | None:
    import urllib.request
    import urllib.error
    import time

    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )

    def handle_lro(location, retry_after):
        print(f"  LRO started, polling in {retry_after}s...")
        time.sleep(retry_after)
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
                    print(f"  LRO FAILED: {poll_data.get('error')}")
                    return poll_data
                print(f"  Still processing ({status}, attempt {attempt + 1})...")
                time.sleep(5)
        return None

    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            if resp.status == 202:
                loc = resp.headers.get("Location", "")
                ra = int(resp.headers.get("Retry-After", "10"))
                if loc:
                    return handle_lro(loc, ra)
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        if exc.code == 202:
            loc = exc.headers.get("Location", "")
            ra = int(exc.headers.get("Retry-After", "10"))
            if loc:
                return handle_lro(loc, ra)
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ontology-path", required=True)
    args = parser.parse_args()

    config_path = Path(args.ontology_path) / "config.json"
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    workspace_id = config["workspace"]["id"]
    ontology_id = config["ontology"]["id"]

    print("Fetching deployed definition...")
    token = get_token()
    
    definition = api_post(
        f"/workspaces/{workspace_id}/ontologies/{ontology_id}/getDefinition",
        None,
        token,
        follow_result=True,
    )

    if not definition:
        print("Failed to get definition")
        sys.exit(1)

    parts = definition.get("definition", {}).get("parts", [])
    print(f"Got {len(parts)} parts")

    # Extract entity types with their deployed IDs
    entity_types = {}  # name -> full definition
    relationships = {}  # name -> full definition
    
    for part in parts:
        path = part.get("path", "")
        payload = part.get("payload", "")
        try:
            decoded = json.loads(base64.b64decode(payload).decode())
        except:
            continue
        
        if "EntityTypes/" in path and path.endswith("/definition.json"):
            name = decoded.get("name")
            if name:
                entity_types[name] = decoded
                print(f"  Entity: {name} (id={decoded.get('id')})")
        
        if "RelationshipTypes/" in path and path.endswith("/definition.json"):
            name = decoded.get("name")
            if name:
                relationships[name] = decoded
                print(f"  Relationship: {name} (id={decoded.get('id')})")

    print("\nUpdating local files...")
    ont_path = Path(args.ontology_path) / "ontology"

    # Build property ID map: entity_name.property_name -> deployed_id
    prop_map = {}
    for et_name, et_def in entity_types.items():
        for prop in et_def.get("properties", []):
            prop_map[f"{et_name}.{prop['name']}"] = prop["id"]

    # 1. Update entity types
    et_dir = ont_path / "entity-types"
    for f in sorted(et_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            local = json.load(fp)
        
        name = local["name"]
        if name not in entity_types:
            print(f"  SKIP: {name} not in deployed definition")
            continue
        
        deployed = entity_types[name]
        
        # Update the full entity definition from deployed
        local["id"] = deployed["id"]
        local["entityIdParts"] = deployed.get("entityIdParts", [])
        local["displayNamePropertyId"] = deployed.get("displayNamePropertyId")
        
        # Update properties by matching names
        for local_prop in local.get("properties", []):
            for deployed_prop in deployed.get("properties", []):
                if local_prop["name"] == deployed_prop["name"]:
                    local_prop["id"] = deployed_prop["id"]
                    break
        
        with open(f, "w", encoding="utf-8") as fp:
            json.dump(local, fp, indent=2)
        print(f"  Updated: {f.name}")

    # 2. Update relationships
    rel_dir = ont_path / "relationships"
    for f in sorted(rel_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            local = json.load(fp)
        
        name = local["name"]
        if name not in relationships:
            print(f"  SKIP: {name} not in deployed definition")
            continue
        
        deployed = relationships[name]
        local["id"] = deployed["id"]
        
        # Update source/target entity type IDs
        src_et_id = deployed.get("source", {}).get("entityTypeId")
        tgt_et_id = deployed.get("target", {}).get("entityTypeId")
        if src_et_id:
            local["source"]["entityTypeId"] = src_et_id
        if tgt_et_id:
            local["target"]["entityTypeId"] = tgt_et_id
        
        with open(f, "w", encoding="utf-8") as fp:
            json.dump(local, fp, indent=2)
        print(f"  Updated: {f.name}")

    # 3. Update non-timeseries bindings
    nts_dir = ont_path / "bindings" / "nontimeseries"
    file_to_entity = {
        "plant": "Plant", "production-line": "ProductionLine", "equipment": "Equipment",
        "sensor": "Sensor", "product": "Product", "workorder": "WorkOrder"
    }
    for f in sorted(nts_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            local = json.load(fp)
        
        et_name = file_to_entity.get(f.stem)
        if not et_name or et_name not in entity_types:
            continue
        
        deployed_et = entity_types[et_name]
        local["entityTypeId"] = deployed_et["id"]
        
        # Update property bindings
        for binding in local.get("dataBindingConfiguration", {}).get("propertyBindings", []):
            col_name = binding["sourceColumnName"]
            key = f"{et_name}.{col_name}"
            if key in prop_map:
                binding["targetPropertyId"] = prop_map[key]
        
        with open(f, "w", encoding="utf-8") as fp:
            json.dump(local, fp, indent=2)
        print(f"  Updated: {f.name}")

    # 4. Update timeseries bindings
    ts_dir = ont_path / "bindings" / "timeseries"
    for f in sorted(ts_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            local = json.load(fp)
        
        et_name = file_to_entity.get(f.stem)
        if not et_name or et_name not in entity_types:
            continue
        
        deployed_et = entity_types[et_name]
        local["entityTypeId"] = deployed_et["id"]
        
        # Update property bindings
        for binding in local.get("dataBindingConfiguration", {}).get("propertyBindings", []):
            col_name = binding["sourceColumnName"]
            key = f"{et_name}.{col_name}"
            if key in prop_map:
                binding["targetPropertyId"] = prop_map[key]
        
        with open(f, "w", encoding="utf-8") as fp:
            json.dump(local, fp, indent=2)
        print(f"  Updated: {f.name}")

    # 5. Update contextualizations
    ctx_dir = ont_path / "contextualizations"
    file_to_rel = {
        "has-line": "Has_Line", "has-equipment": "Has_Equipment", "has-sensor": "Has_Sensor",
        "assigned-to": "Assigned_To", "produces": "Produces"
    }
    for f in sorted(ctx_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            local = json.load(fp)
        
        rel_name = file_to_rel.get(f.stem)
        if not rel_name or rel_name not in relationships:
            continue
        
        deployed_rel = relationships[rel_name]
        local["relationshipTypeId"] = deployed_rel["id"]
        
        # Update source/target key bindings
        for binding in local.get("sourceKeyRefBindings", []):
            col_name = binding["sourceColumnName"]
            for et_name in entity_types:
                key = f"{et_name}.{col_name}"
                if key in prop_map:
                    binding["targetPropertyId"] = prop_map[key]
                    break
        
        for binding in local.get("targetKeyRefBindings", []):
            col_name = binding["sourceColumnName"]
            for et_name in entity_types:
                key = f"{et_name}.{col_name}"
                if key in prop_map:
                    binding["targetPropertyId"] = prop_map[key]
                    break
        
        with open(f, "w", encoding="utf-8") as fp:
            json.dump(local, fp, indent=2)
        print(f"  Updated: {f.name}")

    print("\n✅ Local files synced with deployed IDs")
    print("Now run: python deploy/deploy_ontology_definition.py --ontology-path ontologies/SaintGobain")


if __name__ == "__main__":
    main()
