#!/usr/bin/env python3
"""Check KQL telemetry data and ontology entity status"""
import json
import requests
from azure.identity import DefaultAzureCredential

with open('ontologies/SaintGobain/config.json') as f:
    config = json.load(f)

ws = config['workspace']['id']
kql_uri = config['kqlDatabase']['queryServiceUri']
kql_db = config['kqlDatabase']['name']
lh_id = config['lakehouse']['id']
API = 'https://api.fabric.microsoft.com/v1'

cred = DefaultAzureCredential()
fab_token = cred.get_token('https://api.fabric.microsoft.com/.default').token
h_fab = {'Authorization': f'Bearer {fab_token}'}

# 1. Check KQL tables for telemetry data
print('=== KQL TELEMETRY DATA ===')
try:
    kusto_token = cred.get_token('https://kusto.kusto.windows.net/.default').token
    h_kql = {'Authorization': f'Bearer {kusto_token}', 'Content-Type': 'application/json'}
    
    tables = ['SensorTelemetry', 'EquipmentStatus', 'ProductionMetrics', 'Alerts']
    for table in tables:
        body = {
            'db': kql_db,
            'csl': f'{table} | count'
        }
        r = requests.post(f'{kql_uri}/v1/rest/query', headers=h_kql, json=body)
        if r.status_code == 200:
            frames = r.json().get('Tables', [])
            if frames:
                rows = frames[0].get('Rows', [])
                count = rows[0][0] if rows else 0
                print(f'  {table}: {count} rows')
            else:
                print(f'  {table}: no frames returned')
        else:
            print(f'  {table}: HTTP {r.status_code} - {r.text[:100]}')
    
    # Check latest timestamp for any table with data
    for table in ['SensorTelemetry', 'ProductionMetrics', 'EquipmentStatus']:
        body = {'db': kql_db, 'csl': f'{table} | summarize MaxTS=max(Timestamp), MinTS=min(Timestamp) | project MinTS, MaxTS'}
        r = requests.post(f'{kql_uri}/v1/rest/query', headers=h_kql, json=body)
        if r.status_code == 200:
            frames = r.json().get('Tables', [])
            if frames and frames[0].get('Rows'):
                row = frames[0]['Rows'][0]
                print(f'  {table} time range: {row[0]} → {row[1]}')
except Exception as e:
    print(f'  KQL Error: {e}')

print()

# 2. Check Lakehouse tables for entity data  
print('=== LAKEHOUSE SOURCE DATA ===')
r = requests.get(f'{API}/workspaces/{ws}/lakehouses/{lh_id}/tables', headers=h_fab)
if r.status_code == 200:
    tables = r.json().get('data', [])
    print(f'Tables: {len(tables)}')
    for t in tables:
        print(f'  {t.get("name")}')
else:
    print(f'Tables API: HTTP {r.status_code}')

print()

# 3. Check companion lakehouse for materialized data
print('=== COMPANION LAKEHOUSE ===')
items = requests.get(f'{API}/workspaces/{ws}/items', headers=h_fab).json().get('value', [])
for i in items:
    if i['type'] == 'Lakehouse' and '_lh_' in i['displayName']:
        comp_id = i['id']
        print(f'Name: {i["displayName"]}')
        r = requests.get(f'{API}/workspaces/{ws}/lakehouses/{comp_id}/tables', headers=h_fab)
        print(f'Tables API: HTTP {r.status_code}')
        if r.status_code == 200:
            tables = r.json().get('data', [])
            print(f'Tables: {len(tables)}')
            for t in tables:
                print(f'  {t.get("name")}')
        else:
            # Check via OneLake
            storage_token = cred.get_token('https://storage.azure.com/.default').token
            h_ol = {'Authorization': f'Bearer {storage_token}'}
            ws_name = config['workspace']['name']
            comp_name = i['displayName']
            url = f'https://onelake.dfs.fabric.microsoft.com/{ws_name}/{comp_name}.Lakehouse/Tables?resource=filesystem&recursive=true'
            r_ol = requests.get(url, headers=h_ol)
            print(f'OneLake /Tables: HTTP {r_ol.status_code}')
            if r_ol.status_code == 200:
                paths = r_ol.json().get('paths', [])
                print(f'Contents: {len(paths)} entries')
                for p in paths[:20]:
                    pname = p.get('name', '?')
                    isdir = p.get('isDirectory', False)
                    print(f'  {pname} (dir={isdir})')

print()

# 4. Check graph index
print('=== GRAPH INDEX ===')
for i in items:
    if i['type'] == 'GraphIndex' or 'graph' in i['displayName'].lower():
        print(f'GraphIndex: {i["displayName"]} ({i["id"][:8]}...)')
        storage_token = cred.get_token('https://storage.azure.com/.default').token
        h_ol = {'Authorization': f'Bearer {storage_token}'}
        ws_name = config['workspace']['name']
        url = f'https://onelake.dfs.fabric.microsoft.com/{ws_name}/{i["displayName"]}.GraphIndex?resource=filesystem&recursive=true'
        r_gi = requests.get(url, headers=h_ol)
        print(f'OneLake: HTTP {r_gi.status_code}')
        if r_gi.status_code == 200:
            paths = r_gi.json().get('paths', [])
            print(f'Contents: {len(paths)} entries')
            for p in paths[:30]:
                print(f'  {p.get("name", "?")}')
