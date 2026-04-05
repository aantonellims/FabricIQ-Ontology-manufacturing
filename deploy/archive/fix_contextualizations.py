"""Fix ontology contextualizations with correct property ID references.

Usage:
    python deploy/fix_contextualizations.py --ontology-path ontologies/SaintGobain
"""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ontology-path", required=True)
    args = parser.parse_args()

    ont_path = Path(args.ontology_path) / "ontology"
    
    # Build property map from entity types: entity_name -> {prop_name -> prop_id}
    entity_props = {}
    entity_ids = {}  # name -> id
    
    et_dir = ont_path / "entity-types"
    for f in sorted(et_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        
        name = data["name"]
        entity_ids[name] = data["id"]
        entity_props[name] = {}
        
        for prop in data.get("properties", []):
            entity_props[name][prop["name"]] = prop["id"]
        
        print(f"Entity: {name} (id={data['id']})")
        for prop_name, prop_id in entity_props[name].items():
            print(f"   {prop_name}: {prop_id}")
    
    # Build relationship map from files: name -> (source_entity, target_entity)
    rel_entities = {}  # relationship_name -> {"source": entity_name, "target": entity_name}
    rel_ids = {}  # name -> id
    
    rel_dir = ont_path / "relationships"
    for f in sorted(rel_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        
        rel_name = data["name"]
        rel_ids[rel_name] = data["id"]
        
        # Map entity IDs to names
        src_id = data["source"]["entityTypeId"]
        tgt_id = data["target"]["entityTypeId"]
        
        src_name = None
        tgt_name = None
        for en, eid in entity_ids.items():
            if eid == src_id:
                src_name = en
            if eid == tgt_id:
                tgt_name = en
        
        rel_entities[rel_name] = {"source": src_name, "target": tgt_name}
        print(f"\nRelationship: {rel_name}")
        print(f"   Source: {src_name} ({src_id})")
        print(f"   Target: {tgt_name} ({tgt_id})")
    
    # Fix contextualizations
    print("\n" + "=" * 60)
    print("FIXING CONTEXTUALIZATIONS")
    print("=" * 60)
    
    ctx_dir = ont_path / "contextualizations"
    file_to_rel = {
        "has-line": "Has_Line",
        "has-equipment": "Has_Equipment", 
        "has-sensor": "Has_Sensor",
        "assigned-to": "Assigned_To",
        "produces": "Produces"
    }
    
    for f in sorted(ctx_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        
        rel_name = file_to_rel.get(f.stem)
        if not rel_name:
            print(f"SKIP: {f.name} - unknown mapping")
            continue
        
        rel_info = rel_entities.get(rel_name)
        if not rel_info:
            print(f"SKIP: {f.name} - relationship {rel_name} not found")
            continue
        
        print(f"\n{f.name} ({rel_name}):")
        print(f"   Relationship: {rel_info['source']} → {rel_info['target']}")
        
        # Update relationshipTypeId
        data["relationshipTypeId"] = rel_ids[rel_name]
        
        # Fix sourceKeyRefBindings - use source entity's properties
        source_entity = rel_info["source"]
        if source_entity and source_entity in entity_props:
            for binding in data.get("sourceKeyRefBindings", []):
                col_name = binding["sourceColumnName"]
                if col_name in entity_props[source_entity]:
                    old_id = binding["targetPropertyId"]
                    new_id = entity_props[source_entity][col_name]
                    binding["targetPropertyId"] = new_id
                    print(f"   sourceKeyRef {col_name}: {old_id} → {new_id}")
        
        # Fix targetKeyRefBindings - use target entity's properties
        target_entity = rel_info["target"]
        if target_entity and target_entity in entity_props:
            for binding in data.get("targetKeyRefBindings", []):
                col_name = binding["sourceColumnName"]
                if col_name in entity_props[target_entity]:
                    old_id = binding["targetPropertyId"]
                    new_id = entity_props[target_entity][col_name]
                    binding["targetPropertyId"] = new_id
                    print(f"   targetKeyRef {col_name}: {old_id} → {new_id}")
        
        with open(f, "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2)
    
    print("\n✅ Contextualizations fixed")


if __name__ == "__main__":
    main()
