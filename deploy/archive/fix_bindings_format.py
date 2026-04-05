"""Fix data binding files - remove entityTypeId field.

The entityTypeId is determined by the path (EntityTypes/{ID}/DataBindings/), 
not a field in the JSON.

Usage:
    python deploy/fix_bindings_format.py --ontology-path ontologies/SaintGobain
"""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ontology-path", required=True)
    args = parser.parse_args()

    ont_path = Path(args.ontology_path) / "ontology"

    # Fix non-timeseries bindings
    print("Fixing non-timeseries bindings...")
    nts_dir = ont_path / "bindings" / "nontimeseries"
    for f in sorted(nts_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        
        # Remove entityTypeId if present (it's determined by path, not field)
        if "entityTypeId" in data:
            print(f"  {f.name}: Removing entityTypeId={data['entityTypeId']}")
            del data["entityTypeId"]
            
            with open(f, "w", encoding="utf-8") as fp:
                json.dump(data, fp, indent=2)

    # Fix timeseries bindings
    print("\nFixing timeseries bindings...")
    ts_dir = ont_path / "bindings" / "timeseries"
    for f in sorted(ts_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        
        if "entityTypeId" in data:
            print(f"  {f.name}: Removing entityTypeId={data['entityTypeId']}")
            del data["entityTypeId"]
            
            with open(f, "w", encoding="utf-8") as fp:
                json.dump(data, fp, indent=2)

    print("\n✅ Binding files fixed")


if __name__ == "__main__":
    main()
