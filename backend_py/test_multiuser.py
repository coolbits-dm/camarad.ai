"""Test multi-user isolation and export/import"""
from app import app
import json

client = app.test_client()

def set_user(uid):
    """Set current user cookie for Flask 2.3+ test client"""
    client.set_cookie('camarad_user_id', str(uid), domain='localhost')

print("=" * 60)
print("TEST 1: /api/users returns 3 mock users")
print("=" * 60)
r = client.get('/api/users')
users = r.get_json()
print(f"  Users: {users}")
assert len(users) >= 3, "Should have at least 3 users"
print("  ✅ Pass")

print()
print("=" * 60)
print("TEST 2: Default user (no cookie) = User 1")
print("=" * 60)
# Save flow as User 1 (default)
r = client.post('/api/flows',
    data=json.dumps({"name": "User1 Flow", "flow": {"nodes": [{"id": "n1", "type": "trigger"}]}, "thumbnail": "thumb1"}),
    content_type='application/json')
data = r.get_json()
print(f"  Save as User1: {data}")
u1_flow_id = data['flow_id']

# Save agent config as User 1
r = client.post('/api/agents/ppc-specialist',
    data=json.dumps({"custom_name": "User1 PPC", "llm_provider": "Grok", "llm_model": "grok-1", "status": "Active"}),
    content_type='application/json')
print(f"  Agent config User1: {r.get_json()}")

# Save connector config as User 1
r = client.post('/api/connectors/google-ads',
    data=json.dumps({"status": "Connected", "config": {"api_key": "user1key"}}),
    content_type='application/json')
print(f"  Connector config User1: {r.get_json()}")
print("  ✅ Pass")

print()
print("=" * 60)
print("TEST 3: User 2 sees empty flows (isolation)")
print("=" * 60)
# Set cookie for User 2
set_user(2)
r = client.get('/api/flows')
flows = r.get_json()
print(f"  User2 flows: {len(flows)} (should be 0)")
assert len(flows) == 0, "User2 should have no flows"

# User 2 saves their own flow
r = client.post('/api/flows',
    data=json.dumps({"name": "User2 Flow", "flow": {"nodes": [{"id": "n2", "type": "agent"}]}, "thumbnail": "thumb2"}),
    content_type='application/json')
u2_data = r.get_json()
print(f"  User2 saves flow: {u2_data}")

# User 2 saves agent config
r = client.post('/api/agents/ppc-specialist',
    data=json.dumps({"custom_name": "Alice PPC Expert", "llm_provider": "OpenAI", "llm_model": "gpt-4", "status": "Active"}),
    content_type='application/json')
print(f"  Agent config User2: {r.get_json()}")
print("  ✅ Pass")

print()
print("=" * 60)
print("TEST 4: User 1 still sees only their flow")
print("=" * 60)
set_user(1)
r = client.get('/api/flows')
flows = r.get_json()
print(f"  User1 flows: {len(flows)} (should be 1)")
assert len(flows) == 1 and flows[0]['name'] == 'User1 Flow', "User1 should only see their flow"

# Verify agent config is User1's
r = client.get('/api/agents/ppc-specialist')
config = r.get_json()
print(f"  User1 agent name: {config.get('custom_name')} (should be 'User1 PPC')")
assert config.get('custom_name') == 'User1 PPC'
print("  ✅ Pass")

print()
print("=" * 60)
print("TEST 5: User 2 sees only their config")
print("=" * 60)
set_user(2)
r = client.get('/api/agents/ppc-specialist')
config = r.get_json()
print(f"  User2 agent name: {config.get('custom_name')} (should be 'Alice PPC Expert')")
assert config.get('custom_name') == 'Alice PPC Expert'

r = client.get('/api/flows')
flows = r.get_json()
print(f"  User2 flows: {len(flows)} (should be 1)")
assert len(flows) == 1 and flows[0]['name'] == 'User2 Flow'
print("  ✅ Pass")

print()
print("=" * 60)
print("TEST 6: Export User 1 config")
print("=" * 60)
set_user(1)
r = client.get('/api/export')
export_data = r.get_json()
print(f"  Exported: {export_data['agents'].__len__()} agents, {len(export_data['connectors'])} connectors, {len(export_data['flows'])} flows")
print(f"  Version: {export_data.get('version')}, User: {export_data.get('user_id')}")
assert export_data['user_id'] == 1
assert len(export_data['agents']) >= 1
assert len(export_data['flows']) >= 1
print("  ✅ Pass")

print()
print("=" * 60)
print("TEST 7: Import into User 3")
print("=" * 60)
set_user(3)

# First verify User 3 has nothing
r = client.get('/api/flows')
assert len(r.get_json()) == 0, "User3 should start empty"

# Import User1's export
r = client.post('/api/import',
    data=json.dumps(export_data),
    content_type='application/json')
result = r.get_json()
print(f"  Import result: {result}")
assert result['success']

# Verify User 3 now has the imported data
r = client.get('/api/flows')
flows = r.get_json()
print(f"  User3 flows after import: {len(flows)} (should be 1)")
assert len(flows) >= 1

r = client.get('/api/agents/ppc-specialist')
config = r.get_json()
print(f"  User3 agent name: {config.get('custom_name')} (should be 'User1 PPC' from import)")
assert config.get('custom_name') == 'User1 PPC'
print("  ✅ Pass")

print()
print("=" * 60)
print("TEST 8: User 2 unaffected by User 3's import")
print("=" * 60)
set_user(2)
r = client.get('/api/agents/ppc-specialist')
config = r.get_json()
print(f"  User2 still: {config.get('custom_name')} (should be 'Alice PPC Expert')")
assert config.get('custom_name') == 'Alice PPC Expert'
print("  ✅ Pass")

# Cleanup
print()
print("=" * 60)
print("CLEANUP: Delete test flows")
print("=" * 60)
for uid_str in ['1', '2', '3']:
    set_user(int(uid_str))
    r = client.get('/api/flows')
    for f in r.get_json():
        client.delete(f'/api/flows/{f["id"]}')
        print(f"  Deleted user{uid_str} flow [{f['id']}] {f['name']}")

print("\n✅ ALL MULTI-USER + EXPORT/IMPORT TESTS PASSED!")
