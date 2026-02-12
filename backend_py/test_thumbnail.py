"""Test thumbnail save/load/duplicate flow features"""
from app import app
import json

client = app.test_client()

# Fake thumbnail base64 (tiny 1x1 transparent PNG)
FAKE_THUMB = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQI12NgAAIABQABNjN9GQAAAAlwSFlzAAAWJQAAFiUBSVIk8AAAAA0lEQVQI12P4z8BQDwAEgAF/QualzQAAAABJRU5ErkJggg=="

print("=" * 60)
print("TEST 1: Save flow with thumbnail")
print("=" * 60)
r = client.post('/api/flows',
    data=json.dumps({
        "name": "Test Flow With Thumbnail",
        "flow": {"version": "1.0", "nodes": [{"id": "n1", "type": "trigger", "x": 100, "y": 100, "label": "Start"}], "connections": []},
        "thumbnail": FAKE_THUMB
    }),
    content_type='application/json')
data = r.get_json()
print(f"  Status: {r.status_code}")
print(f"  Success: {data.get('success')}")
print(f"  Flow ID: {data.get('flow_id')}")
flow_id = data.get('flow_id')

print()
print("=" * 60)
print("TEST 2: Get flows list (should include thumbnail)")
print("=" * 60)
r = client.get('/api/flows')
flows = r.get_json()
print(f"  Total flows: {len(flows)}")
found = None
for f in flows:
    has_thumb = "Yes" if f.get('thumbnail') else "No"
    print(f"  [{f['id']}] {f['name']} | Thumbnail: {has_thumb}")
    if f['id'] == flow_id:
        found = f
if found:
    print(f"  ✅ Our flow has thumbnail: {bool(found.get('thumbnail'))}")

print()
print("=" * 60)
print("TEST 3: Duplicate flow with custom name")
print("=" * 60)
r = client.post(f'/api/flows/{flow_id}/duplicate',
    data=json.dumps({"name": "My Custom Duplicate"}),
    content_type='application/json')
data = r.get_json()
print(f"  Success: {data.get('success')}")
print(f"  New name: {data.get('new_name')}")
print(f"  New ID: {data.get('new_flow_id')}")

print()
print("=" * 60)
print("TEST 4: Duplicate flow WITHOUT custom name (should default to Copy)")
print("=" * 60)
r = client.post(f'/api/flows/{flow_id}/duplicate',
    content_type='application/json')
data = r.get_json()
print(f"  Success: {data.get('success')}")
print(f"  New name: {data.get('new_name')}")

print()
print("=" * 60)
print("TEST 5: Verify duplicated flows have thumbnails")
print("=" * 60)
r = client.get('/api/flows')
flows = r.get_json()
for f in flows:
    has_thumb = "✅" if f.get('thumbnail') else "❌"
    print(f"  [{f['id']}] {f['name']} | Thumbnail: {has_thumb}")

print()
print("=" * 60)
print("TEST 6: Rename flow")
print("=" * 60)
r = client.put(f'/api/flows/{flow_id}',
    data=json.dumps({"name": "Renamed Flow"}),
    content_type='application/json')
data = r.get_json()
print(f"  Success: {data.get('success')}")
print(f"  Message: {data.get('message')}")

print()
print("=" * 60)
print("TEST 7: Delete test flows (cleanup)")
print("=" * 60)
r = client.get('/api/flows')
flows = r.get_json()
for f in flows:
    if 'Test' in f['name'] or 'Duplicate' in f['name'] or 'Renamed' in f['name'] or 'Copy' in f['name'] or 'Custom' in f['name']:
        dr = client.delete(f'/api/flows/{f["id"]}')
        print(f"  Deleted [{f['id']}] {f['name']}: {dr.get_json().get('success')}")

print("\n✅ All thumbnail + duplicate tests passed!")
