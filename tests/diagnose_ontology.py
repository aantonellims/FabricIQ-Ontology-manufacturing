"""Diagnose ontology status - check API state and definition.

Usage:
    python tests/diagnose_ontology.py --ontology-path ontologies/SaintGobain
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


def api_get(path: str, token: str) -> dict | None:
    import urllib.request
    import urllib.error

    req = urllib.request.Request(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode() if exc.fp else ""
        print(f"HTTP {exc.code}: {err_body[:500]}")
        return None


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
        err_body = exc.read().decode() if exc.fp else ""
        if exc.code == 202:
            loc = exc.headers.get("Location", "")
            ra = int(exc.headers.get("Retry-After", "10"))
            if loc:
                return handle_lro(loc, ra)
        print(f"HTTP {exc.code}: {err_body[:500]}")
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
    ontology_name = config["ontology"]["name"]

    print("=" * 60)
    print("ONTOLOGY DIAGNOSTIC")
    print("=" * 60)
    print(f"Workspace: {config['workspace']['name']} ({workspace_id})")
    print(f"Ontology:  {ontology_name} ({ontology_id})")
    print()

    token = get_token()

    # 1. Check ontology item exists
    print("1. Checking ontology item exists...")
    ontology_info = api_get(f"/workspaces/{workspace_id}/ontologies/{ontology_id}", token)
    if ontology_info:
        print(f"   ✅ Found: {ontology_info.get('displayName', 'N/A')}")
        print(f"   State: {ontology_info.get('state', 'N/A')}")
        print(f"   Type: {ontology_info.get('type', 'N/A')}")
    else:
        print("   ❌ Ontology not found or inaccessible")

    # 2. Get the current definition
    print("\n2. Fetching current definition via getDefinition...")
    definition = api_post(
        f"/workspaces/{workspace_id}/ontologies/{ontology_id}/getDefinition",
        None,
        token,
        follow_result=True,
    )
    
    if definition:
        parts = definition.get("definition", {}).get("parts", [])
        print(f"   ✅ Definition has {len(parts)} parts")
        
        # Decode and analyze entity types
        entity_types = []
        bindings = []
        relationships = []
        contextualizations = []
        
        for part in parts:
            path = part.get("path", "")
            payload = part.get("payload", "")
            try:
                decoded = json.loads(base64.b64decode(payload).decode())
            except:
                decoded = None
            
            if "EntityTypes/" in path and path.endswith("/definition.json"):
                entity_types.append({"path": path, "data": decoded})
            elif "DataBindings/" in path:
                bindings.append({"path": path, "data": decoded})
            elif "RelationshipTypes/" in path and path.endswith("/definition.json"):
                relationships.append({"path": path, "data": decoded})
            elif "Contextualizations/" in path:
                contextualizations.append({"path": path, "data": decoded})
        
        print(f"\n   Entity Types: {len(entity_types)}")
        for et in entity_types:
            if et["data"]:
                et_id = et["data"].get("id", "?")
                et_name = et["data"].get("name", "?")
                props = len(et["data"].get("properties", []))
                print(f"      - {et_name} (id={et_id}, {props} properties)")
        
        print(f"\n   Data Bindings: {len(bindings)}")
        for b in bindings:
            if b["data"]:
                b_id = b["data"].get("id", "?")
                et_id = b["data"].get("entityTypeId", "?")
                print(f"      - {b_id} → entityTypeId={et_id}")
        
        print(f"\n   Relationships: {len(relationships)}")
        for r in relationships:
            if r["data"]:
                r_id = r["data"].get("id", "?")
                r_name = r["data"].get("name", "?")
                print(f"      - {r_name} (id={r_id})")
        
        print(f"\n   Contextualizations: {len(contextualizations)}")
        for c in contextualizations:
            if c["data"]:
                c_id = c["data"].get("id", "?")
                rel_id = c["data"].get("relationshipTypeId", "?")
                print(f"      - {c_id} → relationshipTypeId={rel_id}")
    else:
        print("   ❌ No definition returned - ontology may not be initialized")
        print("   This could mean:")
        print("      - The ontology has never had a definition pushed")
        print("      - The definition push failed")
        print("      - There's a service issue")

    # 3. Check local entity type IDs
    print("\n3. Checking local entity type files...")
    ont_path = Path(args.ontology_path) / "ontology" / "entity-types"
    if ont_path.exists():
        for f in sorted(ont_path.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            et_id = data.get("id", "?")
            et_name = data.get("name", "?")
            # Check if ID is a proper 64-bit integer (> 1 billion)
            try:
                id_int = int(et_id)
                is_valid = id_int > 1_000_000_000
            except:
                is_valid = False
            status = "✅" if is_valid else "❌ (too small, needs 64-bit)"
            print(f"   {f.name}: {et_name} (id={et_id}) {status}")
    else:
        print("   No local entity types found")

    print("\n" + "=" * 60)
    print("RECOMMENDATION:")
    if entity_types and all(et.get("data") for et in entity_types):
        print("  - Definition exists with entity types. Ontology may be initializing.")
        print("  - Wait a few minutes or check the Fabric portal for errors.")
    else:
        print("  - Definition appears empty or missing.")
        print("  - Need to push a valid definition with 64-bit entity IDs.")
        print("  - Run: python deploy/deploy_ontology_definition.py --ontology-path ontologies/SaintGobain")
    print("=" * 60)


if __name__ == "__main__":
    main()
