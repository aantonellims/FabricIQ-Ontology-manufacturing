"""Regenerate ontology entity types with proper large 64-bit integer IDs and push to Fabric."""
import base64
import json
import time
import uuid
import urllib.request
import urllib.error
from azure.identity import DefaultAzureCredential

API = "https://api.fabric.microsoft.com/v1"

# Fixed large IDs for reproducibility
ENTITY_IDS = {
    "Plant":          296482030633,
    "ProductionLine": 227205227397,
    "Equipment":      278359882408,
    "Sensor":         852218420047,
    "Product":        521093514768,
    "WorkOrder":      335473340519,
}

# Relationship IDs
REL_IDS = {
    "Has_Line":       100100100100101,
    "Has_Equipment":  100100100100102,
    "Has_Sensor":     100100100100103,
    "Assigned_To":    100100100100104,
    "Produces":       100100100100105,
}


def pid(entity_name, prop_index):
    """Generate property ID."""
    return str(ENTITY_IDS[entity_name] * 1000 + prop_index)


def eid(entity_name):
    """Get entity type ID as string."""
    return str(ENTITY_IDS[entity_name])


def b64encode(obj):
    return base64.b64encode(json.dumps(obj).encode()).decode()


def build_entity_types():
    """Build all 6 entity type definitions."""
    return {
        "Plant": {
            "id": eid("Plant"),
            "namespace": "usertypes",
            "baseEntityTypeId": None,
            "name": "Plant",
            "entityIdParts": [pid("Plant", 1)],
            "displayNamePropertyId": pid("Plant", 2),
            "namespaceType": "Custom",
            "visibility": "Visible",
            "properties": [
                {"id": pid("Plant", 1), "name": "PlantId", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Plant", 2), "name": "Name", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Plant", 3), "name": "Location", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Plant", 4), "name": "Country", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Plant", 5), "name": "Division", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Plant", 6), "name": "Capacity", "redefines": None, "baseTypeNamespaceType": None, "valueType": "BigInt"},
                {"id": pid("Plant", 7), "name": "Status", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Plant", 8), "name": "Latitude", "redefines": None, "baseTypeNamespaceType": None, "valueType": "Double"},
                {"id": pid("Plant", 9), "name": "Longitude", "redefines": None, "baseTypeNamespaceType": None, "valueType": "Double"},
            ],
            "timeseriesProperties": [],
        },
        "ProductionLine": {
            "id": eid("ProductionLine"),
            "namespace": "usertypes",
            "baseEntityTypeId": None,
            "name": "ProductionLine",
            "entityIdParts": [pid("ProductionLine", 1)],
            "displayNamePropertyId": pid("ProductionLine", 2),
            "namespaceType": "Custom",
            "visibility": "Visible",
            "properties": [
                {"id": pid("ProductionLine", 1), "name": "LineId", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("ProductionLine", 2), "name": "Name", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("ProductionLine", 3), "name": "PlantId", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("ProductionLine", 4), "name": "LineType", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("ProductionLine", 5), "name": "Capacity", "redefines": None, "baseTypeNamespaceType": None, "valueType": "BigInt"},
                {"id": pid("ProductionLine", 6), "name": "Status", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
            ],
            "timeseriesProperties": [
                {"id": pid("ProductionLine", 101), "name": "Efficiency", "redefines": None, "baseTypeNamespaceType": None, "valueType": "Double"},
                {"id": pid("ProductionLine", 102), "name": "UnitCount", "redefines": None, "baseTypeNamespaceType": None, "valueType": "BigInt"},
                {"id": pid("ProductionLine", 103), "name": "CycleTime", "redefines": None, "baseTypeNamespaceType": None, "valueType": "Double"},
            ],
        },
        "Equipment": {
            "id": eid("Equipment"),
            "namespace": "usertypes",
            "baseEntityTypeId": None,
            "name": "Equipment",
            "entityIdParts": [pid("Equipment", 1)],
            "displayNamePropertyId": pid("Equipment", 2),
            "namespaceType": "Custom",
            "visibility": "Visible",
            "properties": [
                {"id": pid("Equipment", 1), "name": "EquipmentId", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Equipment", 2), "name": "Name", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Equipment", 3), "name": "LineId", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Equipment", 4), "name": "EquipmentType", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Equipment", 5), "name": "Manufacturer", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Equipment", 6), "name": "Model", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Equipment", 7), "name": "InstallDate", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Equipment", 8), "name": "Status", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
            ],
            "timeseriesProperties": [
                {"id": pid("Equipment", 101), "name": "RunTimeMinutes", "redefines": None, "baseTypeNamespaceType": None, "valueType": "Double"},
                {"id": pid("Equipment", 102), "name": "DownTimeMinutes", "redefines": None, "baseTypeNamespaceType": None, "valueType": "Double"},
                {"id": pid("Equipment", 103), "name": "OperatingStatus", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
            ],
        },
        "Sensor": {
            "id": eid("Sensor"),
            "namespace": "usertypes",
            "baseEntityTypeId": None,
            "name": "Sensor",
            "entityIdParts": [pid("Sensor", 1)],
            "displayNamePropertyId": pid("Sensor", 2),
            "namespaceType": "Custom",
            "visibility": "Visible",
            "properties": [
                {"id": pid("Sensor", 1), "name": "SensorId", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Sensor", 2), "name": "Name", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Sensor", 3), "name": "EquipmentId", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Sensor", 4), "name": "SensorType", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Sensor", 5), "name": "Unit", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Sensor", 6), "name": "MinValue", "redefines": None, "baseTypeNamespaceType": None, "valueType": "Double"},
                {"id": pid("Sensor", 7), "name": "MaxValue", "redefines": None, "baseTypeNamespaceType": None, "valueType": "Double"},
                {"id": pid("Sensor", 8), "name": "Status", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
            ],
            "timeseriesProperties": [
                {"id": pid("Sensor", 101), "name": "Value", "redefines": None, "baseTypeNamespaceType": None, "valueType": "Double"},
                {"id": pid("Sensor", 102), "name": "Quality", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
            ],
        },
        "Product": {
            "id": eid("Product"),
            "namespace": "usertypes",
            "baseEntityTypeId": None,
            "name": "Product",
            "entityIdParts": [pid("Product", 1)],
            "displayNamePropertyId": pid("Product", 3),
            "namespaceType": "Custom",
            "visibility": "Visible",
            "properties": [
                {"id": pid("Product", 1), "name": "ProductId", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Product", 2), "name": "SKU", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Product", 3), "name": "Name", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Product", 4), "name": "Category", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Product", 5), "name": "Division", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("Product", 6), "name": "UnitCost", "redefines": None, "baseTypeNamespaceType": None, "valueType": "Double"},
                {"id": pid("Product", 7), "name": "UnitPrice", "redefines": None, "baseTypeNamespaceType": None, "valueType": "Double"},
                {"id": pid("Product", 8), "name": "Weight", "redefines": None, "baseTypeNamespaceType": None, "valueType": "Double"},
                {"id": pid("Product", 9), "name": "Status", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
            ],
            "timeseriesProperties": [],
        },
        "WorkOrder": {
            "id": eid("WorkOrder"),
            "namespace": "usertypes",
            "baseEntityTypeId": None,
            "name": "WorkOrder",
            "entityIdParts": [pid("WorkOrder", 1)],
            "displayNamePropertyId": pid("WorkOrder", 1),
            "namespaceType": "Custom",
            "visibility": "Visible",
            "properties": [
                {"id": pid("WorkOrder", 1), "name": "WorkOrderId", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("WorkOrder", 2), "name": "ProductId", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("WorkOrder", 3), "name": "LineId", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("WorkOrder", 4), "name": "Quantity", "redefines": None, "baseTypeNamespaceType": None, "valueType": "BigInt"},
                {"id": pid("WorkOrder", 5), "name": "StartDate", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("WorkOrder", 6), "name": "DueDate", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("WorkOrder", 7), "name": "Status", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
                {"id": pid("WorkOrder", 8), "name": "Priority", "redefines": None, "baseTypeNamespaceType": None, "valueType": "String"},
            ],
            "timeseriesProperties": [],
        },
    }


def build_relationships():
    return [
        {"namespace": "usertypes", "id": str(REL_IDS["Has_Line"]), "name": "Has_Line", "namespaceType": "Custom",
         "source": {"entityTypeId": eid("Plant")}, "target": {"entityTypeId": eid("ProductionLine")}},
        {"namespace": "usertypes", "id": str(REL_IDS["Has_Equipment"]), "name": "Has_Equipment", "namespaceType": "Custom",
         "source": {"entityTypeId": eid("ProductionLine")}, "target": {"entityTypeId": eid("Equipment")}},
        {"namespace": "usertypes", "id": str(REL_IDS["Has_Sensor"]), "name": "Has_Sensor", "namespaceType": "Custom",
         "source": {"entityTypeId": eid("Equipment")}, "target": {"entityTypeId": eid("Sensor")}},
        {"namespace": "usertypes", "id": str(REL_IDS["Assigned_To"]), "name": "Assigned_To", "namespaceType": "Custom",
         "source": {"entityTypeId": eid("WorkOrder")}, "target": {"entityTypeId": eid("ProductionLine")}},
        {"namespace": "usertypes", "id": str(REL_IDS["Produces"]), "name": "Produces", "namespaceType": "Custom",
         "source": {"entityTypeId": eid("WorkOrder")}, "target": {"entityTypeId": eid("Product")}},
    ]


def build_nts_binding(entity_name, ws_id, lh_id, table_name, props):
    binding_id = str(uuid.uuid4())
    return {
        "id": binding_id,
        "dataBindingConfiguration": {
            "dataBindingType": "NonTimeSeries",
            "propertyBindings": [
                {"sourceColumnName": p["name"], "targetPropertyId": p["id"]}
                for p in props
            ],
            "sourceTableProperties": {
                "sourceType": "LakehouseTable",
                "workspaceId": ws_id,
                "itemId": lh_id,
                "sourceTableName": table_name,
            },
        },
    }


def build_ts_binding(entity_name, ws_id, kql_id, cluster_uri, db_name, table_name, ts_props, id_prop):
    binding_id = str(uuid.uuid4())
    bindings = [{"sourceColumnName": p["name"], "targetPropertyId": p["id"]} for p in ts_props]
    bindings.append({"sourceColumnName": id_prop["name"], "targetPropertyId": id_prop["id"]})
    return {
        "id": binding_id,
        "dataBindingConfiguration": {
            "dataBindingType": "TimeSeries",
            "timestampColumnName": "Timestamp",
            "propertyBindings": bindings,
            "sourceTableProperties": {
                "sourceType": "KustoTable",
                "workspaceId": ws_id,
                "itemId": kql_id,
                "clusterUri": cluster_uri,
                "databaseName": db_name,
                "sourceTableName": table_name,
            },
        },
    }


def build_contextualization(ws_id, lh_id, source_table, source_col, source_prop_id, target_col, target_prop_id):
    return {
        "id": str(uuid.uuid4()),
        "dataBindingTable": {
            "workspaceId": ws_id,
            "itemId": lh_id,
            "sourceTableName": source_table,
            "sourceType": "LakehouseTable",
        },
        "sourceKeyRefBindings": [{"sourceColumnName": source_col, "targetPropertyId": source_prop_id}],
        "targetKeyRefBindings": [{"sourceColumnName": target_col, "targetPropertyId": target_prop_id}],
    }


def fabric_lro_post(path, body, token, follow_result=False):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{API}{path}", data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            if resp.status == 202:
                loc = resp.headers.get("Location", "")
                ra = int(resp.headers.get("Retry-After", "10"))
                return _poll_lro(loc, ra, token, follow_result)
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        body_txt = exc.read().decode() if exc.fp else ""
        if exc.code == 202:
            loc = exc.headers.get("Location", "")
            ra = int(exc.headers.get("Retry-After", "10"))
            return _poll_lro(loc, ra, token, follow_result)
        print(f"HTTP {exc.code}: {body_txt[:500]}")
        raise


def _poll_lro(location, retry_after, token, follow_result):
    time.sleep(retry_after)
    for i in range(30):
        req = urllib.request.Request(location, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode() or "{}")
            status = data.get("status", "")
            if status == "Succeeded":
                if follow_result:
                    rr = urllib.request.Request(location + "/result", headers={"Authorization": f"Bearer {token}"})
                    with urllib.request.urlopen(rr) as rr_resp:
                        return json.loads(rr_resp.read().decode() or "{}")
                return data
            elif status == "Failed":
                print(f"LRO FAILED: {data.get('error')}")
                return data
            print(f"  Processing... ({status}, attempt {i+1})")
            time.sleep(5)
    return None


def main():
    with open("ontologies/SaintGobain/config.json") as f:
        config = json.load(f)

    ws_id = config["workspace"]["id"]
    lh_id = config["lakehouse"]["id"]
    kql_id = config["kqlDatabase"]["id"]
    ont_id = config["ontology"]["id"]
    cluster_uri = config["kqlDatabase"]["queryServiceUri"]
    db_name = config["kqlDatabase"]["name"]

    cred = DefaultAzureCredential()
    token = cred.get_token("https://api.fabric.microsoft.com/.default").token

    # Build entity types
    entity_types = build_entity_types()
    relationships = build_relationships()

    # Build definition parts
    parts = []

    # Platform
    platform = {"metadata": {"type": "Ontology", "displayName": "SaintGobainManufacturing"}}
    parts.append({"path": ".platform", "payload": b64encode(platform), "payloadType": "InlineBase64"})
    parts.append({"path": "definition.json", "payload": b64encode({}), "payloadType": "InlineBase64"})

    # Entity types + NonTimeSeries bindings
    table_map = {
        "Plant": "DIM_PLANT", "ProductionLine": "DIM_LINE", "Equipment": "DIM_EQUIPMENT",
        "Sensor": "DIM_SENSOR", "Product": "DIM_PRODUCT", "WorkOrder": "DIM_WORKORDER",
    }

    for name, et in entity_types.items():
        et_id = et["id"]
        parts.append({"path": f"EntityTypes/{et_id}/definition.json", "payload": b64encode(et), "payloadType": "InlineBase64"})

        # NTS binding
        nts = build_nts_binding(name, ws_id, lh_id, table_map[name], et["properties"])
        parts.append({"path": f"EntityTypes/{et_id}/DataBindings/{nts['id']}.json", "payload": b64encode(nts), "payloadType": "InlineBase64"})

    # TimeSeries bindings for entities with telemetry
    ts_config = {
        "Sensor": ("SensorTelemetry", entity_types["Sensor"]["timeseriesProperties"], entity_types["Sensor"]["properties"][0]),
        "Equipment": ("EquipmentStatus", entity_types["Equipment"]["timeseriesProperties"], entity_types["Equipment"]["properties"][0]),
        "ProductionLine": ("ProductionMetrics", entity_types["ProductionLine"]["timeseriesProperties"], entity_types["ProductionLine"]["properties"][0]),
    }
    for name, (table, ts_props, id_prop) in ts_config.items():
        et_id = entity_types[name]["id"]
        ts = build_ts_binding(name, ws_id, kql_id, cluster_uri, db_name, table, ts_props, id_prop)
        parts.append({"path": f"EntityTypes/{et_id}/DataBindings/{ts['id']}.json", "payload": b64encode(ts), "payloadType": "InlineBase64"})

    # Relationships
    for rel in relationships:
        rel_id = rel["id"]
        parts.append({"path": f"RelationshipTypes/{rel_id}/definition.json", "payload": b64encode(rel), "payloadType": "InlineBase64"})

    # Contextualizations
    ctx_config = [
        ("Has_Line", "DIM_LINE", "PlantId", pid("Plant", 1), "LineId", pid("ProductionLine", 1)),
        ("Has_Equipment", "DIM_EQUIPMENT", "LineId", pid("ProductionLine", 1), "EquipmentId", pid("Equipment", 1)),
        ("Has_Sensor", "DIM_SENSOR", "EquipmentId", pid("Equipment", 1), "SensorId", pid("Sensor", 1)),
        ("Assigned_To", "DIM_WORKORDER", "WorkOrderId", pid("WorkOrder", 1), "LineId", pid("ProductionLine", 1)),
        ("Produces", "DIM_WORKORDER", "WorkOrderId", pid("WorkOrder", 1), "ProductId", pid("Product", 1)),
    ]
    for rel_name, table, src_col, src_pid, tgt_col, tgt_pid in ctx_config:
        rel_id = str(REL_IDS[rel_name])
        ctx = build_contextualization(ws_id, lh_id, table, src_col, src_pid, tgt_col, tgt_pid)
        parts.append({"path": f"RelationshipTypes/{rel_id}/Contextualizations/{ctx['id']}.json",
                       "payload": b64encode(ctx), "payloadType": "InlineBase64"})

    print(f"Built {len(parts)} definition parts:")
    for p in parts:
        print(f"  {p['path']}")

    # Push
    print(f"\nPushing to ontology {ont_id}...")
    payload = {"definition": {"parts": parts}}
    result = fabric_lro_post(f"/workspaces/{ws_id}/ontologies/{ont_id}/updateDefinition", payload, token)
    print(f"Push result: {result}")

    # Validate
    print("\nValidating via getDefinition...")
    time.sleep(5)
    defn = fabric_lro_post(f"/workspaces/{ws_id}/ontologies/{ont_id}/getDefinition", None, token, follow_result=True)
    if defn:
        result_parts = defn.get("definition", {}).get("parts", [])
        print(f"Parts returned: {len(result_parts)}")
        et_count = sum(1 for p in result_parts if p["path"].startswith("EntityTypes/") and p["path"].endswith("/definition.json"))
        rel_count = sum(1 for p in result_parts if p["path"].startswith("RelationshipTypes/") and p["path"].endswith("/definition.json"))
        db_count = sum(1 for p in result_parts if "/DataBindings/" in p["path"])
        ctx_count = sum(1 for p in result_parts if "/Contextualizations/" in p["path"])
        print(f"Entity Types: {et_count}, Relationships: {rel_count}, DataBindings: {db_count}, Contextualizations: {ctx_count}")
    else:
        print("ERROR: getDefinition returned empty")


if __name__ == "__main__":
    main()
