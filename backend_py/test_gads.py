"""Quick test for all Google Ads mock API endpoints"""
import requests

BASE = "http://localhost:5051"

# 1. Accounts
r = requests.get(f"{BASE}/api/connectors/google-ads/accounts")
assert r.status_code == 200
d = r.json()
print(f"✅ 1. Accounts: {len(d['accounts'])} loaded (MCC + {len(d['accounts'])-1} clients)")

# 2. Campaigns
r = requests.get(f"{BASE}/api/connectors/google-ads/campaigns?account_id=123-456-7890")
assert r.status_code == 200
d = r.json()
print(f"✅ 2. Campaigns: {len(d['campaigns'])} campaigns, spent=${d['summary']['total_spent']}, ROAS={d['summary']['avg_roas']}x")

# 3. Keywords
r = requests.get(f"{BASE}/api/connectors/google-ads/keywords?campaign_id=c-1001")
assert r.status_code == 200
d = r.json()
print(f"✅ 3. Keywords: {len(d['keywords'])} keywords for campaign {d['campaign_id']}")

# 4. Metrics
r = requests.get(f"{BASE}/api/connectors/google-ads/metrics?days=7")
assert r.status_code == 200
d = r.json()
print(f"✅ 4. Metrics: {len(d['daily_metrics'])} daily datapoints over {d['days']} days")

# 5. Reports (campaign_performance)
r = requests.get(f"{BASE}/api/connectors/google-ads/reports?type=campaign_performance&account_id=123-456-7890")
assert r.status_code == 200
d = r.json()
print(f"✅ 5. Report (perf): {len(d['rows'])} rows, generated at {d['generated_at'][:19]}")

# 5b. Reports (budget_pacing)
r = requests.get(f"{BASE}/api/connectors/google-ads/reports?type=budget_pacing&account_id=123-456-7890")
assert r.status_code == 200
d = r.json()
print(f"✅ 5b. Report (pacing): {len(d['rows'])} rows")

# 6. Asset Generator
r = requests.post(f"{BASE}/api/connectors/google-ads/generate-assets", json={"product": "Running Shoes", "tone": "casual"})
assert r.status_code == 200
d = r.json()
print(f"✅ 6. Assets: {len(d['headlines'])} headlines, {len(d['descriptions'])} descriptions, tone={d['tone']}")

# 7. Test API Call
r = requests.post(f"{BASE}/api/connectors/google-ads/test-call", json={"method": "GET", "endpoint": "/v17/customers/123456/campaigns"})
assert r.status_code == 200
d = r.json()
print(f"✅ 7. API Test: status={d['response']['status_code']}, latency={d['latency_ms']}ms, quota={d['quota']['operations_remaining']}/{d['quota']['daily_limit']}")

# 8. Page loads
r = requests.get(f"{BASE}/connectors")
assert r.status_code == 200
assert "googleAdsPanel" in r.text
assert "gadsTabs" in r.text
print(f"✅ 8. Connectors page loads OK ({len(r.text)} bytes), Google Ads panel present")

print("\n🎉 ALL 8 TESTS PASSED — Google Ads mock connector fully operational!")
