"""
Test suite for Avatar Level 2 Upgrade
Tests: expressions, CSS animations, DB persistence, integration across views
"""
import requests

BASE = "http://localhost:5051"

def test_agents_page():
    r = requests.get(f"{BASE}/agents")
    assert r.status_code == 200, f"Agents page: {r.status_code}"
    assert "CamaradAvatars" in r.text, "Missing avatars JS reference"
    assert "injectAvatarsIntoCards" in r.text, "Missing card injection function"
    print("[PASS] 1/10 — /agents page loads with avatar system")

def test_agent_detail_level2():
    r = requests.get(f"{BASE}/agent/ceo-strategy")
    assert r.status_code == 200, f"Agent detail: {r.status_code}"
    assert "micro-tilt" in r.text, "Missing Level 2 micro-tilt class"
    assert 'data-expr="wink"' in r.text, "Missing wink expression button"
    assert 'data-expr="excited"' in r.text, "Missing excited expression button"
    assert "avatar-photo-wrap" in r.text, "Missing photo wrapper"
    assert "removePhotoBtn" in r.text, "Missing remove photo button"
    assert "agent-name-accent" in r.text, "Missing name accent class"
    print("[PASS] 2/10 — /agent/ceo-strategy has Level 2 features")

def test_save_avatar_config():
    r = requests.post(f"{BASE}/api/agents/ceo-strategy", json={
        "custom_name": "CEO Oracle",
        "avatar_colors": {"accent": "#ff6b6b", "skin": "#D4A574", "hair": "#2C2C2C"},
        "llm_provider": "Grok",
        "llm_model": "grok-beta",
        "temperature": 0.7,
        "max_tokens": 2048,
        "rag_enabled": True,
        "status": "Active"
    })
    assert r.status_code == 200, f"Save config: {r.status_code}"
    data = r.json()
    assert data.get("success"), f"Save failed: {data}"
    print("[PASS] 3/10 — POST /api/agents/ceo-strategy with avatar_colors")

def test_load_avatar_config():
    r = requests.get(f"{BASE}/api/agents/ceo-strategy")
    data = r.json()
    assert data["custom_name"] == "CEO Oracle", f"Name mismatch: {data['custom_name']}"
    assert data["avatar_colors"] is not None, "avatar_colors not saved"
    assert data["avatar_colors"]["accent"] == "#ff6b6b", f"Color mismatch: {data['avatar_colors']}"
    print("[PASS] 4/10 — GET /api/agents/ceo-strategy returns avatar_colors")

def test_agents_list_api():
    r = requests.get(f"{BASE}/api/agents/list")
    agents = r.json()
    ceo = next((a for a in agents if a["slug"] == "ceo-strategy"), None)
    assert ceo is not None, "CEO not in agents list"
    assert ceo["name"] == "CEO Oracle", f"List name: {ceo['name']}"
    assert ceo["avatar_colors"]["accent"] == "#ff6b6b", "List colors missing"
    print("[PASS] 5/10 — /api/agents/list returns custom name + colors")

def test_chat_page_integration():
    r = requests.get(f"{BASE}/chat/business/ceo-strategy")
    assert r.status_code == 200, f"Chat: {r.status_code}"
    assert "micro-tilt" in r.text, "Chat missing micro-tilt"
    assert "_agentPhotoSrc" in r.text, "Chat missing photo support"
    assert "avatar_colors" in r.text, "Chat missing colors integration"
    print("[PASS] 6/10 — /chat/business/ceo-strategy has Level 2 integration")

def test_boardroom_integration():
    r = requests.get(f"{BASE}/boardroom")
    assert r.status_code == 200, f"Boardroom: {r.status_code}"
    assert "getSVG" in r.text, "Boardroom missing avatar SVG in transcript"
    assert "chat-avatar-wrap" in r.text, "Boardroom missing avatar wrapper in bubbles"
    print("[PASS] 7/10 — /boardroom has avatar integration in transcript")

def test_css_level2():
    r = requests.get(f"{BASE}/static/css/avatars.css")
    assert r.status_code == 200
    assert "Level 2" in r.text, "CSS missing Level 2 header"
    assert "avatarBlinkCSS" in r.text, "CSS missing blink animation"
    assert "avatarMicroTilt" in r.text, "CSS missing micro-tilt animation"
    assert "avatar-photo-wrap" in r.text, "CSS missing photo wrapper styles"
    assert "agent-name-accent" in r.text, "CSS missing name accent"
    assert "gesture-celebrate" in r.text, "CSS missing celebrate gesture"
    assert "gesture-speak" in r.text, "CSS missing speak gesture"
    assert "gesture-alert" in r.text, "CSS missing alert gesture"
    assert "typingDotsAnim" in r.text, "CSS missing typing dots animation"
    print("[PASS] 8/10 — avatars.css has all Level 2 animations + styles")

def test_js_level2_expressions():
    r = requests.get(f"{BASE}/static/js/avatars.js")
    assert r.status_code == 200
    assert "case 'wink'" in r.text, "JS missing wink expression"
    assert "case 'excited'" in r.text, "JS missing excited expression"
    assert "wink:" in r.text, "JS missing wink gesture"
    # Check expression cycle includes new expressions
    assert "'wink'" in r.text and "'excited'" in r.text, "Expression cycle missing new expressions"
    print("[PASS] 9/10 — avatars.js has wink + excited expressions + gestures")

def test_save_and_reload_different_agent():
    # Test with a different agent to ensure independence
    r = requests.post(f"{BASE}/api/agents/creative-muse", json={
        "custom_name": "Artemis",
        "avatar_colors": {"accent": "#f778ba", "skin": "#E0AC69"},
        "llm_provider": "Grok",
        "llm_model": "grok-beta",
        "temperature": 0.9,
        "max_tokens": 4096,
        "rag_enabled": True,
        "status": "Active"
    })
    assert r.status_code == 200, f"Save muse: {r.status_code}"
    
    r = requests.get(f"{BASE}/api/agents/creative-muse")
    data = r.json()
    assert data["custom_name"] == "Artemis", f"Muse name: {data['custom_name']}"
    assert data["avatar_colors"]["accent"] == "#f778ba", "Muse colors not saved"
    
    # CEO should still be intact
    r = requests.get(f"{BASE}/api/agents/ceo-strategy")
    data = r.json()
    assert data["custom_name"] == "CEO Oracle", "CEO was corrupted by muse save"
    print("[PASS] 10/10 — Multiple agents save/load independently")


if __name__ == "__main__":
    tests = [
        test_agents_page,
        test_agent_detail_level2,
        test_save_avatar_config,
        test_load_avatar_config,
        test_agents_list_api,
        test_chat_page_integration,
        test_boardroom_integration,
        test_css_level2,
        test_js_level2_expressions,
        test_save_and_reload_different_agent,
    ]
    
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1
    
    print(f"\n{'='*55}")
    print(f"  Avatar Level 2 Tests: {passed}/{passed+failed} passed")
    if failed == 0:
        print("  ✅ ALL TESTS PASSED!")
    else:
        print(f"  ❌ {failed} FAILED")
    print(f"{'='*55}")
