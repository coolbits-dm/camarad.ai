"""GA4 OAuth callback canonical flow tests (shadow, local test client)."""
from urllib.parse import urlparse, parse_qs
import uuid

import app as m


def _hdr(uid=1):
    return {"X-User-ID": str(uid)}


def run():
    original_gateway = m.COOLBITS_GATEWAY_ENABLED
    original_coolbits_request = m._coolbits_request
    original_requests_get = m.requests.get
    m.COOLBITS_GATEWAY_ENABLED = True
    state_value = f"state-{uuid.uuid4().hex}"

    def fake_coolbits_request(method, path, params=None, body=None, timeout=25, extra_headers=None):
        if path == "/api/connectors/ga4/auth/url":
            return 200, {
                "url": (
                    "https://accounts.google.com/o/oauth2/v2/auth?"
                    "client_id=demo"
                    "&redirect_uri=https%3A%2F%2Fcloud.cblm.ai%2Fapi%2Fconnectors%2Fga4%2Foauth%2Fcallback"
                    "&response_type=code"
                    "&scope=openid"
                    f"&state={state_value}"
                )
            }, ""
        if path == "/api/connectors/ga4/status":
            return 200, {"connected": True, "status": "connected", "selectedPropertyId": "properties/999"}, ""
        if path == "/api/connectors/ga4/report":
            return 200, {"data": {"overview": {"sessions": 11, "users": 9, "conversions": 2, "revenue": 1.25}}}, ""
        return 404, {"error": "not_found"}, ""

    class _Resp:
        status_code = 200
        content = b"<html>ok</html>"
        headers = {"content-type": "text/html"}

    def fake_requests_get(url, params=None, headers=None, timeout=30, allow_redirects=False):
        return _Resp()

    m._coolbits_request = fake_coolbits_request
    m.requests.get = fake_requests_get

    c = m.app.test_client()

    # 1) auth-url gets rewritten to canonical callback host.
    r = c.get("/api/connectors/ga4/auth-url", headers=_hdr(1))
    assert r.status_code == 200, r.get_data(as_text=True)
    payload = r.get_json()
    parsed = urlparse(payload.get("url") or "")
    redirect_uri = parse_qs(parsed.query).get("redirect_uri", [""])[0]
    assert redirect_uri.endswith("/api/connectors/ga4/oauth/callback"), redirect_uri

    # 2) callback consumes state and returns popup close html with no-store.
    r2 = c.get(f"/api/connectors/ga4/oauth/callback?code=ok&state={state_value}", headers=_hdr(1))
    body2 = r2.get_data(as_text=True)
    assert r2.status_code == 200
    assert "postMessage" in body2
    assert "no-store" in str(r2.headers.get("Cache-Control") or "").lower()

    # 3) second call with same state is rejected (state replay protection).
    r3 = c.get(f"/api/connectors/ga4/oauth/callback?code=ok&state={state_value}", headers=_hdr(1))
    assert r3.status_code == 400

    # 4) overview without property_id uses active property from status.
    r4 = c.get("/api/connectors/ga4/overview?range=7days", headers=_hdr(1))
    data4 = r4.get_json()
    assert r4.status_code == 200
    assert data4.get("property_id") == "properties/999"
    assert data4.get("source") == "coolbits"

    m.COOLBITS_GATEWAY_ENABLED = original_gateway
    m._coolbits_request = original_coolbits_request
    m.requests.get = original_requests_get
    print("GA4 OAuth tests: OK")


if __name__ == "__main__":
    run()
