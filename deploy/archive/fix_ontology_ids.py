"""Fix and redeploy ontology with proper 64-bit IDs.

Generates deterministic 64-bit IDs from names and updates all files.

Usage:
    python deploy/fix_ontology_ids.py --ontology-path ontologies/SaintGobain
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path


def generate_id(name: str, prefix: int = 100) -> str:
    """Generate a deterministic 64-bit ID from a name."""
    # Use hash to generate a large but deterministic number
    h = hashlib.sha256(name.encode()).hexdigest()[:12]
    # Convert to int and ensure it's in valid range
    num = int(h, 16) % (10**12) + prefix * (10**12)
    return str(num)


def generate_property_id(entity_name: str, prop_name: str) -> str:
    """Generate a property ID based on entity and property name."""
    h = hashlib.sha256(f"{entity_name}.{prop_name}".encode()).hexdigest()[:12]
    num = int(h, 16) % (10**12) + 200 * (10**12)  # Different prefix for properties
    return str(num)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ontology-path", required=True)
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    args = parser.parse_args()

    ont_path = Path(args.ontology_path) / "ontology"
    
    # Entity type name → ID mapping
    entity_ids: dict[str, str] = {}
    # Property (entity.prop) → ID mapping
    property_ids: dict[str, str] = {}
    # Relationship name → ID mapping
    relationship_ids: dict[str, str] = {}

    # 1. Process entity types
    print("1. Processing entity types...")
    et_dir = ont_path / "entity-types"
    for f in sorted(et_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        
        name = data["name"]
        old_id = data["id"]
        new_id = generate_id(name, prefix=100)
        entity_ids[name] = new_id
        
        print(f"   {name}: {old_id} → {new_id}")
        
        # Update entity ID
        data["id"] = new_id
        
        # Update property IDs
        new_entity_id_parts = []
        for prop in data.get("properties", []):
            prop_name = prop["name"]
            old_prop_id = prop["id"]
            new_prop_id = generate_property_id(name, prop_name)
            property_ids[f"{name}.{prop_name}"] = new_prop_id
            prop["id"] = new_prop_id
            
            # Track entity ID parts (usually the first property like PlantId)
            if old_prop_id in data.get("entityIdParts", []):
                new_entity_id_parts.append(new_prop_id)
        
        # Update entityIdParts
        if data.get("entityIdParts"):
            data["entityIdParts"] = new_entity_id_parts
        
        # Update displayNamePropertyId
        if data.get("displayNamePropertyId"):
            # Find the Name property
            for prop in data.get("properties", []):
                if prop["name"] == "Name":
                    data["displayNamePropertyId"] = prop["id"]
                    break
        
        if not args.dry_run:
            with open(f, "w", encoding="utf-8") as fp:
                json.dump(data, fp, indent=2)

    # 2. Process relationships
    print("\n2. Processing relationships...")
    rel_dir = ont_path / "relationships"
    for f in sorted(rel_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        
        name = data["name"]
        old_id = data["id"]
        new_id = generate_id(name, prefix=300)
        relationship_ids[name] = new_id
        
        print(f"   {name}: {old_id} → {new_id}")
        
        data["id"] = new_id
        
        # Update source/target entity type IDs
        source_et = None
        target_et = None
        for et_name, et_id in entity_ids.items():
            # Map old entity type IDs to new ones
            if data["source"]["entityTypeId"] in ["1001", "1002", "1003", "1004", "1005", "1006"]:
                idx = int(data["source"]["entityTypeId"]) - 1001
                et_names = ["Plant", "ProductionLine", "Equipment", "Sensor", "Product", "WorkOrder"]
                if idx < len(et_names):
                    source_et = et_names[idx]
            if data["target"]["entityTypeId"] in ["1001", "1002", "1003", "1004", "1005", "1006"]:
                idx = int(data["target"]["entityTypeId"]) - 1001
                et_names = ["Plant", "ProductionLine", "Equipment", "Sensor", "Product", "WorkOrder"]
                if idx < len(et_names):
                    target_et = et_names[idx]
        
        if source_et and source_et in entity_ids:
            data["source"]["entityTypeId"] = entity_ids[source_et]
        if target_et and target_et in entity_ids:
            data["target"]["entityTypeId"] = entity_ids[target_et]
        
        if not args.dry_run:
            with open(f, "w", encoding="utf-8") as fp:
                json.dump(data, fp, indent=2)

    # 3. Process non-timeseries bindings
    print("\n3. Processing non-timeseries bindings...")
    nts_dir = ont_path / "bindings" / "nontimeseries"
    entity_name_map = {
        "1001": "Plant", "1002": "ProductionLine", "1003": "Equipment",
        "1004": "Sensor", "1005": "Product", "1006": "WorkOrder"
    }
    for f in sorted(nts_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        
        old_et_id = data["entityTypeId"]
        et_name = entity_name_map.get(old_et_id, f.stem.replace("-", "").title())
        
        # Fix entity name mapping for files
        file_to_entity = {
            "plant": "Plant", "production-line": "ProductionLine", "equipment": "Equipment",
            "sensor": "Sensor", "product": "Product", "workorder": "WorkOrder"
        }
        et_name = file_to_entity.get(f.stem, et_name)
        
        if et_name in entity_ids:
            new_et_id = entity_ids[et_name]
            print(f"   {f.name}: entityTypeId {old_et_id} → {new_et_id}")
            data["entityTypeId"] = new_et_id
            
            # Update property bindings
            for binding in data.get("dataBindingConfiguration", {}).get("propertyBindings", []):
                prop_name = binding["sourceColumnName"]
                key = f"{et_name}.{prop_name}"
                if key in property_ids:
                    binding["targetPropertyId"] = property_ids[key]
        
        if not args.dry_run:
            with open(f, "w", encoding="utf-8") as fp:
                json.dump(data, fp, indent=2)

    # 4. Process timeseries bindings
    print("\n4. Processing timeseries bindings...")
    ts_dir = ont_path / "bindings" / "timeseries"
    for f in sorted(ts_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        
        old_et_id = data["entityTypeId"]
        et_name = entity_name_map.get(old_et_id, f.stem.replace("-", "").title())
        et_name = file_to_entity.get(f.stem, et_name)
        
        if et_name in entity_ids:
            new_et_id = entity_ids[et_name]
            print(f"   {f.name}: entityTypeId {old_et_id} → {new_et_id}")
            data["entityTypeId"] = new_et_id
            
            # Update property bindings
            for binding in data.get("dataBindingConfiguration", {}).get("propertyBindings", []):
                prop_name = binding["sourceColumnName"]
                key = f"{et_name}.{prop_name}"
                if key in property_ids:
                    binding["targetPropertyId"] = property_ids[key]
        
        if not args.dry_run:
            with open(f, "w", encoding="utf-8") as fp:
                json.dump(data, fp, indent=2)

    # 5. Process contextualizations
    print("\n5. Processing contextualizations...")
    ctx_dir = ont_path / "contextualizations"
    rel_name_map = {
        "2001": "Has_Line", "2002": "Has_Equipment", "2003": "Has_Sensor",
        "2004": "Assigned_To", "2005": "Produces"
    }
    for f in sorted(ctx_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        
        old_rel_id = data["relationshipTypeId"]
        rel_name = rel_name_map.get(old_rel_id)
        
        # Map file to relationship
        file_to_rel = {
            "has-line": "Has_Line", "has-equipment": "Has_Equipment", "has-sensor": "Has_Sensor",
            "assigned-to": "Assigned_To", "produces": "Produces"
        }
        rel_name = file_to_rel.get(f.stem, rel_name)
        
        if rel_name and rel_name in relationship_ids:
            new_rel_id = relationship_ids[rel_name]
            print(f"   {f.name}: relationshipTypeId {old_rel_id} → {new_rel_id}")
            data["relationshipTypeId"] = new_rel_id
        
        # Update source/target key bindings
        for binding in data.get("sourceKeyRefBindings", []):
            col_name = binding["sourceColumnName"]
            # Find which entity type this property belongs to
            for et_name in entity_ids:
                key = f"{et_name}.{col_name}"
                if key in property_ids:
                    binding["targetPropertyId"] = property_ids[key]
                    break
        
        for binding in data.get("targetKeyRefBindings", []):
            col_name = binding["sourceColumnName"]
            for et_name in entity_ids:
                key = f"{et_name}.{col_name}"
                if key in property_ids:
                    binding["targetPropertyId"] = property_ids[key]
                    break
        
        if not args.dry_run:
            with open(f, "w", encoding="utf-8") as fp:
                json.dump(data, fp, indent=2)

    print("\n" + "=" * 60)
    print("ID MAPPING SUMMARY:")
    print("=" * 60)
    print("\nEntity Types:")
    for name, eid in entity_ids.items():
        print(f"  {name}: {eid}")
    print("\nRelationships:")
    for name, rid in relationship_ids.items():
        print(f"  {name}: {rid}")
    
    if args.dry_run:
        print("\n[DRY RUN - no files modified]")
    else:
        print("\n✅ All files updated. Now run:")
        print("   python deploy/deploy_ontology_definition.py --ontology-path ontologies/SaintGobain")


if __name__ == "__main__":
    main()
