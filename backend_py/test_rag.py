"""Test RAG improvements end-to-end"""
from app import app
import json

client = app.test_client()

print("=" * 60)
print("TEST 1: /api/rag/api-docs with connector filter (Google Ads)")
print("=" * 60)
r = client.get('/api/rag/api-docs?q=campaign+budget&connector=Google+Ads&limit=2')
data = r.get_json()
print(f"  Results: {len(data)}")
for d in data:
    print(f"  [{d['connector']}] {d['title'][:60]}")
    print(f"    URL: {d['url'][:80]}")
    print(f"    Type: {d['section_type']}")
    print()

print("=" * 60)
print("TEST 2: /api/rag/api-docs keyword search (no filter)")
print("=" * 60)
r = client.get('/api/rag/api-docs?q=create+campaign&limit=3')
data = r.get_json()
print(f"  Results: {len(data)}")
for d in data:
    print(f"  [{d['connector']}] {d['title'][:60]}")

print()
print("=" * 60)
print("TEST 3: /api/agent-connectors/ppc-specialist")
print("=" * 60)
r = client.get('/api/agent-connectors/ppc-specialist')
print(f"  Connectors: {r.get_json()}")

print()
print("=" * 60)
print("TEST 4: Chat POST with PPC specialist (should include API docs)")
print("=" * 60)
r = client.post('/chat/agency/ppc-specialist',
    data=json.dumps({"message": "show me campaign budget info"}),
    content_type='application/json')
data = r.get_json()
resp = data.get('response', '')
has_docs = '📚' in resp or 'API Documentation' in resp
print(f"  Status: {r.status_code}")
print(f"  Has API docs section: {has_docs}")
print(f"  Response preview: {resp[:300]}...")

print()
print("=" * 60)
print("TEST 5: Chat POST with DevOps (should get GitHub/GCP docs)")
print("=" * 60)
r = client.post('/chat/development/devops-infra',
    data=json.dumps({"message": "how to set up CI/CD pipeline"}),
    content_type='application/json')
data = r.get_json()
resp = data.get('response', '')
has_docs = '📚' in resp or 'API Documentation' in resp
print(f"  Status: {r.status_code}")
print(f"  Has API docs section: {has_docs}")
print(f"  Response preview: {resp[:300]}...")

print()
print("=" * 60)
print("TEST 6: Chat POST with Life Coach (no connectors, no docs)")
print("=" * 60)
r = client.post('/chat/personal/life-coach',
    data=json.dumps({"message": "help me set goals"}),
    content_type='application/json')
data = r.get_json()
resp = data.get('response', '')
has_docs = '📚' in resp
print(f"  Status: {r.status_code}")
print(f"  Has API docs section: {has_docs} (should be False)")
print(f"  Response preview: {resp[:200]}...")

print("\n✅ All RAG tests completed!")
