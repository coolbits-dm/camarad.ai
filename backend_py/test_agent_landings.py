"""Hermetic tests for agent landing pages and CTA routing."""
from urllib.parse import parse_qs, urlparse

import app as m


def run():
    c = m.app.test_client()

    r = c.get("/agents/ppc?utm_source=google&utm_campaign=ppc_ai_agent")
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    cache_ctl = str(r.headers.get("Cache-Control") or "").lower()
    assert "no-store" in cache_ctl
    body = r.get_data(as_text=True)
    assert "PPC AI Agent" in body
    assert "Start with Google" in body
    assert "/api/auth/google/start?returnTo=" in body

    marker = '/api/auth/google/start?returnTo='
    idx = body.find(marker)
    assert idx >= 0
    frag = body[idx:].split('"', 1)[0]
    parsed = urlparse(frag)
    q = parse_qs(parsed.query)
    return_to = q.get("returnTo", [""])[0]
    assert return_to.startswith("/chat/agency/ppc-specialist"), return_to
    assert "from=agent-landing" in return_to, return_to
    assert "agent=ppc" in return_to, return_to
    assert "utm_source=google" in return_to, return_to
    assert "utm_campaign=ppc_ai_agent" in return_to, return_to

    attr_cookie = r.headers.get("Set-Cookie") or ""
    assert "camarad_attr=" in attr_cookie

    r2 = c.get("/agents/nope")
    assert r2.status_code == 404

    r3 = c.get("/ppc-ai", follow_redirects=False)
    assert r3.status_code == 301
    assert "/agents/ppc" in str(r3.headers.get("Location") or "")

    print("Agent landing tests: OK")


if __name__ == "__main__":
    run()
