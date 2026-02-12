from flask import Flask, render_template, request, jsonify, g, redirect, url_for, make_response, has_request_context
from config import Config
from database import init_db, get_db, save_message, get_messages, get_daily_message_count, is_user_premium, get_recent_conversations, get_conversation_context, create_new_conversation, get_or_create_conversation, update_conversation_title, search_conversations
from models import workspaces, get_agent_name, simulate_response, detect_handover, enhance_context, get_llm_response, get_api_docs_context
import markdown
import json
import copy
import math
from markupsafe import Markup
import os
import time
import requests
import re
import uuid
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from werkzeug.exceptions import HTTPException

# ── Agent-to-Connector relevance map ──────────────────────────────
# Maps each agent slug to the connectors whose API docs are most relevant
AGENT_CONNECTOR_MAP = {
    'ppc-specialist':        ['Google Ads', 'Meta Ads', 'LinkedIn Ads', 'Twitter/X Ads'],
    'seo-content':           ['Google Analytics 4', 'Google Tag Manager', 'Google Search Console'],
    'creative-director':     ['Meta Ads', 'TikTok Ads', 'Google Ads'],
    'social-media':          ['Meta Ads', 'TikTok Ads', 'Twitter/X Ads', 'Telegram'],
    'performance-analytics': ['Google Analytics 4', 'Google Tag Manager', 'Google Ads', 'Datadog'],
    'ceo-strategy':          ['Google Analytics 4', 'LinkedIn Ads', 'Stripe', 'HubSpot', 'Salesforce'],
    'cto-innovation':        ['GitHub', 'GitLab', 'Google Cloud Platform', 'Microsoft Azure', 'AWS'],
    'cmo-growth':            ['Google Ads', 'Meta Ads', 'TikTok Ads', 'LinkedIn Ads', 'Google Analytics 4', 'Mailchimp', 'Klaviyo', 'HubSpot'],
    'cfo-finance':           ['Stripe', 'PayPal', 'Shopify', 'QuickBooks'],
    'coo-operations':        ['Notion', 'Todoist', 'Stripe', 'HubSpot', 'Pipedrive', 'Salesforce'],
    'devops-infra':          ['GitHub', 'GitHub Actions', 'Google Cloud Platform', 'Microsoft Azure', 'AWS', 'Vercel', 'Netlify', 'Render'],
    'fullstack-dev':         ['GitHub', 'GitLab', 'Vercel', 'Netlify', 'Sentry'],
    'backend-architect':     ['GitHub', 'Google Cloud Platform', 'Microsoft Azure', 'AWS', 'Datadog', 'Sentry'],
    'frontend-uiux':         ['GitHub', 'Vercel', 'Netlify', 'Sentry'],
    'security-quality':      ['Snyk', 'SonarQube', 'Sentry', 'GitHub'],
    'life-coach':            [],
    'psychologist':          [],
    'personal-mentor':       ['Notion', 'Todoist'],
    'fitness-wellness':      ['Strava'],
    'creative-muse':         ['Notion'],
}

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config.from_object(Config)

# ── Coolbits Gateway (Google stack) ────────────────────────────────
# We can reuse Coolbits' mature OAuth + MCC logic by proxying Camarad connector calls to
# the local Coolbits service. Keep it feature-flagged until fully wired in UI.
COOLBITS_GATEWAY_ENABLED = str(os.getenv("COOLBITS_GATEWAY_ENABLED", "")).strip().lower() in ("1", "true", "yes", "on")
COOLBITS_URL = str(os.getenv("COOLBITS_URL", "http://127.0.0.1:8788")).strip().rstrip("/")
COOLBITS_PUBLIC_URL = str(os.getenv("COOLBITS_PUBLIC_URL", "")).strip().rstrip("/")
COOLBITS_GATEWAY_EMAIL = str(os.getenv("COOLBITS_GATEWAY_EMAIL", "dev@camarad.ai")).strip().lower()
COOLBITS_WORKSPACE_ID = str(os.getenv("COOLBITS_WORKSPACE_ID", "business")).strip().lower()  # coolbits: business/agency/developer
AUTH_REQUIRED = str(os.getenv("AUTH_REQUIRED", "1")).strip().lower() in ("1", "true", "yes", "on")
AUTH_COOKIE_SECURE = str(os.getenv("AUTH_COOKIE_SECURE", "0")).strip().lower() in ("1", "true", "yes", "on")
_coolbits_auth_cache = {"token": None, "fetched_at": 0.0}
FORCE_VERTEX_ALL_AGENTS = str(os.getenv("FORCE_VERTEX_ALL_AGENTS", "1")).strip().lower() in ("1", "true", "yes", "on")
_ALL_WORKSPACE_AGENT_SLUGS = {
    str(agent_slug).strip().lower()
    for _ws_data in (workspaces or {}).values()
    for agent_slug in ((_ws_data.get("agents") or {}).keys())
    if str(agent_slug).strip()
}
_REAL_AGENT_SLUGS_ENV = {
    s.strip().lower() for s in str(os.getenv("REAL_AGENT_SLUGS", "ppc-specialist,seo-content,life-coach")).split(",") if s.strip()
}
REAL_AGENT_SLUGS = (set(_ALL_WORKSPACE_AGENT_SLUGS) if FORCE_VERTEX_ALL_AGENTS else set(_REAL_AGENT_SLUGS_ENV))
COOLBITS_VERTEX_PROFILE = str(os.getenv("COOLBITS_VERTEX_PROFILE", "google-vertex-sterile")).strip() or "google-vertex-sterile"
GOOGLE_SITE_VERIFICATION = str(os.getenv("GOOGLE_SITE_VERIFICATION", "")).strip()
GOOGLE_SITE_VERIFICATION_FILE = str(os.getenv("GOOGLE_SITE_VERIFICATION_FILE", "")).strip()
GTM_CONTAINER_ID = str(os.getenv("GTM_CONTAINER_ID", "GTM-KGGP4B9N")).strip().upper()
BILLING_INTERNAL_TOKEN = str(os.getenv("BILLING_INTERNAL_TOKEN", "")).strip()
CALIBRATION_MIN_ROWS_WITH_TOKENS = int(os.getenv("CALIBRATION_MIN_ROWS_WITH_TOKENS", "200") or 200)
CALIBRATION_MIN_ROWS_WITH_BILLABLE = int(os.getenv("CALIBRATION_MIN_ROWS_WITH_BILLABLE", "150") or 150)
CALIBRATION_MIN_CT_ACTUAL_SUM = int(os.getenv("CALIBRATION_MIN_CT_ACTUAL_SUM", "10000") or 10000)
CALIBRATION_MIN_BILLABLE_USD = float(os.getenv("CALIBRATION_MIN_BILLABLE_USD", "5.0") or 5.0)
CALIBRATION_MAX_DELTA_PCT = float(os.getenv("CALIBRATION_MAX_DELTA_PCT", "0.15") or 0.15)
CALIBRATION_ALPHA = float(os.getenv("CALIBRATION_ALPHA", "0.30") or 0.30)
CALIBRATION_APPLY_DELAY_MINUTES = int(os.getenv("CALIBRATION_APPLY_DELAY_MINUTES", "0") or 0)
GA4_OAUTH_STATE_TTL_SECONDS = int(os.getenv("GA4_OAUTH_STATE_TTL_SECONDS", "900") or 900)

_REAL_AGENT_OBJECTIVES = {
    "life-coach": (
        "You are Personal Assistant, the default Camarad guide inside the Camarad product environment. "
        "Never present yourself as a generic model or mention model training origin. "
        "Be concise, practical, and action-oriented. "
        "Coordinate with specialist agents when needed: PPC Specialist for paid media and SEO Strategist for organic/content. "
        "If request is outside your scope, propose a handoff clearly."
    ),
    "ppc-specialist": (
        "You are PPC Specialist inside Camarad. "
        "Never present yourself as a generic model or mention model training origin. "
        "Focus on paid acquisition strategy and optimization. "
        "Use clear steps: diagnosis -> actions -> expected impact. "
        "Mention when SEO Strategist or Personal Assistant should be involved."
    ),
    "seo-content": (
        "You are SEO & Content Strategist inside Camarad. "
        "Never present yourself as a generic model or mention model training origin. "
        "Focus on technical/content SEO and growth content planning. "
        "Give prioritized actions and measurable KPIs. "
        "Mention when PPC Specialist or Personal Assistant should be involved."
    ),
}


def _sanitize_gtm_container_id(raw):
    value = str(raw or "").strip().upper()
    if not value:
        return ""
    if re.fullmatch(r"GTM-[A-Z0-9]+", value):
        return value
    return ""


def _sanitize_google_verification_file(raw):
    value = str(raw or "").strip()
    if not value:
        return ""
    # expected format: google1234567890abcdef.html
    if re.fullmatch(r"google[a-zA-Z0-9_-]+\.html", value):
        return value
    return ""


GTM_CONTAINER_ID = _sanitize_gtm_container_id(GTM_CONTAINER_ID)
GOOGLE_SITE_VERIFICATION_FILE = _sanitize_google_verification_file(GOOGLE_SITE_VERIFICATION_FILE)


@app.context_processor
def inject_site_integrations():
    return {
        "google_site_verification": GOOGLE_SITE_VERIFICATION,
        "gtm_container_id": GTM_CONTAINER_ID,
    }

PRICING_PLAN_CATALOG = [
    {
        "code": "starter",
        "label": "Starter",
        "description": "For solo operators and small teams.",
        "price": {"currency": "EUR", "amount": 6, "interval": "month", "trial_days": 15},
        "entitlements": {
            "workspaces_max": 1,
            "projects_max": 3,
            "agents_max": 5,
            "connectors_max": 6,
            "tokens_monthly": 100000,
            "max_per_message": 120,
            "daily_limit": 1200,
        },
        "cta": "Start trial",
    },
    {
        "code": "pro",
        "label": "Pro",
        "description": "For active agencies and growth teams.",
        "price": {"currency": "EUR", "amount": 18, "interval": "month", "trial_days": 15},
        "entitlements": {
            "workspaces_max": 3,
            "projects_max": 10,
            "agents_max": 12,
            "connectors_max": 20,
            "tokens_monthly": 600000,
            "max_per_message": 220,
            "daily_limit": 6000,
        },
        "cta": "Upgrade to Pro",
    },
    {
        "code": "enterprise",
        "label": "Enterprise",
        "description": "For multi-client operations and larger execution teams.",
        "price": {"currency": "EUR", "amount": 40, "interval": "month", "trial_days": 15},
        "entitlements": {
            "workspaces_max": 8,
            "projects_max": 40,
            "agents_max": 25,
            "connectors_max": 40,
            "tokens_monthly": 2000000,
            "max_per_message": 300,
            "daily_limit": 20000,
        },
        "cta": "Upgrade to Enterprise",
    },
]

EUR_PER_RON = float(os.getenv("EUR_PER_RON", "0.20"))
EUR_PER_USD = float(os.getenv("EUR_PER_USD", "0.92"))


def _pricing_catalog_map():
    return {str(p.get("code")): p for p in PRICING_PLAN_CATALOG if isinstance(p, dict) and p.get("code")}


def _normalize_plan_code(raw_code):
    c = str(raw_code or "").strip().lower()
    if c in ("free", "starter", ""):
        return "starter"
    if c in ("pro", "premium"):
        return "pro"
    if c in ("enterprise", "ent"):
        return "enterprise"
    return c or "starter"


def _amount_to_eur(amount, currency):
    try:
        v = float(amount or 0)
    except Exception:
        return 0.0
    cur = str(currency or "").strip().upper()
    if cur in ("RON", "LEI", "ROL"):
        return round(v * EUR_PER_RON, 2)
    if cur in ("USD",):
        return round(v * EUR_PER_USD, 2)
    return round(v, 2)


def _stripe_subscriptions_to_eur(rows):
    out = []
    for r in (rows or []):
        if not isinstance(r, dict):
            continue
        x = dict(r)
        x["amount"] = _amount_to_eur(x.get("amount") or 0, x.get("currency"))
        x["currency"] = "EUR"
        out.append(x)
    return out


def _stripe_payments_to_eur(rows):
    out = []
    for r in (rows or []):
        if not isinstance(r, dict):
            continue
        x = dict(r)
        x["amount"] = _amount_to_eur(x.get("amount") or 0, x.get("currency"))
        x["currency"] = "EUR"
        out.append(x)
    return out


def _coolbits_browser_base_url():
    """Public URL used by browser redirects/popups."""
    if COOLBITS_PUBLIC_URL:
        return COOLBITS_PUBLIC_URL
    lc = COOLBITS_URL.lower()
    if "127.0.0.1" in lc or "localhost" in lc:
        return "https://coolbits.ai"
    return COOLBITS_URL


def _build_real_agent_objective(agent_slug, ws_slug, user_message, recent_history):
    base = _REAL_AGENT_OBJECTIVES.get(agent_slug) or "You are a helpful specialist assistant."
    ws_name = str((workspaces.get(ws_slug) or {}).get("name") or ws_slug or "Workspace")
    history_lines = []
    for msg in (recent_history or [])[-6:]:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "").strip().lower()
        content = str(msg.get("content") or "").strip()
        if role in ("user", "agent") and content:
            prefix = "User" if role == "user" else "Assistant"
            history_lines.append(f"{prefix}: {content[:280]}")
    history_txt = "\n".join(history_lines) if history_lines else "No prior context."

    uid = get_current_user_id()
    client_id = get_current_client_id()
    runtime_ctx = _get_chat_runtime_context(uid, client_id)
    client_label = str(runtime_ctx.get("client_name") or "None")
    connected_connectors = runtime_ctx.get("connected_connectors") or []
    connected_txt = ", ".join(connected_connectors[:6]) if connected_connectors else "none"
    focus_connectors = AGENT_CONNECTOR_MAP.get(agent_slug, []) or []
    focus_txt = ", ".join(focus_connectors[:6]) if focus_connectors else "none"

    return (
        f"{base}\n\n"
        f"Context:\n"
        f"- Workspace: {ws_name}\n"
        f"- Agent slug: {agent_slug}\n"
        f"- Active client: {client_label}\n"
        f"- Connected tools: {connected_txt}\n"
        f"- Role focus tools: {focus_txt}\n"
        f"- User request: {user_message[:900]}\n"
        f"- Recent chat:\n{history_txt}\n\n"
        f"Output rules:\n"
        f"- You are speaking as a Camarad agent, not as a generic model.\n"
        f"- If user asks your role/environment, explain your concrete role in Camarad and what you can do now.\n"
        f"- Keep answer practical and structured.\n"
        f"- Use max 6 bullets unless user asks long format.\n"
        f"- Match user's language when possible.\n"
        f"- If a specialist handoff helps, add 'Handoff:' line with target agent.\n"
    )


def _connector_slug_to_name_map():
    out = {}
    try:
        for _name, _slug in (CONNECTOR_NAME_TO_SLUG or {}).items():
            if _slug and _name:
                out[str(_slug)] = str(_name)
    except Exception:
        pass
    return out


def _get_chat_runtime_context(user_id, client_id):
    info = {
        "client_name": "None",
        "connected_connectors": [],
    }
    if int(user_id or 0) <= 0:
        return info

    conn = None
    try:
        conn = get_db()
        _ensure_client_tables(conn)
        cursor = conn.cursor()

        cid = None
        if client_id is not None and _client_owned(conn, user_id, client_id):
            cid = int(client_id)
            row_client = cursor.execute(
                "SELECT COALESCE(NULLIF(TRIM(company_name), ''), NULLIF(TRIM(name), ''), 'Client ' || id) FROM clients WHERE id = ? LIMIT 1",
                (cid,),
            ).fetchone()
            if row_client and row_client[0]:
                info["client_name"] = str(row_client[0]).strip()

        slug_to_name = _connector_slug_to_name_map()

        sql = "SELECT connector_slug FROM connectors_config WHERE user_id = ? AND LOWER(status) = 'connected'"
        params = [int(user_id)]
        if cid is not None:
            sql += " AND COALESCE(client_id, 0) = ?"
            params.append(cid)
        rows = cursor.execute(sql, tuple(params)).fetchall()

        if (not rows) and cid is not None:
            rows = cursor.execute(
                "SELECT connector_slug FROM connectors_config WHERE user_id = ? AND LOWER(status) = 'connected' AND COALESCE(client_id, 0) = 0",
                (int(user_id),),
            ).fetchall()

        names = []
        seen = set()
        for r in rows:
            slug = str(r[0] or "").strip()
            if not slug or slug in seen:
                continue
            seen.add(slug)
            names.append(slug_to_name.get(slug, _humanize_slug(slug)))
        info["connected_connectors"] = names
    except Exception:
        pass
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return info


def _should_attach_docs_context(agent_slug, user_message):
    text = str(user_message or "").strip().lower()
    if not text:
        return False
    role_q = ("what is your role", "who are you", "cine esti", "ce rol", "role in this environment", "what can you do")
    if any(p in text for p in role_q):
        return False
    if agent_slug not in AGENT_CONNECTOR_MAP:
        return False
    technical_hints = (
        "api", "endpoint", "oauth", "token", "connect", "connector", "report",
        "metrics", "campaign", "roas", "ctr", "conversion", "ga4", "google ads",
        "search console", "webhook", "debug", "integration",
    )
    return any(k in text for k in technical_hints)


def _build_chat_suggestions(agent_slug, ws_slug, runtime_ctx, last_user_message, last_agent_message):
    _ = ws_slug
    connected = runtime_ctx.get("connected_connectors") or []
    client_name = str(runtime_ctx.get("client_name") or "this client")
    connected_lower = {c.lower() for c in connected}
    last_txt = str(last_user_message or "").strip().lower()

    role_probe = any(k in last_txt for k in ("role", "who are you", "ce rol", "cine esti", "what can you do", "environment"))
    very_short = len(last_txt) <= 4

    suggestions = []
    if agent_slug == "life-coach":
        suggestions = [
            f"Give me a 5-point action plan for {client_name} for the next 7 days.",
            "Route this task to the best specialist and explain why: improve qualified leads fast.",
            "Build a daily briefing template I can run every morning (PPC + SEO + priorities).",
            "What should I ask first to get the fastest business value from Camarad?",
        ]
        if ("google ads" in connected_lower) or ("google analytics 4" in connected_lower):
            suggestions[2] = "Create a daily growth brief from Google Ads + GA4 with top risks and opportunities."
    elif agent_slug == "ppc-specialist":
        suggestions = [
            "Audit Google Ads for last 30 days: waste, opportunities, and top 5 fixes.",
            "Prioritize quick wins to increase ROAS this week, with expected impact.",
            "Build a testing plan for ad copy + audiences + bidding for next 14 days.",
            "Draft a weekly PPC report format for client-facing updates.",
        ]
        if "google ads" not in connected_lower:
            suggestions[0] = "I don't have Google Ads connected yet. Give me the exact connect + validation checklist."
    elif agent_slug == "seo-content":
        suggestions = [
            "Create a 30-day SEO sprint: technical, content, and authority tasks.",
            "Identify high-intent content clusters and propose 10 article briefs.",
            "Build KPI targets for organic growth for next month.",
            "Give me an SEO audit checklist I can run weekly in 15 minutes.",
        ]
        if ("google analytics 4" in connected_lower) or ("google search console" in connected_lower):
            suggestions[1] = "Use GA4/GSC context to propose top landing pages to optimize first."
    else:
        suggestions = [
            "Give me 3 priority actions based on current context.",
            "What should I do first for quick measurable impact?",
            "Create a 7-day execution plan with owners and KPIs.",
            "Show risks and opportunities in one concise summary.",
        ]

    if role_probe or very_short:
        suggestions = [
            "Explain your role in Camarad, your scope, and when you hand off to another agent.",
            "What can you do right now with my current client and connected tools?",
            "Give me 5 example prompts that fit your role.",
            "How do you collaborate with Personal Assistant, PPC Specialist, and SEO Strategist?",
        ]

    if str(last_agent_message or "").strip():
        suggestions = suggestions[:3] + ["Continue from your last answer with concrete next actions and priorities."]

    out = []
    seen = set()
    for idx, prompt in enumerate(suggestions):
        p = str(prompt or "").strip()
        if not p or p in seen:
            continue
        seen.add(p)
        out.append({
            "id": f"s{idx + 1}",
            "label": p[:72] + ("..." if len(p) > 72 else ""),
            "prompt": p,
        })
        if len(out) >= 4:
            break
    return out


def _fallback_real_agent_reply(agent_slug, ws_slug, user_message, runtime_ctx):
    _ = ws_slug
    msg = str(user_message or "").strip()
    lower = msg.lower()
    client_name = str(runtime_ctx.get("client_name") or "current client")
    connected = runtime_ctx.get("connected_connectors") or []
    connected_txt = ", ".join(connected[:4]) if connected else "no connected tools yet"

    asks_role = any(k in lower for k in ("role", "who are you", "what can you do", "environment", "ce rol", "cine esti"))
    if agent_slug == "life-coach":
        if asks_role:
            return (
                "I am your Personal Assistant in Camarad.\n\n"
                "What I do here:\n"
                "- Translate your goal into a short execution plan.\n"
                "- Route tasks to the right specialist (PPC or SEO) when needed.\n"
                "- Keep priorities and next actions clear.\n\n"
                f"Current context: client `{client_name}`, connected tools: {connected_txt}."
            )
        return (
            f"Understood. I will help you move this forward for `{client_name}`.\n\n"
            "Proposed next step:\n"
            "1. Clarify the target outcome and deadline.\n"
            "2. Pick the owner agent (Personal/PPC/SEO).\n"
            "3. Execute the first action now.\n\n"
            "If you want, I can route this immediately to PPC Specialist or SEO Strategist."
        )

    if agent_slug == "ppc-specialist":
        if asks_role:
            return (
                "I am PPC Specialist in Camarad.\n\n"
                "I handle:\n"
                "- Paid acquisition strategy (Google Ads / Meta / LinkedIn).\n"
                "- Campaign diagnostics and optimization priorities.\n"
                "- Action plans with expected impact on ROAS/CPL.\n\n"
                f"Current context: client `{client_name}`, connected tools: {connected_txt}."
            )
        return (
            "PPC Specialist ready.\n\n"
            "Recommended structure:\n"
            "- Diagnose spend, CTR, CVR, and ROAS.\n"
            "- Identify top 3 waste drivers.\n"
            "- Propose fast wins and test plan for next 7-14 days."
        )

    if agent_slug == "seo-content":
        if asks_role:
            return (
                "I am SEO & Content Strategist in Camarad.\n\n"
                "I handle:\n"
                "- Technical and on-page SEO priorities.\n"
                "- Content strategy and topic clusters.\n"
                "- KPI-driven organic growth plans.\n\n"
                f"Current context: client `{client_name}`, connected tools: {connected_txt}."
            )
        return (
            "SEO Strategist ready.\n\n"
            "Recommended structure:\n"
            "- Technical baseline (indexation, performance, internal links).\n"
            "- Content plan by search intent.\n"
            "- Weekly KPIs: impressions, clicks, rankings, conversions."
        )

    return "I can help with a practical next-step plan. Tell me your main objective for this week."


def _sanitize_real_agent_output(agent_slug, ws_slug, user_message, response_text):
    txt = str(response_text or "").strip()
    if agent_slug not in REAL_AGENT_SLUGS:
        return txt
    bad_markers = (
        "i am a large language model",
        "trained by google",
        "as an ai language model",
    )
    lower = txt.lower()
    if any(m in lower for m in bad_markers):
        return _fallback_real_agent_reply(
            agent_slug=agent_slug,
            ws_slug=ws_slug,
            user_message=user_message,
            runtime_ctx=_get_chat_runtime_context(get_current_user_id(), get_current_client_id()),
        )
    return txt


def _generate_real_agent_response(agent_slug, ws_slug, user_message, recent_history):
    objective = _build_real_agent_objective(agent_slug, ws_slug, user_message, recent_history)
    try:
        status, payload, text = _coolbits_request(
            "POST",
            "/api/runs",
            body={"title": f"camarad-{agent_slug}"},
            timeout=20,
        )
        if not (200 <= int(status) < 300) or not isinstance(payload, dict) or not payload.get("runId"):
            return None

        run_id = str(payload.get("runId"))
        llm_body = {
            "profileName": COOLBITS_VERTEX_PROFILE,
            "input": user_message,
            "promptEnvelope": {"envelopeVersion": "v1", "objective": objective},
            "real": True,
        }
        status2, payload2, text2 = _coolbits_request(
            "POST",
            f"/api/runs/{run_id}/llm",
            body=llm_body,
            timeout=60,
            extra_headers={"X-Real-LLM-Confirm": "true"},
        )
        if 200 <= int(status2) < 300 and isinstance(payload2, dict) and str(payload2.get("text") or "").strip():
            return str(payload2.get("text")).strip()

        # If real call is disabled/guarded, keep behavior stable and fallback.
        err_code = str((payload2 or {}).get("error") or "").strip().lower() if isinstance(payload2, dict) else ""
        if err_code in {"real_calls_disabled", "real_rate_limited", "cost_cap_exceeded", "profile_not_found", "profile_disabled"}:
            return None

    except Exception as e:
        print(f"real_agent_response_error({agent_slug}): {e}")
    return None


def _coolbits_get_request_token():
    if not has_request_context():
        return None
    token = str(request.cookies.get("camarad_cb_token") or "").strip()
    if token:
        return token
    auth_hdr = str(request.headers.get("Authorization") or "").strip()
    if auth_hdr.lower().startswith("bearer "):
        return auth_hdr[7:].strip()
    return None


def _coolbits_get_token(force=False):
    request_token = _coolbits_get_request_token()
    if request_token:
        return request_token

    # Coolbits issues 30d JWTs; refresh occasionally and on 401.
    now = time.time()
    if (not force) and _coolbits_auth_cache.get("token") and (now - float(_coolbits_auth_cache.get("fetched_at") or 0.0) < 6 * 3600):
        return _coolbits_auth_cache["token"]

    try:
        r = requests.post(
            f"{COOLBITS_URL}/api/auth/mock-login",
            json={"email": COOLBITS_GATEWAY_EMAIL},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json() if r.content else {}
        token = data.get("token")
        if not token:
            raise RuntimeError("missing_token")
        _coolbits_auth_cache["token"] = token
        _coolbits_auth_cache["fetched_at"] = now
        return token
    except Exception as e:
        raise RuntimeError(f"coolbits_auth_failed: {e}")


def _coolbits_request(method, path, params=None, body=None, timeout=25, extra_headers=None):
    token = _coolbits_get_token(force=False)
    url = f"{COOLBITS_URL}{path if path.startswith('/') else '/' + path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-Id": COOLBITS_WORKSPACE_ID,
        "Content-Type": "application/json",
    }
    if isinstance(extra_headers, dict):
        for k, v in extra_headers.items():
            if k and v is not None:
                headers[str(k)] = str(v)
    r = requests.request(method, url, params=params, json=body, headers=headers, timeout=timeout)
    if r.status_code == 401 and not _coolbits_get_request_token():
        token = _coolbits_get_token(force=True)
        headers["Authorization"] = f"Bearer {token}"
        r = requests.request(method, url, params=params, json=body, headers=headers, timeout=timeout)
    ct = (r.headers.get("content-type") or "").lower()
    payload = None
    if "application/json" in ct:
        try:
            payload = r.json()
        except Exception:
            payload = None
    return r.status_code, payload, r.text


def _ensure_users_auth_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            is_premium BOOLEAN DEFAULT FALSE
        )
    """)
    for stmt in (
        "ALTER TABLE users ADD COLUMN email TEXT",
        "ALTER TABLE users ADD COLUMN auth_provider TEXT DEFAULT 'local'",
        "ALTER TABLE users ADD COLUMN created_at TEXT",
        "ALTER TABLE users ADD COLUMN last_login_at TEXT",
    ):
        try:
            conn.execute(stmt)
            conn.commit()
        except Exception:
            pass
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email)")
        conn.commit()
    except Exception:
        pass


def _normalize_email(value):
    return str(value or "").strip().lower()


def _slug_username_from_email(email):
    base = _normalize_email(email).split("@", 1)[0]
    base = re.sub(r"[^a-zA-Z0-9._-]+", "-", base).strip("-._")
    return (base or "user")[:40]


def _build_unique_username(conn, email, display_name=None):
    seeds = [str(display_name or "").strip(), _slug_username_from_email(email), "user"]
    for seed in seeds:
        seed = re.sub(r"[^a-zA-Z0-9._-]+", "-", seed).strip("-._")
        if seed:
            break
    base = (seed or "user")[:40]
    candidate = base
    for i in range(1, 500):
        row = conn.execute("SELECT 1 FROM users WHERE username = ? LIMIT 1", (candidate,)).fetchone()
        if not row:
            return candidate
        suffix = f"-{i}"
        candidate = (base[: max(1, 40 - len(suffix))] + suffix)
    return f"user-{int(time.time())}"


def _upsert_local_user_from_auth(email, display_name="", auth_provider="google"):
    email_norm = _normalize_email(email)
    if not email_norm:
        raise RuntimeError("missing_email")
    conn = get_db()
    try:
        _ensure_users_auth_schema(conn)
        row = conn.execute(
            "SELECT id, username, is_premium, email FROM users WHERE lower(coalesce(email,'')) = ? LIMIT 1",
            (email_norm,),
        ).fetchone()
        if row:
            uid = int(row["id"])
            if str(row["email"] or "").strip().lower() != email_norm:
                conn.execute("UPDATE users SET email = ? WHERE id = ?", (email_norm, uid))
            conn.execute(
                "UPDATE users SET auth_provider = ?, last_login_at = datetime('now') WHERE id = ?",
                (str(auth_provider or "google"), uid),
            )
            conn.commit()
            return {"id": uid, "username": str(row["username"] or f"user-{uid}"), "email": email_norm}

        username = _build_unique_username(conn, email_norm, display_name=display_name)
        cur = conn.execute(
            "INSERT INTO users (username, is_premium, email, auth_provider, last_login_at) VALUES (?, 0, ?, ?, datetime('now'))",
            (username, email_norm, str(auth_provider or "google")),
        )
        conn.commit()
        uid = int(cur.lastrowid)
        return {"id": uid, "username": username, "email": email_norm}
    finally:
        conn.close()


def _coolbits_auth_me(token):
    token = str(token or "").strip()
    if not token:
        raise RuntimeError("missing_token")
    resp = requests.get(
        f"{COOLBITS_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {token}", "X-Workspace-Id": COOLBITS_WORKSPACE_ID},
        timeout=15,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"coolbits_auth_me_http_{resp.status_code}")
    payload = resp.json() if resp.content else {}
    user = payload.get("user") if isinstance(payload, dict) else {}
    if not isinstance(user, dict):
        raise RuntimeError("coolbits_invalid_user_payload")
    return user


def _auth_cookie_opts():
    return {"path": "/", "secure": AUTH_COOKIE_SECURE, "samesite": "Lax"}


def get_current_user_id():
    """Resolve authenticated user id; falls back to dev id=1 only when auth is disabled."""
    raw_cookie = request.cookies.get("camarad_user_id")
    try:
        uid = int(raw_cookie)
        if uid > 0:
            return uid
    except (TypeError, ValueError):
        pass

    if not AUTH_REQUIRED:
        for raw in (request.headers.get("X-User-ID"), request.cookies.get("camarad_user_id")):
            try:
                uid = int(raw)
                if uid > 0:
                    return uid
            except (TypeError, ValueError):
                pass
        return 1
    return 0


def is_user_authenticated():
    uid = get_current_user_id()
    if not AUTH_REQUIRED:
        return bool(uid > 0)
    token = str(request.cookies.get("camarad_cb_token") or "").strip()
    return bool(uid > 0 and token)


def get_current_client_id():
    """Read active client id from header/query. Returns int or None."""
    raw = request.headers.get("X-Client-ID")
    if raw is None:
        raw = request.args.get("client_id")
    if raw is None:
        return None
    raw_txt = str(raw).strip().lower()
    if raw_txt in ("", "0", "none", "null", "undefined"):
        return None
    try:
        cid = int(raw_txt)
        return cid if cid > 0 else None
    except (TypeError, ValueError):
        return None


def _scope_effective_user_id():
    uid = int(get_current_user_id() or 0)
    if uid > 0:
        return uid
    env_mode = str(
        os.getenv("APP_ENV")
        or os.getenv("FLASK_ENV")
        or os.getenv("ENVIRONMENT")
        or "development"
    ).strip().lower()
    is_prod = env_mode in ("prod", "production")
    internal_token = str(os.getenv("BILLING_INTERNAL_TOKEN") or "").strip()
    request_internal = str(request.headers.get("X-Internal-Token") or "").strip()
    allow_header_fallback = (not is_prod) or (internal_token and request_internal == internal_token)
    if not allow_header_fallback:
        return 0
    raw = request.headers.get("X-User-ID")
    try:
        uid = int(str(raw or "").strip())
        return uid if uid > 0 else 0
    except (TypeError, ValueError):
        return 0


VALID_WORKSPACES = {"personal", "business", "agency", "development"}
VALID_LANDING = {"orchestrator", "agents", "connectors", "boardroom", "settings", "workspace", "home", "chat"}
VALID_GRID_STYLE = {"dots", "lines", "off"}
VALID_THEME = {"dark", "light"}
VALID_LLM = {"Grok", "OpenAI", "Anthropic", "Gemini", "Custom"}
SCOPED_API_PREFIXES = (
    "/api/agents/",
    "/api/connectors/",
    "/api/flows",
    "/api/orchestrator/",
    "/api/conversations",
    "/api/chats",
)
REQUIRES_CLIENT_SCOPE_RULES = (
    ("POST", "/api/orchestrator/execute", True),
    ("GET", "/api/orchestrator/history/", False),
    ("POST", "/api/connectors/ga4/property", True),
    ("GET", "/api/conversations/", False),
    ("DELETE", "/api/conversations/", False),
)


def _path_matches_scope_rule(method, path):
    m = str(method or "").upper()
    p = str(path or "")
    for rule_method, rule_path, exact in REQUIRES_CLIENT_SCOPE_RULES:
        if m != rule_method:
            continue
        if exact and p == rule_path:
            return True
        if not exact and p.startswith(rule_path):
            return True
    return False


def _client_scope_parse_error(raw_client_value):
    raw = str(raw_client_value or "").strip().lower()
    if raw in ("", "0", "none", "null", "undefined"):
        return None
    try:
        return int(raw) > 0
    except Exception:
        return False


PRICING_PRESETS = {
    "free": {
        "cost_multiplier": 1.0,
        "monthly_grant": 1000,
        "max_per_message": 80,
        "daily_limit": 200,
        "monthly_reset_day": 1,
        "monthly_reset_hour": 0,
        "monthly_reset_minute": 0,
    },
    "pro": {
        "cost_multiplier": 0.7,
        "monthly_grant": 10000,
        "max_per_message": 150,
        "daily_limit": 1000,
        "monthly_reset_day": 1,
        "monthly_reset_hour": 0,
        "monthly_reset_minute": 0,
    },
    "enterprise": {
        "cost_multiplier": 0.5,
        "monthly_grant": 50000,
        "max_per_message": 300,
        "daily_limit": 5000,
        "monthly_reset_day": 1,
        "monthly_reset_hour": 0,
        "monthly_reset_minute": 0,
    },
}
VALID_ECONOMY_PRESETS = set(PRICING_PRESETS.keys())

DEFAULT_USER_SETTINGS = {
    "profile": {
        "display_name": "",
        "email": "",
        "role": "",
        "timezone": "Europe/Bucharest",
        "language": "en",
    },
    "preferences": {
        "default_workspace": "agency",
        "default_landing": "orchestrator",
        "default_chat_workspace": "personal",
        "default_chat_agent_slug": "life-coach",
        "chat_home_v2": True,
        "always_open_home": False,
        "onboarding_completed": False,
        "compact_sidebar": False,
        "reduce_motion": False,
        "show_tips": True,
    },
    "notifications": {
        "toast_enabled": True,
        "chat_alerts": True,
        "connector_alerts": True,
        "boardroom_alerts": True,
        "daily_digest": False,
    },
    "orchestrator": {
        "grid_style": "dots",
        "default_zoom": 100,
        "snap_to_grid": False,
        "auto_route": True,
    },
    "integrations": {
        "preferred_llm": "Grok",
        "byok_enabled": False,
        "strict_client_scope": True,
    },
    "economy": {
        "preset": "free",
        "cost_multiplier": 1.0,
        "monthly_grant": 1000,
        "max_per_message": 80,
        "daily_limit": 200,
        "monthly_reset_day": 1,
        "monthly_reset_hour": 0,
        "monthly_reset_minute": 0,
    },
    "privacy": {
        "retain_days": 90,
        "mask_api_keys": True,
        "share_telemetry": False,
    },
    "appearance": {
        "theme": "dark",
    },
}


def _to_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return default


def _deep_merge_dict(base_obj, patch_obj):
    out = copy.deepcopy(base_obj)
    if not isinstance(patch_obj, dict):
        return out
    for key, val in patch_obj.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge_dict(out[key], val)
        else:
            out[key] = val
    return out


def _sanitize_user_settings(settings_obj):
    merged = _deep_merge_dict(DEFAULT_USER_SETTINGS, settings_obj if isinstance(settings_obj, dict) else {})

    profile = merged["profile"]
    profile["display_name"] = str(profile.get("display_name") or "").strip()[:80]
    profile["email"] = str(profile.get("email") or "").strip()[:160]
    profile["role"] = str(profile.get("role") or "").strip()[:80]
    profile["timezone"] = str(profile.get("timezone") or "Europe/Bucharest").strip()[:80] or "Europe/Bucharest"
    profile["language"] = str(profile.get("language") or "en").strip().lower()[:8] or "en"

    prefs = merged["preferences"]
    ws = str(prefs.get("default_workspace") or "agency").strip().lower()
    prefs["default_workspace"] = ws if ws in VALID_WORKSPACES else "agency"
    chat_ws = str(prefs.get("default_chat_workspace") or "personal").strip().lower()
    prefs["default_chat_workspace"] = chat_ws if chat_ws in VALID_WORKSPACES else "personal"
    prefs["default_chat_agent_slug"] = str(prefs.get("default_chat_agent_slug") or "life-coach").strip().lower() or "life-coach"
    prefs["chat_home_v2"] = _to_bool(prefs.get("chat_home_v2"), True)
    landing = str(prefs.get("default_landing") or "orchestrator").strip().lower()
    prefs["default_landing"] = landing if landing in VALID_LANDING else "orchestrator"
    prefs["always_open_home"] = _to_bool(prefs.get("always_open_home"), False)
    prefs["onboarding_completed"] = _to_bool(prefs.get("onboarding_completed"), False)
    prefs["compact_sidebar"] = _to_bool(prefs.get("compact_sidebar"), False)
    prefs["reduce_motion"] = _to_bool(prefs.get("reduce_motion"), False)
    prefs["show_tips"] = _to_bool(prefs.get("show_tips"), True)

    notifications = merged["notifications"]
    notifications["toast_enabled"] = _to_bool(notifications.get("toast_enabled"), True)
    notifications["chat_alerts"] = _to_bool(notifications.get("chat_alerts"), True)
    notifications["connector_alerts"] = _to_bool(notifications.get("connector_alerts"), True)
    notifications["boardroom_alerts"] = _to_bool(notifications.get("boardroom_alerts"), True)
    notifications["daily_digest"] = _to_bool(notifications.get("daily_digest"), False)

    orchestrator = merged["orchestrator"]
    grid_style = str(orchestrator.get("grid_style") or "dots").strip().lower()
    orchestrator["grid_style"] = grid_style if grid_style in VALID_GRID_STYLE else "dots"
    try:
        zoom = int(orchestrator.get("default_zoom", 100))
    except (TypeError, ValueError):
        zoom = 100
    orchestrator["default_zoom"] = max(40, min(200, zoom))
    orchestrator["snap_to_grid"] = _to_bool(orchestrator.get("snap_to_grid"), False)
    orchestrator["auto_route"] = _to_bool(orchestrator.get("auto_route"), True)

    integrations = merged["integrations"]
    llm = str(integrations.get("preferred_llm") or "Grok").strip()
    integrations["preferred_llm"] = llm if llm in VALID_LLM else "Grok"
    integrations["byok_enabled"] = _to_bool(integrations.get("byok_enabled"), False)
    integrations["strict_client_scope"] = _to_bool(integrations.get("strict_client_scope"), True)


    economy = merged["economy"]
    preset = str(economy.get("preset") or "free").strip().lower()
    if preset not in VALID_ECONOMY_PRESETS:
        preset = "free"
    economy["preset"] = preset

    preset_base = PRICING_PRESETS.get(preset, PRICING_PRESETS["free"])

    try:
        cost_multiplier = float(economy.get("cost_multiplier", preset_base["cost_multiplier"]))
    except (TypeError, ValueError):
        cost_multiplier = float(preset_base["cost_multiplier"])
    economy["cost_multiplier"] = max(0.1, min(2.0, round(cost_multiplier, 3)))

    try:
        monthly_grant = int(economy.get("monthly_grant", preset_base["monthly_grant"]))
    except (TypeError, ValueError):
        monthly_grant = int(preset_base["monthly_grant"])
    economy["monthly_grant"] = max(100, min(500000, monthly_grant))

    try:
        max_per_message = int(economy.get("max_per_message", preset_base["max_per_message"]))
    except (TypeError, ValueError):
        max_per_message = int(preset_base["max_per_message"])
    economy["max_per_message"] = max(20, min(500, max_per_message))

    try:
        daily_limit = int(economy.get("daily_limit", preset_base["daily_limit"]))
    except (TypeError, ValueError):
        daily_limit = int(preset_base["daily_limit"])
    economy["daily_limit"] = max(50, min(500000, daily_limit))

    try:
        monthly_reset_day = int(economy.get("monthly_reset_day", preset_base.get("monthly_reset_day", 1)))
    except (TypeError, ValueError):
        monthly_reset_day = int(preset_base.get("monthly_reset_day", 1))
    economy["monthly_reset_day"] = max(1, min(28, monthly_reset_day))

    try:
        monthly_reset_hour = int(economy.get("monthly_reset_hour", preset_base.get("monthly_reset_hour", 0)))
    except (TypeError, ValueError):
        monthly_reset_hour = int(preset_base.get("monthly_reset_hour", 0))
    economy["monthly_reset_hour"] = max(0, min(23, monthly_reset_hour))

    try:
        monthly_reset_minute = int(economy.get("monthly_reset_minute", preset_base.get("monthly_reset_minute", 0)))
    except (TypeError, ValueError):
        monthly_reset_minute = int(preset_base.get("monthly_reset_minute", 0))
    monthly_reset_minute = max(0, min(59, monthly_reset_minute))
    monthly_reset_minute = int((monthly_reset_minute // 15) * 15)
    economy["monthly_reset_minute"] = monthly_reset_minute if monthly_reset_minute in (0, 15, 30, 45) else 0

    privacy = merged["privacy"]
    try:
        retain_days = int(privacy.get("retain_days", 90))
    except (TypeError, ValueError):
        retain_days = 90
    privacy["retain_days"] = max(7, min(3650, retain_days))
    privacy["mask_api_keys"] = _to_bool(privacy.get("mask_api_keys"), True)
    privacy["share_telemetry"] = _to_bool(privacy.get("share_telemetry"), False)

    appearance = merged["appearance"]
    theme = str(appearance.get("theme") or "dark").strip().lower()
    appearance["theme"] = theme if theme in VALID_THEME else "dark"

    return merged


def _ensure_user_settings_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            settings_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)


def _load_user_settings(conn, user_id):
    _ensure_user_settings_table(conn)
    row = conn.execute("SELECT settings_json FROM user_settings WHERE user_id = ? LIMIT 1", (user_id,)).fetchone()
    parsed = {}
    if row and row[0]:
        try:
            parsed = json.loads(row[0])
        except Exception:
            parsed = {}
    return _sanitize_user_settings(parsed)


def _save_user_settings(conn, user_id, settings_obj):
    _ensure_user_settings_table(conn)
    sanitized = _sanitize_user_settings(settings_obj)
    payload = json.dumps(sanitized)
    conn.execute("""
        INSERT INTO user_settings (user_id, settings_json, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(user_id) DO UPDATE SET
            settings_json = excluded.settings_json,
            updated_at = datetime('now')
    """, (user_id, payload))
    return sanitized


def _get_user_settings(user_id):
    conn = get_db()
    try:
        settings = _load_user_settings(conn, user_id)
    finally:
        conn.close()
    return settings


_PERSONAL_ASSISTANT_NAME_MIGRATED = False
_CLIENT_SCOPED_CONFIGS_MIGRATED = False


def _table_exists(conn, table_name):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (str(table_name),),
    ).fetchone()
    return bool(row)


def _table_columns(conn, table_name):
    cols = {}
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        for r in rows:
            cols[str(r[1])] = {
                "type": str(r[2] or ""),
                "notnull": int(r[3] or 0),
                "dflt": r[4],
                "pk": int(r[5] or 0),
            }
    except Exception:
        return {}
    return cols


def _has_unique_index_on_columns(conn, table_name, wanted_cols):
    wanted = [str(x) for x in (wanted_cols or [])]
    try:
        idx_rows = conn.execute(f"PRAGMA index_list({table_name})").fetchall()
    except Exception:
        return False
    for idx in idx_rows or []:
        unique = int(idx[2] or 0)
        idx_name = str(idx[1] or "")
        if unique != 1 or not idx_name:
            continue
        try:
            info_rows = conn.execute(f"PRAGMA index_info('{idx_name}')").fetchall()
        except Exception:
            continue
        cols = [str(r[2]) for r in info_rows if r[2] is not None]
        if cols == wanted:
            return True
    return False


def _rebuild_agents_config_per_client(conn):
    if not _table_exists(conn, "agents_config"):
        return
    cols = _table_columns(conn, "agents_config")
    if (
        cols.get("client_id", {}).get("notnull") == 1
        and _has_unique_index_on_columns(conn, "agents_config", ["user_id", "agent_slug", "client_id"])
    ):
        return

    old_name = "agents_config_old_m3"
    conn.execute(f"DROP TABLE IF EXISTS {old_name}")
    conn.execute("ALTER TABLE agents_config RENAME TO agents_config_old_m3")
    conn.execute(
        """
        CREATE TABLE agents_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            client_id INTEGER NOT NULL DEFAULT 0,
            agent_slug TEXT NOT NULL,
            custom_name TEXT,
            avatar_base64 TEXT,
            avatar_colors TEXT,
            llm_provider TEXT,
            llm_model TEXT,
            api_key TEXT,
            temperature REAL DEFAULT 0.7,
            max_tokens INTEGER DEFAULT 2048,
            rag_enabled INTEGER DEFAULT 1,
            status TEXT DEFAULT 'Active',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, agent_slug, client_id)
        )
        """
    )

    old_cols = _table_columns(conn, old_name)
    expr = {
        "id": "id" if "id" in old_cols else "NULL",
        "user_id": "user_id" if "user_id" in old_cols else "1",
        "client_id": "COALESCE(client_id, 0)" if "client_id" in old_cols else "0",
        "agent_slug": "agent_slug" if "agent_slug" in old_cols else "''",
        "custom_name": "custom_name" if "custom_name" in old_cols else "NULL",
        "avatar_base64": "avatar_base64" if "avatar_base64" in old_cols else "NULL",
        "avatar_colors": "avatar_colors" if "avatar_colors" in old_cols else "NULL",
        "llm_provider": "llm_provider" if "llm_provider" in old_cols else "NULL",
        "llm_model": "llm_model" if "llm_model" in old_cols else "NULL",
        "api_key": "api_key" if "api_key" in old_cols else "NULL",
        "temperature": "temperature" if "temperature" in old_cols else "0.7",
        "max_tokens": "max_tokens" if "max_tokens" in old_cols else "2048",
        "rag_enabled": "rag_enabled" if "rag_enabled" in old_cols else "1",
        "status": "status" if "status" in old_cols else "'Active'",
        "created_at": "created_at" if "created_at" in old_cols else "datetime('now')",
        "updated_at": "updated_at" if "updated_at" in old_cols else "datetime('now')",
    }
    conn.execute(
        f"""
        INSERT INTO agents_config (
            id, user_id, client_id, agent_slug, custom_name, avatar_base64, avatar_colors,
            llm_provider, llm_model, api_key, temperature, max_tokens, rag_enabled, status, created_at, updated_at
        )
        SELECT
            {expr["id"]}, {expr["user_id"]}, {expr["client_id"]}, {expr["agent_slug"]}, {expr["custom_name"]},
            {expr["avatar_base64"]}, {expr["avatar_colors"]}, {expr["llm_provider"]}, {expr["llm_model"]},
            {expr["api_key"]}, {expr["temperature"]}, {expr["max_tokens"]}, {expr["rag_enabled"]},
            {expr["status"]}, {expr["created_at"]}, {expr["updated_at"]}
        FROM {old_name}
        """
    )
    conn.execute(f"DROP TABLE {old_name}")


def _rebuild_connectors_config_per_client(conn):
    if not _table_exists(conn, "connectors_config"):
        return
    cols = _table_columns(conn, "connectors_config")
    if (
        cols.get("client_id", {}).get("notnull") == 1
        and _has_unique_index_on_columns(conn, "connectors_config", ["user_id", "connector_slug", "client_id"])
    ):
        return

    old_name = "connectors_config_old_m3"
    conn.execute(f"DROP TABLE IF EXISTS {old_name}")
    conn.execute("ALTER TABLE connectors_config RENAME TO connectors_config_old_m3")
    conn.execute(
        """
        CREATE TABLE connectors_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            client_id INTEGER NOT NULL DEFAULT 0,
            connector_slug TEXT NOT NULL,
            status TEXT DEFAULT 'Disconnected',
            config_json TEXT,
            last_connected TEXT,
            UNIQUE(user_id, connector_slug, client_id)
        )
        """
    )

    old_cols = _table_columns(conn, old_name)
    expr = {
        "id": "id" if "id" in old_cols else "NULL",
        "user_id": "user_id" if "user_id" in old_cols else "1",
        "client_id": "COALESCE(client_id, 0)" if "client_id" in old_cols else "0",
        "connector_slug": "connector_slug" if "connector_slug" in old_cols else "''",
        "status": "status" if "status" in old_cols else "'Disconnected'",
        "config_json": "config_json" if "config_json" in old_cols else "NULL",
        "last_connected": "last_connected" if "last_connected" in old_cols else "NULL",
    }
    conn.execute(
        f"""
        INSERT INTO connectors_config (
            id, user_id, client_id, connector_slug, status, config_json, last_connected
        )
        SELECT
            {expr["id"]}, {expr["user_id"]}, {expr["client_id"]}, {expr["connector_slug"]},
            {expr["status"]}, {expr["config_json"]}, {expr["last_connected"]}
        FROM {old_name}
        """
    )
    conn.execute(f"DROP TABLE {old_name}")


def _ensure_client_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL DEFAULT 'person',
            name TEXT,
            company_name TEXT,
            email TEXT,
            website TEXT,
            phone TEXT,
            address TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS client_connectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            connector_slug TEXT NOT NULL,
            account_id TEXT,
            account_name TEXT,
            status TEXT DEFAULT 'pending',
            config_json TEXT,
            last_synced TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    for stmt in (
        "ALTER TABLE flows ADD COLUMN client_id INTEGER",
        "ALTER TABLE conversations ADD COLUMN client_id INTEGER",
        "ALTER TABLE agents_config ADD COLUMN client_id INTEGER",
        "ALTER TABLE connectors_config ADD COLUMN client_id INTEGER",
    ):
        try:
            conn.execute(stmt)
        except Exception:
            pass
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_clients_user ON clients(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_client_connectors_client ON client_connectors(client_id)")
    except Exception:
        pass
    global _CLIENT_SCOPED_CONFIGS_MIGRATED
    if not _CLIENT_SCOPED_CONFIGS_MIGRATED:
        try:
            conn.execute("BEGIN")
            _rebuild_agents_config_per_client(conn)
            _rebuild_connectors_config_per_client(conn)
            conn.execute("COMMIT")
            _CLIENT_SCOPED_CONFIGS_MIGRATED = True
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass

    # One-time migration: keep slug `life-coach` but persist branding as "Personal Assistant"
    # when custom_name is empty. This avoids UI regressions without breaking history.
    global _PERSONAL_ASSISTANT_NAME_MIGRATED
    if not _PERSONAL_ASSISTANT_NAME_MIGRATED:
        try:
            conn.execute(
                """
                UPDATE agents_config
                SET custom_name = ?
                WHERE agent_slug = ?
                  AND (custom_name IS NULL OR TRIM(custom_name) = '')
                """,
                ("Personal Assistant", "life-coach"),
            )
            conn.commit()
            _PERSONAL_ASSISTANT_NAME_MIGRATED = True
        except Exception:
            pass


CT_MONTHLY_GRANT_FREE = 1000
CT_MONTHLY_GRANT_PREMIUM = 10000
CT_LOW_BALANCE_WARN_PCT = 20
SHADOW_DEFAULT_BUFFER_PCT = 0.15
SHADOW_DEFAULT_MARGIN_PCT = 0.50
SHADOW_DEFAULT_CT_VALUE_USD = 0.00010


def _ensure_usage_ledger_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            client_id INTEGER,
            event_type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    try:
        conn.execute("ALTER TABLE usage_ledger ADD COLUMN client_id INTEGER")
    except Exception:
        pass
    # Shadow billing telemetry (Phase 1): additive columns only.
    for stmt in (
        "ALTER TABLE usage_ledger ADD COLUMN request_id TEXT",
        "ALTER TABLE usage_ledger ADD COLUMN workspace_id TEXT",
        "ALTER TABLE usage_ledger ADD COLUMN run_id TEXT",
        "ALTER TABLE usage_ledger ADD COLUMN step_id TEXT",
        "ALTER TABLE usage_ledger ADD COLUMN agent_id TEXT",
        "ALTER TABLE usage_ledger ADD COLUMN trace_id TEXT",
        "ALTER TABLE usage_ledger ADD COLUMN provider TEXT DEFAULT 'mock'",
        "ALTER TABLE usage_ledger ADD COLUMN model TEXT DEFAULT 'mock'",
        "ALTER TABLE usage_ledger ADD COLUMN region TEXT DEFAULT 'unknown'",
        "ALTER TABLE usage_ledger ADD COLUMN model_class TEXT DEFAULT 'auto'",
        "ALTER TABLE usage_ledger ADD COLUMN input_tokens INTEGER DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN output_tokens INTEGER DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN tool_calls INTEGER DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN connector_calls INTEGER DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN latency_ms INTEGER DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN status TEXT DEFAULT 'ok'",
        "ALTER TABLE usage_ledger ADD COLUMN error_code TEXT",
        "ALTER TABLE usage_ledger ADD COLUMN cost_estimate_usd REAL DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN cost_final_usd REAL DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN cost_estimate_eur REAL DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN cost_final_eur REAL DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN overhead_eur REAL DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN billable_eur REAL",
        "ALTER TABLE usage_ledger ADD COLUMN billable_usd REAL",
        "ALTER TABLE usage_ledger ADD COLUMN overhead_usd REAL DEFAULT 0",
        "ALTER TABLE usage_ledger ADD COLUMN ct_shadow_debit INTEGER",
        "ALTER TABLE usage_ledger ADD COLUMN risk_buffer_pct REAL DEFAULT 0.15",
        "ALTER TABLE usage_ledger ADD COLUMN target_margin_pct REAL DEFAULT 0.50",
        "ALTER TABLE usage_ledger ADD COLUMN minimum_ct_debit INTEGER DEFAULT 1",
        "ALTER TABLE usage_ledger ADD COLUMN ct_actual_debit INTEGER",
        "ALTER TABLE usage_ledger ADD COLUMN ct_debit_shadow INTEGER",
        "ALTER TABLE usage_ledger ADD COLUMN ct_ledger_txn_id TEXT",
        "ALTER TABLE usage_ledger ADD COLUMN pricing_catalog_id TEXT",
        "ALTER TABLE usage_ledger ADD COLUMN ct_rate_id TEXT",
        "ALTER TABLE usage_ledger ADD COLUMN meta_json TEXT",
    ):
        try:
            conn.execute(stmt)
        except Exception:
            pass
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_ledger_user_created ON usage_ledger(user_id, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_ledger_user_event ON usage_ledger(user_id, event_type)")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_usage_ledger_request_id_unique "
            "ON usage_ledger(request_id) WHERE request_id IS NOT NULL AND request_id <> ''"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_ledger_status_created ON usage_ledger(status, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_ledger_provider_model_created ON usage_ledger(provider, model, created_at)")
    except Exception:
        pass
    _ensure_pricing_engine_tables(conn)


def _ensure_pricing_engine_tables(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pricing_catalog (
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            region TEXT NOT NULL DEFAULT 'unknown',
            input_price_per_1k_usd REAL NOT NULL DEFAULT 0,
            output_price_per_1k_usd REAL NOT NULL DEFAULT 0,
            tool_call_price_usd REAL NOT NULL DEFAULT 0,
            connector_call_price_usd REAL NOT NULL DEFAULT 0,
            effective_from TEXT NOT NULL,
            effective_to TEXT,
            version INTEGER NOT NULL DEFAULT 1,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            notes TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ct_rates (
            id TEXT PRIMARY KEY,
            ct_value_usd REAL NOT NULL,
            effective_from TEXT NOT NULL,
            effective_to TEXT,
            version INTEGER NOT NULL DEFAULT 1,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            notes TEXT
        )
        """
    )
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pricing_lookup ON pricing_catalog(provider, model, region, effective_from)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ct_rates_effective ON ct_rates(effective_from)")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_pricing_provider_model_version "
            "ON pricing_catalog(provider, model, version)"
        )
    except Exception:
        pass

    # Seed default ct rate once.
    row = conn.execute("SELECT id FROM ct_rates ORDER BY effective_from DESC LIMIT 1").fetchone()
    if not row:
        conn.execute(
            """
            INSERT INTO ct_rates (id, ct_value_usd, effective_from, effective_to, version, is_active, notes)
            VALUES (?, ?, datetime('now'), NULL, 1, 1, ?)
            """,
            (str(uuid.uuid4()), float(SHADOW_DEFAULT_CT_VALUE_USD), "bootstrap shadow ct rate"),
        )

    # Seed a minimal pricing catalog for currently used models.
    seeds = [
        ("vertex", "gemini-1.5-flash-002", "unknown", 0.000075, 0.000300, 1),
        ("vertex", "gemini-1.5-pro-002", "unknown", 0.001250, 0.005000, 1),
        ("anthropic", "claude-3-5-sonnet-20241022", "unknown", 0.003000, 0.015000, 1),
        ("xai", "grok-beta", "unknown", 0.000200, 0.000800, 1),
        ("grok", "grok-1", "unknown", 0.000200, 0.000800, 1),
    ]
    for provider, model, region, in_p, out_p, version in seeds:
        exists = conn.execute(
            "SELECT id FROM pricing_catalog WHERE provider = ? AND model = ? AND version = ? LIMIT 1",
            (provider, model, int(version)),
        ).fetchone()
        if not exists:
            conn.execute(
                """
                INSERT INTO pricing_catalog (
                    id, provider, model, region,
                    input_price_per_1k_usd, output_price_per_1k_usd,
                    tool_call_price_usd, connector_call_price_usd,
                    effective_from, effective_to, version, is_active, notes
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, datetime('now'), NULL, ?, 1, ?)
                """,
                (str(uuid.uuid4()), provider, model, region, float(in_p), float(out_p), int(version), "seed"),
            )
    # Keep catalog fresh with models observed in live usage.
    try:
        _shadow_seed_pricing_from_usage(conn, window_hours=48)
    except Exception:
        pass


def _shadow_guess_pricing(provider, model):
    p = str(provider or "").strip().lower()
    m = str(model or "").strip().lower()

    # Explicit known defaults (USD / 1k tokens).
    explicit = {
        ("vertex", "gemini-1.5-flash-002"): (0.000075, 0.000300),
        ("vertex", "gemini-1.5-pro-002"): (0.001250, 0.005000),
        ("anthropic", "claude-3-5-sonnet-20241022"): (0.003000, 0.015000),
        ("xai", "grok-beta"): (0.000200, 0.000800),
        ("grok", "grok-1"): (0.000200, 0.000800),
    }
    if (p, m) in explicit:
        return explicit[(p, m)]

    # Heuristic fallback by model family.
    if "flash" in m:
        return (0.000075, 0.000300)
    if "pro" in m:
        return (0.001250, 0.005000)
    if "sonnet" in m:
        return (0.003000, 0.015000)
    if "opus" in m:
        return (0.015000, 0.075000)
    if "haiku" in m:
        return (0.000250, 0.001250)
    if "grok" in m:
        return (0.000200, 0.000800)
    if p in ("vertex", "google"):
        return (0.000150, 0.000600)
    if p in ("anthropic",):
        return (0.003000, 0.015000)
    if p in ("xai", "grok"):
        return (0.000200, 0.000800)
    return None


def _shadow_seed_pricing_from_usage(conn, window_hours=48):
    """Seed pricing rows for recently observed models if missing."""
    try:
        hours = int(window_hours or 48)
    except Exception:
        hours = 48
    hours = max(1, min(24 * 30, hours))

    observed = conn.execute(
        """
        SELECT provider, model, COALESCE(region, 'unknown') AS region, COUNT(*) AS calls
        FROM usage_ledger
        WHERE created_at >= datetime('now', ?)
          AND provider IS NOT NULL AND provider <> ''
          AND model IS NOT NULL AND model <> ''
        GROUP BY provider, model, COALESCE(region, 'unknown')
        ORDER BY calls DESC
        LIMIT 100
        """,
        (f"-{hours} hour",),
    ).fetchall()

    inserted = 0
    for row in (observed or []):
        provider = str(row["provider"] or "").strip()
        model = str(row["model"] or "").strip()
        region = str(row["region"] or "unknown").strip() or "unknown"
        if not provider or not model:
            continue
        exists = conn.execute(
            """
            SELECT id
            FROM pricing_catalog
            WHERE provider = ?
              AND model = ?
              AND region = ?
              AND is_active = 1
            LIMIT 1
            """,
            (provider, model, region),
        ).fetchone()
        if exists:
            continue
        guessed = _shadow_guess_pricing(provider, model)
        if not guessed:
            continue
        in_p, out_p = guessed
        conn.execute(
            """
            INSERT INTO pricing_catalog (
                id, provider, model, region,
                input_price_per_1k_usd, output_price_per_1k_usd,
                tool_call_price_usd, connector_call_price_usd,
                effective_from, effective_to, version, is_active, notes
            ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, datetime('now'), NULL, 1, 1, ?)
            """,
            (
                str(uuid.uuid4()),
                provider[:64],
                model[:128],
                region[:32],
                float(in_p),
                float(out_p),
                "auto-seeded from observed usage",
            ),
        )
        inserted += 1
    return inserted


def _shadow_recompute_request(conn, request_id):
    row = conn.execute(
        """
        SELECT id, request_id, input_tokens, output_tokens, tool_calls, connector_calls, latency_ms, status
        FROM usage_ledger
        WHERE request_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (str(request_id or "")[:96],),
    ).fetchone()
    if not row:
        return False
    _shadow_usage_finalize(
        conn,
        request_id=str(row["request_id"] or ""),
        status=str(row["status"] or "ok"),
        input_tokens=int(row["input_tokens"] or 0),
        output_tokens=int(row["output_tokens"] or 0),
        tool_calls=int(row["tool_calls"] or 0),
        connector_calls=int(row["connector_calls"] or 0),
        latency_ms=int(row["latency_ms"] or 0),
        cost_final_usd=0.0,
        meta={"shadow_backfill": True},
    )
    return True


def _shadow_lookup_pricing(conn, provider, model, region, occurred_at):
    row = conn.execute(
        """
        SELECT id, version, input_price_per_1k_usd, output_price_per_1k_usd, tool_call_price_usd, connector_call_price_usd
        FROM pricing_catalog
        WHERE provider = ?
          AND model = ?
          AND region = ?
          AND is_active = 1
          AND effective_from <= ?
          AND (effective_to IS NULL OR effective_to > ?)
        ORDER BY effective_from DESC
        LIMIT 1
        """,
        (str(provider or "mock"), str(model or "mock"), str(region or "unknown"), str(occurred_at), str(occurred_at)),
    ).fetchone()
    if row:
        return row
    # region fallback to unknown
    return conn.execute(
        """
        SELECT id, version, input_price_per_1k_usd, output_price_per_1k_usd, tool_call_price_usd, connector_call_price_usd
        FROM pricing_catalog
        WHERE provider = ?
          AND model = ?
          AND region = 'unknown'
          AND is_active = 1
          AND effective_from <= ?
          AND (effective_to IS NULL OR effective_to > ?)
        ORDER BY effective_from DESC
        LIMIT 1
        """,
        (str(provider or "mock"), str(model or "mock"), str(occurred_at), str(occurred_at)),
    ).fetchone()


def _shadow_lookup_ct_rate(conn, occurred_at):
    return conn.execute(
        """
        SELECT id, version, ct_value_usd
        FROM ct_rates
        WHERE is_active = 1
          AND effective_from <= ?
          AND (effective_to IS NULL OR effective_to > ?)
        ORDER BY effective_from DESC
        LIMIT 1
        """,
        (str(occurred_at), str(occurred_at)),
    ).fetchone()


def _shadow_request_id(raw_value=None):
    raw = str(raw_value or "").strip()
    if raw:
        return raw[:96]
    return str(uuid.uuid4())


def _current_workspace_slug():
    try:
        ws = str(request.view_args.get("ws_slug") or "").strip().lower() if request and request.view_args else ""
    except Exception:
        ws = ""
    if ws in VALID_WORKSPACES:
        return ws
    return COOLBITS_WORKSPACE_ID or "business"


def _estimate_tokens(text):
    t = str(text or "").strip()
    if not t:
        return 0
    return max(1, int(math.ceil(len(t) / 4.0)))


def _shadow_usage_preflight(
    conn,
    *,
    request_id,
    user_id,
    client_id,
    workspace_id,
    event_type,
    amount=0,
    description="",
    provider="mock",
    model="mock",
    region="unknown",
    model_class="auto",
    agent_id=None,
    run_id=None,
    step_id=None,
    trace_id=None,
    cost_estimate_usd=0.0,
    meta=None,
):
    try:
        _ensure_usage_ledger_table(conn)
        meta_json = json.dumps(meta or {}, ensure_ascii=True)
        conn.execute(
            """
            INSERT OR IGNORE INTO usage_ledger (
                user_id, client_id, workspace_id, event_type, amount, description, created_at,
                request_id, run_id, step_id, agent_id, trace_id,
                provider, model, region, model_class,
                cost_estimate_usd, cost_final_usd, status, meta_json
            ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'),
                      ?, ?, ?, ?, ?,
                      ?, ?, ?, ?,
                      ?, 0, 'ok', ?)
            """,
            (
                int(user_id),
                int(client_id) if client_id is not None else None,
                str(workspace_id or "unknown"),
                str(event_type or "unknown").strip().lower() or "unknown",
                int(amount or 0),
                str(description or "")[:300],
                str(request_id or "")[:96],
                str(run_id or "")[:64] or None,
                str(step_id or "")[:64] or None,
                str(agent_id or "")[:64] or None,
                str(trace_id or "")[:96] or None,
                str(provider or "mock")[:64],
                str(model or "mock")[:128],
                str(region or "unknown")[:32],
                str(model_class or "auto")[:24],
                float(cost_estimate_usd or 0.0),
                meta_json[:8000],
            ),
        )
    except Exception as e:
        print(f"shadow_usage_preflight_error: {e}")


def _shadow_usage_finalize(
    conn,
    *,
    request_id,
    status="ok",
    error_code=None,
    input_tokens=0,
    output_tokens=0,
    tool_calls=0,
    connector_calls=0,
    latency_ms=0,
    cost_final_usd=0.0,
    meta=None,
):
    try:
        _ensure_usage_ledger_table(conn)
        # Resolve row context first for pricing lookup and reproducibility.
        row = conn.execute(
            """
            SELECT id, created_at, user_id, workspace_id, provider, model, region
            FROM usage_ledger
            WHERE request_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (str(request_id or "")[:96],),
        ).fetchone()
        if not row:
            return

        effective_provider = str((row["provider"] if row["provider"] is not None else "mock") or "mock")
        effective_model = str((row["model"] if row["model"] is not None else "mock") or "mock")
        effective_region = str((row["region"] if row["region"] is not None else "unknown") or "unknown")
        occurred_at = str(row["created_at"] or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # Pull user economy knobs when available (shadow only).
        risk_buffer = float(SHADOW_DEFAULT_BUFFER_PCT)
        target_margin = float(SHADOW_DEFAULT_MARGIN_PCT)
        minimum_ct = 1
        try:
            uid = int(row["user_id"] or 0)
            if uid > 0:
                settings_obj = _get_user_settings(uid)
                econ = settings_obj.get("economy") if isinstance(settings_obj.get("economy"), dict) else {}
                risk_buffer = float(econ.get("risk_buffer_pct", risk_buffer) or risk_buffer)
                target_margin = float(econ.get("target_margin_pct", target_margin) or target_margin)
                minimum_ct = int(econ.get("minimum_ct_debit", 1) or 1)
        except Exception:
            pass
        risk_buffer = max(0.0, min(3.0, float(risk_buffer)))
        target_margin = max(0.0, min(3.0, float(target_margin)))
        minimum_ct = max(1, min(1000, int(minimum_ct)))

        pricing = _shadow_lookup_pricing(conn, effective_provider, effective_model, effective_region, occurred_at)
        ct_rate = _shadow_lookup_ct_rate(conn, occurred_at)

        computed_cost_final_usd = float(cost_final_usd or 0.0)
        pricing_id = None
        pricing_version = None
        if pricing:
            pricing_id = str(pricing["id"] or "")
            pricing_version = int(pricing["version"] or 0)
            # In phase 2, compute from tokens/calls whenever pricing is available.
            computed_cost_final_usd = (
                (float(int(input_tokens or 0)) / 1000.0) * float(pricing["input_price_per_1k_usd"] or 0.0)
                + (float(int(output_tokens or 0)) / 1000.0) * float(pricing["output_price_per_1k_usd"] or 0.0)
                + float(int(tool_calls or 0)) * float(pricing["tool_call_price_usd"] or 0.0)
                + float(int(connector_calls or 0)) * float(pricing["connector_call_price_usd"] or 0.0)
            )

        ct_rate_id = None
        ct_rate_value = None
        ct_rate_version = None
        billable_usd = None
        ct_shadow_debit = None
        if ct_rate:
            ct_rate_id = str(ct_rate["id"] or "")
            ct_rate_value = float(ct_rate["ct_value_usd"] or 0.0)
            ct_rate_version = int(ct_rate["version"] or 0)
            if ct_rate_value > 0:
                overhead = 0.0
                billable_usd = (float(computed_cost_final_usd) + overhead) * (1.0 + risk_buffer + target_margin)
                ct_shadow_debit = max(int(minimum_ct), int(math.ceil(float(billable_usd) / float(ct_rate_value))))

        meta_dict = {}
        if isinstance(meta, dict):
            meta_dict.update(meta)
        meta_dict.update({
            "shadow_mode": True,
            "pricing_source": "pricing_catalog_v1" if pricing else "missing_pricing",
            "pricing_missing": not bool(pricing),
            "ct_rate_missing": not bool(ct_rate),
            "pricing_version_used": pricing_version,
            "ct_rate_version_used": ct_rate_version,
            "risk_buffer_pct": risk_buffer,
            "target_margin_pct": target_margin,
            "minimum_ct_debit": minimum_ct,
        })
        meta_json = json.dumps(meta_dict, ensure_ascii=True)
        conn.execute(
            """
            UPDATE usage_ledger
            SET input_tokens = ?,
                output_tokens = ?,
                tool_calls = ?,
                connector_calls = ?,
                latency_ms = ?,
                status = ?,
                error_code = ?,
                cost_final_usd = ?,
                billable_usd = ?,
                ct_shadow_debit = ?,
                pricing_catalog_id = ?,
                ct_rate_id = ?,
                risk_buffer_pct = ?,
                target_margin_pct = ?,
                minimum_ct_debit = ?,
                meta_json = ?
            WHERE request_id = ?
            """,
            (
                int(input_tokens or 0),
                int(output_tokens or 0),
                int(tool_calls or 0),
                int(connector_calls or 0),
                int(latency_ms or 0),
                str(status or "ok")[:16],
                str(error_code or "")[:64] or None,
                float(computed_cost_final_usd or 0.0),  # shadow only for now
                float(billable_usd) if billable_usd is not None else None,
                int(ct_shadow_debit) if ct_shadow_debit is not None else None,
                pricing_id if pricing_id else None,
                ct_rate_id if ct_rate_id else None,
                float(risk_buffer),
                float(target_margin),
                int(minimum_ct),
                meta_json[:8000],
                str(request_id or "")[:96],
            ),
        )
    except Exception as e:
        print(f"shadow_usage_finalize_error: {e}")


def _is_premium_user(conn, user_id):
    try:
        row = conn.execute("SELECT COALESCE(is_premium, 0) FROM users WHERE id = ? LIMIT 1", (int(user_id),)).fetchone()
        return bool(row[0]) if row else False
    except Exception:
        return False


def _ct_monthly_limit(is_premium, settings_obj=None):
    if isinstance(settings_obj, dict):
        economy = settings_obj.get("economy") if isinstance(settings_obj.get("economy"), dict) else {}
        try:
            configured = int(economy.get("monthly_grant", 0) or 0)
            if configured > 0:
                return configured
        except Exception:
            pass
    return CT_MONTHLY_GRANT_PREMIUM if bool(is_premium) else CT_MONTHLY_GRANT_FREE


def _ct_daily_limit(settings_obj=None):
    if isinstance(settings_obj, dict):
        economy = settings_obj.get("economy") if isinstance(settings_obj.get("economy"), dict) else {}
        try:
            configured = int(economy.get("daily_limit", 0) or 0)
            if configured > 0:
                return configured
        except Exception:
            pass
    return 0


def _ct_cost_multiplier(settings_obj=None):
    if isinstance(settings_obj, dict):
        economy = settings_obj.get("economy") if isinstance(settings_obj.get("economy"), dict) else {}
        try:
            configured = float(economy.get("cost_multiplier", 1.0) or 1.0)
            return max(0.1, min(2.0, configured))
        except Exception:
            pass
    return 1.0


def _ct_monthly_reset_day(settings_obj=None):
    if isinstance(settings_obj, dict):
        economy = settings_obj.get("economy") if isinstance(settings_obj.get("economy"), dict) else {}
        try:
            configured = int(economy.get("monthly_reset_day", 1) or 1)
            return max(1, min(28, configured))
        except Exception:
            pass
    return 1


def _ct_monthly_reset_hour(settings_obj=None):
    if isinstance(settings_obj, dict):
        economy = settings_obj.get("economy") if isinstance(settings_obj.get("economy"), dict) else {}
        try:
            configured = int(economy.get("monthly_reset_hour", 0) or 0)
            return max(0, min(23, configured))
        except Exception:
            pass
    return 0


def _ct_monthly_reset_minute(settings_obj=None):
    if isinstance(settings_obj, dict):
        economy = settings_obj.get("economy") if isinstance(settings_obj.get("economy"), dict) else {}
        try:
            configured = int(economy.get("monthly_reset_minute", 0) or 0)
            configured = max(0, min(59, configured))
            configured = int((configured // 15) * 15)
            return configured if configured in (0, 15, 30, 45) else 0
        except Exception:
            pass
    return 0


def _ct_current_cycle_window(reset_day, reset_hour=0, reset_minute=0):
    rd = max(1, min(28, int(reset_day or 1)))
    rh = max(0, min(23, int(reset_hour or 0)))
    rm = max(0, min(59, int(reset_minute or 0)))
    rm = int((rm // 15) * 15)
    if rm not in (0, 15, 30, 45):
        rm = 0
    now = datetime.now()

    candidate = datetime(now.year, now.month, rd, rh, rm, 0)
    if now >= candidate:
        start_year, start_month = now.year, now.month
    else:
        if now.month == 1:
            start_year, start_month = now.year - 1, 12
        else:
            start_year, start_month = now.year, now.month - 1

    start_dt = datetime(start_year, start_month, rd, rh, rm, 0)

    if start_month == 12:
        end_year, end_month = start_year + 1, 1
    else:
        end_year, end_month = start_year, start_month + 1

    end_dt = datetime(end_year, end_month, rd, rh, rm, 0)
    return start_dt, end_dt


def _ensure_monthly_ct_grant(conn, user_id, settings_obj=None):
    _ensure_usage_ledger_table(conn)
    is_premium = _is_premium_user(conn, user_id)
    settings_obj = settings_obj if isinstance(settings_obj, dict) else _load_user_settings(conn, user_id)
    monthly_limit = _ct_monthly_limit(is_premium, settings_obj=settings_obj)
    reset_day = _ct_monthly_reset_day(settings_obj)
    reset_hour = _ct_monthly_reset_hour(settings_obj)
    reset_minute = _ct_monthly_reset_minute(settings_obj)
    cycle_start_dt, cycle_end_dt = _ct_current_cycle_window(reset_day, reset_hour, reset_minute)
    cycle_start = cycle_start_dt.strftime('%Y-%m-%d %H:%M:%S')
    cycle_end = cycle_end_dt.strftime('%Y-%m-%d %H:%M:%S')

    row = conn.execute(
        """
        SELECT id FROM usage_ledger
        WHERE user_id = ?
          AND event_type = 'monthly_grant'
          AND created_at >= ?
          AND created_at < ?
        ORDER BY id DESC LIMIT 1
        """,
        (int(user_id), cycle_start, cycle_end),
    ).fetchone()

    if not row:
        desc = f"Monthly CT grant ({monthly_limit} CT) [reset day {reset_day} @ {reset_hour:02d}:{reset_minute:02d}]"
        conn.execute(
            "INSERT INTO usage_ledger (user_id, client_id, event_type, amount, description) VALUES (?, NULL, 'monthly_grant', ?, ?)",
            (int(user_id), int(monthly_limit), desc),
        )

    return bool(is_premium), int(monthly_limit)


def _get_user_ct_snapshot(conn, user_id, client_id=None):
    _ensure_usage_ledger_table(conn)
    settings_obj = _load_user_settings(conn, user_id)
    economy = settings_obj.get("economy") if isinstance(settings_obj.get("economy"), dict) else {}
    is_premium, monthly_limit = _ensure_monthly_ct_grant(conn, user_id, settings_obj=settings_obj)
    reset_day = _ct_monthly_reset_day(settings_obj)
    reset_hour = _ct_monthly_reset_hour(settings_obj)
    reset_minute = _ct_monthly_reset_minute(settings_obj)
    cycle_start_dt, cycle_end_dt = _ct_current_cycle_window(reset_day, reset_hour, reset_minute)
    cycle_start = cycle_start_dt.strftime('%Y-%m-%d %H:%M:%S')
    cycle_end = cycle_end_dt.strftime('%Y-%m-%d %H:%M:%S')

    row = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM usage_ledger WHERE user_id = ?", (int(user_id),)).fetchone()
    balance = int((row[0] if row else 0) or 0)

    row = conn.execute(
        """
        SELECT COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0)
        FROM usage_ledger
        WHERE user_id = ?
          AND created_at >= ?
          AND created_at < ?
        """,
        (int(user_id), cycle_start, cycle_end),
    ).fetchone()
    used_month = int((row[0] if row else 0) or 0)

    if client_id is None:
        row = conn.execute(
            """
            SELECT COUNT(*) FROM usage_ledger
            WHERE user_id = ?
              AND event_type = 'run_flow'
              AND DATE(created_at) = DATE('now')
            """,
            (int(user_id),),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT COUNT(*) FROM usage_ledger
            WHERE user_id = ?
              AND event_type = 'run_flow'
              AND DATE(created_at) = DATE('now')
              AND COALESCE(client_id, 0) = ?
            """,
            (int(user_id), int(client_id)),
        ).fetchone()
    requests_today = int((row[0] if row else 0) or 0)

    row = conn.execute(
        """
        SELECT COUNT(*) FROM usage_ledger
        WHERE user_id = ?
          AND event_type = 'run_flow'
          AND created_at >= datetime('now', '-30 day')
        """,
        (int(user_id),),
    ).fetchone()
    requests_30d = int((row[0] if row else 0) or 0)

    usage_pct = 0
    if monthly_limit > 0:
        usage_pct = int(round((float(used_month) / float(monthly_limit)) * 100))
    usage_pct = max(0, min(100, int(usage_pct)))

    remaining_pct = 0
    if monthly_limit > 0:
        remaining_pct = max(0, min(100, int(round((float(balance) / float(monthly_limit)) * 100))))

    try:
        max_per_message = int(economy.get("max_per_message", 80) or 80)
    except Exception:
        max_per_message = 80
    max_per_message = max(20, min(500, max_per_message))

    daily_limit = _ct_daily_limit(settings_obj)
    cost_multiplier = _ct_cost_multiplier(settings_obj)
    preset = str(economy.get("preset") or "").strip().lower()
    if preset not in VALID_ECONOMY_PRESETS:
        preset = "premium" if bool(is_premium) else "free"

    rows = conn.execute(
        """
        SELECT event_type, COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0)
        FROM usage_ledger
        WHERE user_id = ?
          AND created_at >= datetime('now', '-30 day')
        GROUP BY event_type
        """,
        (int(user_id),),
    ).fetchall()

    raw_breakdown = {'chat': 0, 'rag': 0, 'flow': 0, 'asset': 0}
    for r in rows:
        et = str((r[0] if len(r) > 0 else '') or '').strip().lower()
        val = int((r[1] if len(r) > 1 else 0) or 0)
        if val <= 0:
            continue
        if et in {'chat_message'}:
            raw_breakdown['chat'] += val
        elif et in {'rag_query', 'agent_rag'}:
            raw_breakdown['rag'] += val
        elif et in {'run_flow'}:
            raw_breakdown['flow'] += val
        elif et in {'asset_gen', 'boardroom_run', 'connector_fetch'}:
            raw_breakdown['asset'] += val

    total_breakdown = sum(raw_breakdown.values())
    usage_breakdown = {'chat': 40, 'rag': 25, 'flow': 20, 'asset': 15}
    if total_breakdown > 0:
        usage_breakdown = {
            'chat': int(round((raw_breakdown['chat'] / float(total_breakdown)) * 100)),
            'rag': int(round((raw_breakdown['rag'] / float(total_breakdown)) * 100)),
            'flow': int(round((raw_breakdown['flow'] / float(total_breakdown)) * 100)),
            'asset': int(round((raw_breakdown['asset'] / float(total_breakdown)) * 100)),
        }
        delta = 100 - sum(usage_breakdown.values())
        if delta != 0:
            largest_key = max(usage_breakdown, key=lambda k: usage_breakdown[k])
            usage_breakdown[largest_key] = max(0, usage_breakdown[largest_key] + delta)

    return {
        "is_premium": bool(is_premium),
        "plan": preset,
        "tier": preset,
        "economy_preset": preset,
        "cost_multiplier": float(cost_multiplier),
        "monthly_grant": int(monthly_limit),
        "max_per_message": int(max_per_message),
        "daily_limit": int(daily_limit),
        "monthly_reset_day": int(reset_day),
        "monthly_reset_hour": int(reset_hour),
        "monthly_reset_minute": int(reset_minute),
        "ct_monthly_limit": int(monthly_limit),
        "ct_used_month": int(used_month),
        "ct_balance": int(max(0, balance)),
        "ct_usage_pct": int(usage_pct),
        "requests_today": int(requests_today),
        "requests_30d": int(requests_30d),
        "low_balance": bool(remaining_pct <= CT_LOW_BALANCE_WARN_PCT),
        "remaining_pct": int(remaining_pct),
        "usage_breakdown": usage_breakdown,
    }


def _spend_ct(conn, user_id, amount, event_type="unknown", description="", client_id=None):
    requested_amt = int(amount or 0)
    if requested_amt <= 0:
        return {"success": False, "error": "Invalid amount"}

    snap = _get_user_ct_snapshot(conn, user_id, client_id=client_id)
    multiplier = float(snap.get("cost_multiplier", 1.0) or 1.0)
    multiplier = max(0.1, min(2.0, multiplier))
    amt = int(math.ceil(float(requested_amt) * multiplier))
    if amt <= 0:
        amt = 1

    daily_limit = int(snap.get("daily_limit", 0) or 0)
    used_today_row = conn.execute(
        """
        SELECT COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0)
        FROM usage_ledger
        WHERE user_id = ?
          AND DATE(created_at) = DATE('now')
        """,
        (int(user_id),),
    ).fetchone()
    used_today = int((used_today_row[0] if used_today_row else 0) or 0)
    if daily_limit > 0 and (used_today + amt) > daily_limit:
        return {
            "success": False,
            "error": "Daily CT limit reached",
            "required": int(amt),
            "requested": int(requested_amt),
            "cost_multiplier": float(multiplier),
            "daily_limit": int(daily_limit),
            "used_today": int(used_today),
            "remaining_today": int(max(0, daily_limit - used_today)),
        }

    balance = int(snap.get("ct_balance", 0) or 0)
    if balance < amt:
        return {
            "success": False,
            "error": "Insufficient CT balance",
            "required": amt,
            "requested": int(requested_amt),
            "cost_multiplier": float(multiplier),
            "available": balance,
        }

    etype = str(event_type or "unknown").strip().lower() or "unknown"
    desc = str(description or "").strip()[:300]
    conn.execute(
        "INSERT INTO usage_ledger (user_id, client_id, event_type, amount, description) VALUES (?, ?, ?, ?, ?)",
        (int(user_id), int(client_id) if client_id is not None else None, etype, -amt, desc),
    )
    new_balance = balance - amt
    limit = int(snap.get("ct_monthly_limit", 0) or 0)
    remaining_pct = int(round((float(new_balance) / float(limit)) * 100)) if limit > 0 else 0
    return {
        "success": True,
        "requested": int(requested_amt),
        "spent": int(amt),
        "cost_multiplier": float(multiplier),
        "daily_limit": int(daily_limit),
        "used_today": int(used_today + amt),
        "new_balance": int(max(0, new_balance)),
        "remaining_pct": int(max(0, min(100, remaining_pct))),
        "low_balance": bool(int(max(0, min(100, remaining_pct))) <= CT_LOW_BALANCE_WARN_PCT),
    }


def _topup_ct(conn, user_id, amount, description="Manual top-up (mock)", client_id=None):
    amt = int(amount or 0)
    if amt <= 0:
        return {"success": False, "error": "Invalid amount"}

    _ensure_monthly_ct_grant(conn, user_id)
    desc = str(description or "Manual top-up (mock)").strip()[:300]
    conn.execute(
        "INSERT INTO usage_ledger (user_id, client_id, event_type, amount, description) VALUES (?, ?, 'topup', ?, ?)",
        (int(user_id), int(client_id) if client_id is not None else None, int(amt), desc),
    )
    row = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM usage_ledger WHERE user_id = ?", (int(user_id),)).fetchone()
    new_balance = int((row[0] if row else 0) or 0)
    return {"success": True, "topup": int(amt), "new_balance": int(max(0, new_balance))}

def _client_owned(conn, user_id, client_id):
    if client_id is None:
        return False
    row = conn.execute(
        "SELECT id FROM clients WHERE id = ? AND user_id = ? LIMIT 1",
        (int(client_id), int(user_id)),
    ).fetchone()
    return bool(row)


def _humanize_slug(slug):
    text = str(slug or "").strip().replace("_", "-")
    if not text:
        return "Unknown"
    return " ".join(part.capitalize() for part in text.split("-") if part)


def _default_agent_custom_name(agent_slug: str) -> str:
    s = str(agent_slug or "").strip().lower()
    if not s:
        return "Agent"
    if s == "life-coach":
        return "Personal Assistant"
    for _ws_data in workspaces.values():
        agents = _ws_data.get("agents") or {}
        if s in agents:
            label = str(agents.get(s) or "").strip()
            if label:
                return label
            break
    return _humanize_slug(s)


def _all_workspace_agents():
    out = []
    for ws_slug, ws_data in (workspaces or {}).items():
        ws_agents = ws_data.get("agents") or {}
        for agent_slug, default_name in ws_agents.items():
            out.append((str(ws_slug).strip().lower(), str(agent_slug).strip().lower(), str(default_name or "").strip()))
    return out


def _ensure_vertex_defaults_for_user(user_id):
    """Force all workspace agents to Vertex runtime defaults for this user (non-destructive)."""
    if int(user_id or 0) <= 0:
        return
    conn = None
    try:
        conn = get_db()
        _ensure_client_tables(conn)
        cursor = conn.cursor()
        for _ws_slug, agent_slug, default_name in _all_workspace_agents():
            custom_name = _default_agent_custom_name(agent_slug)
            if default_name:
                custom_name = default_name
            cursor.execute(
                """
                INSERT OR IGNORE INTO agents_config
                (user_id, client_id, agent_slug, custom_name, llm_provider, llm_model, temperature, max_tokens, rag_enabled, status, updated_at)
                VALUES (?, NULL, ?, ?, 'vertex', ?, 0.7, 2048, 1, 'Active', datetime('now'))
                """,
                (int(user_id), str(agent_slug), str(custom_name), str(COOLBITS_VERTEX_PROFILE)),
            )
            cursor.execute(
                """
                UPDATE agents_config
                SET llm_provider = 'vertex',
                    llm_model = ?,
                    updated_at = datetime('now')
                WHERE user_id = ?
                  AND agent_slug = ?
                  AND (
                      lower(COALESCE(llm_provider, '')) <> 'vertex'
                      OR COALESCE(llm_model, '') <> ?
                  )
                """,
                (str(COOLBITS_VERTEX_PROFILE), int(user_id), str(agent_slug), str(COOLBITS_VERTEX_PROFILE)),
            )
        conn.commit()
    except Exception as e:
        print(f"ensure_vertex_defaults_error: {e}")
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


# Global error handlers to prevent crashes
@app.errorhandler(500)
def internal_error(error):
    import traceback
    traceback.print_exc()
    if request.is_json or request.content_type == 'application/json':
        return jsonify({"error": "Internal server error"}), 500
    return "Internal Server Error", 500

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        if request.is_json or request.content_type == 'application/json':
            return jsonify({"error": e.description, "status": e.code}), e.code
        return e
    import traceback
    print(f"Unhandled exception: {e}")
    traceback.print_exc()
    if request.is_json or request.content_type == 'application/json':
        return jsonify({"error": str(e)}), 500
    return f"Server Error: {e}", 500


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok", "service": "camarad"}), 200


@app.route("/readyz")
def readyz():
    db_ok = False
    db_error = None
    try:
        conn = get_db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        db_ok = True
    except Exception as exc:
        db_error = str(exc)

    status = "ready" if db_ok else "degraded"
    payload = {
        "status": status,
        "checks": {
            "db": {"ok": db_ok, "error": db_error},
        },
    }
    return jsonify(payload), (200 if db_ok else 503)

# @app.before_request
# def before_request():
#     init_db()

# @app.before_request
# def log_request():
#     print(f"Request: {request.method} {request.path}")
#     print(f"Headers: {dict(request.headers)}")
#     if request.method == "POST":
#         print(f"Body: {request.data}")
#     return

def _resolve_default_chat_target(settings_obj):
    prefs = (settings_obj or {}).get("preferences") or {}
    ws_slug = str(prefs.get("default_chat_workspace") or "personal").strip().lower()
    if ws_slug not in VALID_WORKSPACES:
        ws_slug = "personal"

    requested_slug = str(prefs.get("default_chat_agent_slug") or "life-coach").strip().lower()
    ws_agents = list((workspaces.get(ws_slug, {}).get("agents") or {}).keys())
    if requested_slug in ws_agents:
        return ws_slug, requested_slug
    if ws_agents:
        return ws_slug, ws_agents[0]
    return "personal", "life-coach"


def _is_chat_home_v2_enabled(settings_obj):
    prefs = (settings_obj or {}).get("preferences") or {}
    return _to_bool(prefs.get("chat_home_v2"), True)


def _compact_time_label(raw_ts):
    txt = str(raw_ts or "").strip()
    if not txt:
        return ""
    txt = txt.replace("T", " ")
    if len(txt) >= 16:
        return txt[5:16]
    return txt[:16]


def _agent_presence_label(raw_status):
    status = str(raw_status or "").strip().lower()
    if status in ("active", "ready", "connected", "online", "ok"):
        return "Online"
    if status in ("paused", "idle", "away", "pending"):
        return "Away"
    if not status:
        return "Online"
    return "Offline"


def _workspace_icon_class(ws_slug):
    return {
        "personal": "bi-person-heart",
        "business": "bi-briefcase",
        "agency": "bi-megaphone",
        "development": "bi-code-slash",
        "other": "bi-grid",
    }.get(str(ws_slug or "").strip().lower(), "bi-grid")


def _build_chat_home_payload(user_id, client_id, settings_obj):
    conn = get_db()
    _ensure_client_tables(conn)

    if client_id is not None and not _client_owned(conn, user_id, client_id):
        conn.close()
        return {"groups": [], "agents": [], "total_agents": 0, "forbidden_client": True}

    if client_id is not None:
        cfg_rows = conn.execute(
            """
            SELECT agent_slug, custom_name, status, avatar_base64, avatar_colors, COALESCE(client_id, 0) AS cid
            FROM agents_config
            WHERE user_id = ? AND COALESCE(client_id, 0) = ?
            ORDER BY datetime(updated_at) DESC, id DESC
            """,
            (user_id, int(client_id)),
        ).fetchall()
    else:
        cfg_rows = conn.execute(
            """
            SELECT agent_slug, custom_name, status, avatar_base64, avatar_colors, COALESCE(client_id, 0) AS cid
            FROM agents_config
            WHERE user_id = ?
            ORDER BY CASE WHEN COALESCE(client_id, 0) = 0 THEN 0 ELSE 1 END ASC, datetime(updated_at) DESC, id DESC
            """,
            (user_id,),
        ).fetchall()

    agent_cfg = {}
    for row in cfg_rows:
        slug = str(row[0] or "").strip()
        if not slug or slug in agent_cfg:
            continue
        avatar_colors = None
        try:
            avatar_colors = json.loads(row[4]) if row[4] else None
        except Exception:
            avatar_colors = None
        agent_cfg[slug] = {
            "custom_name": (row[1] or "").strip(),
            "status": row[2] or "Active",
            "avatar_base64": row[3] or None,
            "avatar_colors": avatar_colors,
            "client_id": int(row[5] or 0),
        }

    convo_sql = """
        SELECT c.id, c.workspace_slug, c.agent_slug, c.title, c.created_at,
               (SELECT content FROM messages WHERE conv_id = c.id ORDER BY timestamp DESC LIMIT 1) AS last_message,
               (SELECT MAX(timestamp) FROM messages WHERE conv_id = c.id) AS last_activity
        FROM conversations c
        WHERE c.user_id = ?
    """
    convo_params = [user_id]
    if client_id is not None:
        convo_sql += " AND COALESCE(c.client_id, 0) = ?"
        convo_params.append(int(client_id))
    convo_sql += " ORDER BY COALESCE((SELECT MAX(timestamp) FROM messages WHERE conv_id = c.id), c.created_at) DESC"
    convo_rows = conn.execute(convo_sql, tuple(convo_params)).fetchall()
    conn.close()

    latest_by_agent = {}
    for row in convo_rows:
        ws_slug = str(row[1] or "").strip().lower()
        agent_slug = str(row[2] or "").strip().lower()
        if not ws_slug or not agent_slug:
            continue
        key = (ws_slug, agent_slug)
        if key in latest_by_agent:
            continue
        msg = str(row[5] or "").strip()
        if len(msg) > 120:
            msg = msg[:120] + "…"
        latest_by_agent[key] = {
            "conv_id": int(row[0]),
            "title": (row[3] or "").strip(),
            "created_at": row[4],
            "last_message": msg,
            "last_activity": row[6] or row[4],
        }

    group_order = ["personal", "business", "agency", "development"]
    known_slugs = set()
    groups = []
    flat_agents = []

    for ws_slug in group_order:
        ws_data = workspaces.get(ws_slug) or {}
        ws_name = ws_data.get("name", ws_slug.title())
        ws_agents = []
        for agent_slug, default_name in (ws_data.get("agents") or {}).items():
            known_slugs.add(agent_slug)
            cfg = agent_cfg.get(agent_slug) or {}
            latest = latest_by_agent.get((ws_slug, agent_slug)) or {}
            name = str(cfg.get("custom_name") or default_name or _humanize_slug(agent_slug)).strip()
            conv_id = latest.get("conv_id")
            open_url = f"/chat/{ws_slug}/{agent_slug}?conv_id={conv_id}" if conv_id else f"/chat/{ws_slug}/{agent_slug}"
            status_text = _agent_presence_label(cfg.get("status"))
            card = {
                "workspace_slug": ws_slug,
                "workspace_name": ws_name,
                "workspace_icon": _workspace_icon_class(ws_slug),
                "agent_slug": agent_slug,
                "agent_name": name,
                "status": status_text,
                "status_class": status_text.lower(),
                "avatar_base64": cfg.get("avatar_base64"),
                "avatar_colors": cfg.get("avatar_colors"),
                "has_photo": bool(cfg.get("avatar_base64")),
                "has_conversation": bool(conv_id),
                "conv_id": conv_id,
                "open_url": open_url,
                "last_message": latest.get("last_message") or "Start a new conversation",
                "last_activity": latest.get("last_activity") or "",
                "last_activity_label": _compact_time_label(latest.get("last_activity")),
                "search_text": f"{name} {agent_slug} {ws_name}".lower(),
            }
            ws_agents.append(card)
            flat_agents.append(card)
        groups.append({
            "workspace_slug": ws_slug,
            "workspace_name": ws_name,
            "workspace_icon": _workspace_icon_class(ws_slug),
            "agents": ws_agents,
            "count": len(ws_agents),
        })

    extra_slugs = sorted((set(agent_cfg.keys()) | {k[1] for k in latest_by_agent.keys()}) - known_slugs)
    if extra_slugs:
        extra_agents = []
        for agent_slug in extra_slugs:
            cfg = agent_cfg.get(agent_slug) or {}
            latest = None
            latest_ws = "other"
            for (ws_key, slug_key), item in latest_by_agent.items():
                if slug_key == agent_slug:
                    latest = item
                    latest_ws = ws_key
                    break
            name = str(cfg.get("custom_name") or _humanize_slug(agent_slug)).strip()
            conv_id = latest.get("conv_id") if latest else None
            open_url = f"/chat/{latest_ws}/{agent_slug}?conv_id={conv_id}" if conv_id else f"/chat/{latest_ws}/{agent_slug}"
            status_text = _agent_presence_label(cfg.get("status"))
            card = {
                "workspace_slug": latest_ws,
                "workspace_name": "Other",
                "workspace_icon": _workspace_icon_class("other"),
                "agent_slug": agent_slug,
                "agent_name": name,
                "status": status_text,
                "status_class": status_text.lower(),
                "avatar_base64": cfg.get("avatar_base64"),
                "avatar_colors": cfg.get("avatar_colors"),
                "has_photo": bool(cfg.get("avatar_base64")),
                "has_conversation": bool(conv_id),
                "conv_id": conv_id,
                "open_url": open_url,
                "last_message": (latest or {}).get("last_message") or "Start a new conversation",
                "last_activity": (latest or {}).get("last_activity") or "",
                "last_activity_label": _compact_time_label((latest or {}).get("last_activity")),
                "search_text": f"{name} {agent_slug} other".lower(),
            }
            extra_agents.append(card)
            flat_agents.append(card)
        groups.append({
            "workspace_slug": "other",
            "workspace_name": "Other",
            "workspace_icon": _workspace_icon_class("other"),
            "agents": extra_agents,
            "count": len(extra_agents),
        })

    default_ws, default_agent = _resolve_default_chat_target(settings_obj)
    return {
        "groups": groups,
        "agents": flat_agents,
        "total_agents": len(flat_agents),
        "forbidden_client": False,
        "default_ws": default_ws,
        "default_agent": default_agent,
    }


def _safe_next_path(raw_next):
    nxt = str(raw_next or "").strip()
    if not nxt.startswith("/") or nxt.startswith("//"):
        return "/app"
    if nxt.startswith("/api/"):
        return "/app"
    return nxt


def _is_onboarding_complete(settings_obj):
    settings_obj = settings_obj if isinstance(settings_obj, dict) else {}
    prefs = settings_obj.get("preferences") or {}
    return _to_bool(prefs.get("onboarding_completed"), False)


def _auth_redirect(next_path=None):
    return redirect(url_for("signup_page", next=_safe_next_path(next_path or request.path)))


def _must_complete_onboarding(user_id):
    if int(user_id or 0) <= 0:
        return False
    return not _is_onboarding_complete(_get_user_settings(int(user_id)))


def _render_app_home():
    # Explicit bypass for users that always want classic home
    force_home = str(request.args.get("home") or "").strip().lower()
    if force_home in ("1", "true", "yes", "on"):
        return render_template('home.html', workspaces=workspaces)

    uid = get_current_user_id()
    settings = _get_user_settings(uid)
    prefs = settings.get("preferences") or {}

    if _to_bool(prefs.get("always_open_home"), False):
        return render_template('home.html', workspaces=workspaces)

    landing = str(prefs.get("default_landing") or "orchestrator").strip().lower()
    if landing not in VALID_LANDING:
        landing = "orchestrator"

    if landing == "home":
        return render_template('home.html', workspaces=workspaces)
    if landing == "orchestrator":
        return redirect(url_for("orchestrator"))
    if landing == "agents":
        return redirect(url_for("agents"))
    if landing == "connectors":
        return redirect(url_for("connectors"))
    if landing == "boardroom":
        return redirect(url_for("boardroom"))
    if landing == "settings":
        return redirect(url_for("settings_page"))
    if landing == "workspace":
        ws_slug = str(prefs.get("default_workspace") or "agency").strip().lower()
        if ws_slug not in VALID_WORKSPACES:
            ws_slug = "agency"
        return redirect(url_for("workspace", ws_slug=ws_slug))
    if landing == "chat":
        if _is_chat_home_v2_enabled(settings):
            return redirect(url_for("chat_home"))
        ws_slug, agent_slug = _resolve_default_chat_target(settings)
        return redirect(url_for("chat", ws_slug=ws_slug, agent_slug=agent_slug))

    return redirect(url_for("orchestrator"))


@app.route('/')
def home():
    host = str(request.host or "").strip().lower()
    if host.startswith("api.camarad.ai"):
        return jsonify({
            "service": "camarad-api",
            "status": "ok",
            "message": "Camarad API root",
            "endpoints": {
                "healthz": "/healthz",
                "readyz": "/readyz",
                "app": "/app",
                "signup": "/signup",
            },
        }), 200

    force_landing = str(request.args.get("landing") or "").strip().lower()
    if force_landing in ("1", "true", "yes", "on"):
        return render_template("landing.html")

    force_home = str(request.args.get("home") or "").strip().lower()
    if force_home in ("1", "true", "yes", "on"):
        return render_template('home.html', workspaces=workspaces)

    # Public homepage for anonymous visitors.
    if not is_user_authenticated():
        return render_template("landing.html")

    uid = get_current_user_id()
    if uid <= 0:
        return render_template("landing.html")
    if _must_complete_onboarding(uid):
        return redirect(url_for("onboarding_page"))

    settings = _get_user_settings(uid)
    prefs = settings.get("preferences") or {}
    if _to_bool(prefs.get("always_open_home"), False):
        return render_template('home.html', workspaces=workspaces)

    if _is_chat_home_v2_enabled(settings):
        return redirect(url_for("chat_home"))

    ws_slug, agent_slug = _resolve_default_chat_target(settings)
    return redirect(url_for("chat", ws_slug=ws_slug, agent_slug=agent_slug))


@app.route('/landing')
def landing_page():
    return render_template("landing.html")


@app.route("/login")
@app.route("/login/")
@app.route("/register")
@app.route("/register/")
def legacy_auth_redirects():
    nxt = _safe_next_path(request.args.get("next") or "/app")
    return redirect(url_for("signup_page", next=nxt), code=301)


@app.route("/api/auth/google/start", methods=["GET"])
def api_auth_google_start_proxy():
    """Proxy Google OAuth start through Camarad domain."""
    return_to = _safe_next_path(request.args.get("returnTo") or request.args.get("next") or "/app")
    try:
        upstream = requests.get(
            f"{COOLBITS_URL}/api/auth/google/start",
            params={"returnTo": return_to},
            timeout=20,
            allow_redirects=False,
        )
    except Exception as exc:
        return jsonify({"error": "oauth_start_unreachable", "detail": str(exc)}), 502

    resp = make_response(upstream.content, int(upstream.status_code))
    ct = upstream.headers.get("content-type")
    if ct:
        resp.headers["Content-Type"] = ct
    cache_ctl = upstream.headers.get("cache-control")
    if cache_ctl:
        resp.headers["Cache-Control"] = cache_ctl
    loc = upstream.headers.get("location")
    if loc:
        resp.headers["Location"] = loc
    set_cookie = upstream.headers.get("set-cookie")
    if set_cookie:
        resp.headers.add("Set-Cookie", set_cookie)
    return resp


@app.route("/api/auth/google/callback", methods=["GET"])
def api_auth_google_callback_proxy():
    """Proxy Google OAuth callback through Camarad domain."""
    cookie_hdr = request.headers.get("Cookie", "")
    try:
        upstream = requests.get(
            f"{COOLBITS_URL}/api/auth/google/callback",
            params=request.args,
            headers={"Cookie": cookie_hdr},
            timeout=30,
            allow_redirects=False,
        )
    except Exception as exc:
        return jsonify({"error": "oauth_callback_unreachable", "detail": str(exc)}), 502

    resp = make_response(upstream.content, int(upstream.status_code))
    ct = upstream.headers.get("content-type")
    if ct:
        resp.headers["Content-Type"] = ct
    cache_ctl = upstream.headers.get("cache-control")
    if cache_ctl:
        resp.headers["Cache-Control"] = cache_ctl
    loc = upstream.headers.get("location")
    if loc:
        resp.headers["Location"] = loc
    set_cookie = upstream.headers.get("set-cookie")
    if set_cookie:
        resp.headers.add("Set-Cookie", set_cookie)
    return resp


@app.route('/signup')
def signup_page():
    if is_user_authenticated():
        uid = get_current_user_id()
        if uid > 0 and _must_complete_onboarding(uid):
            return redirect(url_for("onboarding_page"))
        return redirect(_safe_next_path(request.args.get("next") or "/app"))
    return render_template(
        "signup.html",
        oauth_start_url="/api/auth/google/start",
        next_path=_safe_next_path(request.args.get("next") or "/app"),
    )


@app.route('/onboarding')
def onboarding_page():
    if AUTH_REQUIRED and not is_user_authenticated():
        return _auth_redirect(next_path="/onboarding")
    uid = get_current_user_id()
    if uid <= 0:
        return _auth_redirect(next_path="/onboarding")
    settings = _get_user_settings(uid)
    if _is_onboarding_complete(settings):
        return redirect(_safe_next_path(request.args.get("next") or "/app"))
    profile = settings.get("profile") if isinstance(settings, dict) else {}
    return render_template("onboarding.html", profile=profile or {})


@app.route("/api/auth/session", methods=["POST"])
def api_auth_session():
    payload = request.get_json(force=True, silent=True) or {}
    token = str(payload.get("token") or "").strip()
    if not token:
        return jsonify({"error": "missing_token"}), 400

    try:
        remote_user = _coolbits_auth_me(token)
    except Exception as exc:
        return jsonify({"error": "auth_failed", "detail": str(exc)}), 401

    email = _normalize_email(remote_user.get("email"))
    if not email:
        return jsonify({"error": "missing_email"}), 400
    display_name = str(remote_user.get("name") or remote_user.get("displayName") or "").strip()

    local_user = _upsert_local_user_from_auth(email=email, display_name=display_name, auth_provider="google")
    uid = int(local_user["id"])

    conn = get_db()
    try:
        _ensure_user_settings_table(conn)
        settings = _load_user_settings(conn, uid)
        profile = settings.get("profile") or {}
        if display_name and not str(profile.get("display_name") or "").strip():
            profile["display_name"] = display_name[:80]
        if email:
            profile["email"] = email[:160]
        settings["profile"] = profile
        settings = _save_user_settings(conn, uid, settings)
        conn.commit()
    finally:
        conn.close()

    resp = jsonify({
        "success": True,
        "authenticated": True,
        "user_id": uid,
        "email": email,
        "display_name": (settings.get("profile") or {}).get("display_name") or local_user.get("username"),
        "onboarding_completed": _is_onboarding_complete(settings),
        "next": "/onboarding" if not _is_onboarding_complete(settings) else _safe_next_path(payload.get("next") or "/app"),
    })
    cookie_opts = _auth_cookie_opts()
    resp.set_cookie("camarad_user_id", str(uid), max_age=30 * 24 * 3600, **cookie_opts)
    resp.set_cookie("camarad_cb_token", token, max_age=30 * 24 * 3600, httponly=True, **cookie_opts)
    return resp


@app.route("/api/auth/status", methods=["GET"])
def api_auth_status():
    if not is_user_authenticated():
        return jsonify({"authenticated": False, "user_id": None, "onboarding_completed": False})

    uid = get_current_user_id()
    if uid <= 0:
        return jsonify({"authenticated": False, "user_id": None, "onboarding_completed": False})
    settings = _get_user_settings(uid)
    profile = settings.get("profile") or {}
    return jsonify({
        "authenticated": True,
        "user_id": uid,
        "display_name": str(profile.get("display_name") or "").strip() or f"user-{uid}",
        "email": str(profile.get("email") or "").strip(),
        "onboarding_completed": _is_onboarding_complete(settings),
    })


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    resp = jsonify({"success": True})
    cookie_opts = _auth_cookie_opts()
    resp.set_cookie("camarad_user_id", "", max_age=0, **cookie_opts)
    resp.set_cookie("camarad_cb_token", "", max_age=0, httponly=True, **cookie_opts)
    resp.set_cookie("camarad_client_id", "", max_age=0, **cookie_opts)
    return resp


@app.route("/api/auth/onboarding", methods=["POST"])
def api_auth_onboarding():
    if AUTH_REQUIRED and not is_user_authenticated():
        return jsonify({"error": "unauthorized"}), 401
    uid = get_current_user_id()
    if uid <= 0:
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(force=True, silent=True) or {}
    display_name = str(payload.get("display_name") or "").strip()[:80]
    role = str(payload.get("role") or "").strip()[:80]
    timezone = str(payload.get("timezone") or "Europe/Bucharest").strip()[:80]
    language = str(payload.get("language") or "en").strip().lower()[:8]
    default_workspace = str(payload.get("default_workspace") or "agency").strip().lower()
    company_name = str(payload.get("company_name") or "").strip()[:120]
    company_website = str(payload.get("company_website") or "").strip()[:200]

    conn = get_db()
    try:
        _ensure_user_settings_table(conn)
        _ensure_client_tables(conn)
        settings = _load_user_settings(conn, uid)
        profile = settings.get("profile") or {}
        if display_name:
            profile["display_name"] = display_name
        if role:
            profile["role"] = role
        profile["timezone"] = timezone or "Europe/Bucharest"
        profile["language"] = language or "en"
        settings["profile"] = profile

        prefs = settings.get("preferences") or {}
        prefs["default_workspace"] = default_workspace if default_workspace in VALID_WORKSPACES else "agency"
        prefs["onboarding_completed"] = True
        settings["preferences"] = prefs
        settings = _save_user_settings(conn, uid, settings)

        created_client_id = None
        if company_name:
            existing = conn.execute(
                """
                SELECT id FROM clients
                WHERE user_id = ? AND lower(type) = 'company' AND lower(coalesce(company_name,'')) = lower(?)
                LIMIT 1
                """,
                (uid, company_name),
            ).fetchone()
            if existing:
                created_client_id = int(existing["id"])
            else:
                cur = conn.execute(
                    """
                    INSERT INTO clients (user_id, type, company_name, website, email, notes)
                    VALUES (?, 'company', ?, ?, ?, ?)
                    """,
                    (uid, company_name, company_website, str(profile.get("email") or "").strip(), "Created from onboarding"),
                )
                created_client_id = int(cur.lastrowid)
        conn.commit()
    finally:
        conn.close()

    resp = jsonify({
        "success": True,
        "onboarding_completed": True,
        "client_id": created_client_id,
        "next": _safe_next_path(payload.get("next") or "/app"),
    })
    if created_client_id:
        resp.set_cookie("camarad_client_id", str(created_client_id), max_age=30 * 24 * 3600, **_auth_cookie_opts())
    return resp


@app.route('/app')
def app_home():
    if AUTH_REQUIRED and not is_user_authenticated():
        return _auth_redirect(next_path="/app")
    uid = get_current_user_id()
    if uid > 0 and _must_complete_onboarding(uid):
        return redirect(url_for("onboarding_page"))
    return _render_app_home()


@app.route('/about')
def about_page():
    return render_template(
        "simple_page.html",
        page_title="About Camarad.ai",
        page_description="Camarad.ai helps people and teams execute faster with AI agents, orchestrated workflows, and live connectors.",
    )


@app.route("/robots.txt")
def robots_txt():
    host = (request.host_url or "https://camarad.ai").rstrip("/")
    body = (
        "User-agent: *\n"
        "Allow: /\n\n"
        f"Sitemap: {host}/sitemap.xml\n"
    )
    resp = make_response(body, 200)
    resp.headers["Content-Type"] = "text/plain; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/sitemap.xml")
def sitemap_xml():
    base = (request.host_url or "https://camarad.ai").rstrip("/")
    today = time.strftime("%Y-%m-%d")
    urls = [
        ("/", "daily", "1.0"),
        ("/pricing", "weekly", "0.9"),
        ("/signup", "weekly", "0.8"),
        ("/about", "monthly", "0.6"),
        ("/legal", "monthly", "0.5"),
        ("/privacy", "monthly", "0.5"),
        ("/terms", "monthly", "0.5"),
    ]
    items = []
    for path, changefreq, priority in urls:
        items.append(
            "  <url>\n"
            f"    <loc>{base}{path}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            "  </url>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(items)
        + "\n</urlset>\n"
    )
    resp = make_response(xml, 200)
    resp.headers["Content-Type"] = "application/xml; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route('/pricing')
def pricing_page():
    return render_template("pricing.html", plans=PRICING_PLAN_CATALOG)


@app.route('/api/pricing/plans', methods=["GET"])
def api_pricing_plans():
    return jsonify({"success": True, "plans": PRICING_PLAN_CATALOG})


@app.route('/legal')
def legal_page():
    return render_template("legal.html")


@app.route('/privacy')
def privacy_page():
    return render_template("privacy.html")


@app.route('/terms')
def terms_page():
    return render_template("terms.html")


@app.route('/settings')
def settings_page():
    if AUTH_REQUIRED and not is_user_authenticated():
        return _auth_redirect(next_path="/settings")
    uid = get_current_user_id()
    if uid > 0 and _must_complete_onboarding(uid):
        return redirect(url_for("onboarding_page"))
    return render_template('settings.html')


@app.route('/workspace/<ws_slug>')
def workspace(ws_slug):
    if AUTH_REQUIRED and not is_user_authenticated():
        return _auth_redirect(next_path=f"/workspace/{ws_slug}")
    uid = get_current_user_id()
    if uid > 0 and _must_complete_onboarding(uid):
        return redirect(url_for("onboarding_page"))
    if ws_slug not in workspaces:
        return "Workspace not found", 404
    ws_data = workspaces[ws_slug]
    return render_template('workspace.html', ws_slug=ws_slug, ws_data=ws_data)

@app.route('/search/<ws_slug>')
def search(ws_slug):
    if AUTH_REQUIRED and not is_user_authenticated():
        return _auth_redirect(next_path=f"/search/{ws_slug}")
    uid = get_current_user_id()
    if uid > 0 and _must_complete_onboarding(uid):
        return redirect(url_for("onboarding_page"))
    if ws_slug not in workspaces:
        return "Workspace not found", 404
    query = request.args.get('q', '')
    if not query:
        return redirect(url_for('workspace', ws_slug=ws_slug))
    results = search_conversations(uid, ws_slug, query)
    return render_template('search_results.html', ws_slug=ws_slug, query=query, results=results)


@app.route('/chat')
@app.route('/chat/')
def chat_home():
    if AUTH_REQUIRED and not is_user_authenticated():
        return _auth_redirect(next_path="/chat")
    uid = get_current_user_id()
    if uid > 0 and _must_complete_onboarding(uid):
        return redirect(url_for("onboarding_page"))
    if FORCE_VERTEX_ALL_AGENTS and uid > 0:
        _ensure_vertex_defaults_for_user(uid)

    settings = _get_user_settings(uid)
    if not _is_chat_home_v2_enabled(settings):
        ws_slug, agent_slug = _resolve_default_chat_target(settings)
        return redirect(url_for("chat", ws_slug=ws_slug, agent_slug=agent_slug))

    client_id = get_current_client_id()
    payload = _build_chat_home_payload(uid, client_id, settings)
    if payload.get("forbidden_client"):
        return "Client not found", 404

    ws_filter = str(request.args.get("workspace") or request.args.get("ws") or "all").strip().lower()
    if ws_filter not in (set(VALID_WORKSPACES) | {"all", "other"}):
        ws_filter = "all"
    q = str(request.args.get("q") or "").strip()

    return render_template(
        "chat_home.html",
        chat_home=payload,
        ws_filter=ws_filter,
        q=q,
    )


@app.route('/chat/<ws_slug>/<agent_slug>', methods=['GET', 'POST'])
def chat(ws_slug, agent_slug):
    if AUTH_REQUIRED and not is_user_authenticated():
        return _auth_redirect(next_path=f"/chat/{ws_slug}/{agent_slug}")
    uid = get_current_user_id()
    if uid > 0 and _must_complete_onboarding(uid):
        return redirect(url_for("onboarding_page"))

    if request.method == 'POST':
        try:
            # Anti-crash: parse JSON safely
            data = request.get_json(force=True, silent=True)
            if not data or not isinstance(data, dict):
                data = {}

            user_message = data.get('message', '').strip()
            request_id = _shadow_request_id(data.get("request_id") or request.headers.get("X-Request-ID"))
            conv_id = data.get('conv_id')
            if not user_message:
                user_message = request.form.get('message', '').strip()
            if not user_message:
                return jsonify({"error": "No message provided"}), 400

            agent_name = get_agent_name(ws_slug, agent_slug)

            # Get or create conversation
            if conv_id:
                conv_id = int(conv_id)
            else:
                conv_id = get_or_create_conversation(uid, ws_slug, agent_slug)

            # Auto-title: use first message if conversation has no title
            try:
                conn_t = get_db()
                row_t = conn_t.execute('SELECT title FROM conversations WHERE id = ?', (conv_id,)).fetchone()
                if row_t and (not row_t[0] or row_t[0] == agent_slug):
                    title = user_message[:50] + ('…' if len(user_message) > 50 else '')
                    conn_t.execute('UPDATE conversations SET title = ? WHERE id = ?', (title, conv_id))
                    conn_t.commit()
                conn_t.close()
            except Exception:
                pass

            # Save user message to DB
            save_message(conv_id, 'user', user_message)
            t0 = time.time()
            llm_provider = "mock"
            llm_model = "simulate_response"
            llm_status = "ok"
            llm_error = None

            # Try real Vertex via Coolbits for selected agents, fallback to existing mock flow
            try:
                response_text = None
                if agent_slug in REAL_AGENT_SLUGS:
                    try:
                        recent_history = get_messages(conv_id) or []
                    except Exception:
                        recent_history = []
                    response_text = _generate_real_agent_response(
                        agent_slug=agent_slug,
                        ws_slug=ws_slug,
                        user_message=user_message,
                        recent_history=recent_history,
                    )
                    if response_text:
                        llm_provider = "vertex"
                        llm_model = COOLBITS_VERTEX_PROFILE
                if not response_text and agent_slug in REAL_AGENT_SLUGS:
                    response_text = _fallback_real_agent_reply(
                        agent_slug=agent_slug,
                        ws_slug=ws_slug,
                        user_message=user_message,
                        runtime_ctx=_get_chat_runtime_context(uid, get_current_client_id()),
                    )
                    if response_text:
                        llm_provider = "camarad-fallback"
                        llm_model = f"{agent_slug}-fallback"
                if not response_text:
                    response_text = simulate_response(agent_slug, user_message)
                    if response_text:
                        llm_provider = "mock"
                        llm_model = "simulate_response"
                if not response_text:
                    response_text = get_llm_response(user_message)
                    llm_provider = "grok"
                    llm_model = "grok-1"
                response_text = _sanitize_real_agent_output(agent_slug, ws_slug, user_message, response_text)
            except Exception as llm_err:
                print(f"Response generation error: {llm_err}")
                llm_status = "error"
                llm_error = str(llm_err)
                response_text = f"{agent_name}: Received '{user_message}'. (Mock response - generation failed)"

            # Append connector-specific API docs context with citations (only when query is tool/API oriented)
            try:
                relevant_connectors = AGENT_CONNECTOR_MAP.get(agent_slug, [])
                if relevant_connectors and _should_attach_docs_context(agent_slug, user_message):
                    docs_context = get_api_docs_context(user_message, relevant_connectors, top_k=3)
                    if docs_context:
                        response_text += "\n\n---\n\n📚 **Relevant API Documentation:**\n\n" + docs_context
            except Exception as docs_err:
                print(f"API docs enrichment error: {docs_err}")

            # Save agent response to DB
            save_message(conv_id, 'agent', response_text)

            # Shadow usage telemetry (no CT debit changes).
            try:
                conn_shadow = get_db()
                _ensure_usage_ledger_table(conn_shadow)
                client_id = get_current_client_id()
                in_tok = _estimate_tokens(user_message)
                out_tok = _estimate_tokens(response_text)
                latency_ms = int(max(0, round((time.time() - t0) * 1000)))
                _shadow_usage_preflight(
                    conn_shadow,
                    request_id=request_id,
                    user_id=uid,
                    client_id=client_id,
                    workspace_id=ws_slug or _current_workspace_slug(),
                    event_type="chat_message",
                    amount=0,
                    description=f"Chat message ({agent_slug})",
                    provider=llm_provider,
                    model=llm_model,
                    region="unknown",
                    model_class="auto",
                    agent_id=agent_slug,
                    cost_estimate_usd=0.0,
                    meta={"shadow_mode": True, "source": "chat"},
                )
                _shadow_usage_finalize(
                    conn_shadow,
                    request_id=request_id,
                    status=llm_status,
                    error_code=llm_error,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    tool_calls=0,
                    connector_calls=0,
                    latency_ms=latency_ms,
                    cost_final_usd=0.0,
                    meta={"shadow_mode": True, "source": "chat", "agent_slug": agent_slug},
                )
                conn_shadow.commit()
                conn_shadow.close()
            except Exception as shadow_err:
                print(f"chat_shadow_usage_error: {shadow_err}")

            # Convert markdown to HTML safely
            try:
                response_html = Markup(markdown.markdown(response_text))
            except Exception:
                response_html = response_text

            return jsonify({
                "response": response_text,
                "response_html": str(response_html),
                "conv_id": conv_id,
                "request_id": request_id,
            })

        except Exception as e:
            import traceback
            print(f"CHAT POST CRASH: {e}")
            traceback.print_exc()
            return jsonify({"error": f"Server error: {str(e)}"}), 500

    # GET: render chat page
    try:
        agent_name = get_agent_name(ws_slug, agent_slug)
        conv_id = request.args.get('conv_id', type=int)
        history = []

        if conv_id:
            # Load existing conversation messages
            history = get_messages(conv_id)
        else:
            # Get most recent conversation for this agent, or create new
            conv_id = get_or_create_conversation(uid, ws_slug, agent_slug)
            history = get_messages(conv_id)

        recent_convs = get_recent_conversations(uid, ws_slug, limit=10)
        return render_template('chat.html', ws_slug=ws_slug, agent_slug=agent_slug,
                               agent_name=agent_name, history=history,
                               recent_convs=recent_convs, conv_id=conv_id)
    except Exception as e:
        print(f"CHAT GET error: {e}")
        return f"Error loading chat: {e}", 500


@app.route('/api/chat/suggestions', methods=['GET'])
def chat_suggestions():
    if AUTH_REQUIRED and not is_user_authenticated():
        return jsonify({"error": "unauthorized"}), 401

    uid = get_current_user_id()
    ws_slug = str(request.args.get("ws_slug") or "").strip().lower()
    agent_slug = str(request.args.get("agent_slug") or "").strip().lower()
    conv_id = request.args.get("conv_id", type=int)

    if ws_slug not in VALID_WORKSPACES or not agent_slug:
        return jsonify({"suggestions": []})

    runtime_ctx = _get_chat_runtime_context(uid, get_current_client_id())

    last_user_message = ""
    last_agent_message = ""
    if conv_id:
        conn = None
        try:
            conn = get_db()
            rows = conn.execute(
                """
                SELECT m.role, m.content
                FROM messages m
                JOIN conversations c ON c.id = m.conv_id
                WHERE c.id = ? AND c.user_id = ?
                ORDER BY m.id DESC
                LIMIT 12
                """,
                (int(conv_id), int(uid)),
            ).fetchall()
            for r in rows:
                role = str(r[0] or "").strip().lower()
                content = str(r[1] or "").strip()
                if role == "user" and (not last_user_message):
                    last_user_message = content
                elif role == "agent" and (not last_agent_message):
                    last_agent_message = content
                if last_user_message and last_agent_message:
                    break
        except Exception:
            pass
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    suggestions = _build_chat_suggestions(
        agent_slug=agent_slug,
        ws_slug=ws_slug,
        runtime_ctx=runtime_ctx,
        last_user_message=last_user_message,
        last_agent_message=last_agent_message,
    )
    return jsonify({
        "suggestions": suggestions,
        "context": {
            "client_name": runtime_ctx.get("client_name"),
            "connected_connectors": runtime_ctx.get("connected_connectors", []),
        },
    })


@app.route('/testchat', methods=['POST'])
def testchat():
    data = request.get_json()
    user_message = data.get('message', '')
    response = f"Mock response: {user_message}"
    return jsonify({
        "response": response,
        "response_html": response
    })
def _migrate_flows_table(conn):
    """Ensure flows table has required columns for templates and client scoping."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS flows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT 'Untitled Flow',
            user_id INTEGER DEFAULT 1,
            client_id INTEGER,
            flow_json TEXT NOT NULL,
            thumbnail TEXT,
            category TEXT DEFAULT 'Uncategorized',
            description TEXT DEFAULT '',
            is_template INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            is_active INTEGER DEFAULT 1
        )
    """)
    for stmt in (
        "ALTER TABLE flows ADD COLUMN thumbnail TEXT",
        "ALTER TABLE flows ADD COLUMN category TEXT DEFAULT 'Uncategorized'",
        "ALTER TABLE flows ADD COLUMN description TEXT DEFAULT ''",
        "ALTER TABLE flows ADD COLUMN is_template INTEGER DEFAULT 0",
        "ALTER TABLE flows ADD COLUMN client_id INTEGER",
    ):
        try:
            conn.execute(stmt)
        except Exception:
            pass
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_flows_user_template ON flows(user_id, is_template)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_flows_user_client_template ON flows(user_id, client_id, is_template)")
    except Exception:
        pass
    conn.commit()


def _flow_template_thumbnail(name, category):
    from urllib.parse import quote
    import html
    title = html.escape(name or "Flow Template")
    cat = html.escape(category or "Uncategorized")
    svg = f"<svg xmlns='http://www.w3.org/2000/svg' width='360' height='220'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0%' stop-color='#1f6feb'/><stop offset='100%' stop-color='#0d1117'/></linearGradient></defs><rect width='360' height='220' fill='url(#g)'/><circle cx='64' cy='64' r='22' fill='#3fb950' fill-opacity='0.8'/><circle cx='150' cy='112' r='14' fill='#58a6ff' fill-opacity='0.85'/><circle cx='240' cy='76' r='16' fill='#d29922' fill-opacity='0.8'/><rect x='26' y='156' width='308' height='44' rx='10' fill='#0b1220' fill-opacity='0.78'/><text x='34' y='176' font-family='Segoe UI, Arial, sans-serif' font-size='11' fill='#8b949e'>{cat}</text><text x='34' y='192' font-family='Segoe UI, Arial, sans-serif' font-size='14' fill='#e6edf3'>{title}</text></svg>"
    return "data:image/svg+xml;utf8," + quote(svg)


def _seed_flow_templates_if_missing(conn, user_id, client_id=None):
    """Persist realistic templates from ORCHESTRATOR_TEMPLATES for current user/client scope."""
    _migrate_flows_table(conn)
    if client_id is not None and not _client_owned(conn, user_id, client_id):
        return

    sql = "SELECT name, flow_json FROM flows WHERE user_id = ? AND COALESCE(is_template, 0) = 1"
    params = [user_id]
    if client_id is not None:
        sql += " AND COALESCE(client_id, 0) = ?"
        params.append(int(client_id))

    rows = conn.execute(sql, tuple(params)).fetchall()
    existing_ids = set()
    existing_names = set()
    for r in rows:
        name = str(r[0] or "").strip().lower()
        if name:
            existing_names.add(name)
        flow_json_raw = r[1]
        try:
            parsed = json.loads(flow_json_raw) if flow_json_raw else {}
        except Exception:
            parsed = {}
        if isinstance(parsed, dict):
            tpl_id = str(parsed.get("template_id") or "").strip().lower()
            if tpl_id:
                existing_ids.add(tpl_id)

    inserted = 0
    for t in (globals().get("ORCHESTRATOR_TEMPLATES", []) or []):
        tpl_id = str(t.get("id") or "").strip().lower()
        tpl_name = str(t.get("name") or "Flow Template").strip()
        if (tpl_id and tpl_id in existing_ids) or (tpl_name.lower() in existing_names):
            continue

        flow_obj = {
            "version": "1.0",
            "created": __import__('datetime').datetime.utcnow().isoformat(),
            "template_id": t.get("id"),
            "scenario": t.get("scenario"),
            "nodes": t.get("nodes", []),
            "connections": t.get("connections", []),
        }
        conn.execute(
            """
            INSERT INTO flows (name, user_id, client_id, flow_json, thumbnail, category, description, is_template, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))
            """,
            (
                tpl_name,
                user_id,
                client_id,
                json.dumps(flow_obj),
                _flow_template_thumbnail(t.get("name"), t.get("category")),
                t.get("category", "Uncategorized"),
                t.get("description", ""),
            ),
        )
        inserted += 1

    if inserted:
        conn.commit()


@app.route("/api/flows", methods=["GET"])
def get_flows():
    try:
        uid = get_current_user_id()
        cid = get_current_client_id()

        conn = get_db()
        cursor = conn.cursor()
        _migrate_flows_table(conn)
        _ensure_client_tables(conn)

        if cid is not None and not _client_owned(conn, uid, cid):
            conn.close()
            return jsonify([])

        sql = """
            SELECT id, name, created_at, updated_at, thumbnail, category, description, client_id
            FROM flows
            WHERE user_id = ? AND COALESCE(is_template, 0) = 0
        """
        params = [uid]
        if cid is not None:
            sql += " AND COALESCE(client_id, 0) = ?"
            params.append(cid)
        sql += " ORDER BY updated_at DESC"

        rows = cursor.execute(sql, tuple(params)).fetchall()
        conn.close()

        flows = [
            {
                "id": r[0],
                "name": r[1],
                "created": r[2],
                "updated": r[3],
                "thumbnail": r[4],
                "category": (r[5] or "Uncategorized"),
                "description": (r[6] or ""),
                "client_id": r[7] if len(r) > 7 else None,
            }
            for r in rows
        ]
        return jsonify(flows)
    except Exception as e:
        print(f"Error in get_flows: {e}")
        return jsonify([]), 500


@app.route("/api/flows", methods=["POST"])
def save_flow():
    data = request.get_json(force=True, silent=True) or {}
    if not data or 'flow' not in data:
        return jsonify({"error": "No flow data"}), 400

    uid = get_current_user_id()
    cid = get_current_client_id()

    flow_json = json.dumps(data['flow'])
    name = (data.get('name') or 'Untitled Flow').strip() or 'Untitled Flow'
    thumbnail = data.get('thumbnail')
    category = (data.get('category') or 'Uncategorized').strip() or 'Uncategorized'
    description = (data.get('description') or '').strip()
    is_template = 1 if data.get('is_template') else 0

    conn = get_db()
    cursor = conn.cursor()
    _migrate_flows_table(conn)
    _ensure_client_tables(conn)

    if cid is not None and not _client_owned(conn, uid, cid):
        conn.close()
        return jsonify({"error": "Client not found or not owned"}), 404

    cursor.execute(
        """
        INSERT INTO flows (name, user_id, client_id, flow_json, thumbnail, category, description, is_template, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (name, uid, cid, flow_json, thumbnail, category, description, is_template),
    )

    conn.commit()
    flow_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "success": True,
        "flow_id": flow_id,
        "message": "Flow saved",
        "category": category,
        "description": description,
        "is_template": bool(is_template),
        "client_id": cid,
    })


@app.route("/api/flows/<int:flow_id>", methods=["GET"])
def get_flow(flow_id):
    uid = get_current_user_id()
    cid = get_current_client_id()

    conn = get_db()
    cursor = conn.cursor()
    _migrate_flows_table(conn)
    _ensure_client_tables(conn)

    if cid is not None and not _client_owned(conn, uid, cid):
        conn.close()
        return jsonify({"error": "Flow not found"}), 404

    sql = """
        SELECT name, flow_json, created_at, updated_at, category, description, COALESCE(is_template, 0), client_id
        FROM flows
        WHERE id = ? AND user_id = ?
    """
    params = [flow_id, uid]
    if cid is not None:
        sql += " AND COALESCE(client_id, 0) = ?"
        params.append(cid)

    row = cursor.execute(sql, tuple(params)).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Flow not found"}), 404

    flow_data = json.loads(row[1]) if row[1] else {}

    return jsonify({
        "id": flow_id,
        "name": row[0],
        "created": row[2],
        "updated": row[3],
        "category": row[4] or "Uncategorized",
        "description": row[5] or "",
        "is_template": bool(row[6]),
        "client_id": row[7] if len(row) > 7 else None,
        "flow": flow_data,
    })


@app.route("/api/flows/<int:flow_id>", methods=["DELETE"])
def delete_flow(flow_id):
    uid = get_current_user_id()
    cid = get_current_client_id()

    conn = get_db()
    cursor = conn.cursor()
    _migrate_flows_table(conn)
    _ensure_client_tables(conn)

    if cid is not None and not _client_owned(conn, uid, cid):
        conn.close()
        return jsonify({"error": "Flow not found or not owned"}), 404

    sql = "DELETE FROM flows WHERE id = ? AND user_id = ?"
    params = [flow_id, uid]
    if cid is not None:
        sql += " AND COALESCE(client_id, 0) = ?"
        params.append(cid)

    cursor.execute(sql, tuple(params))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()

    if deleted:
        return jsonify({"success": True, "message": f"Flow {flow_id} deleted"})
    return jsonify({"error": "Flow not found or not owned"}), 404


@app.route("/api/flows/<int:flow_id>", methods=["PUT"])
def update_flow_name(flow_id):
    data = request.get_json(force=True, silent=True) or {}
    if not data or 'name' not in data:
        return jsonify({"error": "No name provided"}), 400

    new_name = data['name'].strip()
    if not new_name:
        return jsonify({"error": "Name cannot be empty"}), 400

    uid = get_current_user_id()
    cid = get_current_client_id()

    conn = get_db()
    cursor = conn.cursor()
    _migrate_flows_table(conn)
    _ensure_client_tables(conn)

    if cid is not None and not _client_owned(conn, uid, cid):
        conn.close()
        return jsonify({"error": "Flow not found or not owned"}), 404

    sql = "UPDATE flows SET name = ?, updated_at = datetime('now') WHERE id = ? AND user_id = ?"
    params = [new_name, flow_id, uid]
    if cid is not None:
        sql += " AND COALESCE(client_id, 0) = ?"
        params.append(cid)

    cursor.execute(sql, tuple(params))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()

    if updated:
        return jsonify({"success": True, "message": f"Flow renamed to '{new_name}'"})
    return jsonify({"error": "Flow not found or not owned"}), 404


@app.route("/api/flows/<int:flow_id>/duplicate", methods=["POST"])
def duplicate_flow(flow_id):
    uid = get_current_user_id()
    cid = get_current_client_id()

    conn = get_db()
    cursor = conn.cursor()
    _migrate_flows_table(conn)
    _ensure_client_tables(conn)

    if cid is not None and not _client_owned(conn, uid, cid):
        conn.close()
        return jsonify({"error": "Flow not found"}), 404

    sql = """
        SELECT name, flow_json, thumbnail, category, description, COALESCE(is_template, 0), client_id
        FROM flows
        WHERE id = ? AND user_id = ?
    """
    params = [flow_id, uid]
    if cid is not None:
        sql += " AND COALESCE(client_id, 0) = ?"
        params.append(cid)

    row = cursor.execute(sql, tuple(params)).fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Flow not found"}), 404

    original_name = row[0]
    flow_json = row[1]
    thumbnail = row[2]
    category = row[3] or "Uncategorized"
    description = row[4] or ""
    original_is_template = row[5]
    original_client_id = row[6] if len(row) > 6 else None

    data = request.get_json(force=True, silent=True) or {}
    new_name = (data.get('name') or '').strip()
    if not new_name:
        new_name = f"{original_name} (Copy)"

    is_template = original_is_template
    if 'is_template' in data:
        is_template = 1 if data.get('is_template') else 0

    cursor.execute(
        """
        INSERT INTO flows (name, user_id, client_id, flow_json, thumbnail, category, description, is_template, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (new_name, uid, original_client_id, flow_json, thumbnail, category, description, is_template),
    )

    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "new_flow_id": new_id,
        "new_name": new_name,
        "message": f"Flow duplicated as '{new_name}'",
        "is_template": bool(is_template),
        "client_id": original_client_id,
    })


@app.route("/api/flows/templates", methods=["GET"])
def get_flow_templates():
    """Return persistent flow templates (auto-seeded in DB if missing)."""
    uid = get_current_user_id()
    cid = get_current_client_id()
    category_filter = request.args.get("category", "").strip().lower()
    if category_filter in ("all", "*"):
        category_filter = ""

    conn = get_db()
    cursor = conn.cursor()
    _migrate_flows_table(conn)
    _ensure_client_tables(conn)

    if cid is not None and not _client_owned(conn, uid, cid):
        conn.close()
        return jsonify([])

    _seed_flow_templates_if_missing(conn, uid, cid)

    sql = """
        SELECT id, name, category, description, thumbnail, flow_json, updated_at, client_id
        FROM flows
        WHERE user_id = ? AND COALESCE(is_template, 0) = 1
    """
    params = [uid]
    if cid is not None:
        sql += " AND COALESCE(client_id, 0) = ?"
        params.append(cid)
    sql += " ORDER BY updated_at DESC"

    rows = cursor.execute(sql, tuple(params)).fetchall()
    conn.close()

    templates = []
    for r in rows:
        try:
            flow_data = json.loads(r[5]) if r[5] else {}
        except Exception:
            flow_data = {}
        if not isinstance(flow_data, dict):
            flow_data = {}

        tpl = {
            "id": r[0],
            "name": r[1],
            "category": r[2] or "Uncategorized",
            "description": r[3] or "",
            "thumbnail": r[4] or _flow_template_thumbnail(r[1], r[2]),
            "updated": r[6],
            "flow": flow_data,
            "nodes": flow_data.get("nodes", []),
            "connections": flow_data.get("connections", []),
            "client_id": (r[7] if len(r) > 7 else None),
        }
        if category_filter and tpl["category"].lower() != category_filter:
            continue
        templates.append(tpl)

    return jsonify(templates)


@app.route("/connectors")
def connectors():
    if AUTH_REQUIRED and not is_user_authenticated():
        return _auth_redirect(next_path="/connectors")
    uid = get_current_user_id()
    if uid > 0 and _must_complete_onboarding(uid):
        return redirect(url_for("onboarding_page"))
    return render_template("connectors.html")

@app.route("/agents")
def agents():
    if AUTH_REQUIRED and not is_user_authenticated():
        return _auth_redirect(next_path="/agents")
    uid = get_current_user_id()
    if uid > 0 and _must_complete_onboarding(uid):
        return redirect(url_for("onboarding_page"))
    if FORCE_VERTEX_ALL_AGENTS and uid > 0:
        _ensure_vertex_defaults_for_user(uid)

    settings = _get_user_settings(uid)
    client_id = get_current_client_id()
    payload = _build_chat_home_payload(uid, client_id, settings)
    if payload.get("forbidden_client"):
        return "Client not found", 404

    ws_filter = str(request.args.get("workspace") or request.args.get("ws") or "all").strip().lower()
    if ws_filter not in (set(VALID_WORKSPACES) | {"all", "other"}):
        ws_filter = "all"
    q = str(request.args.get("q") or "").strip()
    return render_template(
        "agents.html",
        agents_home=payload,
        ws_filter=ws_filter,
        q=q,
    )

@app.route("/agent/<slug>")
def agent_detail(slug):
    if AUTH_REQUIRED and not is_user_authenticated():
        return _auth_redirect(next_path=f"/agent/{slug}")
    uid = get_current_user_id()
    if uid > 0 and _must_complete_onboarding(uid):
        return redirect(url_for("onboarding_page"))
    return render_template("agent_detail.html", slug=slug, agent_title=_default_agent_custom_name(slug))

@app.route("/orchestrator")
def orchestrator():
    if AUTH_REQUIRED and not is_user_authenticated():
        return _auth_redirect(next_path="/orchestrator")
    uid = get_current_user_id()
    if uid > 0 and _must_complete_onboarding(uid):
        return redirect(url_for("onboarding_page"))
    return render_template("orchestrator.html")

# ─── Orchestrator Engine API ──────────────────────────────────────────────────

CONNECTOR_OVERVIEW_ENDPOINTS = {
    "google-ads": "/api/connectors/google-ads/overview",
    "ga4": "/api/connectors/ga4/overview",
    "google-search-console": "/api/connectors/google-search-console/overview",
    "google-tag-manager": "/api/connectors/google-tag-manager/overview",
    "meta-ads": "/api/connectors/meta-ads/overview",
    "tiktok-ads": "/api/connectors/tiktok-ads/overview",
    "linkedin-ads": "/api/connectors/linkedin-ads/overview",
    "stripe": "/api/connectors/stripe/overview",
    "shopify": "/api/connectors/shopify/overview",
    "hubspot": "/api/connectors/hubspot/overview",
    "salesforce": "/api/connectors/salesforce/overview",
    "quickbooks": "/api/connectors/quickbooks/overview",
    "mailchimp": "/api/connectors/mailchimp/overview",
    "paypal": "/api/connectors/paypal/overview",
    "notion": "/api/connectors/notion/overview",
    "github": "/api/connectors/github/overview",
    "todoist": "/api/connectors/todoist/overview",
    "telegram": "/api/connectors/telegram/overview",
    "aws": "/api/connectors/aws/overview",
    "vercel": "/api/connectors/vercel/overview",
}

# Reverse map: connector display name → slug for the 20 live connectors
CONNECTOR_NAME_TO_SLUG = {
    "Google Ads": "google-ads", "Google Analytics 4": "ga4",
    "Google Search Console": "google-search-console", "Google Tag Manager": "google-tag-manager",
    "Meta Ads": "meta-ads", "TikTok Ads": "tiktok-ads", "LinkedIn Ads": "linkedin-ads",
    "Stripe": "stripe", "Shopify": "shopify", "HubSpot": "hubspot",
    "Salesforce": "salesforce", "QuickBooks": "quickbooks", "Mailchimp": "mailchimp",
    "PayPal": "paypal", "Notion": "notion", "GitHub": "github",
    "Todoist": "todoist", "Telegram": "telegram", "AWS": "aws", "Vercel": "vercel",
}

# All 20 agents with metadata for routing
ORCHESTRATOR_AGENTS = {}
for _ws_slug, _ws_data in workspaces.items():
    for _a_slug, _a_name in _ws_data.get("agents", {}).items():
        ORCHESTRATOR_AGENTS[_a_slug] = {
            "slug": _a_slug, "name": _a_name, "workspace": _ws_slug,
            "connectors": AGENT_CONNECTOR_MAP.get(_a_slug, []),
        }

# Routing keywords (lowercase) for smart task→agent matching
ROUTING_KEYWORDS_FLAT = {
    "ppc-specialist": ["ads", "ppc", "campaign", "google ads", "cpc", "bid", "keyword", "adgroup", "ad copy", "roas", "impression", "click"],
    "seo-content": ["seo", "organic", "keyword", "ranking", "content", "blog", "backlink", "serp", "indexing", "sitemap"],
    "creative-director": ["design", "creative", "visual", "banner", "video", "brand identity", "ad creative", "thumbnail"],
    "social-media": ["social", "instagram", "facebook", "tiktok", "post", "engagement", "follower", "story", "reel", "community"],
    "performance-analytics": ["analytics", "kpi", "data", "traffic", "conversion", "funnel", "ga4", "dashboard", "report", "metric"],
    "ceo-strategy": ["strategy", "vision", "scaling", "growth", "roadmap", "okr", "board", "investor", "market", "competitive"],
    "cto-innovation": ["tech", "innovation", "stack", "architecture", "cloud", "ai", "ml", "infrastructure", "scalability"],
    "cmo-growth": ["marketing", "brand", "growth", "campaign", "acquisition", "retention", "ltv", "cac", "channel"],
    "cfo-finance": ["budget", "finance", "investment", "revenue", "profit", "cash flow", "forecast", "expense", "margin", "p&l"],
    "coo-operations": ["operations", "efficiency", "process", "team", "execution", "workflow", "supply chain", "kpi", "project"],
    "devops-infra": ["deploy", "ci/cd", "infrastructure", "docker", "kubernetes", "aws", "server", "monitoring", "pipeline"],
    "fullstack-dev": ["code", "bug", "debug", "react", "node", "api", "database", "frontend", "backend", "feature"],
    "backend-architect": ["backend", "database", "api", "microservice", "schema", "rest", "graphql", "cache", "queue"],
    "frontend-uiux": ["frontend", "ui", "ux", "css", "responsive", "component", "figma", "prototype", "accessibility"],
    "security-quality": ["security", "vulnerability", "testing", "penetration", "audit", "compliance", "encryption", "owasp"],
    "life-coach": ["goal", "habit", "motivation", "balance", "purpose", "mindset", "personal growth"],
    "psychologist": ["anxiety", "depression", "therapy", "stress", "coping", "mental health", "emotion"],
    "personal-mentor": ["learn", "skill", "education", "career", "mentorship", "self-improvement"],
    "fitness-wellness": ["exercise", "nutrition", "health", "workout", "diet", "sleep", "wellness"],
    "creative-muse": ["art", "writing", "inspiration", "creativity", "poetry", "music", "brainstorm"],
}

ORCHESTRATOR_TEMPLATES = [
    {
        "id": "tpl-growth-war-room-live", "name": "Growth War Room (Live Ads + GA4)",
        "description": "Real Google Ads + GA4 signals → PPC + SEO + Personal Assistant alignment → executive next-action brief.",
        "category": "Growth", "icon": "bi-lightning-charge",
        "nodes": [
            {"id": "node-1", "type": "trigger", "x": 60, "y": 170, "label": "Manual Trigger (Now)"},
            {"id": "node-2", "type": "connector", "x": 290, "y": 90, "slug": "google-ads", "label": "Google Ads (Live)", "config": {"days": 30}},
            {"id": "node-3", "type": "connector", "x": 290, "y": 250, "slug": "ga4", "label": "GA4 (Live)", "config": {"range": "30days"}},
            {"id": "node-4", "type": "agent", "x": 540, "y": 90, "slug": "ppc-specialist", "label": "PPC Specialist"},
            {"id": "node-5", "type": "agent", "x": 540, "y": 250, "slug": "seo-content", "label": "SEO Strategist"},
            {"id": "node-6", "type": "condition", "x": 790, "y": 170, "label": "ROAS >= 3.0?", "config": {"condition_metric": "roas", "condition_operator": ">=", "condition_value": 3, "condition_then_label": "Healthy", "condition_else_label": "Needs Action"}},
            {"id": "node-7", "type": "agent", "x": 1010, "y": 170, "slug": "life-coach", "label": "Personal Assistant"},
            {"id": "node-8", "type": "output", "x": 1240, "y": 170, "label": "Executive Brief", "config": {"output_destination": "chat", "output_template": "Growth War Room Summary: {{last_agent_response}}"}},
        ],
        "connections": [
            {"from": "node-1", "to": "node-2"}, {"from": "node-1", "to": "node-3"},
            {"from": "node-2", "to": "node-4"}, {"from": "node-3", "to": "node-5"},
            {"from": "node-4", "to": "node-6"}, {"from": "node-5", "to": "node-6"},
            {"from": "node-6", "to": "node-7"}, {"from": "node-7", "to": "node-8"},
        ],
    },
    {
        "id": "tpl-marketing-report", "name": "Marketing Performance Report",
        "description": "Pull ad performance from all paid channels → PPC Specialist analyzes → unified report output",
        "category": "Marketing", "icon": "bi-graph-up",
        "nodes": [
            {"id": "node-1", "type": "trigger", "x": 60, "y": 140, "label": "Daily 9 AM Schedule"},
            {"id": "node-2", "type": "agent", "x": 300, "y": 140, "slug": "ppc-specialist", "label": "PPC Specialist"},
            {"id": "node-3", "type": "connector", "x": 560, "y": 40, "slug": "google-ads", "label": "Google Ads"},
            {"id": "node-4", "type": "connector", "x": 560, "y": 140, "slug": "meta-ads", "label": "Meta Ads"},
            {"id": "node-5", "type": "connector", "x": 560, "y": 240, "slug": "linkedin-ads", "label": "LinkedIn Ads"},
            {"id": "node-6", "type": "output", "x": 800, "y": 140, "label": "Email Report"},
        ],
        "connections": [
            {"from": "node-1", "to": "node-2"}, {"from": "node-2", "to": "node-3"},
            {"from": "node-2", "to": "node-4"}, {"from": "node-2", "to": "node-5"},
            {"from": "node-3", "to": "node-6"}, {"from": "node-4", "to": "node-6"},
            {"from": "node-5", "to": "node-6"},
        ],
    },
    {
        "id": "tpl-revenue-dashboard", "name": "Revenue Dashboard Pipeline",
        "description": "Aggregate revenue from Stripe + PayPal + Shopify → CFO analyzes margins → dashboard output",
        "category": "Finance", "icon": "bi-currency-dollar",
        "nodes": [
            {"id": "node-1", "type": "trigger", "x": 60, "y": 140, "label": "Hourly Webhook"},
            {"id": "node-2", "type": "connector", "x": 280, "y": 40, "slug": "stripe", "label": "Stripe"},
            {"id": "node-3", "type": "connector", "x": 280, "y": 140, "slug": "paypal", "label": "PayPal"},
            {"id": "node-4", "type": "connector", "x": 280, "y": 240, "slug": "shopify", "label": "Shopify"},
            {"id": "node-5", "type": "agent", "x": 520, "y": 140, "slug": "cfo-finance", "label": "CFO / Finance"},
            {"id": "node-6", "type": "output", "x": 760, "y": 140, "label": "Dashboard Widget"},
        ],
        "connections": [
            {"from": "node-1", "to": "node-2"}, {"from": "node-1", "to": "node-3"},
            {"from": "node-1", "to": "node-4"}, {"from": "node-2", "to": "node-5"},
            {"from": "node-3", "to": "node-5"}, {"from": "node-4", "to": "node-5"},
            {"from": "node-5", "to": "node-6"},
        ],
    },
    {
        "id": "tpl-devops-health", "name": "DevOps Health Check",
        "description": "Monitor GitHub repos + AWS infra + Vercel deployments → DevOps engineer triages → Slack alert",
        "category": "Engineering", "icon": "bi-gear",
        "nodes": [
            {"id": "node-1", "type": "trigger", "x": 60, "y": 140, "label": "Every 15 min Cron"},
            {"id": "node-2", "type": "connector", "x": 280, "y": 40, "slug": "github", "label": "GitHub"},
            {"id": "node-3", "type": "connector", "x": 280, "y": 140, "slug": "aws", "label": "AWS"},
            {"id": "node-4", "type": "connector", "x": 280, "y": 240, "slug": "vercel", "label": "Vercel"},
            {"id": "node-5", "type": "agent", "x": 520, "y": 140, "slug": "devops-infra", "label": "DevOps Engineer"},
            {"id": "node-6", "type": "condition", "x": 720, "y": 140, "label": "Has Critical Issue?"},
            {"id": "node-7", "type": "output", "x": 920, "y": 80, "label": "Slack Alert"},
            {"id": "node-8", "type": "output", "x": 920, "y": 200, "label": "Log & Skip"},
        ],
        "connections": [
            {"from": "node-1", "to": "node-2"}, {"from": "node-1", "to": "node-3"},
            {"from": "node-1", "to": "node-4"}, {"from": "node-2", "to": "node-5"},
            {"from": "node-3", "to": "node-5"}, {"from": "node-4", "to": "node-5"},
            {"from": "node-5", "to": "node-6"}, {"from": "node-6", "to": "node-7"},
            {"from": "node-6", "to": "node-8"},
        ],
    },
    {
        "id": "tpl-seo-audit", "name": "SEO Audit Pipeline",
        "description": "Pull search data from GSC + GA4 → SEO expert analyzes → audit report",
        "category": "Marketing", "icon": "bi-search",
        "nodes": [
            {"id": "node-1", "type": "trigger", "x": 60, "y": 120, "label": "Weekly Monday 8 AM"},
            {"id": "node-2", "type": "connector", "x": 280, "y": 60, "slug": "google-search-console", "label": "Search Console"},
            {"id": "node-3", "type": "connector", "x": 280, "y": 180, "slug": "ga4", "label": "GA4"},
            {"id": "node-4", "type": "agent", "x": 520, "y": 120, "slug": "seo-content", "label": "SEO Strategist"},
            {"id": "node-5", "type": "output", "x": 760, "y": 120, "label": "SEO Audit PDF"},
        ],
        "connections": [
            {"from": "node-1", "to": "node-2"}, {"from": "node-1", "to": "node-3"},
            {"from": "node-2", "to": "node-4"}, {"from": "node-3", "to": "node-4"},
            {"from": "node-4", "to": "node-5"},
        ],
    },
    {
        "id": "tpl-crm-sync", "name": "CRM Sync & Enrichment",
        "description": "Sync HubSpot + Salesforce contacts → COO validates → Notion task list",
        "category": "Operations", "icon": "bi-people",
        "nodes": [
            {"id": "node-1", "type": "trigger", "x": 60, "y": 120, "label": "New Contact Webhook"},
            {"id": "node-2", "type": "connector", "x": 280, "y": 60, "slug": "hubspot", "label": "HubSpot"},
            {"id": "node-3", "type": "connector", "x": 280, "y": 180, "slug": "salesforce", "label": "Salesforce"},
            {"id": "node-4", "type": "agent", "x": 520, "y": 120, "slug": "coo-operations", "label": "COO / Operations"},
            {"id": "node-5", "type": "connector", "x": 720, "y": 120, "slug": "notion", "label": "Notion"},
            {"id": "node-6", "type": "output", "x": 920, "y": 120, "label": "Synced & Tagged"},
        ],
        "connections": [
            {"from": "node-1", "to": "node-2"}, {"from": "node-1", "to": "node-3"},
            {"from": "node-2", "to": "node-4"}, {"from": "node-3", "to": "node-4"},
            {"from": "node-4", "to": "node-5"}, {"from": "node-5", "to": "node-6"},
        ],
    },
    {
        "id": "tpl-social-review", "name": "Social Campaign Review",
        "description": "Pull social ad data from Meta + TikTok + Telegram → Social manager reviews → Todoist tasks",
        "category": "Marketing", "icon": "bi-share",
        "nodes": [
            {"id": "node-1", "type": "trigger", "x": 60, "y": 140, "label": "Friday 5 PM Schedule"},
            {"id": "node-2", "type": "connector", "x": 280, "y": 40, "slug": "meta-ads", "label": "Meta Ads"},
            {"id": "node-3", "type": "connector", "x": 280, "y": 140, "slug": "tiktok-ads", "label": "TikTok Ads"},
            {"id": "node-4", "type": "connector", "x": 280, "y": 240, "slug": "telegram", "label": "Telegram"},
            {"id": "node-5", "type": "agent", "x": 520, "y": 140, "slug": "social-media", "label": "Social Manager"},
            {"id": "node-6", "type": "connector", "x": 720, "y": 140, "slug": "todoist", "label": "Todoist"},
            {"id": "node-7", "type": "output", "x": 920, "y": 140, "label": "Weekly Summary"},
        ],
        "connections": [
            {"from": "node-1", "to": "node-2"}, {"from": "node-1", "to": "node-3"},
            {"from": "node-1", "to": "node-4"}, {"from": "node-2", "to": "node-5"},
            {"from": "node-3", "to": "node-5"}, {"from": "node-4", "to": "node-5"},
            {"from": "node-5", "to": "node-6"}, {"from": "node-6", "to": "node-7"},
        ],
    },
    {
        "id": "tpl-budget-reallocate", "name": "Budget Reallocate Alert",
        "description": "Monitor ad spend pacing → CFO validates risk threshold → reallocate budget plan",
        "category": "Finance", "icon": "bi-pie-chart",
        "nodes": [
            {"id": "node-1", "type": "trigger", "x": 60, "y": 120, "label": "Daily Budget Check"},
            {"id": "node-2", "type": "connector", "x": 280, "y": 120, "slug": "google-ads", "label": "Google Ads"},
            {"id": "node-3", "type": "condition", "x": 500, "y": 120, "label": "Spend > 80%?"},
            {"id": "node-4", "type": "agent", "x": 700, "y": 120, "slug": "cfo-finance", "label": "CFO / Finance"},
            {"id": "node-5", "type": "output", "x": 920, "y": 70, "label": "Reallocate Plan"},
            {"id": "node-6", "type": "output", "x": 920, "y": 180, "label": "No Action"},
        ],
        "connections": [
            {"from": "node-1", "to": "node-2"}, {"from": "node-2", "to": "node-3"},
            {"from": "node-3", "to": "node-4"}, {"from": "node-4", "to": "node-5"},
            {"from": "node-3", "to": "node-6"},
        ],
    },
    {
        "id": "tpl-creative-approval", "name": "Creative Approval Flow",
        "description": "Generate ad creative brief → creative director reviews → approve/reject output",
        "category": "Creative", "icon": "bi-brush",
        "nodes": [
            {"id": "node-1", "type": "trigger", "x": 60, "y": 120, "label": "Asset Ready Event"},
            {"id": "node-2", "type": "agent", "x": 280, "y": 120, "slug": "creative-director", "label": "Creative Director"},
            {"id": "node-3", "type": "condition", "x": 500, "y": 120, "label": "Approved?"},
            {"id": "node-4", "type": "connector", "x": 720, "y": 70, "slug": "meta-ads", "label": "Meta Ads"},
            {"id": "node-5", "type": "output", "x": 940, "y": 70, "label": "Publish Asset"},
            {"id": "node-6", "type": "output", "x": 940, "y": 180, "label": "Revision Request"},
        ],
        "connections": [
            {"from": "node-1", "to": "node-2"}, {"from": "node-2", "to": "node-3"},
            {"from": "node-3", "to": "node-4"}, {"from": "node-4", "to": "node-5"},
            {"from": "node-3", "to": "node-6"},
        ],
    },
    {
        "id": "tpl-lead-gen-launch", "name": "Lead Gen Campaign Launch",
        "description": "Plan lead-gen strategy → create campaigns in Google Ads + HubSpot tracking",
        "category": "Sales", "icon": "bi-bullseye",
        "nodes": [
            {"id": "node-1", "type": "trigger", "x": 60, "y": 120, "label": "Manual Launch"},
            {"id": "node-2", "type": "agent", "x": 280, "y": 120, "slug": "cmo-growth", "label": "Marketing Specialist"},
            {"id": "node-3", "type": "connector", "x": 520, "y": 70, "slug": "google-ads", "label": "Google Ads"},
            {"id": "node-4", "type": "connector", "x": 520, "y": 180, "slug": "hubspot", "label": "HubSpot"},
            {"id": "node-5", "type": "output", "x": 760, "y": 120, "label": "Launch Confirmation"},
        ],
        "connections": [
            {"from": "node-1", "to": "node-2"}, {"from": "node-2", "to": "node-3"},
            {"from": "node-2", "to": "node-4"}, {"from": "node-3", "to": "node-5"},
            {"from": "node-4", "to": "node-5"},
        ],
    },
    {
        "id": "tpl-personal-goal-tracker", "name": "Personal Goal Tracker",
        "description": "Daily habit check from Todoist + mentor coaching response for accountability",
        "category": "Personal", "icon": "bi-heart-pulse",
        "nodes": [
            {"id": "node-1", "type": "trigger", "x": 60, "y": 120, "label": "Daily Morning Check"},
            {"id": "node-2", "type": "connector", "x": 280, "y": 120, "slug": "todoist", "label": "Todoist"},
            {"id": "node-3", "type": "agent", "x": 520, "y": 120, "slug": "personal-mentor", "label": "Personal Mentor"},
            {"id": "node-4", "type": "output", "x": 760, "y": 120, "label": "Motivational Brief"},
        ],
        "connections": [
            {"from": "node-1", "to": "node-2"}, {"from": "node-2", "to": "node-3"},
            {"from": "node-3", "to": "node-4"},
        ],
    },
]

@app.route("/api/orchestrator/templates", methods=["GET"])
def orchestrator_templates():
    """Alias to the primary DB-backed templates endpoint."""
    return get_flow_templates()


def _extract_json_object(raw_text):
    txt = str(raw_text or "").strip()
    if not txt:
        return None

    # Direct parse first.
    try:
        obj = json.loads(txt)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # Fenced block parse.
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", txt, flags=re.IGNORECASE)
    if m:
        blob = m.group(1)
        try:
            obj = json.loads(blob)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    # Best-effort first object.
    i = txt.find("{")
    j = txt.rfind("}")
    if i >= 0 and j > i:
        blob = txt[i:j + 1]
        try:
            obj = json.loads(blob)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    return None


def _compose_flow_heuristic(prompt):
    p = str(prompt or "").strip().lower()
    wants_ga4 = any(k in p for k in ("ga4", "analytics", "sessions", "traffic", "users", "events"))
    wants_ads = any(k in p for k in ("ads", "google ads", "roas", "cpc", "ppc", "campaign"))
    wants_seo = any(k in p for k in ("seo", "content", "organic", "ranking", "search console"))
    wants_cfo = any(k in p for k in ("cfo", "finance", "budget", "cost"))
    wants_alert = any(k in p for k in ("alert", "warn", "notify", "slack", "email"))

    condition_val = 3.0
    m = re.search(r"(?:roas[^0-9]*|sub)\s*([0-9]+(?:\.[0-9]+)?)", p)
    if m:
        try:
            condition_val = float(m.group(1))
        except Exception:
            condition_val = 3.0

    nodes = [
        {"id": "node-1", "type": "trigger", "x": 60, "y": 170, "label": "Trigger", "config": {"trigger_type": "manual", "trigger_description": "Composed from prompt"}},
    ]
    conns = []

    next_x = 300
    connector_ids = []
    if wants_ads or (not wants_ga4):
        connector_ids.append("node-2")
        nodes.append({"id": "node-2", "type": "connector", "x": next_x, "y": 100, "slug": "google-ads", "label": "Google Ads"})
    if wants_ga4:
        connector_ids.append("node-3")
        nodes.append({"id": "node-3", "type": "connector", "x": next_x, "y": 250, "slug": "ga4", "label": "GA4"})

    for cid in connector_ids:
        conns.append({"from": "node-1", "to": cid})

    nodes.append({"id": "node-4", "type": "agent", "x": 560, "y": 110, "slug": "ppc-specialist", "label": "PPC Specialist"})
    conns.append({"from": connector_ids[0] if connector_ids else "node-1", "to": "node-4"})

    if wants_seo or wants_ga4:
        nodes.append({"id": "node-5", "type": "agent", "x": 560, "y": 250, "slug": "seo-content", "label": "SEO Strategist"})
        if len(connector_ids) > 1:
            conns.append({"from": connector_ids[1], "to": "node-5"})
        else:
            conns.append({"from": connector_ids[0] if connector_ids else "node-1", "to": "node-5"})
        cond_input = "node-4"
    else:
        cond_input = "node-4"

    nodes.append({
        "id": "node-6", "type": "condition", "x": 790, "y": 170, "label": "ROAS Check",
        "config": {
            "condition_metric": "roas",
            "condition_operator": ">=",
            "condition_value": condition_val,
            "condition_then_label": "Healthy",
            "condition_else_label": "Needs Action",
        }
    })
    conns.append({"from": cond_input, "to": "node-6"})

    reviewer_slug = "cfo-finance" if wants_cfo else "life-coach"
    reviewer_label = "CFO / Finance" if wants_cfo else "Personal Assistant"
    nodes.append({"id": "node-7", "type": "agent", "x": 1010, "y": 170, "slug": reviewer_slug, "label": reviewer_label})
    conns.append({"from": "node-6", "to": "node-7"})

    output_label = "Alert Output" if wants_alert else "Executive Brief"
    output_tmpl = "Alert: {{last_agent_response}}" if wants_alert else "Flow Summary: {{last_agent_response}}"
    nodes.append({
        "id": "node-8", "type": "output", "x": 1240, "y": 170, "label": output_label,
        "config": {"output_destination": "chat", "output_template": output_tmpl}
    })
    conns.append({"from": "node-7", "to": "node-8"})

    return {"nodes": nodes, "connections": conns}


def _normalize_composed_flow(flow_obj):
    if not isinstance(flow_obj, dict):
        return None, "flow_not_object"

    nodes = flow_obj.get("nodes")
    connections = flow_obj.get("connections")
    if not isinstance(nodes, list) or not isinstance(connections, list) or not nodes:
        return None, "missing_nodes_or_connections"

    valid_types = {"trigger", "agent", "connector", "condition", "output"}
    valid_agents = set(ORCHESTRATOR_AGENTS.keys())
    valid_connectors = set(CONNECTOR_OVERVIEW_ENDPOINTS.keys())

    out_nodes = []
    node_ids = set()
    for idx, n in enumerate(nodes, start=1):
        if not isinstance(n, dict):
            continue
        ntype = str(n.get("type") or "").strip().lower()
        if ntype not in valid_types:
            continue
        nid = str(n.get("id") or f"node-{idx}").strip()
        if not nid:
            nid = f"node-{idx}"
        if nid in node_ids:
            nid = f"{nid}-{idx}"
        node_ids.add(nid)

        slug = str(n.get("slug") or "").strip().lower()
        if ntype == "agent" and slug and slug not in valid_agents:
            slug = ""
        if ntype == "connector" and slug and slug not in valid_connectors:
            slug = ""

        x = n.get("x", 80 + (idx * 120))
        y = n.get("y", 100 + ((idx % 3) * 100))
        try:
            x = float(x)
        except Exception:
            x = float(80 + (idx * 120))
        try:
            y = float(y)
        except Exception:
            y = float(100 + ((idx % 3) * 100))

        cfg = n.get("config")
        if not isinstance(cfg, dict):
            cfg = {}

        item = {
            "id": nid,
            "type": ntype,
            "x": x,
            "y": y,
            "label": str(n.get("label") or _humanize_slug(slug or ntype)).strip(),
        }
        if slug:
            item["slug"] = slug
        if cfg:
            item["config"] = cfg
        out_nodes.append(item)

    if not out_nodes:
        return None, "no_valid_nodes"

    out_ids = {n["id"] for n in out_nodes}
    out_connections = []
    for c in connections:
        if not isinstance(c, dict):
            continue
        a = str(c.get("from") or "").strip()
        b = str(c.get("to") or "").strip()
        if a in out_ids and b in out_ids:
            out_connections.append({"from": a, "to": b})

    if not out_connections and len(out_nodes) > 1:
        for i in range(len(out_nodes) - 1):
            out_connections.append({"from": out_nodes[i]["id"], "to": out_nodes[i + 1]["id"]})

    # Ensure at least one trigger and one output for orchestration usability.
    has_trigger = any(n.get("type") == "trigger" for n in out_nodes)
    has_output = any(n.get("type") == "output" for n in out_nodes)
    if not has_trigger:
        tid = "node-trigger-auto"
        out_nodes.insert(0, {"id": tid, "type": "trigger", "x": 60.0, "y": 170.0, "label": "Trigger"})
        if out_nodes and len(out_nodes) > 1:
            out_connections.insert(0, {"from": tid, "to": out_nodes[1]["id"]})
    if not has_output:
        oid = "node-output-auto"
        last_id = out_nodes[-1]["id"]
        out_nodes.append({"id": oid, "type": "output", "x": 1240.0, "y": 170.0, "label": "Output", "config": {"output_destination": "chat", "output_template": "Result: {{last_agent_response}}"}})
        out_connections.append({"from": last_id, "to": oid})

    return {"nodes": out_nodes, "connections": out_connections}, None


@app.route("/api/orchestrator/compose", methods=["POST"])
def orchestrator_compose():
    payload = request.get_json(force=True, silent=True) or {}
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    uid = get_current_user_id()
    cid = get_current_client_id()

    conn = get_db()
    _migrate_flows_table(conn)
    _ensure_client_tables(conn)
    if cid is not None and not _client_owned(conn, uid, cid):
        conn.close()
        return jsonify({"error": "Client not found or not owned"}), 404
    conn.close()

    agent_slugs = sorted(ORCHESTRATOR_AGENTS.keys())
    connector_slugs = sorted(CONNECTOR_OVERVIEW_ENDPOINTS.keys())
    compose_prompt = (
        "You are Camarad Flow Builder.\n"
        "Return only JSON object with keys: nodes, connections.\n"
        "Allowed node types: trigger, agent, connector, condition, output.\n"
        f"Allowed agent slugs: {', '.join(agent_slugs)}\n"
        f"Allowed connector slugs: {', '.join(connector_slugs)}\n"
        "Each node must include id,type,x,y,label. Optional: slug,config.\n"
        "Connections are objects with from,to.\n\n"
        f"User prompt: {prompt}"
    )

    raw_llm = ""
    llm_obj = None
    source = "llm"
    try:
        raw_llm = get_llm_response(compose_prompt)
        llm_obj = _extract_json_object(raw_llm)
    except Exception as e:
        raw_llm = f"llm_exception: {e}"
        llm_obj = None

    if not isinstance(llm_obj, dict):
        source = "heuristic"
        llm_obj = _compose_flow_heuristic(prompt)

    normalized, err = _normalize_composed_flow(llm_obj)
    if err or not normalized:
        return jsonify({
            "error": err or "compose_failed",
            "raw_response": raw_llm[:4000],
        }), 400

    flow_obj = {
        "version": "1.0",
        "created": __import__('datetime').datetime.utcnow().isoformat(),
        "template_id": "composed-from-prompt",
        "scenario": "prompt-compose",
        "nodes": normalized["nodes"],
        "connections": normalized["connections"],
        "meta": {"prompt": prompt, "source": source},
    }

    flow_name = (payload.get("name") or prompt[:96] or "Composed Flow").strip()
    if len(flow_name) > 120:
        flow_name = flow_name[:120]

    conn = get_db()
    _migrate_flows_table(conn)
    _ensure_client_tables(conn)
    cur = conn.execute(
        """
        INSERT INTO flows (name, user_id, client_id, flow_json, category, description, is_template, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 0, datetime('now'))
        """,
        (
            flow_name,
            uid,
            cid,
            json.dumps(flow_obj),
            "AI Composed",
            f"Auto-generated from prompt: {prompt[:220]}",
        ),
    )
    flow_id = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "flow_id": flow_id,
        "flow_json": flow_obj,
        "source": source,
        "message": "Flow generated successfully",
    })


@app.route("/api/orchestrator/route", methods=["POST"])
def orchestrator_route():
    """Smart routing: given a task description, find the best agent(s) + relevant connectors."""
    data = request.get_json(force=True, silent=True) or {}
    task = data.get("task", "").strip().lower()
    top_k = data.get("top_k", 3)
    if not task:
        return jsonify({"error": "No task provided"}), 400

    scores = []
    for slug, keywords in ROUTING_KEYWORDS_FLAT.items():
        hits = sum(1 for kw in keywords if kw in task)
        if hits > 0:
            confidence = round(min(hits / max(len(keywords) * 0.4, 1), 1.0), 3)
            agent_info = ORCHESTRATOR_AGENTS.get(slug, {})
            live_connectors = []
            for c_name in agent_info.get("connectors", []):
                c_slug = CONNECTOR_NAME_TO_SLUG.get(c_name)
                if c_slug and c_slug in CONNECTOR_OVERVIEW_ENDPOINTS:
                    live_connectors.append({"name": c_name, "slug": c_slug, "status": "live"})
                else:
                    live_connectors.append({"name": c_name, "slug": c_slug, "status": "planned"})
            scores.append({
                "agent_slug": slug,
                "agent_name": agent_info.get("name", slug),
                "workspace": agent_info.get("workspace", "unknown"),
                "confidence": confidence,
                "keyword_hits": hits,
                "connectors": live_connectors,
            })

    scores.sort(key=lambda x: x["confidence"], reverse=True)
    return jsonify({"task": task, "matches": scores[:top_k], "total_candidates": len(scores)})

@app.route("/api/orchestrator/agent-brief/<slug>", methods=["GET"])
def orchestrator_agent_brief(slug):
    """Get a comprehensive brief for an agent, including live connector KPI summaries."""
    agent_info = ORCHESTRATOR_AGENTS.get(slug)
    if not agent_info:
        return jsonify({"error": "Agent not found"}), 404

    connector_summaries = []
    for c_name in agent_info.get("connectors", []):
        c_slug = CONNECTOR_NAME_TO_SLUG.get(c_name)
        endpoint = CONNECTOR_OVERVIEW_ENDPOINTS.get(c_slug) if c_slug else None
        summary = {"name": c_name, "slug": c_slug, "status": "planned", "kpis": {}}
        if endpoint:
            try:
                with app.test_client() as tc:
                    resp = tc.get(endpoint)
                    if resp.status_code == 200:
                        overview_data = resp.get_json()
                        # Extract top-level KPIs (varies by connector)
                        if isinstance(overview_data, dict):
                            for k in list(overview_data.keys())[:8]:
                                v = overview_data[k]
                                if isinstance(v, (int, float, str, bool)):
                                    summary["kpis"][k] = v
                        summary["status"] = "live"
            except Exception:
                summary["status"] = "error"
        connector_summaries.append(summary)

    return jsonify({
        "agent": agent_info,
        "connector_summaries": connector_summaries,
        "total_live": sum(1 for c in connector_summaries if c["status"] == "live"),
        "total_planned": sum(1 for c in connector_summaries if c["status"] == "planned"),
    })

@app.route("/api/orchestrator/execute", methods=["POST"])
def orchestrator_execute():
    """Execute flow in current scope and return detailed timed trace."""
    import time as _time
    import re as _re
    from datetime import datetime, timezone

    payload = request.get_json(force=True, silent=True) or {}
    flow = payload.get("flow") or payload.get("flow_json")
    if not flow or not flow.get("nodes"):
        return jsonify({"error": "No flow data provided"}), 400

    uid = get_current_user_id()
    cid = get_current_client_id()
    flow_name = str(payload.get("name") or "Unnamed Flow").strip() or "Unnamed Flow"

    scope_conn = get_db()
    _ensure_client_tables(scope_conn)
    if cid is not None and not _client_owned(scope_conn, uid, cid):
        scope_conn.close()
        return jsonify({"error": "Client not found or not owned"}), 404

    flow_id = None
    try:
        if payload.get("flow_id") not in (None, "", "null"):
            flow_id = int(payload.get("flow_id"))
    except Exception:
        flow_id = None

    if flow_id is not None:
        if cid is None:
            ok = scope_conn.execute("SELECT id FROM flows WHERE id=? AND user_id=?", (flow_id, uid)).fetchone()
        else:
            ok = scope_conn.execute("SELECT id FROM flows WHERE id=? AND user_id=? AND COALESCE(client_id,0)=?", (flow_id, uid, cid)).fetchone()
        if not ok:
            scope_conn.close()
            return jsonify({"error": "Flow not found in active client scope"}), 404
    scope_conn.close()

    nodes = {n["id"]: n for n in flow.get("nodes", []) if isinstance(n, dict) and n.get("id")}
    adj = {}
    for c in flow.get("connections", []) or []:
        if not isinstance(c, dict):
            continue
        a, b = c.get("from"), c.get("to")
        if a and b:
            adj.setdefault(a, []).append(b)

    def _num(v):
        if isinstance(v, (int, float)):
            return float(v)
        if v is None:
            return None
        m = _re.search(r"-?\d+(?:\.\d+)?", str(v).replace(',', '').replace('$', '').replace('%', '').replace('x', ''))
        return float(m.group(0)) if m else None

    def _eval(actual, op, thr):
        actual = 0.0 if actual is None else actual
        thr = 0.0 if thr is None else thr
        if op == '<': return actual < thr
        if op == '>=': return actual >= thr
        if op == '<=': return actual <= thr
        if op in ('==', '='): return actual == thr
        if op == '!=': return actual != thr
        return actual > thr

    def _iso(dt):
        return dt.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    started_at = _iso(datetime.now(timezone.utc))
    start_perf = _time.perf_counter()

    def _parse_days_from_range(range_val, default_days=30):
        txt = str(range_val or "").strip().lower()
        if not txt:
            return int(default_days)
        if txt in ("7days", "7d"):
            return 7
        if txt in ("14days", "14d"):
            return 14
        if txt in ("30days", "30d"):
            return 30
        if txt in ("60days", "60d"):
            return 60
        if txt in ("90days", "90d"):
            return 90
        m = _re.search(r"(\d+)", txt)
        if m:
            try:
                return max(1, min(365, int(m.group(1))))
            except Exception:
                pass
        return int(default_days)

    def _safe_json_parse(raw, fallback=None):
        if isinstance(raw, dict):
            return raw
        if fallback is None:
            fallback = {}
        try:
            return json.loads(raw) if raw else dict(fallback)
        except Exception:
            return dict(fallback)

    def _load_connector_runtime_cfg(conn, user_id, client_id, connector_slug):
        row = None
        if client_id is not None:
            row = conn.execute(
                """
                SELECT config_json
                FROM connectors_config
                WHERE user_id = ? AND connector_slug = ? AND COALESCE(client_id, 0) = ?
                ORDER BY last_connected DESC
                LIMIT 1
                """,
                (int(user_id), str(connector_slug), int(client_id)),
            ).fetchone()
        if not row:
            row = conn.execute(
                """
                SELECT config_json
                FROM connectors_config
                WHERE user_id = ? AND connector_slug = ? AND COALESCE(client_id, 0) = 0
                ORDER BY last_connected DESC
                LIMIT 1
                """,
                (int(user_id), str(connector_slug)),
            ).fetchone()
        if not row:
            return {}
        return _safe_json_parse(row[0], {})

    def _live_connector_snapshot(connector_slug, node_cfg):
        cfg_node = node_cfg if isinstance(node_cfg, dict) else {}
        runtime_cfg = {}
        conn = None
        try:
            conn = get_db()
            _ensure_client_tables(conn)
            runtime_cfg = _load_connector_runtime_cfg(conn, uid, cid, connector_slug)
        except Exception:
            runtime_cfg = {}
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        merged = dict(runtime_cfg)
        merged.update(cfg_node)

        if connector_slug == "google-ads":
            account_id = str(
                merged.get("account_id")
                or merged.get("customer_id")
                or merged.get("customerId")
                or ""
            ).strip()
            mcc_id = str(merged.get("mcc_id") or "").strip()
            days = int(_parse_days_from_range(merged.get("days") or merged.get("date_range") or "30days", 30))

            params = {"days": days}
            if account_id:
                params["account_id"] = account_id
            if mcc_id:
                params["mcc_id"] = mcc_id

            with app.test_client() as tc:
                resp = tc.get("/api/connectors/google-ads/campaigns", query_string=params)
                if resp.status_code != 200:
                    raise RuntimeError(f"google_ads_http_{resp.status_code}")
                payload = resp.get_json(silent=True) or {}

            summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
            kpis = {
                "roas": float(summary.get("avg_roas") or 0),
                "spend": float(summary.get("total_spent") or 0),
                "clicks": int(summary.get("total_clicks") or 0),
                "conversions": int(summary.get("total_conversions") or 0),
                "impressions": int(summary.get("total_impressions") or 0),
                "campaigns": int(summary.get("total_campaigns") or 0),
            }
            src = str(payload.get("source") or "unknown")
            out_txt = f"ROAS {kpis['roas']:.2f} | Spend {kpis['spend']:.2f} | Clicks {kpis['clicks']} | Conv {kpis['conversions']} ({src})"
            return {
                "connector": "google-ads",
                "source": src,
                "metric_values": kpis,
                "kpis": kpis,
                "account_id": account_id,
                "days": days,
                "out": out_txt,
            }

        if connector_slug == "ga4":
            prop = str(
                merged.get("property_id")
                or merged.get("propertyId")
                or merged.get("selected_property")
                or ""
            ).strip()
            range_v = str(merged.get("range") or merged.get("date_range") or "30days").strip()
            params = {"range": range_v}
            if prop:
                params["property_id"] = prop

            with app.test_client() as tc:
                resp = tc.get("/api/connectors/ga4/overview", query_string=params)
                if resp.status_code != 200:
                    raise RuntimeError(f"ga4_http_{resp.status_code}")
                payload = resp.get_json(silent=True) or {}

            kpis = {
                "sessions": int(payload.get("sessions") or 0),
                "users": int(payload.get("users") or payload.get("active_users") or 0),
                "conversions": int(payload.get("conversions") or 0),
                "revenue": float(payload.get("revenue") or 0),
                "sessions_per_user": float(payload.get("sessions_per_user") or 0),
            }
            src = str(payload.get("source") or "unknown")
            out_txt = f"Sessions {kpis['sessions']} | Users {kpis['users']} | Conv {kpis['conversions']} | Revenue {kpis['revenue']:.2f} ({src})"
            return {
                "connector": "ga4",
                "source": src,
                "metric_values": kpis,
                "kpis": kpis,
                "property_id": prop,
                "range": range_v,
                "out": out_txt,
            }

        return None

    queue = [nid for nid, n in nodes.items() if n.get("type") == "trigger"] or ([next(iter(nodes.keys()))] if nodes else [])
    visited = set()
    results = []
    steps = []
    step_no = 0
    prev_output = "Flow started"
    prev_label = "Start"

    while queue:
        nid = queue.pop(0)
        if nid in visited:
            continue
        visited.add(nid)
        node = nodes.get(nid)
        if not node:
            continue

        step_no += 1
        s0 = _time.perf_counter()
        ntype = node.get("type", "unknown")
        label = node.get("label", ntype)
        slug = node.get("slug", "")
        cfg = node.get("config") if isinstance(node.get("config"), dict) else {}

        status = "success"
        fail_reason = ""
        inp = prev_output if step_no > 1 else "Flow started"
        out = "Step completed"
        data = {}

        if ntype == "trigger":
            msg = f"Trigger '{cfg.get('trigger_description') or label}' fired"
            data = {"triggered": True, "trigger_type": str(cfg.get("trigger_type") or "manual"), "message": msg}
            inp = "Execution request received"
            out = msg
        elif ntype == "connector":
            cslug = slug or CONNECTOR_NAME_TO_SLUG.get(label)
            live = None
            if cslug in ("google-ads", "ga4"):
                try:
                    live = _live_connector_snapshot(cslug, cfg)
                except Exception as live_err:
                    live = {"connector": cslug, "source": "error", "metric_values": {}, "kpis": {}, "error": str(live_err), "out": f"{cslug} live pull failed"}
                    status = "warning"
                    fail_reason = str(live_err)

            metrics = {}
            if live and isinstance(live.get("metric_values"), dict) and live.get("metric_values"):
                metrics.update(live.get("metric_values") or {})
                data = dict(live)
                data["connector"] = cslug or label
            else:
                if cslug == "google-ads":
                    metrics.update({"roas": 4.2, "spend": 89.0, "ctr": 2.8})
                elif cslug in ("meta-ads", "tiktok-ads", "linkedin-ads"):
                    metrics.update({"roas": 3.1, "spend": 56.0, "ctr": 1.9})
                elif cslug in ("stripe", "paypal", "shopify"):
                    metrics.update({"revenue": 4812.0, "mrr": 4812.0})
                elif cslug in ("github", "aws", "vercel"):
                    metrics.update({"uptime": 99.7})
                data = {"connector": cslug or label, "kpis": dict(metrics), "metric_values": metrics, "source": "mock"}

            bits = []
            if "roas" in metrics: bits.append(f"ROAS {metrics['roas']}")
            if "spend" in metrics: bits.append(f"Spend {metrics['spend']}")
            if "ctr" in metrics: bits.append(f"CTR {metrics['ctr']}")
            if "sessions" in metrics: bits.append(f"Sessions {metrics['sessions']}")
            if "conversions" in metrics: bits.append(f"Conv {metrics['conversions']}")
            if "uptime" in metrics: bits.append(f"Uptime {metrics['uptime']}%")
            if "revenue" in metrics: bits.append(f"Revenue {metrics['revenue']}")
            inp = f"Signals from {prev_label}"
            if live and live.get("out"):
                out = str(live.get("out"))
            else:
                out = " | ".join(bits[:4]) if bits else "Connector data fetched"
        elif ntype == "agent":
            conn_steps = [r for r in results if r.get("type") == "connector"]
            roas_vals = [((r.get("data") or {}).get("metric_values") or {}).get("roas") for r in conn_steps]
            roas_vals = [x for x in roas_vals if isinstance(x, (int, float))]
            rec = "No blocking signals detected. Continue monitoring."
            if roas_vals:
                rec = "ROAS below target. Reallocate spend to best performers and pause weak segments." if (sum(roas_vals) / len(roas_vals)) < 3 else "ROAS healthy. Scale top ad groups gradually."
            data = {"agent": slug or label, "analysis": rec, "recommendation": rec, "input_connectors": len(conn_steps)}
            inp = f"Context from {len(conn_steps)} connector(s)"
            out = rec
        elif ntype == "condition":
            metric = str(cfg.get("condition_metric") or cfg.get("metric") or "ROAS")
            op = str(cfg.get("condition_operator") or cfg.get("operator") or ">")
            thr_raw = cfg.get("condition_value", cfg.get("value", 0))
            thr = _num(thr_raw)
            actual = None
            key = metric.lower().replace(' ', '_')
            for r in reversed(results):
                if r.get("type") != "connector":
                    continue
                m = (r.get("data") or {}).get("metric_values") or {}
                if key in m:
                    actual = m[key]
                    break
                for mk, mv in m.items():
                    if key in mk:
                        actual = mv
                        break
                if actual is not None:
                    break
            passed = _eval(actual, op, thr)
            then_label = str(cfg.get("condition_then_label") or cfg.get("thenLabel") or "Yes")
            else_label = str(cfg.get("condition_else_label") or cfg.get("elseLabel") or "No")
            branch = "yes" if passed else "no"
            branch_label = then_label if passed else else_label
            if not passed:
                status = "warning"
                fail_reason = f"Condition false: {metric} {op} {thr_raw}"
            data = {"evaluated": True, "metric": metric, "operator": op, "threshold": thr, "actual_value": actual, "branch": branch, "branch_label": branch_label}
            inp = f"Evaluate {metric}"
            out = f"{branch_label} (actual={actual if actual is not None else 'n/a'})"
        elif ntype == "output":
            template = str(cfg.get("output_template") or cfg.get("template") or "Here is your result: {{last_agent_response}}")
            last_agent = next((r for r in reversed(results) if r.get("type") == "agent"), None)
            msg = template.replace("{{last_agent_response}}", str(((last_agent or {}).get("data") or {}).get("analysis", "No agent response available")))
            data = {"output": True, "format": str(cfg.get("output_format") or cfg.get("format") or "text"), "destination": str(cfg.get("output_destination") or cfg.get("destination") or "chat"), "message": msg}
            inp = f"Assemble output for {data['destination']}"
            out = msg
        else:
            data = {"note": f"Node type '{ntype}' executed in mock mode."}
            out = data["note"]

        delays = {"trigger": 0.007, "connector": 0.019, "agent": 0.016, "condition": 0.011, "output": 0.008}
        _time.sleep(delays.get(ntype, 0.006))
        dur = round((_time.perf_counter() - s0) * 1000, 2)

        legacy_status = "ok" if status == "success" else status
        legacy = {"step": step_no, "node_id": nid, "type": ntype, "label": label, "status": legacy_status, "data": data, "duration_ms": dur, "input": str(inp), "output": str(out), "fail_reason": str(fail_reason)}
        results.append(legacy)

        trace = {"step": step_no, "node_id": nid, "node_label": label, "type": ntype, "status": status, "input": str(inp), "output": str(out), "fail_reason": str(fail_reason), "duration_ms": dur}
        if ntype == "connector":
            trace["kpis"] = (data.get("metric_values") or data.get("kpis") or {})
        steps.append(trace)

        prev_output = str(out)
        prev_label = label
        for nxt in adj.get(nid, []):
            if nxt not in visited:
                queue.append(nxt)

    elapsed_ms = round((_time.perf_counter() - start_perf) * 1000, 2)
    finished_at = _iso(datetime.now(timezone.utc))

    succ = sum(1 for s in steps if s.get("status") == "success")
    warn = sum(1 for s in steps if s.get("status") == "warning")
    err = sum(1 for s in steps if s.get("status") == "error")
    overall = "error" if err else ("warning" if warn else "success")

    exec_id = None
    trace_exec_id = None
    try:
        conn = get_db()
        _ensure_client_tables(conn)
        conn.execute("""CREATE TABLE IF NOT EXISTS flow_executions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, client_id INTEGER, flow_name TEXT, nodes_count INTEGER, steps_count INTEGER, elapsed_ms REAL, status TEXT, result_json TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        try:
            conn.execute("ALTER TABLE flow_executions ADD COLUMN client_id INTEGER")
        except Exception:
            pass
        cur = conn.execute("INSERT INTO flow_executions (user_id, client_id, flow_name, nodes_count, steps_count, elapsed_ms, status, result_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (uid, cid, flow_name, len(nodes), step_no, elapsed_ms, overall, json.dumps(results)))
        exec_id = cur.lastrowid

        conn.execute("""CREATE TABLE IF NOT EXISTS executions (id INTEGER PRIMARY KEY AUTOINCREMENT, flow_id INTEGER, user_id INTEGER NOT NULL, client_id INTEGER, started_at TEXT NOT NULL, finished_at TEXT NOT NULL, status TEXT NOT NULL, steps_json TEXT NOT NULL)""")
        try:
            conn.execute("ALTER TABLE executions ADD COLUMN client_id INTEGER")
        except Exception:
            pass
        cur2 = conn.execute("INSERT INTO executions (flow_id, user_id, client_id, started_at, finished_at, status, steps_json) VALUES (?, ?, ?, ?, ?, ?, ?)", (flow_id, uid, cid, started_at, finished_at, overall, json.dumps(steps)))
        trace_exec_id = cur2.lastrowid
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Flow execution save error: {e}")

    summary = {
        "steps_count": step_no,
        "success": succ,
        "warning": warn,
        "error": err,
        "run_status": overall,
        "total_duration_ms": elapsed_ms,
    }
    return jsonify({
        "success": True,
        "execution_id": exec_id,
        "trace_execution_id": trace_exec_id,
        "flow_id": flow_id,
        "client_id": cid,
        "status": "completed",
        "run_status": overall,
        "overall_status": overall,
        "nodes_total": len(nodes),
        "steps_executed": step_no,
        "elapsed_ms": elapsed_ms,
        "total_duration_ms": elapsed_ms,
        "success_steps": succ,
        "warning_steps": warn,
        "failed_steps": err,
        "started_at": started_at,
        "finished_at": finished_at,
        "steps": steps,
        "results": results,
        "summary": summary,
    })

@app.route("/api/orchestrator/history", methods=["GET"])
def orchestrator_history():
    """Return recent flow executions for the current user/client scope."""
    limit = request.args.get("limit", 20, type=int)
    uid = get_current_user_id()
    cid = get_current_client_id()

    try:
        conn = get_db()
        _ensure_client_tables(conn)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS flow_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                client_id INTEGER,
                flow_name TEXT,
                nodes_count INTEGER,
                steps_count INTEGER,
                elapsed_ms REAL,
                status TEXT,
                result_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            conn.execute("ALTER TABLE flow_executions ADD COLUMN client_id INTEGER")
        except Exception:
            pass

        if cid is not None and not _client_owned(conn, uid, cid):
            conn.close()
            return jsonify([])

        sql = """
            SELECT id, flow_name, nodes_count, steps_count, elapsed_ms, status, created_at, client_id
            FROM flow_executions
            WHERE user_id = ?
        """
        params = [uid]
        if cid is not None:
            sql += " AND COALESCE(client_id, 0) = ?"
            params.append(cid)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, tuple(params)).fetchall()
        conn.close()

        return jsonify([
            {
                "id": r[0],
                "flow_name": r[1],
                "nodes_count": r[2],
                "steps_count": r[3],
                "elapsed_ms": r[4],
                "status": r[5],
                "created_at": r[6],
                "client_id": r[7] if len(r) > 7 else None,
            }
            for r in rows
        ])
    except Exception:
        return jsonify([])
@app.route("/api/orchestrator/history/<int:exec_id>", methods=["GET"])
def orchestrator_history_detail(exec_id):
    """Return full results of a specific execution in current user/client scope."""
    uid = get_current_user_id()
    cid = get_current_client_id()

    try:
        conn = get_db()
        _ensure_client_tables(conn)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS flow_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                client_id INTEGER,
                flow_name TEXT,
                nodes_count INTEGER,
                steps_count INTEGER,
                elapsed_ms REAL,
                status TEXT,
                result_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            conn.execute("ALTER TABLE flow_executions ADD COLUMN client_id INTEGER")
        except Exception:
            pass

        if cid is not None and not _client_owned(conn, uid, cid):
            conn.close()
            return jsonify({"error": "Execution not found"}), 404

        sql = """
            SELECT id, flow_name, nodes_count, steps_count, elapsed_ms, status, result_json, created_at, client_id
            FROM flow_executions
            WHERE id = ? AND user_id = ?
        """
        params = [exec_id, uid]
        if cid is not None:
            sql += " AND COALESCE(client_id, 0) = ?"
            params.append(cid)

        row = conn.execute(sql, tuple(params)).fetchone()
        conn.close()

        if not row:
            return jsonify({"error": "Execution not found"}), 404

        return jsonify({
            "id": row[0],
            "flow_name": row[1],
            "nodes_count": row[2],
            "steps_count": row[3],
            "elapsed_ms": row[4],
            "status": row[5],
            "results": json.loads(row[6]) if row[6] else [],
            "created_at": row[7],
            "client_id": row[8] if len(row) > 8 else None,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/api/rag/search")
def rag_search():
    query = request.args.get('q', '').strip().lower()
    limit = request.args.get('limit', 3, type=int)
    
    if not query:
        return jsonify([])
    
    # Split query into words for better matching
    words = query.split()
    like_conditions = " OR ".join(["LOWER(content) LIKE ? OR LOWER(title) LIKE ? OR LOWER(summary) LIKE ?"] * len(words))
    params = []
    for word in words:
        params.extend([f"%{word}%", f"%{word}%", f"%{word}%"])
    params.append(limit)
    
    conn = get_db()
    cursor = conn.cursor()
    sql = f"""
        SELECT title, summary, content, source
        FROM chunks
        WHERE {like_conditions}
        ORDER BY LENGTH(content) DESC
        LIMIT ?
    """
    rows = cursor.execute(sql, params).fetchall()
    conn.close()
    
    results = [
        {"title": r[0], "summary": r[1], "content": r[2], "source": r[3]}
        for r in rows
    ]
    return jsonify(results)

@app.route("/api/agents/<slug>", methods=["GET", "POST"])
def agent_config(slug):
    user_id = get_current_user_id()
    client_id = get_current_client_id()
    scoped_client_id = int(client_id or 0)
    conn = get_db()
    cursor = conn.cursor()
    _ensure_client_tables(conn)

    if request.method == "GET":
        row = None
        if client_id is not None:
            row = cursor.execute("""
                SELECT custom_name, avatar_base64, llm_provider, llm_model, api_key, temperature, max_tokens, rag_enabled, status, avatar_colors, client_id
                FROM agents_config
                WHERE user_id = ? AND agent_slug = ? AND COALESCE(client_id, 0) = ?
                LIMIT 1
            """, (user_id, slug, client_id)).fetchone()
        if not row:
            row = cursor.execute("""
                SELECT custom_name, avatar_base64, llm_provider, llm_model, api_key, temperature, max_tokens, rag_enabled, status, avatar_colors, client_id
                FROM agents_config
                WHERE user_id = ? AND agent_slug = ? AND COALESCE(client_id, 0) = 0
                LIMIT 1
            """, (user_id, slug)).fetchone()

        rag_chunks = 0
        last_response_time = None
        active_conversations = 0
        try:
            rag_row = cursor.execute("SELECT COUNT(*) FROM chunks").fetchone()
            rag_chunks = int(rag_row[0] or 0) if rag_row else 0

            convo_sql = """
                SELECT COUNT(*), MAX(m.timestamp)
                FROM conversations c
                LEFT JOIN messages m ON m.conv_id = c.id AND m.role = 'agent'
                WHERE c.user_id = ? AND c.agent_slug = ?
            """
            convo_params = [user_id, slug]
            if client_id is not None:
                convo_sql += " AND COALESCE(c.client_id, 0) = ?"
                convo_params.append(client_id)

            convo_row = cursor.execute(convo_sql, tuple(convo_params)).fetchone()
            if convo_row:
                active_conversations = int(convo_row[0] or 0)
                last_response_time = convo_row[1]
        except Exception:
            pass

        if row:
            avatar_colors = None
            try:
                avatar_colors = json.loads(row[9]) if row[9] else None
            except Exception:
                pass
            custom_name = str(row[0] or "").strip()
            if not custom_name:
                custom_name = _default_agent_custom_name(slug)
            conn.close()
            return jsonify({
                "custom_name": custom_name,
                "avatar_base64": row[1],
                "llm_provider": row[2],
                "llm_model": row[3],
                "api_key": row[4],
                "temperature": row[5],
                "max_tokens": row[6],
                "rag_enabled": bool(row[7]),
                "status": row[8],
                "avatar_colors": avatar_colors,
                "rag_chunks": rag_chunks,
                "last_response_time": last_response_time,
                "active_conversations": active_conversations,
                "client_id": row[10],
            })

        conn.close()
        return jsonify({
            "custom_name": _default_agent_custom_name(slug),
            "avatar_base64": None,
            "llm_provider": "vertex",
            "llm_model": COOLBITS_VERTEX_PROFILE,
            "api_key": "",
            "temperature": 0.7,
            "max_tokens": 2048,
            "rag_enabled": True,
            "status": "Active",
            "avatar_colors": None,
            "rag_chunks": rag_chunks,
            "last_response_time": last_response_time,
            "active_conversations": active_conversations,
            "client_id": client_id,
        })

    data = request.json or {}
    avatar_colors_json = None
    if data.get('avatar_colors'):
        avatar_colors_json = json.dumps(data['avatar_colors'])

    cursor.execute("""
        INSERT OR REPLACE INTO agents_config
        (user_id, client_id, agent_slug, custom_name, avatar_base64, avatar_colors, llm_provider, llm_model, api_key, temperature, max_tokens, rag_enabled, status, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        user_id,
        scoped_client_id,
        slug,
        data.get('custom_name'),
        data.get('avatar_base64'),
        avatar_colors_json,
        data.get('llm_provider'),
        data.get('llm_model'),
        data.get('api_key'),
        data.get('temperature', 0.7),
        data.get('max_tokens', 2048),
        1 if data.get('rag_enabled') else 0,
        data.get('status', 'Active')
    ))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Agent config saved", "client_id": scoped_client_id})


@app.route("/api/connectors/<slug>", methods=["GET", "POST"])
def connector_config(slug):
    user_id = get_current_user_id()
    client_id = get_current_client_id()
    scoped_client_id = int(client_id or 0)
    conn = get_db()
    cursor = conn.cursor()
    _ensure_client_tables(conn)

    if request.method == "GET":
        row = None
        if client_id is not None:
            row = cursor.execute("""
                SELECT status, config_json, last_connected, client_id
                FROM connectors_config
                WHERE user_id = ? AND connector_slug = ? AND COALESCE(client_id, 0) = ?
                LIMIT 1
            """, (user_id, slug, client_id)).fetchone()
        if not row:
            if client_id is not None:
                row = cursor.execute("""
                    SELECT status, config_json, last_connected, client_id
                    FROM connectors_config
                    WHERE user_id = ? AND connector_slug = ? AND COALESCE(client_id, 0) = 0
                    LIMIT 1
                """, (user_id, slug)).fetchone()
            else:
                row = cursor.execute("""
                    SELECT status, config_json, last_connected, client_id
                    FROM connectors_config
                    WHERE user_id = ? AND connector_slug = ? AND COALESCE(client_id, 0) = 0
                    LIMIT 1
                """, (user_id, slug)).fetchone()

        if row:
            cfg = json.loads(row[1]) if row[1] else {}
            if not isinstance(cfg, dict):
                cfg = {}
            custom_name = str(cfg.get("custom_name", "")).strip() or None
            conn.close()
            return jsonify({
                "status": row[0],
                "config": cfg,
                "last_connected": row[2],
                "custom_name": custom_name,
                "client_id": row[3],
            })

        conn.close()
        return jsonify({
            "status": "Disconnected",
            "config": {},
            "last_connected": None,
            "custom_name": None,
            "client_id": client_id,
        })

    data = request.json or {}
    cfg = data.get('config', {})
    if not isinstance(cfg, dict):
        cfg = {}
    if data.get("custom_name") is not None:
        cfg["custom_name"] = str(data.get("custom_name") or "").strip()

    cursor.execute("""
        INSERT OR REPLACE INTO connectors_config
        (user_id, client_id, connector_slug, status, config_json, last_connected)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
    """, (user_id, scoped_client_id, slug, data.get('status', 'Disconnected'), json.dumps(cfg)))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Connector config saved", "client_id": scoped_client_id})


@app.route("/api/connectors", methods=["GET"])
def get_connectors_status():
    user_id = get_current_user_id()
    client_id = get_current_client_id()
    conn = get_db()
    cursor = conn.cursor()

    sql = "SELECT connector_slug, status FROM connectors_config WHERE user_id = ?"
    params = [user_id]
    if client_id is not None:
        sql += " AND COALESCE(client_id, 0) = ?"
        params.append(client_id)

    rows = cursor.execute(sql, tuple(params)).fetchall()
    conn.close()

    status_map = {r[0]: r[1] for r in rows}
    return jsonify(status_map)


@app.route("/api/agents/list", methods=["GET"])
def list_agents():
    user_id = get_current_user_id()
    client_id = get_current_client_id()
    include_all = str(request.args.get("all") or "").strip().lower() in ("1", "true", "yes")
    if FORCE_VERTEX_ALL_AGENTS and int(user_id or 0) > 0:
        _ensure_vertex_defaults_for_user(user_id)

    conn = get_db()
    cursor = conn.cursor()
    _ensure_client_tables(conn)

    if client_id is not None and not include_all and not _client_owned(conn, user_id, client_id):
        conn.close()
        return jsonify([])

    if client_id is not None and not include_all:
        rows = cursor.execute("""
            SELECT agent_slug, custom_name, status, avatar_base64, avatar_colors, client_id
            FROM agents_config
            WHERE user_id = ? AND COALESCE(client_id, 0) IN (?, 0)
        """, (user_id, client_id)).fetchall()
    else:
        rows = cursor.execute("""
            SELECT agent_slug, custom_name, status, avatar_base64, avatar_colors, client_id
            FROM agents_config
            WHERE user_id = ?
        """, (user_id,)).fetchall()
    conn.close()

    db_agents = {}
    db_score = {}
    for r in rows:
        avatar_colors = None
        try:
            avatar_colors = json.loads(r[4]) if r[4] else None
        except Exception:
            avatar_colors = None

        row_client_id = r[5]
        try:
            row_client_id_num = int(row_client_id) if row_client_id is not None else 0
        except Exception:
            row_client_id_num = 0

        score = 1
        if client_id is not None and row_client_id_num == int(client_id):
            score = 3
        elif row_client_id_num == 0:
            score = 2

        slug = str(r[0] or "").strip()
        if not slug:
            continue
        if slug in db_score and db_score[slug] >= score:
            continue
        db_score[slug] = score
        db_agents[slug] = {
            "name": r[1] or _default_agent_custom_name(slug),
            "status": r[2] or "Ready",
            "has_photo": bool(r[3]),
            "avatar_colors": avatar_colors,
            "client_id": r[5],
        }

    agents = []
    known_slugs = set()
    for ws_slug, ws_data in workspaces.items():
        ws_name = ws_data.get("name", ws_slug.title())
        for agent_slug, default_name in ws_data.get("agents", {}).items():
            known_slugs.add(agent_slug)
            db = db_agents.get(agent_slug, {})
            agents.append({
                "slug": agent_slug,
                "name": db.get("name") or default_name,
                "status": db.get("status") or "Ready",
                "workspace": ws_name,
                "workspace_slug": ws_slug,
                "has_photo": db.get("has_photo", False),
                "avatar_colors": db.get("avatar_colors"),
                "client_id": db.get("client_id"),
            })

    for agent_slug, db in db_agents.items():
        if agent_slug in known_slugs:
            continue
        agents.append({
            "slug": agent_slug,
            "name": db.get("name") or agent_slug.replace("-", " ").title(),
            "status": db.get("status") or "Ready",
            "workspace": "Other",
            "workspace_slug": "other",
            "has_photo": db.get("has_photo", False),
            "avatar_colors": db.get("avatar_colors"),
            "client_id": db.get("client_id"),
        })

    agents.sort(key=lambda a: (a.get("workspace", "Other"), a.get("name", "")))
    return jsonify(agents)


@app.route("/api/connectors/list", methods=["GET"])
def list_connectors():
    user_id = get_current_user_id()
    client_id = get_current_client_id()
    include_all = str(request.args.get("all") or "").strip().lower() in ("1", "true", "yes")

    conn = get_db()
    cursor = conn.cursor()
    _ensure_client_tables(conn)

    if client_id is not None and not include_all:
        if not _client_owned(conn, user_id, client_id):
            conn.close()
            return jsonify([])

        rows = cursor.execute("""
            SELECT cc.id, cc.connector_slug, cc.account_id, cc.account_name, cc.status,
                   c.status, c.config_json
            FROM client_connectors cc
            LEFT JOIN connectors_config c
              ON c.user_id = ? AND c.connector_slug = cc.connector_slug
             AND COALESCE(c.client_id, 0) IN (?, 0)
            WHERE cc.client_id = ?
            ORDER BY cc.updated_at DESC, cc.id DESC
        """, (user_id, client_id, client_id)).fetchall()

        slug_to_display = {v: k for k, v in CONNECTOR_NAME_TO_SLUG.items()}
        out = []
        seen = set()
        for r in rows:
            slug = str(r[1] or "").strip()
            if not slug or slug in seen:
                continue
            seen.add(slug)

            cfg = {}
            if r[6]:
                try:
                    cfg = json.loads(r[6])
                except Exception:
                    cfg = {}
            custom_name = str((cfg or {}).get("custom_name") or "").strip()
            display_name = custom_name or slug_to_display.get(slug) or _humanize_slug(slug)

            status_raw = str(r[5] or r[4] or "Disconnected").strip().lower()
            if status_raw in ("connected", "active"):
                status = "Connected"
            elif status_raw in ("pending", "soon"):
                status = "Pending"
            elif status_raw in ("error", "failed"):
                status = "Error"
            else:
                status = "Disconnected"

            out.append({
                "id": r[0],
                "slug": slug,
                "name": display_name,
                "status": status,
                "account_id": r[2],
                "account_name": r[3],
                "is_live": slug in CONNECTOR_NAME_TO_SLUG.values(),
                "client_id": client_id,
            })

        conn.close()
        out.sort(key=lambda x: x.get("name", ""))
        return jsonify(out)

    rows = cursor.execute("""
        SELECT connector_slug, status, config_json, client_id
        FROM connectors_config
        WHERE user_id = ?
    """, (user_id,)).fetchall()
    conn.close()

    db_status = {r[0]: (r[1] or "Disconnected") for r in rows}
    db_custom_name = {}
    for r in rows:
        slug = r[0]
        config_raw = r[2]
        if not config_raw:
            continue
        try:
            cfg = json.loads(config_raw)
        except Exception:
            cfg = {}
        if not isinstance(cfg, dict):
            continue
        custom_name = str(cfg.get("custom_name", "")).strip()
        if custom_name:
            db_custom_name[slug] = custom_name

    connectors = []
    known_slugs = set()

    for display_name, slug in CONNECTOR_NAME_TO_SLUG.items():
        known_slugs.add(slug)
        connectors.append({
            "slug": slug,
            "name": db_custom_name.get(slug, display_name),
            "status": db_status.get(slug, "Disconnected"),
            "is_live": True,
        })

    for slug, status in db_status.items():
        if slug in known_slugs:
            continue
        connectors.append({
            "slug": slug,
            "name": db_custom_name.get(slug, slug.replace("-", " ").title()),
            "status": status,
            "is_live": False,
        })

    return jsonify(connectors)

@app.route("/api/rag/api-docs")
def rag_api_docs():
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 3, type=int)
    connector_filter = request.args.get('connector', None)  # opțional: doar un conector

    if not query:
        return jsonify([])

    # Smart keyword extraction (skip common stop words, split into meaningful terms)
    stop_words = {'what', 'is', 'the', 'how', 'to', 'for', 'and', 'or', 'but', 'in',
                  'on', 'at', 'by', 'with', 'a', 'an', 'of', 'are', 'was', 'do', 'does',
                  'can', 'could', 'should', 'would', 'will', 'my', 'me', 'i', 'show',
                  'tell', 'about', 'from', 'get', 'give', 'this', 'that', 'these', 'those'}
    words = [w.lower() for w in query.split() if len(w) > 2 and w.lower() not in stop_words]
    if not words:
        words = [query.lower()]

    conn = get_db()
    cursor = conn.cursor()

    # Build OR conditions for each keyword across title and content
    word_conditions = " OR ".join(
        ["(LOWER(title) LIKE ? OR LOWER(content) LIKE ?)" for _ in words]
    )
    params = []
    for w in words:
        params.extend([f"%{w}%", f"%{w}%"])

    sql = f"""
        SELECT connector, title, url, content, section_type
        FROM api_docs
        WHERE ({word_conditions})
    """

    if connector_filter:
        sql += " AND connector = ?"
        params.append(connector_filter)

    sql += " ORDER BY LENGTH(content) DESC LIMIT ?"
    params.append(limit)

    rows = cursor.execute(sql, params).fetchall()
    conn.close()

    results = [
        {
            "connector": r[0],
            "title": r[1],
            "url": r[2],
            "content_preview": r[3][:500] + "..." if len(r[3]) > 500 else r[3],
            "section_type": r[4]
        }
        for r in rows
    ]
    return jsonify(results)

@app.route("/api/agent-connectors/<slug>")
def agent_connectors(slug):
    """Return the list of relevant connector names for an agent"""
    connectors = AGENT_CONNECTOR_MAP.get(slug, [])
    return jsonify(connectors)


# ─── Google Ads Mock API ─────────────────────────────────────────────────────
GOOGLE_ADS_MOCK_ACCOUNTS = [
    {"id": "MCC-000-111-2222", "name": "Camarad MCC (Manager)", "type": "MCC", "currency": "USD", "timezone": "Europe/Bucharest"},
    {"id": "123-456-7890", "name": "E-Shop Romania SRL", "type": "Client", "currency": "RON", "timezone": "Europe/Bucharest", "parent_mcc": "MCC-000-111-2222"},
    {"id": "234-567-8901", "name": "TechStart Agency", "type": "Client", "currency": "EUR", "timezone": "Europe/Berlin", "parent_mcc": "MCC-000-111-2222"},
    {"id": "345-678-9012", "name": "Global Reach Inc.", "type": "Client", "currency": "USD", "timezone": "America/New_York", "parent_mcc": "MCC-000-111-2222"},
]

GOOGLE_ADS_MOCK_CAMPAIGNS = {
    "123-456-7890": [
        {"id": "c-1001", "name": "Summer Sale RO 🇷🇴", "status": "ENABLED", "type": "Search", "budget_daily": 150.00, "budget_total": 5000.00, "spent": 3212.45, "impressions": 87432, "clicks": 4567, "conversions": 189, "cost_per_conv": 17.00, "roas": 4.2, "ctr": 5.22, "avg_cpc": 0.70},
        {"id": "c-1002", "name": "Brand Awareness Display", "status": "PAUSED", "type": "Display", "budget_daily": 80.00, "budget_total": 2500.00, "spent": 1890.23, "impressions": 234567, "clicks": 3421, "conversions": 67, "cost_per_conv": 28.21, "roas": 1.8, "ctr": 1.46, "avg_cpc": 0.55},
        {"id": "c-1003", "name": "Winter Promo Shopping", "status": "ENABLED", "type": "Shopping", "budget_daily": 200.00, "budget_total": 6000.00, "spent": 4123.67, "impressions": 156789, "clicks": 8901, "conversions": 312, "cost_per_conv": 13.22, "roas": 3.8, "ctr": 5.68, "avg_cpc": 0.46},
        {"id": "c-1004", "name": "YouTube Pre-Roll Branding", "status": "ENABLED", "type": "Video", "budget_daily": 100.00, "budget_total": 3000.00, "spent": 1567.89, "impressions": 345678, "clicks": 2345, "conversions": 45, "cost_per_conv": 34.84, "roas": 2.1, "ctr": 0.68, "avg_cpc": 0.67},
        {"id": "c-1005", "name": "Retargeting Cart Abandoners", "status": "ENABLED", "type": "Display", "budget_daily": 60.00, "budget_total": 1800.00, "spent": 1245.32, "impressions": 67890, "clicks": 1890, "conversions": 98, "cost_per_conv": 12.71, "roas": 5.3, "ctr": 2.78, "avg_cpc": 0.66},
    ],
    "234-567-8901": [
        {"id": "c-2001", "name": "Lead Gen - Tech Services", "status": "ENABLED", "type": "Search", "budget_daily": 120.00, "budget_total": 3600.00, "spent": 2100.50, "impressions": 54321, "clicks": 2890, "conversions": 134, "cost_per_conv": 15.67, "roas": 3.5, "ctr": 5.32, "avg_cpc": 0.73},
        {"id": "c-2002", "name": "Performance Max - Agency", "status": "ENABLED", "type": "Performance Max", "budget_daily": 250.00, "budget_total": 7500.00, "spent": 5432.10, "impressions": 432100, "clicks": 12340, "conversions": 456, "cost_per_conv": 11.91, "roas": 4.6, "ctr": 2.86, "avg_cpc": 0.44},
    ],
    "345-678-9012": [
        {"id": "c-3001", "name": "US Expansion - Search", "status": "ENABLED", "type": "Search", "budget_daily": 500.00, "budget_total": 15000.00, "spent": 9876.54, "impressions": 234567, "clicks": 15678, "conversions": 567, "cost_per_conv": 17.42, "roas": 3.9, "ctr": 6.68, "avg_cpc": 0.63},
        {"id": "c-3002", "name": "App Install Campaign", "status": "PAUSED", "type": "App", "budget_daily": 300.00, "budget_total": 9000.00, "spent": 6543.21, "impressions": 567890, "clicks": 23456, "conversions": 1234, "cost_per_conv": 5.30, "roas": 2.8, "ctr": 4.13, "avg_cpc": 0.28},
    ],
}

GOOGLE_ADS_MOCK_KEYWORDS = {
    "c-1001": [
        {"keyword": "magazin online romania", "match_type": "Broad", "status": "ENABLED", "impressions": 23456, "clicks": 1234, "ctr": 5.26, "avg_cpc": 0.65, "quality_score": 8},
        {"keyword": "cumparaturi online", "match_type": "Phrase", "status": "ENABLED", "impressions": 18765, "clicks": 987, "ctr": 5.26, "avg_cpc": 0.72, "quality_score": 7},
        {"keyword": "reduceri vara 2024", "match_type": "Exact", "status": "ENABLED", "impressions": 12345, "clicks": 876, "ctr": 7.10, "avg_cpc": 0.58, "quality_score": 9},
        {"keyword": "oferte speciale", "match_type": "Broad", "status": "PAUSED", "impressions": 8765, "clicks": 345, "ctr": 3.94, "avg_cpc": 0.89, "quality_score": 5},
        {"keyword": "[e-shop romania]", "match_type": "Exact", "status": "ENABLED", "impressions": 5432, "clicks": 432, "ctr": 7.95, "avg_cpc": 0.45, "quality_score": 10},
    ],
    "c-1003": [
        {"keyword": "pantofi sport barbati", "match_type": "Broad", "status": "ENABLED", "impressions": 34567, "clicks": 2345, "ctr": 6.78, "avg_cpc": 0.42, "quality_score": 8},
        {"keyword": "rochii de vara", "match_type": "Phrase", "status": "ENABLED", "impressions": 28765, "clicks": 1987, "ctr": 6.91, "avg_cpc": 0.38, "quality_score": 9},
        {"keyword": "electronice ieftine", "match_type": "Broad", "status": "ENABLED", "impressions": 19876, "clicks": 1567, "ctr": 7.88, "avg_cpc": 0.51, "quality_score": 7},
    ],
}


@app.before_request
def enforce_client_scope_ownership():
    """Global hardening: if client scope is provided on sensitive APIs, it must be owned."""
    if request.method == "OPTIONS":
        return None
    path = str(request.path or "")
    if not path.startswith("/api/"):
        return None
    if not any(path.startswith(prefix) for prefix in SCOPED_API_PREFIXES):
        return None

    requires_client_scope = _path_matches_scope_rule(request.method, path)
    raw_client_value = request.headers.get("X-Client-ID")
    if raw_client_value is None:
        raw_client_value = request.args.get("client_id")

    client_id = get_current_client_id()
    parse_ok = _client_scope_parse_error(raw_client_value)
    if parse_ok is False:
        return jsonify({"error": "Invalid X-Client-ID"}), 400
    if requires_client_scope and client_id is None:
        return jsonify({"error": "Client scope required"}), 400
    if client_id is None:
        return None

    user_id = _scope_effective_user_id()
    if int(user_id or 0) <= 0:
        if AUTH_REQUIRED:
            return jsonify({"error": "Authentication required"}), 401
        return None

    conn = get_db()
    try:
        _ensure_client_tables(conn)
        if not _client_owned(conn, int(user_id), int(client_id)):
            return jsonify({"error": "Client not found or not owned"}), 404
    finally:
        conn.close()
    return None


def _google_ads_build_summary(campaigns):
    campaigns = campaigns if isinstance(campaigns, list) else []
    total_spent = sum(float(c.get("spent") or 0) for c in campaigns if isinstance(c, dict))
    total_budget = sum(float(c.get("budget_total") or 0) for c in campaigns if isinstance(c, dict))
    total_clicks = sum(int(c.get("clicks") or 0) for c in campaigns if isinstance(c, dict))
    total_conversions = sum(int(c.get("conversions") or 0) for c in campaigns if isinstance(c, dict))
    total_impressions = sum(int(c.get("impressions") or 0) for c in campaigns if isinstance(c, dict))
    roas_vals = [float(c.get("roas") or 0) for c in campaigns if isinstance(c, dict) and c.get("roas") is not None]
    avg_roas = round(sum(roas_vals) / len(roas_vals), 2) if roas_vals else 0
    return {
        "total_campaigns": len(campaigns),
        "active_campaigns": sum(1 for c in campaigns if isinstance(c, dict) and str(c.get("status", "")).upper() == "ENABLED"),
        "total_spent": round(total_spent, 2),
        "total_budget": round(total_budget, 2),
        "total_clicks": total_clicks,
        "total_conversions": total_conversions,
        "total_impressions": total_impressions,
        "avg_roas": avg_roas,
        "budget_utilization": round((total_spent / total_budget * 100), 1) if total_budget else 0,
    }


def _google_ads_gateway_fetch(path_candidates, params=None, timeout=25):
    if not COOLBITS_GATEWAY_ENABLED:
        return None, {"enabled": False, "reason": "disabled"}

    last_error = None
    for path in path_candidates:
        try:
            status, payload, text = _coolbits_request("GET", path, params=params, timeout=timeout)
            if 200 <= int(status) < 300:
                return payload, {"enabled": True, "path": path, "status": int(status)}
            last_error = f"{path} -> HTTP {status}"
            if payload is None and text:
                last_error += f" ({text[:180]})"
        except Exception as e:
            last_error = f"{path} -> {e}"

    return None, {"enabled": True, "error": last_error or "gateway_unavailable"}


def _google_ads_list_from_payload(payload, preferred_keys):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in preferred_keys:
        rows = payload.get(key)
        if isinstance(rows, list):
            return rows
    return []


def _google_ads_iso_date_window(days):
    from datetime import datetime, timedelta

    safe_days = max(1, min(int(days or 30), 365))
    end = datetime.utcnow().date()
    start = end - timedelta(days=safe_days - 1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _google_ads_map_coolbits_campaigns(rows):
    rows = rows if isinstance(rows, list) else []
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        clicks = int(r.get("clicks") or 0)
        impressions = int(r.get("impressions") or 0)
        conversions = float(r.get("conversions") or 0)
        spent = float(r.get("spent") if r.get("spent") is not None else (r.get("cost") or 0))
        roas = r.get("roas")
        if roas is None:
            conv_value = float(r.get("convValue") or r.get("conversionValue") or 0)
            roas = round((conv_value / spent), 2) if spent > 0 else 0
        avg_cpc = float(r.get("avg_cpc") or 0)
        if not avg_cpc and clicks > 0:
            avg_cpc = round(spent / clicks, 2)
        ctr = float(r.get("ctr") or 0)
        if not ctr and impressions > 0:
            ctr = round((clicks / impressions) * 100, 2)
        cost_per_conv = float(r.get("cost_per_conv") or 0)
        if not cost_per_conv and conversions > 0:
            cost_per_conv = round(spent / conversions, 2)
        out.append({
            "id": str(r.get("id") or r.get("campaignId") or ""),
            "name": r.get("name") or r.get("campaign") or "Campaign",
            "status": str(r.get("status") or "UNKNOWN"),
            "type": r.get("type") or r.get("channel") or "Search",
            "budget_daily": float(r.get("budget_daily") or r.get("budgetDaily") or 0),
            "budget_total": float(r.get("budget_total") or r.get("budgetTotal") or 0),
            "spent": round(spent, 2),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": int(conversions),
            "cost_per_conv": round(cost_per_conv, 2),
            "roas": float(roas or 0),
            "ctr": round(ctr, 2),
            "avg_cpc": round(avg_cpc, 2),
        })
    return [c for c in out if c.get("id")]


def _google_ads_map_coolbits_keywords(rows):
    rows = rows if isinstance(rows, list) else []
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        clicks = int(r.get("clicks") or 0)
        impressions = int(r.get("impressions") or 0)
        cost = float(r.get("cost") or r.get("spent") or 0)
        ctr = float(r.get("ctr") or 0)
        if not ctr and impressions > 0:
            ctr = round((clicks / impressions) * 100, 2)
        avg_cpc = float(r.get("avg_cpc") or 0)
        if not avg_cpc and clicks > 0:
            avg_cpc = round(cost / clicks, 2)
        out.append({
            "keyword": r.get("keyword") or r.get("text") or "—",
            "match_type": r.get("match_type") or r.get("matchType") or "UNKNOWN",
            "status": r.get("status") or "UNKNOWN",
            "impressions": impressions,
            "clicks": clicks,
            "ctr": round(ctr, 2),
            "avg_cpc": round(avg_cpc, 2),
            "quality_score": int(r.get("quality_score") or r.get("qualityScore") or 0),
            "campaign": r.get("campaign"),
            "ad_group": r.get("adGroup") or r.get("ad_group"),
            "conversions": float(r.get("conversions") or 0),
            "cost": round(cost, 2),
        })
    return out


def _google_ads_map_coolbits_metrics(payload, account_id, days):
    if not isinstance(payload, dict):
        return None
    series_rows = (((payload.get("data") or {}).get("series") or {}).get("daily") or [])
    if not isinstance(series_rows, list):
        series_rows = []
    daily = []
    for r in series_rows:
        if not isinstance(r, dict):
            continue
        impressions = int(r.get("impressions") or 0)
        clicks = int(r.get("clicks") or 0)
        cost = float(r.get("cost") or 0)
        conv_value = float(r.get("convValue") or 0)
        roas = round((conv_value / cost), 2) if cost > 0 else 0
        daily.append({
            "date": r.get("date"),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": int(r.get("conversions") or 0),
            "cost": round(cost, 2),
            "ctr": round((clicks / impressions * 100), 2) if impressions > 0 else 0,
            "avg_cpc": round((cost / clicks), 2) if clicks > 0 else 0,
            "roas": roas,
        })
    if not daily:
        return None
    return {"account_id": account_id, "days": days, "daily_metrics": daily}


def _google_ads_normalize_account_id(raw):
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    if "/" in s:
        m = re.search(r"customers/([0-9\-]+)", s)
        if m:
            s = m.group(1)
    digits = re.sub(r"[^0-9]", "", s)
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return s


def _google_ads_map_accounts(rows):
    rows = rows if isinstance(rows, list) else []
    out = []
    seen = set()
    for r in rows:
        if isinstance(r, str):
            r = {"id": r}
        if not isinstance(r, dict):
            continue
        account_id = _google_ads_normalize_account_id(
            r.get("id")
            or r.get("account_id")
            or r.get("accountId")
            or r.get("customer_id")
            or r.get("customerId")
            or r.get("cid")
            or r.get("resource_name")
            or r.get("resourceName")
        )
        if not account_id:
            continue
        if account_id in seen:
            continue
        seen.add(account_id)

        raw_type = str(r.get("type") or "").strip().upper()
        is_manager = bool(r.get("isManager") or r.get("manager") or r.get("is_manager"))
        if not raw_type:
            raw_type = "MCC" if is_manager else "Client"
        if raw_type in ("MANAGER", "MCC_ACCOUNT", "MCC-ACCOUNT"):
            raw_type = "MCC"
        if raw_type not in ("MCC", "CLIENT"):
            raw_type = "MCC" if is_manager else "Client"
        else:
            raw_type = "MCC" if raw_type == "MCC" else "Client"

        name = (
            r.get("name")
            or r.get("descriptiveName")
            or r.get("customerName")
            or r.get("label")
            or f"Account {account_id}"
        )
        out.append({
            "id": account_id,
            "name": str(name),
            "type": raw_type,
            "currency": str(r.get("currency") or r.get("currencyCode") or "USD"),
            "timezone": str(r.get("timezone") or r.get("timeZone") or "UTC"),
            "parent_mcc": r.get("parent_mcc") or r.get("managerCustomerId") or r.get("manager_id"),
        })
    # Keep clients first (UX), then managers.
    out.sort(key=lambda a: (0 if a.get("type") == "Client" else 1, a.get("name", "")))
    return out


def _google_ads_is_placeholder_account_name(name, account_id):
    n = str(name or "").strip()
    aid = str(account_id or "").strip()
    if not n:
        return True
    if n == aid:
        return True
    if n.lower().startswith("account ") and aid and aid in n:
        return True
    if re.fullmatch(r"[0-9\-]+", n):
        return True
    return False


def _google_ads_extract_account_name_from_report_payload(payload):
    if not isinstance(payload, dict):
        return ""
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    ov = data.get("overview") if isinstance(data.get("overview"), dict) else {}
    candidates = [
        ov.get("account_name"),
        ov.get("accountName"),
        ov.get("customer_name"),
        ov.get("customerName"),
        ov.get("descriptive_name"),
        ov.get("descriptiveName"),
        payload.get("account_name"),
        payload.get("accountName"),
    ]
    for c in candidates:
        s = str(c or "").strip()
        if s:
            return s
    return ""


def _google_ads_enrich_accounts_names(accounts, mcc_id):
    rows = accounts if isinstance(accounts, list) else []
    if not rows:
        return rows
    range_from, range_to = _google_ads_iso_date_window(30)
    out = []
    for a in rows:
        if not isinstance(a, dict):
            continue
        item = dict(a)
        account_id = str(item.get("id") or "").strip()
        if not account_id:
            out.append(item)
            continue
        if not _google_ads_is_placeholder_account_name(item.get("name"), account_id):
            out.append(item)
            continue
        params = _google_ads_attach_mcc_params({
            "account_id": account_id,
            "preset": "overview",
            "from": range_from,
            "to": range_to,
            "blocks": "overview",
        }, mcc_id)
        payload, _gw = _google_ads_gateway_fetch(["/api/connectors/googleads/report"], params=params, timeout=10)
        better_name = _google_ads_extract_account_name_from_report_payload(payload)
        if better_name:
            item["name"] = better_name
        out.append(item)
    return out


def _google_ads_attach_mcc_params(params, mcc_id):
    out = dict(params or {})
    mcc = _google_ads_normalize_account_id(mcc_id)
    if not mcc:
        return out
    mcc_digits = re.sub(r"[^0-9]", "", str(mcc))
    mcc_api = mcc_digits or mcc
    # Keep multiple aliases for compatibility with different gateway handlers.
    out["mcc_id"] = mcc
    out["manager_customer_id"] = mcc_api
    out["login_customer_id"] = mcc_api
    out["managerCustomerId"] = mcc_api
    out["loginCustomerId"] = mcc_api
    out["mcc"] = mcc
    out["mccId"] = mcc
    out["manager_id"] = mcc_api
    out["managerId"] = mcc_api
    out["parent_customer_id"] = mcc_api
    out["parentCustomerId"] = mcc_api
    out["customer_id"] = mcc_api
    out["customerId"] = mcc_api
    out["cid"] = mcc_api
    out["account_id"] = out.get("account_id") or mcc
    out["include_children"] = "1"
    out["children"] = "1"
    out["expand"] = "1"
    out["include_clients"] = "1"
    out["list_children"] = "1"
    return out


def _google_ads_set_active_customer(account_id, mcc_id):
    if not COOLBITS_GATEWAY_ENABLED:
        return {"enabled": False, "reason": "disabled"}
    cid = re.sub(r"[^0-9]", "", str(account_id or ""))
    if not cid:
        return {"enabled": True, "reason": "missing_customer_id"}
    body = {"customerId": cid}
    mcc = re.sub(r"[^0-9]", "", str(mcc_id or ""))
    if mcc:
        body["loginCustomerId"] = int(mcc)
    try:
        status, payload, text = _coolbits_request("POST", "/api/connectors/googleads/customer", body=body, timeout=15)
        if 200 <= int(status) < 300:
            return {"enabled": True, "status": int(status)}
        return {"enabled": True, "status": int(status), "error": (payload or text or "select_customer_failed")}
    except Exception as e:
        return {"enabled": True, "error": str(e)}


def _google_ads_mock_accounts_response():
    return {"accounts": GOOGLE_ADS_MOCK_ACCOUNTS, "source": "mock"}


def _google_ads_mock_campaigns_response(account_id):
    campaigns = GOOGLE_ADS_MOCK_CAMPAIGNS.get(account_id, [])
    return {
        "account_id": account_id,
        "campaigns": campaigns,
        "summary": _google_ads_build_summary(campaigns),
        "source": "mock",
    }


def _google_ads_mock_keywords_response(campaign_id):
    keywords = GOOGLE_ADS_MOCK_KEYWORDS.get(campaign_id, [])
    return {"campaign_id": campaign_id, "keywords": keywords, "source": "mock"}


def _google_ads_mock_metrics_response(account_id, days):
    import random
    from datetime import datetime, timedelta

    random.seed(42)  # Deterministic for consistency
    daily = []
    for i in range(days):
        d = (datetime.now() - timedelta(days=days - 1 - i)).strftime('%Y-%m-%d')
        base_clicks = random.randint(120, 350)
        base_impr = base_clicks * random.randint(15, 25)
        base_conv = int(base_clicks * random.uniform(0.03, 0.08))
        base_cost = round(base_clicks * random.uniform(0.45, 0.85), 2)
        daily.append({
            "date": d,
            "impressions": base_impr,
            "clicks": base_clicks,
            "conversions": base_conv,
            "cost": base_cost,
            "ctr": round(base_clicks / base_impr * 100, 2),
            "avg_cpc": round(base_cost / base_clicks, 2),
            "roas": round(random.uniform(2.5, 5.5), 2)
        })
    return {"account_id": account_id, "days": days, "daily_metrics": daily, "source": "mock"}


@app.route("/api/connectors/google-ads/accounts", methods=["GET"])
def google_ads_accounts():
    """Return Google Ads accounts (Coolbits gateway when enabled, fallback to mock)."""
    mcc_id = request.args.get("mcc_id", "").strip()
    gw_params = _google_ads_attach_mcc_params({}, mcc_id)
    path_candidates = [
        "/api/connectors/googleads/customers",
        "/api/connectors/googleads/clients",
        "/api/google-ads/accounts",
        "/api/connectors/google-ads/accounts",
        "/googleads/accounts",
    ]
    if _google_ads_normalize_account_id(mcc_id):
        path_candidates = ["/api/connectors/googleads/customers/clients"] + path_candidates
    payload, gw = _google_ads_gateway_fetch([
        *path_candidates
    ], params=gw_params or None)
    if payload is not None:
        accounts = _google_ads_list_from_payload(payload, ["accounts", "customers", "clients", "items", "data", "results"])
        mapped_accounts = _google_ads_map_accounts(accounts)
        mapped_accounts = _google_ads_enrich_accounts_names(mapped_accounts, mcc_id)
        if mapped_accounts:
            return jsonify({"accounts": mapped_accounts, "source": "coolbits", "gateway": gw})
    return jsonify(_google_ads_mock_accounts_response())


@app.route("/api/connectors/google-ads/campaigns", methods=["GET"])
def google_ads_campaigns():
    """Return campaigns for an account (Coolbits gateway when enabled, fallback to mock)."""
    account_id = request.args.get('account_id', '123-456-7890')
    mcc_id = request.args.get("mcc_id", "").strip()
    days = request.args.get('days', 30, type=int)
    range_from, range_to = _google_ads_iso_date_window(days)
    _google_ads_set_active_customer(account_id, mcc_id)
    gw_params = _google_ads_attach_mcc_params({
        "account_id": account_id,
        "preset": "campaigns",
        "from": range_from,
        "to": range_to,
        "blocks": "overview,campaigns",
    }, mcc_id)
    payload, gw = _google_ads_gateway_fetch([
        "/api/connectors/googleads/report",
        "/api/google-ads/campaigns",
        "/api/connectors/google-ads/campaigns",
        "/googleads/campaigns",
    ], params=gw_params)
    if payload is not None:
        if isinstance(payload, dict):
            cb_rows = (((payload.get("data") or {}).get("campaigns") or {}).get("rows") or [])
            campaigns = _google_ads_map_coolbits_campaigns(cb_rows)
            if campaigns:
                return jsonify({
                    "account_id": account_id,
                    "campaigns": campaigns,
                    "summary": _google_ads_build_summary(campaigns),
                    "source": "coolbits",
                    "gateway": gw,
                })
        if isinstance(payload, dict) and isinstance(payload.get("campaigns"), list):
            out = dict(payload)
            out.setdefault("account_id", account_id)
            out.setdefault("summary", _google_ads_build_summary(out.get("campaigns") or []))
            out["source"] = "coolbits"
            out["gateway"] = gw
            return jsonify(out)
        campaigns = _google_ads_list_from_payload(payload, ["campaigns", "items", "data", "results"])
        if campaigns:
            return jsonify({
                "account_id": account_id,
                "campaigns": campaigns,
                "summary": _google_ads_build_summary(campaigns),
                "source": "coolbits",
                "gateway": gw,
            })
    return jsonify(_google_ads_mock_campaigns_response(account_id))


@app.route("/api/connectors/google-ads/keywords", methods=["GET"])
def google_ads_keywords():
    """Return keywords for a campaign (Coolbits gateway when enabled, fallback to mock)."""
    campaign_id = request.args.get('campaign_id', 'c-1001')
    account_id = request.args.get('account_id', '').strip()
    mcc_id = request.args.get("mcc_id", "").strip()
    range_from, range_to = _google_ads_iso_date_window(30)
    if account_id:
        _google_ads_set_active_customer(account_id, mcc_id)
    gw_params = _google_ads_attach_mcc_params({
        "campaign_id": campaign_id,
        "preset": "keywords",
        "from": range_from,
        "to": range_to,
        "blocks": "overview,keywords",
    }, mcc_id)
    payload, gw = _google_ads_gateway_fetch([
        "/api/connectors/googleads/report",
        "/api/google-ads/keywords",
        "/api/connectors/google-ads/keywords",
        "/googleads/keywords",
    ], params=gw_params)
    if payload is not None:
        if isinstance(payload, dict):
            cb_rows = (((payload.get("data") or {}).get("keywords") or {}).get("rows") or [])
            keywords = _google_ads_map_coolbits_keywords(cb_rows)
            if keywords:
                return jsonify({
                    "campaign_id": campaign_id,
                    "keywords": keywords,
                    "source": "coolbits",
                    "gateway": gw,
                })
        if isinstance(payload, dict) and isinstance(payload.get("keywords"), list):
            out = dict(payload)
            out.setdefault("campaign_id", campaign_id)
            out["source"] = "coolbits"
            out["gateway"] = gw
            return jsonify(out)
        keywords = _google_ads_list_from_payload(payload, ["keywords", "items", "data", "results"])
        if keywords:
            return jsonify({
                "campaign_id": campaign_id,
                "keywords": keywords,
                "source": "coolbits",
                "gateway": gw,
            })
    return jsonify(_google_ads_mock_keywords_response(campaign_id))


@app.route("/api/connectors/google-ads/metrics", methods=["GET"])
def google_ads_metrics():
    """Return performance metrics (Coolbits gateway when enabled, fallback to mock)."""
    account_id = request.args.get('account_id', '123-456-7890')
    days = request.args.get('days', 30, type=int)
    mcc_id = request.args.get("mcc_id", "").strip()
    _google_ads_set_active_customer(account_id, mcc_id)
    range_from, range_to = _google_ads_iso_date_window(days)
    gw_params = _google_ads_attach_mcc_params({
        "account_id": account_id,
        "days": days,
        "from": range_from,
        "to": range_to,
        "blocks": "overview,series",
    }, mcc_id)
    payload, gw = _google_ads_gateway_fetch([
        "/api/connectors/googleads/report",
        "/api/connectors/googleads/summary",
        "/api/google-ads/metrics",
        "/api/connectors/google-ads/metrics",
        "/googleads/metrics",
    ], params=gw_params)
    if payload is not None:
        mapped = _google_ads_map_coolbits_metrics(payload, account_id, days)
        if mapped:
            mapped["source"] = "coolbits"
            mapped["gateway"] = gw
            return jsonify(mapped)
        if isinstance(payload, dict) and isinstance(payload.get("daily_metrics"), list):
            out = dict(payload)
            out.setdefault("account_id", account_id)
            out.setdefault("days", days)
            out["source"] = "coolbits"
            out["gateway"] = gw
            return jsonify(out)
        daily = _google_ads_list_from_payload(payload, ["daily_metrics", "timeseries", "rows", "data", "results"])
        if daily:
            return jsonify({
                "account_id": account_id,
                "days": days,
                "daily_metrics": daily,
                "source": "coolbits",
                "gateway": gw,
            })
    return jsonify(_google_ads_mock_metrics_response(account_id, days))


@app.route("/api/connectors/google-ads/generate-assets", methods=["POST"])
def google_ads_generate_assets():
    """Generate mock RSA headlines and descriptions"""
    data = request.get_json(force=True, silent=True) or {}
    product = data.get('product', 'Premium Product')
    tone = data.get('tone', 'professional')
    language = data.get('language', 'en')

    # Generate mock assets based on inputs
    headlines_pool = {
        'professional': [
            f"Premium {product} — Shop Now",
            f"Trusted {product} Provider",
            f"Get the Best {product} Deals",
            f"Top-Rated {product} Online",
            f"{product} — Free Shipping Today",
            f"Save Big on {product}",
            f"Expert {product} Solutions",
            f"Discover {product} Quality",
            f"Official {product} Store",
            f"#{product.replace(' ', '')} — Order Today",
            f"Best Price on {product}",
            f"New {product} Collection 2024",
            f"Limited Offer — {product}",
            f"{product} for Every Budget",
            f"Why Choose Our {product}?",
        ],
        'casual': [
            f"🔥 {product} Deals You'll Love",
            f"Hey! Check Out Our {product}",
            f"Your New Fave {product} Awaits",
            f"Grab Amazing {product} Now",
            f"{product}? We've Got You!",
            f"Score Big on {product} 🎯",
            f"Don't Miss This {product} Deal",
            f"Level Up With {product}",
            f"Finally — {product} Done Right",
            f"Best {product} Ever? Maybe! 😊",
            f"You + {product} = 💯",
            f"Treat Yourself: {product}",
            f"Fresh {product} Just Dropped",
            f"Shop {product} Like a Pro",
            f"Loving {product}? Us Too!",
        ],
        'urgent': [
            f"⚡ {product} — Last Chance!",
            f"HURRY: {product} Almost Gone",
            f"24h Only — {product} Sale",
            f"Don't Wait — {product} Sells Fast",
            f"Final Hours: {product} Offer",
            f"Act Now — {product} Deal Ends",
            f"🚨 {product} Clearance Event",
            f"Only 3 Left — {product}",
            f"Flash Sale: {product} -50%",
            f"Expires Tonight — {product}",
            f"Rush: {product} Going Fast",
            f"NOW or Never — {product}!",
            f"Limited Stock: {product}",
            f"Today Only: {product} Deals",
            f"⏰ {product} Timer Running Out",
        ]
    }
    descriptions_pool = [
        f"Shop our premium selection of {product} with free shipping on orders over $50. Trusted by thousands of happy customers. Satisfaction guaranteed or your money back.",
        f"Discover why {product} from our store is rated #1 by experts. Wide selection, competitive pricing, and lightning-fast delivery to your door.",
        f"Looking for the best {product}? Browse our curated collection featuring top brands, exclusive deals, and hassle-free returns within 30 days.",
        f"Upgrade your experience with our premium {product}. Join 10,000+ satisfied customers who chose quality. Order today and see the difference.",
        f"Get {product} delivered in 2 business days. Our expert team hand-picks every item for quality. New customers get 15% off their first order!",
    ]

    selected_headlines = headlines_pool.get(tone, headlines_pool['professional'])[:15]
    selected_descriptions = descriptions_pool[:5]

    # Validate char limits like real Google Ads
    validated_headlines = []
    for h in selected_headlines:
        status = "✅ OK" if len(h) <= 30 else f"⚠️ {len(h)}/30 chars"
        validated_headlines.append({"text": h, "chars": len(h), "limit": 30, "status": status})

    validated_descriptions = []
    for d in selected_descriptions:
        status = "✅ OK" if len(d) <= 90 else f"⚠️ {len(d)}/90 chars"
        validated_descriptions.append({"text": d, "chars": len(d), "limit": 90, "status": status})

    return jsonify({
        "product": product,
        "tone": tone,
        "language": language,
        "headlines": validated_headlines,
        "descriptions": validated_descriptions,
        "rsa_preview": {
            "headline_1": selected_headlines[0] if selected_headlines else "",
            "headline_2": selected_headlines[1] if len(selected_headlines) > 1 else "",
            "headline_3": selected_headlines[2] if len(selected_headlines) > 2 else "",
            "description_1": descriptions_pool[0] if descriptions_pool else "",
            "description_2": descriptions_pool[1] if len(descriptions_pool) > 1 else "",
        }
    })


@app.route("/api/connectors/google-ads/reports", methods=["GET"])
def google_ads_reports():
    """Return report data (Coolbits real when available, fallback to mock)."""
    account_id = request.args.get('account_id', '123-456-7890')
    report_type = request.args.get('type', 'campaign_performance')
    days = request.args.get('days', 30, type=int)
    mcc_id = request.args.get("mcc_id", "").strip()
    _google_ads_set_active_customer(account_id, mcc_id)

    range_from, range_to = _google_ads_iso_date_window(days)
    gw_params = _google_ads_attach_mcc_params({
        "account_id": account_id,
        "preset": "campaigns",
        "from": range_from,
        "to": range_to,
        "blocks": "overview,campaigns",
    }, mcc_id)
    payload, gw = _google_ads_gateway_fetch([
        "/api/connectors/googleads/report",
    ], params=gw_params)

    if payload is not None and isinstance(payload, dict):
        cb_rows = (((payload.get("data") or {}).get("campaigns") or {}).get("rows") or [])
        campaigns_real = _google_ads_map_coolbits_campaigns(cb_rows)
        if campaigns_real:
            generated = __import__('datetime').datetime.now().isoformat()
            if report_type == 'campaign_performance':
                rows = []
                for c in campaigns_real:
                    rows.append({
                        "Campaign": c['name'],
                        "Status": c['status'],
                        "Type": c['type'],
                        "Impressions": f"{c['impressions']:,}",
                        "Clicks": f"{c['clicks']:,}",
                        "CTR": f"{c['ctr']}%",
                        "Avg CPC": f"${c['avg_cpc']:.2f}",
                        "Cost": f"${c['spent']:,.2f}",
                        "Conversions": c['conversions'],
                        "Cost/Conv": f"${c['cost_per_conv']:.2f}",
                        "ROAS": f"{c['roas']}x"
                    })
                return jsonify({
                    "report_type": report_type,
                    "rows": rows,
                    "generated_at": generated,
                    "source": "coolbits",
                    "gateway": gw,
                })

            if report_type == 'budget_pacing':
                rows = []
                for c in campaigns_real:
                    budget_total = float(c.get('budget_total') or 0)
                    spent = float(c.get('spent') or 0)
                    budget_daily = float(c.get('budget_daily') or 0)
                    pct = round(spent / budget_total * 100, 1) if budget_total > 0 else 0
                    days_left = max(1, int((budget_total - spent) / budget_daily)) if (c.get('status') == 'ENABLED' and budget_daily > 0 and budget_total > spent) else 0
                    rows.append({
                        "Campaign": c['name'],
                        "Daily Budget": f"${budget_daily:.2f}",
                        "Total Budget": f"${budget_total:,.2f}",
                        "Spent": f"${spent:,.2f}",
                        "Remaining": f"${max(0, budget_total - spent):,.2f}",
                        "Utilization": f"{pct}%",
                        "Est. Days Left": days_left,
                        "Status": "🟢 On Track" if pct < 80 else ("🟡 Warning" if pct < 95 else "🔴 Over Budget")
                    })
                return jsonify({
                    "report_type": report_type,
                    "rows": rows,
                    "generated_at": generated,
                    "source": "coolbits",
                    "gateway": gw,
                })

    campaigns = GOOGLE_ADS_MOCK_CAMPAIGNS.get(account_id, [])

    if report_type == 'campaign_performance':
        rows = []
        for c in campaigns:
            rows.append({
                "Campaign": c['name'],
                "Status": c['status'],
                "Type": c['type'],
                "Impressions": f"{c['impressions']:,}",
                "Clicks": f"{c['clicks']:,}",
                "CTR": f"{c['ctr']}%",
                "Avg CPC": f"${c['avg_cpc']:.2f}",
                "Cost": f"${c['spent']:,.2f}",
                "Conversions": c['conversions'],
                "Cost/Conv": f"${c['cost_per_conv']:.2f}",
                "ROAS": f"{c['roas']}x"
            })
        return jsonify({"report_type": report_type, "rows": rows, "generated_at": __import__('datetime').datetime.now().isoformat()})

    elif report_type == 'budget_pacing':
        rows = []
        for c in campaigns:
            pct = round(c['spent'] / c['budget_total'] * 100, 1)
            days_left = max(1, int((c['budget_total'] - c['spent']) / c['budget_daily'])) if c['status'] == 'ENABLED' else 0
            rows.append({
                "Campaign": c['name'],
                "Daily Budget": f"${c['budget_daily']:.2f}",
                "Total Budget": f"${c['budget_total']:,.2f}",
                "Spent": f"${c['spent']:,.2f}",
                "Remaining": f"${c['budget_total'] - c['spent']:,.2f}",
                "Utilization": f"{pct}%",
                "Est. Days Left": days_left,
                "Status": "🟢 On Track" if pct < 80 else ("🟡 Warning" if pct < 95 else "🔴 Over Budget")
            })
        return jsonify({"report_type": report_type, "rows": rows, "generated_at": __import__('datetime').datetime.now().isoformat()})

    return jsonify({"report_type": report_type, "rows": [], "message": "Unknown report type"})


@app.route("/api/connectors/google-ads/test-call", methods=["POST"])
def google_ads_test_call():
    """Simulate a Google Ads API call with realistic response"""
    data = request.get_json(force=True, silent=True) or {}
    endpoint = data.get('endpoint', '/v17/customers/123456/campaigns')
    method = data.get('method', 'GET')

    import time
    start = time.time()

    # Simulate API response based on endpoint pattern
    if 'campaigns' in endpoint:
        response_body = {
            "results": [
                {"campaign": {"resourceName": "customers/123456/campaigns/1001", "name": "Summer Sale RO", "status": "ENABLED", "advertisingChannelType": "SEARCH"}},
                {"campaign": {"resourceName": "customers/123456/campaigns/1002", "name": "Brand Awareness Display", "status": "PAUSED", "advertisingChannelType": "DISPLAY"}},
            ],
            "totalResultsCount": "5",
            "fieldMask": "campaign.name,campaign.status,campaign.advertisingChannelType"
        }
    elif 'adGroups' in endpoint or 'ad_groups' in endpoint:
        response_body = {
            "results": [
                {"adGroup": {"resourceName": "customers/123456/adGroups/2001", "name": "Ad Group - Exact Match", "status": "ENABLED", "cpcBidMicros": "750000"}},
                {"adGroup": {"resourceName": "customers/123456/adGroups/2002", "name": "Ad Group - Broad Match", "status": "ENABLED", "cpcBidMicros": "650000"}},
            ],
            "totalResultsCount": "2"
        }
    elif 'keywords' in endpoint:
        response_body = {
            "results": [
                {"adGroupCriterion": {"keyword": {"text": "magazin online romania", "matchType": "BROAD"}, "status": "ENABLED", "qualityInfo": {"qualityScore": 8}}},
            ],
            "totalResultsCount": "5"
        }
    elif 'metrics' in endpoint or 'report' in endpoint:
        response_body = {
            "results": [
                {"metrics": {"impressions": "87432", "clicks": "4567", "conversions": "189", "costMicros": "3212450000", "ctr": "0.0522", "averageCpc": "703421"}},
            ]
        }
    else:
        response_body = {"results": [], "totalResultsCount": "0", "requestId": "mock-req-" + str(int(time.time()))}

    elapsed = round((time.time() - start) * 1000 + 127, 0)  # Add simulated latency

    return jsonify({
        "request": {
            "method": method,
            "endpoint": endpoint,
            "headers": {
                "Authorization": "Bearer ya29.a0A...mock_token",
                "developer-token": "MOCK_DEV_TOKEN_xxxxx",
                "login-customer-id": "000-111-2222",
                "Content-Type": "application/json"
            }
        },
        "response": {
            "status_code": 200,
            "headers": {
                "x-goog-request-id": f"mock-{int(time.time())}",
                "content-type": "application/json"
            },
            "body": response_body
        },
        "latency_ms": elapsed,
        "quota": {"operations_remaining": 14567, "daily_limit": 15000}
    })


# ─── GA4 Mock API ────────────────────────────────────────────────────────────
GA4_MOCK_PROPERTIES = [
    {"id": "G-ABC123DEF4", "name": "Main Website — camarad.ai", "stream": "Web", "url": "https://camarad.ai", "timezone": "Europe/Bucharest", "currency": "USD", "created": "2024-03-15"},
    {"id": "G-MOB987XYZ1", "name": "Mobile App — Camarad iOS/Android", "stream": "iOS + Android", "url": "camarad://app", "timezone": "Europe/Bucharest", "currency": "USD", "created": "2024-06-01"},
    {"id": "G-BLG456QWE7", "name": "Blog — blog.camarad.ai", "stream": "Web", "url": "https://blog.camarad.ai", "timezone": "Europe/Bucharest", "currency": "USD", "created": "2025-01-10"},
]

GA4_MOCK_OVERVIEW = {
    "G-ABC123DEF4": {
        "sessions": 8923, "users": 6124, "new_users": 3891, "active_users": 4567,
        "avg_engagement_time": "1m 48s", "engagement_rate": "62.3%",
        "bounce_rate": "42.1%", "conversions": 590, "event_count": 47823,
        "sessions_per_user": 1.46, "views_per_session": 2.34,
        "revenue": 14567.89,
        "comparison": {"sessions": "+12.4%", "users": "+8.7%", "conversions": "+23.1%", "revenue": "+18.6%"}
    },
    "G-MOB987XYZ1": {
        "sessions": 4210, "users": 3456, "new_users": 1987, "active_users": 2890,
        "avg_engagement_time": "3m 12s", "engagement_rate": "78.9%",
        "bounce_rate": "21.5%", "conversions": 312, "event_count": 28901,
        "sessions_per_user": 1.22, "views_per_session": 4.56,
        "revenue": 8234.50,
        "comparison": {"sessions": "+5.2%", "users": "+3.1%", "conversions": "+15.8%", "revenue": "+9.4%"}
    },
    "G-BLG456QWE7": {
        "sessions": 2345, "users": 1987, "new_users": 1654, "active_users": 1234,
        "avg_engagement_time": "2m 34s", "engagement_rate": "55.6%",
        "bounce_rate": "48.7%", "conversions": 89, "event_count": 12345,
        "sessions_per_user": 1.18, "views_per_session": 1.87,
        "revenue": 2345.00,
        "comparison": {"sessions": "+34.5%", "users": "+28.9%", "conversions": "+67.2%", "revenue": "+45.1%"}
    },
}

GA4_MOCK_TOP_PAGES = {
    "G-ABC123DEF4": [
        {"path": "/", "title": "Home — Camarad AI", "views": 3456, "sessions": 3201, "users": 2890, "avg_time": "0m 52s", "bounce_rate": "38.2%", "conversions": 67},
        {"path": "/product", "title": "Product Features", "views": 2845, "sessions": 1847, "users": 1654, "avg_time": "2m 15s", "bounce_rate": "31.6%", "conversions": 134},
        {"path": "/pricing", "title": "Pricing Plans", "views": 2190, "sessions": 1567, "users": 1432, "avg_time": "1m 43s", "bounce_rate": "25.8%", "conversions": 189},
        {"path": "/blog", "title": "Blog & Resources", "views": 1823, "sessions": 1123, "users": 987, "avg_time": "3m 21s", "bounce_rate": "29.8%", "conversions": 23},
        {"path": "/about", "title": "About Us", "views": 1234, "sessions": 890, "users": 812, "avg_time": "1m 08s", "bounce_rate": "52.1%", "conversions": 12},
        {"path": "/contact", "title": "Contact", "views": 987, "sessions": 756, "users": 698, "avg_time": "1m 32s", "bounce_rate": "35.4%", "conversions": 45},
        {"path": "/demo", "title": "Request Demo", "views": 876, "sessions": 654, "users": 598, "avg_time": "4m 12s", "bounce_rate": "18.9%", "conversions": 87},
        {"path": "/docs", "title": "Documentation", "views": 654, "sessions": 543, "users": 487, "avg_time": "5m 45s", "bounce_rate": "22.3%", "conversions": 8},
    ],
    "G-MOB987XYZ1": [
        {"path": "/home", "title": "App Home", "views": 4567, "sessions": 2100, "users": 1890, "avg_time": "1m 20s", "bounce_rate": "15.2%", "conversions": 89},
        {"path": "/dashboard", "title": "Dashboard", "views": 3456, "sessions": 1800, "users": 1654, "avg_time": "4m 30s", "bounce_rate": "8.7%", "conversions": 123},
        {"path": "/chat", "title": "AI Chat", "views": 2890, "sessions": 1500, "users": 1234, "avg_time": "6m 15s", "bounce_rate": "5.3%", "conversions": 67},
    ],
    "G-BLG456QWE7": [
        {"path": "/ai-marketing-guide", "title": "AI Marketing Guide 2026", "views": 1234, "sessions": 890, "users": 765, "avg_time": "4m 56s", "bounce_rate": "32.1%", "conversions": 34},
        {"path": "/ppc-automation", "title": "PPC Automation Tips", "views": 876, "sessions": 654, "users": 543, "avg_time": "3m 42s", "bounce_rate": "38.7%", "conversions": 21},
        {"path": "/seo-vs-ppc", "title": "SEO vs PPC in 2026", "views": 654, "sessions": 432, "users": 398, "avg_time": "5m 12s", "bounce_rate": "28.9%", "conversions": 12},
    ],
}

GA4_MOCK_SOURCES = {
    "G-ABC123DEF4": [
        {"source": "google", "medium": "organic", "sessions": 4210, "users": 3456, "conversions": 234, "revenue": 6789.50, "bounce_rate": "38.2%"},
        {"source": "(direct)", "medium": "(none)", "sessions": 1987, "users": 1654, "conversions": 156, "revenue": 4567.20, "bounce_rate": "35.6%"},
        {"source": "google", "medium": "cpc", "sessions": 1234, "users": 1098, "conversions": 112, "revenue": 2345.80, "bounce_rate": "32.1%"},
        {"source": "facebook", "medium": "referral", "sessions": 876, "users": 765, "conversions": 45, "revenue": 890.30, "bounce_rate": "52.3%"},
        {"source": "linkedin", "medium": "social", "sessions": 543, "users": 432, "conversions": 34, "revenue": 567.40, "bounce_rate": "41.8%"},
        {"source": "newsletter", "medium": "email", "sessions": 432, "users": 398, "conversions": 28, "revenue": 345.60, "bounce_rate": "28.9%"},
        {"source": "twitter", "medium": "social", "sessions": 234, "users": 198, "conversions": 12, "revenue": 123.40, "bounce_rate": "55.7%"},
        {"source": "bing", "medium": "organic", "sessions": 189, "users": 167, "conversions": 8, "revenue": 98.50, "bounce_rate": "44.2%"},
    ],
}

GA4_MOCK_EVENTS = {
    "G-ABC123DEF4": [
        {"name": "page_view", "count": 23456, "users": 5890, "per_session": 2.63, "category": "Auto"},
        {"name": "scroll", "count": 12890, "users": 4567, "per_session": 1.44, "category": "Auto"},
        {"name": "click", "count": 8765, "users": 3456, "per_session": 0.98, "category": "Auto"},
        {"name": "session_start", "count": 8923, "users": 6124, "per_session": 1.0, "category": "Auto"},
        {"name": "first_visit", "count": 3891, "users": 3891, "per_session": 0.44, "category": "Auto"},
        {"name": "purchase", "count": 590, "users": 487, "per_session": 0.07, "category": "Ecommerce", "value": 14567.89},
        {"name": "add_to_cart", "count": 1456, "users": 1123, "per_session": 0.16, "category": "Ecommerce", "value": 34567.20},
        {"name": "begin_checkout", "count": 876, "users": 765, "per_session": 0.10, "category": "Ecommerce", "value": 23456.50},
        {"name": "view_item", "count": 4567, "users": 2890, "per_session": 0.51, "category": "Ecommerce"},
        {"name": "sign_up", "count": 345, "users": 345, "per_session": 0.04, "category": "Custom"},
        {"name": "generate_lead", "count": 234, "users": 212, "per_session": 0.03, "category": "Custom"},
        {"name": "share", "count": 187, "users": 154, "per_session": 0.02, "category": "Custom"},
        {"name": "video_start", "count": 567, "users": 432, "per_session": 0.06, "category": "Custom"},
        {"name": "video_complete", "count": 234, "users": 198, "per_session": 0.03, "category": "Custom"},
        {"name": "file_download", "count": 123, "users": 109, "per_session": 0.01, "category": "Custom"},
    ],
}

GA4_MOCK_DEVICES = {
    "G-ABC123DEF4": [
        {"category": "desktop", "sessions": 5234, "users": 3890, "conversions": 389, "bounce_rate": "39.2%", "pct": 58.7},
        {"category": "mobile", "sessions": 2987, "users": 1876, "conversions": 156, "bounce_rate": "48.5%", "pct": 33.5},
        {"category": "tablet", "sessions": 702, "users": 358, "conversions": 45, "bounce_rate": "44.1%", "pct": 7.8},
    ],
}

GA4_MOCK_COUNTRIES = {
    "G-ABC123DEF4": [
        {"country": "Romania", "code": "RO", "sessions": 4567, "users": 3456, "conversions": 312, "revenue": 8765.40, "pct": 51.2},
        {"country": "United States", "code": "US", "sessions": 1234, "users": 987, "conversions": 89, "revenue": 2345.60, "pct": 13.8},
        {"country": "Germany", "code": "DE", "sessions": 876, "users": 654, "conversions": 56, "revenue": 1234.50, "pct": 9.8},
        {"country": "United Kingdom", "code": "GB", "sessions": 654, "users": 543, "conversions": 43, "revenue": 987.30, "pct": 7.3},
        {"country": "France", "code": "FR", "sessions": 432, "users": 345, "conversions": 28, "revenue": 567.20, "pct": 4.8},
        {"country": "Netherlands", "code": "NL", "sessions": 345, "users": 287, "conversions": 21, "revenue": 432.10, "pct": 3.9},
        {"country": "Italy", "code": "IT", "sessions": 234, "users": 198, "conversions": 15, "revenue": 298.40, "pct": 2.6},
        {"country": "Spain", "code": "ES", "sessions": 198, "users": 167, "conversions": 12, "revenue": 234.50, "pct": 2.2},
    ],
}

GA4_MOCK_FUNNELS = {
    "ecommerce": {
        "name": "E-commerce Purchase Funnel",
        "steps": [
            {"name": "View Item", "event": "view_item", "users": 2890, "pct": 100},
            {"name": "Add to Cart", "event": "add_to_cart", "users": 1123, "pct": 38.9, "drop_off": 61.1},
            {"name": "Begin Checkout", "event": "begin_checkout", "users": 765, "pct": 26.5, "drop_off": 31.9},
            {"name": "Purchase", "event": "purchase", "users": 487, "pct": 16.9, "drop_off": 36.3},
        ],
        "overall_conversion": "16.9%"
    },
    "lead_gen": {
        "name": "Lead Generation Funnel",
        "steps": [
            {"name": "Page View", "event": "page_view", "users": 5890, "pct": 100},
            {"name": "Sign Up", "event": "sign_up", "users": 345, "pct": 5.9, "drop_off": 94.1},
            {"name": "Generate Lead", "event": "generate_lead", "users": 234, "pct": 4.0, "drop_off": 32.2},
            {"name": "Purchase", "event": "purchase", "users": 487, "pct": 8.3, "drop_off": 0},
        ],
        "overall_conversion": "4.0%"
    },
}


def _ga4_gateway_fetch(path_candidates, params=None, timeout=30):
    if not COOLBITS_GATEWAY_ENABLED:
        return None, {"enabled": False, "reason": "disabled"}

    last_error = None
    for path in path_candidates:
        try:
            status, payload, text = _coolbits_request("GET", path, params=params, timeout=timeout)
            if 200 <= int(status) < 300:
                return payload, {"enabled": True, "path": path, "status": int(status)}
            if int(status) in (400, 401, 403) and isinstance(payload, dict):
                err_code = str(payload.get("error") or "").strip().lower()
                if err_code in ("not_connected", "property_not_set", "missing_refresh_token", "invalid_property"):
                    return payload, {"enabled": True, "path": path, "status": int(status), "error": err_code}
            last_error = f"{path} -> HTTP {status}"
            if payload is None and text:
                last_error += f" ({text[:180]})"
        except Exception as e:
            last_error = f"{path} -> {e}"
    return None, {"enabled": True, "error": last_error or "gateway_unavailable"}


def _ga4_callback_url():
    host = str(request.host or "").strip()
    if host:
        return f"{request.scheme}://{host}/api/connectors/ga4/oauth/callback"
    return "https://camarad.ai/api/connectors/ga4/oauth/callback"


def _ga4_rewrite_auth_url(raw_url):
    raw = str(raw_url or "").strip()
    if not raw:
        return raw
    try:
        parts = list(urlparse(raw))
        query = dict(parse_qsl(parts[4], keep_blank_values=True))
        query["redirect_uri"] = _ga4_callback_url()
        parts[4] = urlencode(query, doseq=True)
        return urlunparse(parts)
    except Exception:
        return raw


def _ensure_oauth_states_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS oauth_states (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            state TEXT NOT NULL,
            user_id INTEGER,
            workspace_id TEXT,
            redirect_uri TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL,
            used_at TEXT,
            meta_json TEXT
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_oauth_states_provider_state
        ON oauth_states(provider, state)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_oauth_states_provider_expires
        ON oauth_states(provider, expires_at)
    """)
    conn.commit()


def _ga4_store_oauth_state(state_value, user_id=None, workspace_id=None, redirect_uri=None, meta=None):
    state_value = str(state_value or "").strip()
    if not state_value:
        return False
    conn = get_db()
    try:
        _ensure_oauth_states_table(conn)
        conn.execute("""
            INSERT OR REPLACE INTO oauth_states
            (provider, state, user_id, workspace_id, redirect_uri, expires_at, meta_json)
            VALUES ('ga4', ?, ?, ?, ?, datetime('now', ?), ?)
        """, (
            state_value,
            int(user_id) if user_id is not None else None,
            str(workspace_id or "") or None,
            str(redirect_uri or "") or None,
            f"+{max(60, int(GA4_OAUTH_STATE_TTL_SECONDS))} seconds",
            json.dumps(meta or {}, ensure_ascii=False),
        ))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def _ga4_validate_oauth_state(state_value):
    state_value = str(state_value or "").strip()
    if not state_value:
        return False, "missing_state", None
    conn = get_db()
    try:
        _ensure_oauth_states_table(conn)
        row = conn.execute("""
            SELECT id, state, created_at, expires_at, used_at, redirect_uri, meta_json
            FROM oauth_states
            WHERE provider = 'ga4' AND state = ?
            LIMIT 1
        """, (state_value,)).fetchone()
        if not row:
            return False, "state_not_found", None
        if row["used_at"]:
            return False, "state_already_used", row
        exp = str(row["expires_at"] or "")
        now_row = conn.execute("SELECT datetime('now') AS now_utc").fetchone()
        now_utc = str((now_row or {}).get("now_utc") if isinstance(now_row, dict) else (now_row["now_utc"] if now_row else ""))
        if exp and now_utc and exp < now_utc:
            return False, "state_expired", row
        return True, "ok", row
    except Exception:
        return False, "state_validation_error", None
    finally:
        conn.close()


def _ga4_mark_oauth_state_used(state_value):
    state_value = str(state_value or "").strip()
    if not state_value:
        return
    conn = get_db()
    try:
        _ensure_oauth_states_table(conn)
        conn.execute("""
            UPDATE oauth_states
            SET used_at = datetime('now')
            WHERE provider = 'ga4' AND state = ? AND used_at IS NULL
        """, (state_value,))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def _ga4_oauth_states_cleanup(max_rows=500):
    conn = get_db()
    try:
        _ensure_oauth_states_table(conn)
        # Keep cleanup bounded for safety on hot paths.
        conn.execute(
            """
            DELETE FROM oauth_states
            WHERE id IN (
                SELECT id FROM oauth_states
                WHERE provider = 'ga4'
                  AND (
                    expires_at < datetime('now')
                    OR (used_at IS NOT NULL AND used_at < datetime('now', '-1 day'))
                  )
                ORDER BY id ASC
                LIMIT ?
            )
            """,
            (int(max(1, min(5000, max_rows))),),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def _ga4_popup_html(ok, message="", details=None):
    status = "success" if ok else "error"
    payload = {
        "source": "camarad-ga4-oauth",
        "provider": "ga4",
        "ok": bool(ok),
        "status": status,
        "message": str(message or ("GA4 connected." if ok else "GA4 OAuth failed.")),
        "details": details if isinstance(details, dict) else {},
    }
    payload_json = json.dumps(payload, ensure_ascii=False)
    title = "GA4 Connected" if ok else "GA4 OAuth Error"
    body_msg = payload["message"]
    html = f"""<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{title}</title>
  <style>
    body {{ font-family: Inter,system-ui,sans-serif; background:#050b16; color:#d9e8ff; display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; }}
    .box {{ border:1px solid #264466; background:#0b1830; border-radius:12px; padding:20px; width:min(92vw,460px); }}
    .ok {{ color:#2dd4bf; }} .err {{ color:#f87171; }}
    code {{ color:#8ec5ff; }}
  </style>
</head><body>
  <div class="box">
    <h2 class="{ 'ok' if ok else 'err' }">{title}</h2>
    <p>{body_msg}</p>
    <p style="font-size:12px;opacity:.8">You can close this window.</p>
  </div>
  <script>
    (function() {{
      var payload = {payload_json};
      try {{
        if (window.opener && !window.opener.closed) {{
          window.opener.postMessage(payload, window.location.origin);
        }}
      }} catch (e) {{}}
      setTimeout(function() {{
        try {{ window.close(); }} catch (e) {{}}
      }}, 120);
    }})();
  </script>
</body></html>"""
    resp = make_response(html, 200 if ok else 400)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _ga4_pick_property_id():
    requested = str(request.args.get("property_id") or "").strip()
    if requested:
        return requested
    if COOLBITS_GATEWAY_ENABLED:
        payload, _gw = _ga4_gateway_fetch(["/api/connectors/ga4/status"], timeout=10)
        if isinstance(payload, dict):
            selected = str(payload.get("selectedPropertyId") or payload.get("propertyId") or payload.get("activePropertyId") or "").strip()
            if selected:
                return selected
    try:
        local = connector_config("ga4").get_json(silent=True) if request.method == "GET" else {}
        cfg = (local or {}).get("config") if isinstance(local, dict) else {}
        if isinstance(cfg, dict):
            selected = str(cfg.get("property_id") or cfg.get("propertyId") or "").strip()
            if selected:
                return selected
    except Exception:
        pass
    return "G-ABC123DEF4"


def _ga4_resolve_range_args(args):
    from datetime import datetime, timedelta

    range_raw = str(args.get("range") or "").strip().lower()
    days = args.get("days", type=int)
    if not days:
        if range_raw in ("7days", "7", "last_7_days"):
            days = 7
        elif range_raw in ("14days", "14", "last_14_days"):
            days = 14
        elif range_raw in ("30days", "30", "last_30_days"):
            days = 30
        elif range_raw in ("60days", "60", "last_60_days"):
            days = 60
        elif range_raw in ("90days", "90", "last_90_days"):
            days = 90
        else:
            days = 30
    days = max(1, min(365, int(days)))

    date_to = str(args.get("to") or "").strip()
    date_from = str(args.get("from") or "").strip()
    if not date_to or not date_from:
        end_dt = datetime.utcnow().date() - timedelta(days=1)
        start_dt = end_dt - timedelta(days=days - 1)
        date_to = end_dt.strftime("%Y-%m-%d")
        date_from = start_dt.strftime("%Y-%m-%d")

    if days <= 7:
        date_range = "last_7_days"
    else:
        date_range = "last_30_days"

    return {"days": days, "from": date_from, "to": date_to, "dateRange": date_range}


def _ga4_to_num(v, default=0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def _ga4_pct_str(num):
    try:
        n = float(num)
        return f"{round(n * 100, 1)}%"
    except Exception:
        return None


def _ga4_delta_str(v):
    if v is None:
        return None
    try:
        val = float(v)
        return f"{'+' if val >= 0 else ''}{round(val, 1)}%"
    except Exception:
        return None


def _ga4_normalize_properties(payload):
    rows = []
    if isinstance(payload, dict):
        rows = payload.get("properties") if isinstance(payload.get("properties"), list) else []
    elif isinstance(payload, list):
        rows = payload
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        prop_id = str(row.get("propertyId") or row.get("id") or "").strip()
        if not prop_id:
            continue
        out.append({
            "id": prop_id,
            "name": str(row.get("displayName") or row.get("name") or prop_id),
            "stream": str(row.get("stream") or row.get("serviceLevel") or "Web"),
            "url": str(row.get("url") or ""),
            "timezone": str(row.get("timeZone") or row.get("timezone") or "UTC"),
            "currency": str(row.get("currencyCode") or row.get("currency") or ""),
            "account_name": str(row.get("accountName") or ""),
        })
    return out


def _ga4_preset_rows(payload, preset):
    if not isinstance(payload, dict):
        return []
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        return []
    bucket = data.get(preset) or {}
    if not isinstance(bucket, dict):
        return []
    rows = bucket.get("rows")
    return rows if isinstance(rows, list) else []


def _ga4_extract_overview(payload):
    if not isinstance(payload, dict):
        return None
    data = payload.get("data") or {}
    overview = data.get("overview") if isinstance(data, dict) else None
    if not isinstance(overview, dict):
        return None

    sessions = int(_ga4_to_num(overview.get("sessions"), 0))
    users = int(_ga4_to_num(overview.get("users"), 0))
    conversions = int(_ga4_to_num(overview.get("conversions"), 0))
    revenue = round(_ga4_to_num(overview.get("revenue"), 0), 2)
    sessions_per_user = round((sessions / users), 2) if users else 0
    deltas = overview.get("deltas") if isinstance(overview.get("deltas"), dict) else {}

    return {
        "sessions": sessions,
        "users": users,
        "new_users": users,
        "active_users": users,
        "avg_engagement_time": "—",
        "engagement_rate": None,
        "bounce_rate": None,
        "conversions": conversions,
        "event_count": None,
        "sessions_per_user": sessions_per_user,
        "views_per_session": None,
        "revenue": revenue,
        "comparison": {
            "sessions": _ga4_delta_str(deltas.get("sessions")),
            "users": _ga4_delta_str(deltas.get("users")),
            "conversions": _ga4_delta_str(deltas.get("conversions")),
            "revenue": _ga4_delta_str(deltas.get("revenue")),
        },
    }


def _ga4_map_pages(rows):
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        engagement_rate = _ga4_to_num(r.get("engagementRate"), None)
        bounce_rate = None
        if engagement_rate is not None:
            bounce_rate = f"{round(max(0, 1.0 - engagement_rate) * 100, 1)}%"
        out.append({
            "path": str(r.get("pagePath") or ""),
            "title": str(r.get("pageTitle") or ""),
            "views": int(_ga4_to_num(r.get("screenPageViews"), 0)),
            "sessions": int(_ga4_to_num(r.get("sessions"), 0)),
            "users": int(_ga4_to_num(r.get("totalUsers"), 0)),
            "avg_time": "—",
            "bounce_rate": bounce_rate or "—",
            "conversions": int(_ga4_to_num(r.get("conversions"), 0)),
        })
    return out


def _ga4_map_sources(rows):
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        source = str(r.get("sessionSource") or "(unknown)")
        medium = str(r.get("sessionMedium") or "(none)")
        engagement_rate = _ga4_to_num(r.get("engagementRate"), None)
        bounce_rate = None
        if engagement_rate is not None:
            bounce_rate = f"{round(max(0, 1.0 - engagement_rate) * 100, 1)}%"
        out.append({
            "source": source,
            "medium": medium,
            "sessions": int(_ga4_to_num(r.get("sessions"), 0)),
            "users": int(_ga4_to_num(r.get("totalUsers"), 0)),
            "conversions": int(_ga4_to_num(r.get("conversions"), 0)),
            "revenue": round(_ga4_to_num(r.get("totalRevenue"), 0), 2),
            "bounce_rate": bounce_rate or "—",
        })
    return out


def _ga4_event_category(name):
    n = str(name or "").strip().lower()
    if n in ("page_view", "scroll", "click", "session_start", "first_visit"):
        return "Auto"
    if any(k in n for k in ("purchase", "checkout", "add_to_cart", "view_item", "refund")):
        return "Ecommerce"
    return "Custom"


def _ga4_map_events(rows):
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        count = int(_ga4_to_num(r.get("eventCount"), 0))
        sessions = _ga4_to_num(r.get("sessions"), 0)
        out.append({
            "name": str(r.get("eventName") or ""),
            "count": count,
            "users": int(_ga4_to_num(r.get("totalUsers"), 0)),
            "per_session": round((count / sessions), 2) if sessions else 0,
            "category": _ga4_event_category(r.get("eventName")),
            "value": round(_ga4_to_num(r.get("totalRevenue"), 0), 2) or None,
        })
    return out


def _ga4_map_devices(rows):
    total_sessions = sum(int(_ga4_to_num(r.get("sessions"), 0)) for r in rows if isinstance(r, dict))
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        sessions = int(_ga4_to_num(r.get("sessions"), 0))
        out.append({
            "category": str(r.get("deviceCategory") or "unknown").lower(),
            "sessions": sessions,
            "users": sessions,
            "conversions": int(_ga4_to_num(r.get("conversions"), 0)),
            "bounce_rate": "—",
            "pct": round((sessions / total_sessions) * 100, 1) if total_sessions else 0,
        })
    return out


def _ga4_map_countries(rows):
    total_sessions = sum(int(_ga4_to_num(r.get("sessions"), 0)) for r in rows if isinstance(r, dict))
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        sessions = int(_ga4_to_num(r.get("sessions"), 0))
        out.append({
            "country": str(r.get("country") or "Unknown"),
            "sessions": sessions,
            "users": sessions,
            "conversions": int(_ga4_to_num(r.get("conversions"), 0)),
            "revenue": 0,
            "pct": round((sessions / total_sessions) * 100, 1) if total_sessions else 0,
        })
    return out


def _ga4_pick_event_count(events, names):
    keys = {str(x).strip().lower() for x in (names or [])}
    best = 0
    for e in events:
        if not isinstance(e, dict):
            continue
        if str(e.get("name") or "").strip().lower() in keys:
            best = max(best, int(_ga4_to_num(e.get("count"), 0)))
    return best


def _ga4_build_funnel_from_events(events, funnel_type, source="coolbits", gateway=None):
    events = events if isinstance(events, list) else []
    if str(funnel_type or "").strip().lower() == "lead_gen":
        steps_cfg = [
            ("Page View", "page_view", ["page_view", "session_start"]),
            ("Sign Up", "sign_up", ["sign_up"]),
            ("Generate Lead", "generate_lead", ["generate_lead"]),
            ("Purchase", "purchase", ["purchase"]),
        ]
        name = "Lead Generation Funnel"
    else:
        steps_cfg = [
            ("View Item", "view_item", ["view_item", "page_view"]),
            ("Add to Cart", "add_to_cart", ["add_to_cart"]),
            ("Begin Checkout", "begin_checkout", ["begin_checkout"]),
            ("Purchase", "purchase", ["purchase"]),
        ]
        name = "E-commerce Purchase Funnel"

    counts = [max(0, _ga4_pick_event_count(events, keys)) for _, _, keys in steps_cfg]
    base = counts[0] if counts and counts[0] > 0 else 1
    steps = []
    prev = None
    for idx, (label, event_key, _) in enumerate(steps_cfg):
        users = int(counts[idx])
        pct = round((users / base) * 100, 1) if base else 0
        step = {"name": label, "event": event_key, "users": users, "pct": pct}
        if prev is not None and prev > 0:
            step["drop_off"] = round(max(0, (prev - users) / prev) * 100, 1)
        steps.append(step)
        prev = users

    overall = round((steps[-1]["users"] / base) * 100, 1) if steps and base else 0
    out = {"name": name, "steps": steps, "overall_conversion": f"{overall}%", "source": source}
    if gateway:
        out["gateway"] = gateway
    return out


@app.route("/api/connectors/ga4/properties", methods=["GET"])
def ga4_properties():
    payload, gw = _ga4_gateway_fetch(["/api/connectors/ga4/properties"], timeout=20)
    if payload is not None:
        props = _ga4_normalize_properties(payload)
        if props:
            return jsonify({"properties": props, "source": "coolbits", "gateway": gw})
        if isinstance(payload, dict) and payload.get("error") == "not_connected":
            return jsonify({"properties": [], "source": "coolbits", "gateway": gw, "error": "not_connected"})
    return jsonify({"properties": GA4_MOCK_PROPERTIES, "source": "mock"})


@app.route("/api/connectors/ga4/status", methods=["GET"])
def ga4_status():
    payload, gw = _ga4_gateway_fetch(["/api/connectors/ga4/status"], timeout=15)
    if payload is not None and isinstance(payload, dict):
        out = dict(payload)
        selected = str(out.get("selectedPropertyId") or out.get("propertyId") or out.get("activePropertyId") or "").strip()
        if selected:
            out["selectedPropertyId"] = selected
            out["propertyId"] = selected
        out["source"] = "coolbits"
        out["gateway"] = gw
        return jsonify(out)

    local = connector_config("ga4").get_json(silent=True) if request.method == "GET" else {}
    status = str((local or {}).get("status") or "Disconnected")
    cfg = (local or {}).get("config") if isinstance(local, dict) else {}
    selected = str((cfg or {}).get("property_id") or (cfg or {}).get("propertyId") or "").strip() if isinstance(cfg, dict) else ""
    return jsonify({
        "connected": status.lower() == "connected",
        "status": status.lower(),
        "selectedPropertyId": selected or None,
        "propertyId": selected or None,
        "source": "mock",
    })


@app.route("/api/connectors/ga4/auth-url", methods=["GET"])
def ga4_auth_url():
    _ga4_oauth_states_cleanup(max_rows=500)
    if not COOLBITS_GATEWAY_ENABLED:
        return jsonify({"error": "gateway_disabled"}), 400
    try:
        status, payload, text = _coolbits_request("GET", "/api/connectors/ga4/auth/url", timeout=15)
        if 200 <= int(status) < 300 and isinstance(payload, dict):
            out = dict(payload)
            raw_url = str(out.get("url") or out.get("authUrl") or "").strip()
            if raw_url:
                rewritten = _ga4_rewrite_auth_url(raw_url)
                out["url"] = rewritten
                if "authUrl" in out:
                    out["authUrl"] = rewritten
                try:
                    parts = urlparse(rewritten)
                    q = dict(parse_qsl(parts.query, keep_blank_values=True))
                    state_value = str(q.get("state") or "").strip()
                    _ga4_store_oauth_state(
                        state_value,
                        user_id=get_current_user_id(),
                        workspace_id=COOLBITS_WORKSPACE_ID,
                        redirect_uri=str(q.get("redirect_uri") or _ga4_callback_url()),
                        meta={"source": "ga4_auth_url"},
                    )
                except Exception:
                    pass
            out.setdefault("callback_url", _ga4_callback_url())
            out.setdefault("popup_mode", "postMessage")
            return jsonify(out)
        return jsonify(payload or {"error": "auth_url_failed", "detail": text[:180]}), int(status or 502)
    except Exception as e:
        return jsonify({"error": "auth_url_failed", "detail": str(e)}), 502


@app.route("/api/connectors/ga4/oauth/callback", methods=["GET"])
def ga4_oauth_callback_proxy():
    """Canonical GA4 OAuth callback via Camarad domain; forwards to Coolbits then closes popup."""
    _ga4_oauth_states_cleanup(max_rows=500)
    state_value = str(request.args.get("state") or "").strip()
    ok_state, state_reason, _state_row = _ga4_validate_oauth_state(state_value)
    if not ok_state:
        return _ga4_popup_html(False, "GA4 OAuth state validation failed.", {"reason": state_reason})

    cookie_hdr = request.headers.get("Cookie", "")
    try:
        token = _coolbits_get_token(force=False)
        headers = {"Cookie": cookie_hdr, "X-Workspace-Id": COOLBITS_WORKSPACE_ID}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        upstream = requests.get(
            f"{COOLBITS_URL}/api/connectors/ga4/oauth/callback",
            params=request.args,
            headers=headers,
            timeout=30,
            allow_redirects=False,
        )
    except Exception as exc:
        return _ga4_popup_html(False, "Could not reach GA4 gateway callback.", {"reason": "upstream_unreachable", "detail": str(exc)})

    status_code = int(upstream.status_code or 500)
    payload = None
    if "application/json" in str(upstream.headers.get("content-type") or "").lower():
        try:
            payload = upstream.json()
        except Exception:
            payload = None
    is_ok = 200 <= status_code < 400
    if isinstance(payload, dict) and payload.get("error"):
        is_ok = False
    if request.args.get("error"):
        is_ok = False

    if is_ok:
        _ga4_mark_oauth_state_used(state_value)
        return _ga4_popup_html(True, "GA4 connection completed.")
    detail = {"status": status_code}
    if isinstance(payload, dict):
        detail.update({"error": str(payload.get("error") or "callback_failed")})
    return _ga4_popup_html(False, "GA4 OAuth callback failed.", detail)


@app.route("/api/connectors/ga4/property", methods=["POST"])
def ga4_select_property():
    data = request.get_json(force=True, silent=True) or {}
    property_id = str(data.get("propertyId") or data.get("property_id") or "").strip()
    if not property_id:
        return jsonify({"error": "invalid_property"}), 400
    if not COOLBITS_GATEWAY_ENABLED:
        return jsonify({"ok": False, "error": "gateway_disabled"}), 400
    try:
        status, payload, text = _coolbits_request("POST", "/api/connectors/ga4/property", body={"propertyId": property_id}, timeout=20)
        if 200 <= int(status) < 300:
            try:
                cfg_payload = connector_config("ga4").get_json(silent=True) if request.method == "POST" else {}
                existing = cfg_payload.get("config") if isinstance(cfg_payload, dict) and isinstance(cfg_payload.get("config"), dict) else {}
                existing["property_id"] = property_id
                existing["provider"] = existing.get("provider") or "coolbits"
                conn = get_db()
                conn.execute("""
                    INSERT OR REPLACE INTO connectors_config
                    (user_id, client_id, connector_slug, status, config_json, last_connected)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                """, (
                    get_current_user_id(),
                    int(get_current_client_id() or 0),
                    "ga4",
                    "Connected",
                    json.dumps(existing),
                ))
                conn.commit()
                conn.close()
            except Exception:
                pass
            out = payload if isinstance(payload, dict) else {"ok": True, "propertyId": property_id}
            out["selectedPropertyId"] = property_id
            out["propertyId"] = property_id
            return jsonify(out)
        return jsonify(payload or {"error": "select_property_failed", "detail": text[:180]}), int(status or 502)
    except Exception as e:
        return jsonify({"error": "select_property_failed", "detail": str(e)}), 502


@app.route("/api/connectors/ga4/overview", methods=["GET"])
def ga4_overview():
    prop_id = _ga4_pick_property_id()
    _range = _ga4_resolve_range_args(request.args)
    report_params = {
        "propertyId": prop_id,
        "from": _range["from"],
        "to": _range["to"],
        "blocks": "overview",
    }
    payload, gw = _ga4_gateway_fetch(["/api/connectors/ga4/report"], params=report_params, timeout=30)
    if payload is not None:
        overview = _ga4_extract_overview(payload)
        if overview:
            out = {"property_id": prop_id, **overview, "source": "coolbits", "gateway": gw}
            return jsonify(out)
        if isinstance(payload, dict) and payload.get("error") == "not_connected":
            return jsonify({"property_id": prop_id, "error": "not_connected", "source": "coolbits", "gateway": gw})

    data = GA4_MOCK_OVERVIEW.get(prop_id, GA4_MOCK_OVERVIEW['G-ABC123DEF4'])
    return jsonify({"property_id": prop_id, **data, "source": "mock"})


@app.route("/api/connectors/ga4/pages", methods=["GET"])
def ga4_pages():
    prop_id = _ga4_pick_property_id()
    _range = _ga4_resolve_range_args(request.args)
    payload, gw = _ga4_gateway_fetch(
        ["/api/connectors/ga4/report"],
        params={
            "propertyId": prop_id,
            "from": _range["from"],
            "to": _range["to"],
            "preset": "pages_screens",
        },
        timeout=30,
    )
    if payload is not None:
        rows = _ga4_preset_rows(payload, "pages_screens")
        if rows:
            return jsonify({"property_id": prop_id, "pages": _ga4_map_pages(rows), "source": "coolbits", "gateway": gw})
        if isinstance(payload, dict) and payload.get("error") == "not_connected":
            return jsonify({"property_id": prop_id, "pages": [], "error": "not_connected", "source": "coolbits", "gateway": gw})
    pages = GA4_MOCK_TOP_PAGES.get(prop_id, [])
    return jsonify({"property_id": prop_id, "pages": pages, "source": "mock"})


@app.route("/api/connectors/ga4/sources", methods=["GET"])
def ga4_sources():
    prop_id = _ga4_pick_property_id()
    _range = _ga4_resolve_range_args(request.args)
    payload, gw = _ga4_gateway_fetch(
        ["/api/connectors/ga4/report"],
        params={
            "propertyId": prop_id,
            "from": _range["from"],
            "to": _range["to"],
            "preset": "traffic_acquisition",
        },
        timeout=30,
    )
    if payload is not None:
        rows = _ga4_preset_rows(payload, "traffic_acquisition")
        if rows:
            return jsonify({"property_id": prop_id, "sources": _ga4_map_sources(rows), "source": "coolbits", "gateway": gw})
        if isinstance(payload, dict) and payload.get("error") == "not_connected":
            return jsonify({"property_id": prop_id, "sources": [], "error": "not_connected", "source": "coolbits", "gateway": gw})
    sources = GA4_MOCK_SOURCES.get(prop_id, GA4_MOCK_SOURCES['G-ABC123DEF4'])
    return jsonify({"property_id": prop_id, "sources": sources, "source": "mock"})


@app.route("/api/connectors/ga4/events", methods=["GET"])
def ga4_events():
    prop_id = _ga4_pick_property_id()
    _range = _ga4_resolve_range_args(request.args)
    payload, gw = _ga4_gateway_fetch(
        ["/api/connectors/ga4/report"],
        params={
            "propertyId": prop_id,
            "from": _range["from"],
            "to": _range["to"],
            "preset": "events",
        },
        timeout=30,
    )
    if payload is not None:
        rows = _ga4_preset_rows(payload, "events")
        if rows:
            return jsonify({"property_id": prop_id, "events": _ga4_map_events(rows), "source": "coolbits", "gateway": gw})
        if isinstance(payload, dict) and payload.get("error") == "not_connected":
            return jsonify({"property_id": prop_id, "events": [], "error": "not_connected", "source": "coolbits", "gateway": gw})
    events = GA4_MOCK_EVENTS.get(prop_id, GA4_MOCK_EVENTS['G-ABC123DEF4'])
    return jsonify({"property_id": prop_id, "events": events, "source": "mock"})


@app.route("/api/connectors/ga4/devices", methods=["GET"])
def ga4_devices():
    prop_id = _ga4_pick_property_id()
    _range = _ga4_resolve_range_args(request.args)
    payload, gw = _ga4_gateway_fetch(
        ["/api/connectors/ga4/report"],
        params={
            "propertyId": prop_id,
            "from": _range["from"],
            "to": _range["to"],
            "blocks": "device,overview",
        },
        timeout=30,
    )
    if payload is not None:
        rows = []
        if isinstance(payload, dict):
            rows = (((payload.get("data") or {}).get("device") or {}).get("deviceCategory") or [])
        if rows:
            return jsonify({"property_id": prop_id, "devices": _ga4_map_devices(rows), "source": "coolbits", "gateway": gw})
        if isinstance(payload, dict) and payload.get("error") == "not_connected":
            return jsonify({"property_id": prop_id, "devices": [], "error": "not_connected", "source": "coolbits", "gateway": gw})
    devices = GA4_MOCK_DEVICES.get(prop_id, GA4_MOCK_DEVICES['G-ABC123DEF4'])
    return jsonify({"property_id": prop_id, "devices": devices, "source": "mock"})


@app.route("/api/connectors/ga4/countries", methods=["GET"])
def ga4_countries():
    prop_id = _ga4_pick_property_id()
    _range = _ga4_resolve_range_args(request.args)
    payload, gw = _ga4_gateway_fetch(
        ["/api/connectors/ga4/report"],
        params={
            "propertyId": prop_id,
            "from": _range["from"],
            "to": _range["to"],
            "blocks": "geo,overview",
        },
        timeout=30,
    )
    if payload is not None:
        rows = []
        if isinstance(payload, dict):
            rows = (((payload.get("data") or {}).get("geo") or {}).get("countries") or [])
        if rows:
            return jsonify({"property_id": prop_id, "countries": _ga4_map_countries(rows), "source": "coolbits", "gateway": gw})
        if isinstance(payload, dict) and payload.get("error") == "not_connected":
            return jsonify({"property_id": prop_id, "countries": [], "error": "not_connected", "source": "coolbits", "gateway": gw})
    countries = GA4_MOCK_COUNTRIES.get(prop_id, GA4_MOCK_COUNTRIES['G-ABC123DEF4'])
    return jsonify({"property_id": prop_id, "countries": countries, "source": "mock"})


@app.route("/api/connectors/ga4/funnel", methods=["GET"])
def ga4_funnel():
    funnel_type = request.args.get('type', 'ecommerce')
    prop_id = _ga4_pick_property_id()
    _range = _ga4_resolve_range_args(request.args)
    payload, gw = _ga4_gateway_fetch(
        ["/api/connectors/ga4/report"],
        params={
            "propertyId": prop_id,
            "from": _range["from"],
            "to": _range["to"],
            "preset": "events",
        },
        timeout=30,
    )
    if payload is not None:
        rows = _ga4_preset_rows(payload, "events")
        if rows:
            events = _ga4_map_events(rows)
            return jsonify(_ga4_build_funnel_from_events(events, funnel_type, source="coolbits", gateway=gw))
        if isinstance(payload, dict) and payload.get("error") == "not_connected":
            return jsonify({"error": "not_connected", "source": "coolbits", "gateway": gw}), 400
    funnel = GA4_MOCK_FUNNELS.get(funnel_type, GA4_MOCK_FUNNELS['ecommerce'])
    out = dict(funnel)
    out["source"] = "mock"
    return jsonify(out)


@app.route("/api/connectors/ga4/timeseries", methods=["GET"])
def ga4_timeseries():
    prop_id = _ga4_pick_property_id()
    _range = _ga4_resolve_range_args(request.args)
    payload, gw = _ga4_gateway_fetch(
        ["/api/connectors/ga4/report"],
        params={
            "propertyId": prop_id,
            "from": _range["from"],
            "to": _range["to"],
            "blocks": "series",
        },
        timeout=30,
    )
    if payload is not None:
        rows = []
        if isinstance(payload, dict):
            rows = (((payload.get("data") or {}).get("series") or {}).get("daily") or [])
        if rows:
            daily = [{
                "date": r.get("date"),
                "sessions": int(r.get("sessions") or 0),
                "conversions": int(r.get("conversions") or 0),
                "users": int(r.get("sessions") or 0),
                "new_users": int(r.get("sessions") or 0),
                "bounce_rate": None,
                "avg_engagement_time": None,
                "event_count": None,
                "revenue": None,
            } for r in rows if isinstance(r, dict)]
            return jsonify({"property_id": prop_id, "days": _range["days"], "daily": daily, "source": "coolbits", "gateway": gw})
    days = int(_range["days"])
    import random
    random.seed(77)
    daily = []
    for i in range(days):
        from datetime import datetime, timedelta
        d = (datetime.now() - timedelta(days=days - 1 - i)).strftime('%Y-%m-%d')
        base_sessions = random.randint(220, 380)
        base_users = int(base_sessions * random.uniform(0.6, 0.8))
        base_new = int(base_users * random.uniform(0.5, 0.7))
        base_conv = int(base_sessions * random.uniform(0.05, 0.09))
        base_bounce = round(random.uniform(35, 52), 1)
        base_engage = f"{random.randint(1, 2)}m {random.randint(10, 55)}s"
        base_events = int(base_sessions * random.uniform(4.5, 6.5))
        base_revenue = round(base_conv * random.uniform(18, 35), 2)
        daily.append({
            "date": d, "sessions": base_sessions, "users": base_users,
            "new_users": base_new, "conversions": base_conv,
            "bounce_rate": base_bounce, "avg_engagement_time": base_engage,
            "event_count": base_events, "revenue": base_revenue
        })
    return jsonify({"property_id": prop_id, "days": days, "daily": daily, "source": "mock"})


@app.route("/api/connectors/ga4/test-call", methods=["POST"])
def ga4_test_call():
    data = request.get_json(force=True, silent=True) or {}
    endpoint = data.get('endpoint', '/v1beta/properties/GA4_PROP/runReport')
    method = data.get('method', 'POST')
    import time
    start = time.time()

    if 'runReport' in endpoint:
        response_body = {
            "dimensionHeaders": [{"name": "date"}, {"name": "sessionSource"}],
            "metricHeaders": [{"name": "sessions", "type": "TYPE_INTEGER"}, {"name": "conversions", "type": "TYPE_INTEGER"}],
            "rows": [
                {"dimensionValues": [{"value": "20260205"}, {"value": "google"}], "metricValues": [{"value": "1234"}, {"value": "56"}]},
                {"dimensionValues": [{"value": "20260205"}, {"value": "(direct)"}], "metricValues": [{"value": "567"}, {"value": "23"}]},
                {"dimensionValues": [{"value": "20260206"}, {"value": "google"}], "metricValues": [{"value": "1345"}, {"value": "62"}]},
                {"dimensionValues": [{"value": "20260206"}, {"value": "(direct)"}], "metricValues": [{"value": "612"}, {"value": "28"}]},
            ],
            "rowCount": 4,
            "metadata": {"currencyCode": "USD", "timeZone": "Europe/Bucharest"}
        }
    elif 'runRealtimeReport' in endpoint:
        response_body = {
            "dimensionHeaders": [{"name": "unifiedScreenName"}],
            "metricHeaders": [{"name": "activeUsers", "type": "TYPE_INTEGER"}],
            "rows": [
                {"dimensionValues": [{"value": "/home"}], "metricValues": [{"value": "47"}]},
                {"dimensionValues": [{"value": "/product"}], "metricValues": [{"value": "23"}]},
                {"dimensionValues": [{"value": "/pricing"}], "metricValues": [{"value": "12"}]},
            ],
            "rowCount": 3
        }
    elif 'metadata' in endpoint:
        response_body = {
            "dimensions": [
                {"apiName": "date", "uiName": "Date", "category": "TIME"},
                {"apiName": "sessionSource", "uiName": "Session source", "category": "TRAFFIC_SOURCE"},
                {"apiName": "pagePath", "uiName": "Page path", "category": "PAGE_SCREEN"},
            ],
            "metrics": [
                {"apiName": "sessions", "uiName": "Sessions", "type": "TYPE_INTEGER"},
                {"apiName": "activeUsers", "uiName": "Active users", "type": "TYPE_INTEGER"},
                {"apiName": "conversions", "uiName": "Conversions", "type": "TYPE_INTEGER"},
            ]
        }
    else:
        response_body = {"rows": [], "rowCount": 0}

    elapsed = round((time.time() - start) * 1000 + 89, 0)

    return jsonify({
        "request": {
            "method": method, "endpoint": endpoint,
            "headers": {
                "Authorization": "Bearer ya29.a0GA4...mock_token",
                "Content-Type": "application/json",
                "x-goog-user-project": "camarad-analytics-prod"
            },
            "body": {
                "dateRanges": [{"startDate": "30daysAgo", "endDate": "today"}],
                "dimensions": [{"name": "date"}, {"name": "sessionSource"}],
                "metrics": [{"name": "sessions"}, {"name": "conversions"}]
            } if method == 'POST' else None
        },
        "response": {
            "status_code": 200,
            "headers": {"content-type": "application/json", "x-goog-request-id": f"ga4-mock-{int(time.time())}"},
            "body": response_body
        },
        "latency_ms": elapsed,
        "quota": {"tokens_remaining": 48750, "daily_limit": 50000}
    })


# ─── Google Search Console Mock API ──────────────────────────────────────────
GSC_MOCK_PROPERTIES = [
    {"id": "sc-domain:camarad.ai", "name": "camarad.ai", "type": "Domain", "permission_level": "siteOwner", "verified": True},
    {"id": "https://shop.camarad.ai/", "name": "shop.camarad.ai", "type": "URL prefix", "permission_level": "siteOwner", "verified": True},
    {"id": "https://blog.camarad.ai/", "name": "blog.camarad.ai", "type": "URL prefix", "permission_level": "siteFullUser", "verified": True},
]

GSC_MOCK_OVERVIEW = {
    "sc-domain:camarad.ai": {
        "total_clicks": 48732, "total_impressions": 1243567, "avg_ctr": 3.92, "avg_position": 12.4,
        "clicks_change": 8.3, "impressions_change": 12.1, "ctr_change": -0.4, "position_change": -1.2,
        "top_query": "camarad ai platform", "top_page": "/features", "crawl_errors": 12, "indexed_pages": 1847
    },
    "https://shop.camarad.ai/": {
        "total_clicks": 23456, "total_impressions": 678901, "avg_ctr": 3.45, "avg_position": 15.7,
        "clicks_change": 5.2, "impressions_change": 9.8, "ctr_change": 0.3, "position_change": -0.8,
        "top_query": "camarad shop online", "top_page": "/products", "crawl_errors": 3, "indexed_pages": 562
    },
    "https://blog.camarad.ai/": {
        "total_clicks": 12890, "total_impressions": 456789, "avg_ctr": 2.82, "avg_position": 18.3,
        "clicks_change": 15.6, "impressions_change": 22.4, "ctr_change": 1.1, "position_change": -2.5,
        "top_query": "marketing automation guide", "top_page": "/blog/seo-tips-2026", "crawl_errors": 1, "indexed_pages": 234
    },
}

GSC_MOCK_QUERIES = {
    "sc-domain:camarad.ai": [
        {"query": "camarad ai platform", "clicks": 4567, "impressions": 45678, "ctr": 10.0, "position": 1.2},
        {"query": "marketing automation tool", "clicks": 3456, "impressions": 78901, "ctr": 4.38, "position": 5.4},
        {"query": "ai marketing agency", "clicks": 2890, "impressions": 56789, "ctr": 5.09, "position": 3.8},
        {"query": "digital marketing platform romania", "clicks": 2345, "impressions": 34567, "ctr": 6.79, "position": 4.1},
        {"query": "ppc management software", "clicks": 1987, "impressions": 45678, "ctr": 4.35, "position": 7.2},
        {"query": "seo audit tool free", "clicks": 1876, "impressions": 67890, "ctr": 2.76, "position": 9.5},
        {"query": "content strategy ai", "clicks": 1654, "impressions": 34567, "ctr": 4.79, "position": 6.3},
        {"query": "social media management ai", "clicks": 1432, "impressions": 56789, "ctr": 2.52, "position": 11.2},
        {"query": "email marketing automation", "clicks": 1298, "impressions": 45678, "ctr": 2.84, "position": 13.5},
        {"query": "google ads optimization tool", "clicks": 1123, "impressions": 23456, "ctr": 4.79, "position": 8.7},
        {"query": "marketing dashboard software", "clicks": 987, "impressions": 34567, "ctr": 2.86, "position": 14.2},
        {"query": "lead generation platform", "clicks": 876, "impressions": 23456, "ctr": 3.73, "position": 10.8},
        {"query": "crm integration marketing", "clicks": 765, "impressions": 12345, "ctr": 6.20, "position": 5.9},
        {"query": "analytics reporting tool", "clicks": 654, "impressions": 23456, "ctr": 2.79, "position": 16.3},
        {"query": "multi-channel marketing", "clicks": 543, "impressions": 12345, "ctr": 4.40, "position": 12.1},
    ],
}

GSC_MOCK_PAGES = {
    "sc-domain:camarad.ai": [
        {"page": "/features", "clicks": 6789, "impressions": 123456, "ctr": 5.50, "position": 4.2},
        {"page": "/pricing", "clicks": 5432, "impressions": 98765, "ctr": 5.50, "position": 5.1},
        {"page": "/", "clicks": 4567, "impressions": 156789, "ctr": 2.91, "position": 8.3},
        {"page": "/blog/seo-tips-2026", "clicks": 3456, "impressions": 78901, "ctr": 4.38, "position": 6.7},
        {"page": "/blog/marketing-automation-guide", "clicks": 2890, "impressions": 67890, "ctr": 4.26, "position": 7.8},
        {"page": "/integrations", "clicks": 2345, "impressions": 56789, "ctr": 4.13, "position": 9.2},
        {"page": "/about", "clicks": 1987, "impressions": 45678, "ctr": 4.35, "position": 10.5},
        {"page": "/docs/api-reference", "clicks": 1654, "impressions": 34567, "ctr": 4.79, "position": 11.3},
        {"page": "/blog/google-ads-tips", "clicks": 1432, "impressions": 45678, "ctr": 3.14, "position": 12.8},
        {"page": "/case-studies", "clicks": 1123, "impressions": 23456, "ctr": 4.79, "position": 8.9},
    ],
}

GSC_MOCK_COUNTRIES = {
    "sc-domain:camarad.ai": [
        {"country": "Romania", "code": "RO", "clicks": 18765, "impressions": 345678, "ctr": 5.43, "position": 8.2},
        {"country": "United States", "code": "US", "clicks": 8901, "impressions": 234567, "ctr": 3.79, "position": 14.5},
        {"country": "United Kingdom", "code": "GB", "clicks": 5432, "impressions": 123456, "ctr": 4.40, "position": 11.3},
        {"country": "Germany", "code": "DE", "clicks": 3456, "impressions": 98765, "ctr": 3.50, "position": 13.7},
        {"country": "France", "code": "FR", "clicks": 2345, "impressions": 67890, "ctr": 3.45, "position": 15.2},
        {"country": "Moldova", "code": "MD", "clicks": 1987, "impressions": 45678, "ctr": 4.35, "position": 9.8},
        {"country": "Canada", "code": "CA", "clicks": 1654, "impressions": 56789, "ctr": 2.91, "position": 16.1},
        {"country": "Netherlands", "code": "NL", "clicks": 1234, "impressions": 34567, "ctr": 3.57, "position": 12.9},
    ],
}

GSC_MOCK_DEVICES = {
    "sc-domain:camarad.ai": [
        {"device": "Mobile", "clicks": 26543, "impressions": 678901, "ctr": 3.91, "position": 13.2, "share": 54.5},
        {"device": "Desktop", "clicks": 18765, "impressions": 432109, "ctr": 4.34, "position": 10.8, "share": 38.5},
        {"device": "Tablet", "clicks": 3424, "impressions": 132557, "ctr": 2.58, "position": 16.4, "share": 7.0},
    ],
}

GSC_MOCK_INDEX_COVERAGE = {
    "sc-domain:camarad.ai": {
        "summary": {"valid": 1847, "warning": 23, "error": 12, "excluded": 345},
        "errors": [
            {"type": "Server error (5xx)", "pages": 5, "severity": "error", "trend": "stable"},
            {"type": "Redirect error", "pages": 4, "severity": "error", "trend": "decreasing"},
            {"type": "Submitted URL not found (404)", "pages": 3, "severity": "error", "trend": "increasing"},
        ],
        "warnings": [
            {"type": "Indexed, though blocked by robots.txt", "pages": 12, "severity": "warning", "trend": "stable"},
            {"type": "Page with redirect", "pages": 8, "severity": "warning", "trend": "decreasing"},
            {"type": "Soft 404", "pages": 3, "severity": "warning", "trend": "stable"},
        ],
        "excluded": [
            {"type": "Crawled - currently not indexed", "pages": 145, "reason": "Low quality content or duplicate"},
            {"type": "Excluded by noindex tag", "pages": 89, "reason": "Intentionally excluded via meta tag"},
            {"type": "Blocked by robots.txt", "pages": 67, "reason": "Blocked in robots.txt rules"},
            {"type": "Duplicate without canonical", "pages": 44, "reason": "Google chose different canonical"},
        ]
    },
}

GSC_MOCK_SITEMAPS = {
    "sc-domain:camarad.ai": [
        {"url": "https://camarad.ai/sitemap.xml", "type": "Sitemap", "submitted": "2026-01-15", "last_read": "2026-02-05", "status": "Success", "discovered_urls": 1847, "indexed_urls": 1502},
        {"url": "https://camarad.ai/sitemap-blog.xml", "type": "Sitemap", "submitted": "2026-01-20", "last_read": "2026-02-05", "status": "Success", "discovered_urls": 234, "indexed_urls": 198},
        {"url": "https://camarad.ai/sitemap-products.xml", "type": "Sitemap", "submitted": "2026-01-25", "last_read": "2026-02-04", "status": "Has errors", "discovered_urls": 562, "indexed_urls": 489},
        {"url": "https://camarad.ai/sitemap-images.xml", "type": "Sitemap index", "submitted": "2026-02-01", "last_read": "2026-02-05", "status": "Success", "discovered_urls": 3456, "indexed_urls": 2890},
    ],
}


@app.route("/api/connectors/google-search-console/properties", methods=["GET"])
def gsc_properties():
    return jsonify({"properties": GSC_MOCK_PROPERTIES})


@app.route("/api/connectors/google-search-console/overview", methods=["GET"])
def gsc_overview():
    prop_id = request.args.get('property_id', 'sc-domain:camarad.ai')
    data = GSC_MOCK_OVERVIEW.get(prop_id, GSC_MOCK_OVERVIEW['sc-domain:camarad.ai'])
    return jsonify({"property_id": prop_id, **data})


@app.route("/api/connectors/google-search-console/queries", methods=["GET"])
def gsc_queries():
    prop_id = request.args.get('property_id', 'sc-domain:camarad.ai')
    queries = GSC_MOCK_QUERIES.get(prop_id, GSC_MOCK_QUERIES['sc-domain:camarad.ai'])
    return jsonify({"property_id": prop_id, "queries": queries})


@app.route("/api/connectors/google-search-console/pages", methods=["GET"])
def gsc_pages():
    prop_id = request.args.get('property_id', 'sc-domain:camarad.ai')
    pages = GSC_MOCK_PAGES.get(prop_id, GSC_MOCK_PAGES['sc-domain:camarad.ai'])
    return jsonify({"property_id": prop_id, "pages": pages})


@app.route("/api/connectors/google-search-console/countries", methods=["GET"])
def gsc_countries():
    prop_id = request.args.get('property_id', 'sc-domain:camarad.ai')
    countries = GSC_MOCK_COUNTRIES.get(prop_id, GSC_MOCK_COUNTRIES['sc-domain:camarad.ai'])
    return jsonify({"property_id": prop_id, "countries": countries})


@app.route("/api/connectors/google-search-console/devices", methods=["GET"])
def gsc_devices():
    prop_id = request.args.get('property_id', 'sc-domain:camarad.ai')
    devices = GSC_MOCK_DEVICES.get(prop_id, GSC_MOCK_DEVICES['sc-domain:camarad.ai'])
    return jsonify({"property_id": prop_id, "devices": devices})


@app.route("/api/connectors/google-search-console/index-coverage", methods=["GET"])
def gsc_index_coverage():
    prop_id = request.args.get('property_id', 'sc-domain:camarad.ai')
    data = GSC_MOCK_INDEX_COVERAGE.get(prop_id, GSC_MOCK_INDEX_COVERAGE['sc-domain:camarad.ai'])
    return jsonify({"property_id": prop_id, **data})


@app.route("/api/connectors/google-search-console/sitemaps", methods=["GET"])
def gsc_sitemaps():
    prop_id = request.args.get('property_id', 'sc-domain:camarad.ai')
    sitemaps = GSC_MOCK_SITEMAPS.get(prop_id, GSC_MOCK_SITEMAPS['sc-domain:camarad.ai'])
    return jsonify({"property_id": prop_id, "sitemaps": sitemaps})


@app.route("/api/connectors/google-search-console/timeseries", methods=["GET"])
def gsc_timeseries():
    prop_id = request.args.get('property_id', 'sc-domain:camarad.ai')
    days = request.args.get('days', 28, type=int)
    import random
    random.seed(99)
    daily = []
    for i in range(days):
        from datetime import datetime, timedelta
        d = (datetime.now() - timedelta(days=days - 1 - i)).strftime('%Y-%m-%d')
        base_clicks = random.randint(1400, 2100)
        base_impr = int(base_clicks * random.uniform(20, 30))
        base_ctr = round(base_clicks / base_impr * 100, 2)
        base_pos = round(random.uniform(10.5, 15.5), 1)
        daily.append({"date": d, "clicks": base_clicks, "impressions": base_impr, "ctr": base_ctr, "position": base_pos})
    return jsonify({"property_id": prop_id, "days": days, "daily": daily})


@app.route("/api/connectors/google-search-console/test-call", methods=["POST"])
def gsc_test_call():
    data = request.get_json(force=True, silent=True) or {}
    endpoint = data.get('endpoint', '/webmasters/v3/sites/sc-domain:camarad.ai/searchAnalytics/query')
    method = data.get('method', 'POST')
    import time
    start = time.time()

    if 'searchAnalytics' in endpoint:
        response_body = {
            "rows": [
                {"keys": ["camarad ai platform"], "clicks": 4567, "impressions": 45678, "ctr": 0.1, "position": 1.2},
                {"keys": ["marketing automation tool"], "clicks": 3456, "impressions": 78901, "ctr": 0.0438, "position": 5.4},
                {"keys": ["ai marketing agency"], "clicks": 2890, "impressions": 56789, "ctr": 0.0509, "position": 3.8},
            ],
            "responseAggregationType": "byPage"
        }
    elif 'sitemaps' in endpoint:
        response_body = {
            "sitemap": [
                {"path": "https://camarad.ai/sitemap.xml", "lastSubmitted": "2026-01-15T00:00:00Z", "isPending": False, "isSitemapsIndex": False,
                 "lastDownloaded": "2026-02-05T12:00:00Z", "warnings": "0", "errors": "0", "contents": [{"type": "web", "submitted": "1847", "indexed": "1502"}]}
            ]
        }
    elif 'urlInspection' in endpoint:
        response_body = {
            "inspectionResult": {
                "indexStatusResult": {"coverageState": "Submitted and indexed", "robotsTxtState": "ALLOWED", "indexingState": "INDEXING_ALLOWED", "lastCrawlTime": "2026-02-05T08:30:00Z", "pageFetchState": "SUCCESSFUL", "googleCanonical": "https://camarad.ai/features"},
                "mobileUsabilityResult": {"verdict": "PASS"},
                "richResultsResult": {"verdict": "PASS", "detectedItems": [{"richResultType": "BreadcrumbList"}]}
            }
        }
    else:
        response_body = {"rows": [], "responseAggregationType": "auto"}

    elapsed = round((time.time() - start) * 1000 + 67, 0)

    return jsonify({
        "request": {
            "method": method, "endpoint": endpoint,
            "headers": {
                "Authorization": "Bearer ya29.a0GSC...mock_token",
                "Content-Type": "application/json",
                "x-goog-user-project": "camarad-seo-prod"
            },
            "body": {
                "startDate": "2026-01-07", "endDate": "2026-02-05",
                "dimensions": ["query"], "rowLimit": 25000
            } if method == 'POST' else None
        },
        "response": {
            "status_code": 200,
            "headers": {"content-type": "application/json", "x-goog-request-id": f"gsc-mock-{int(time.time())}"},
            "body": response_body
        },
        "latency_ms": elapsed,
        "quota": {"queries_remaining": 1150, "daily_limit": 1200}
    })


# ─── Google Tag Manager Mock API ─────────────────────────────────────────────
GTM_MOCK_CONTAINERS = [
    {"id": "GTM-WX4R7N2", "name": "camarad.ai — Main Website", "type": "Web", "workspace": "Default", "public_id": "GTM-WX4R7N2", "fingerprint": "1707321600000", "notes": "Production container"},
    {"id": "GTM-M8KP3V5", "name": "Camarad Mobile App", "type": "iOS / Android", "workspace": "Default", "public_id": "GTM-M8KP3V5", "fingerprint": "1707408000000", "notes": "Mobile SDK container"},
    {"id": "GTM-QJ6D9T1", "name": "Marketing Landing Pages", "type": "Web", "workspace": "Staging", "public_id": "GTM-QJ6D9T1", "fingerprint": "1707494400000", "notes": "Campaign-specific LP container"},
]

GTM_MOCK_OVERVIEW = {
    "GTM-WX4R7N2": {
        "tags_total": 18, "tags_enabled": 15, "tags_paused": 3,
        "triggers_total": 12, "variables_total": 23,
        "tags_fired_7d": 48732, "errors_7d": 3, "warnings_7d": 7,
        "last_published": "2026-02-05 14:30:00", "published_by": "admin@camarad.ai",
        "current_version": 12, "workspaces": ["Default", "Production", "Staging"],
        "daily_fires": [
            {"date": "2026-02-01", "fires": 6823}, {"date": "2026-02-02", "fires": 7102},
            {"date": "2026-02-03", "fires": 6945}, {"date": "2026-02-04", "fires": 7234},
            {"date": "2026-02-05", "fires": 7456}, {"date": "2026-02-06", "fires": 6890},
            {"date": "2026-02-07", "fires": 6282},
        ]
    },
    "GTM-M8KP3V5": {
        "tags_total": 8, "tags_enabled": 7, "tags_paused": 1,
        "triggers_total": 6, "variables_total": 12,
        "tags_fired_7d": 23456, "errors_7d": 1, "warnings_7d": 2,
        "last_published": "2026-02-03 09:15:00", "published_by": "dev@camarad.ai",
        "current_version": 5, "workspaces": ["Default"],
        "daily_fires": [
            {"date": "2026-02-01", "fires": 3234}, {"date": "2026-02-02", "fires": 3456},
            {"date": "2026-02-03", "fires": 3123}, {"date": "2026-02-04", "fires": 3567},
            {"date": "2026-02-05", "fires": 3678}, {"date": "2026-02-06", "fires": 3345},
            {"date": "2026-02-07", "fires": 3053},
        ]
    },
}

GTM_MOCK_TAGS = {
    "GTM-WX4R7N2": [
        {"id": "tag-001", "name": "GA4 — Page View", "type": "Google Analytics: GA4 Event", "status": "Enabled", "fires_on": "All Pages", "priority": 1, "fire_count_7d": 12345, "last_fired": "2026-02-07 10:55:00"},
        {"id": "tag-002", "name": "GA4 — Purchase", "type": "Google Analytics: GA4 Event", "status": "Enabled", "fires_on": "Purchase Confirmation", "priority": 1, "fire_count_7d": 487, "last_fired": "2026-02-07 10:48:00"},
        {"id": "tag-003", "name": "GA4 — Add to Cart", "type": "Google Analytics: GA4 Event", "status": "Enabled", "fires_on": "Add to Cart Click", "priority": 2, "fire_count_7d": 2345, "last_fired": "2026-02-07 10:52:00"},
        {"id": "tag-004", "name": "Google Ads — Conversion", "type": "Google Ads Conversion Tracking", "status": "Enabled", "fires_on": "Purchase Confirmation", "priority": 1, "fire_count_7d": 487, "last_fired": "2026-02-07 10:48:00"},
        {"id": "tag-005", "name": "Google Ads — Remarketing", "type": "Google Ads Remarketing", "status": "Enabled", "fires_on": "All Pages", "priority": 3, "fire_count_7d": 12345, "last_fired": "2026-02-07 10:55:00"},
        {"id": "tag-006", "name": "Meta Pixel — PageView", "type": "Custom HTML", "status": "Enabled", "fires_on": "All Pages", "priority": 2, "fire_count_7d": 12345, "last_fired": "2026-02-07 10:55:00"},
        {"id": "tag-007", "name": "Meta Pixel — Purchase", "type": "Custom HTML", "status": "Enabled", "fires_on": "Purchase Confirmation", "priority": 2, "fire_count_7d": 487, "last_fired": "2026-02-07 10:48:00"},
        {"id": "tag-008", "name": "Hotjar — Session Recording", "type": "Custom HTML", "status": "Enabled", "fires_on": "All Pages", "priority": 5, "fire_count_7d": 12345, "last_fired": "2026-02-07 10:55:00"},
        {"id": "tag-009", "name": "LinkedIn Insight Tag", "type": "Custom HTML", "status": "Enabled", "fires_on": "All Pages", "priority": 4, "fire_count_7d": 12345, "last_fired": "2026-02-07 10:55:00"},
        {"id": "tag-010", "name": "TikTok Pixel — Page View", "type": "Custom HTML", "status": "Enabled", "fires_on": "All Pages", "priority": 4, "fire_count_7d": 12345, "last_fired": "2026-02-07 10:55:00"},
        {"id": "tag-011", "name": "CookieBot — Consent Banner", "type": "Custom HTML", "status": "Enabled", "fires_on": "Consent Initialization", "priority": 0, "fire_count_7d": 12567, "last_fired": "2026-02-07 10:55:00"},
        {"id": "tag-012", "name": "Schema.org — JSON-LD", "type": "Custom HTML", "status": "Enabled", "fires_on": "Product Pages", "priority": 3, "fire_count_7d": 4567, "last_fired": "2026-02-07 10:50:00"},
        {"id": "tag-013", "name": "GA4 — Scroll Depth", "type": "Google Analytics: GA4 Event", "status": "Enabled", "fires_on": "Scroll 25/50/75/90%", "priority": 3, "fire_count_7d": 8901, "last_fired": "2026-02-07 10:54:00"},
        {"id": "tag-014", "name": "GA4 — Form Submit", "type": "Google Analytics: GA4 Event", "status": "Enabled", "fires_on": "Form Submission", "priority": 2, "fire_count_7d": 1234, "last_fired": "2026-02-07 10:45:00"},
        {"id": "tag-015", "name": "Google Ads — Phone Conversion", "type": "Google Ads Conversion Tracking", "status": "Enabled", "fires_on": "Phone Click", "priority": 2, "fire_count_7d": 234, "last_fired": "2026-02-07 09:30:00"},
        {"id": "tag-016", "name": "Custom — Data Layer Push", "type": "Custom HTML", "status": "Paused", "fires_on": "DOM Ready", "priority": 5, "fire_count_7d": 0, "last_fired": None},
        {"id": "tag-017", "name": "A/B Test — Optimize", "type": "Custom HTML", "status": "Paused", "fires_on": "All Pages", "priority": 4, "fire_count_7d": 0, "last_fired": None},
        {"id": "tag-018", "name": "Debug — Console Logger", "type": "Custom HTML", "status": "Paused", "fires_on": "All Pages", "priority": 10, "fire_count_7d": 0, "last_fired": None},
    ],
}

GTM_MOCK_TRIGGERS = {
    "GTM-WX4R7N2": [
        {"id": "trg-001", "name": "All Pages", "type": "Page View", "fires_on": "Page View — All Pages", "filters": [], "used_by_tags": 6},
        {"id": "trg-002", "name": "DOM Ready", "type": "DOM Ready", "fires_on": "DOM Ready — All Pages", "filters": [], "used_by_tags": 1},
        {"id": "trg-003", "name": "Purchase Confirmation", "type": "Page View", "fires_on": "Page URL contains /thank-you", "filters": ["Page URL contains /thank-you"], "used_by_tags": 3},
        {"id": "trg-004", "name": "Add to Cart Click", "type": "Click — All Elements", "fires_on": "Click CSS selector .btn-add-cart", "filters": ["Click Classes contains btn-add-cart"], "used_by_tags": 1},
        {"id": "trg-005", "name": "Form Submission", "type": "Form Submission", "fires_on": "Form Submit — All Forms", "filters": [], "used_by_tags": 1},
        {"id": "trg-006", "name": "Scroll 25/50/75/90%", "type": "Scroll Depth", "fires_on": "Vertical Scroll — 25%, 50%, 75%, 90%", "filters": ["Scroll Depth Threshold: 25, 50, 75, 90"], "used_by_tags": 1},
        {"id": "trg-007", "name": "Phone Click", "type": "Click — Just Links", "fires_on": "Click URL starts with tel:", "filters": ["Click URL starts with tel:"], "used_by_tags": 1},
        {"id": "trg-008", "name": "Product Pages", "type": "Page View", "fires_on": "Page Path matches /product/*", "filters": ["Page Path matches regex /product/.*"], "used_by_tags": 1},
        {"id": "trg-009", "name": "Consent Initialization", "type": "Consent Initialization", "fires_on": "Consent Initialization — All Pages", "filters": [], "used_by_tags": 1},
        {"id": "trg-010", "name": "YouTube Video 50%", "type": "YouTube Video", "fires_on": "Video progress — 50%", "filters": ["Video Status: progress", "Video percent: 50"], "used_by_tags": 0},
        {"id": "trg-011", "name": "Custom Event — lead_form", "type": "Custom Event", "fires_on": "Event name equals lead_form_submit", "filters": ["Event: lead_form_submit"], "used_by_tags": 0},
        {"id": "trg-012", "name": "Timer — 30s", "type": "Timer", "fires_on": "Timer fires every 30000ms, limit 1", "filters": ["Interval: 30000ms", "Limit: 1"], "used_by_tags": 0},
    ],
}

GTM_MOCK_VARIABLES = {
    "GTM-WX4R7N2": [
        {"id": "var-001", "name": "GA4 Measurement ID", "type": "Google Analytics Settings", "value": "G-ABC123DEF4", "scope": "Global"},
        {"id": "var-002", "name": "Google Ads Conversion ID", "type": "Constant", "value": "AW-123456789", "scope": "Global"},
        {"id": "var-003", "name": "Google Ads Conversion Label", "type": "Constant", "value": "AbC-D_efG-h12_34-56", "scope": "Global"},
        {"id": "var-004", "name": "Page Hostname", "type": "URL", "value": "{{Page Hostname}}", "scope": "Built-in"},
        {"id": "var-005", "name": "Page Path", "type": "URL", "value": "{{Page Path}}", "scope": "Built-in"},
        {"id": "var-006", "name": "Click URL", "type": "Auto-Event Variable", "value": "{{Click URL}}", "scope": "Built-in"},
        {"id": "var-007", "name": "Click Classes", "type": "Auto-Event Variable", "value": "{{Click Classes}}", "scope": "Built-in"},
        {"id": "var-008", "name": "Form ID", "type": "Auto-Event Variable", "value": "{{Form ID}}", "scope": "Built-in"},
        {"id": "var-009", "name": "Scroll Depth Threshold", "type": "Auto-Event Variable", "value": "{{Scroll Depth Threshold}}", "scope": "Built-in"},
        {"id": "var-010", "name": "DL — ecommerce.value", "type": "Data Layer Variable", "value": "ecommerce.value", "scope": "User-Defined"},
        {"id": "var-011", "name": "DL — ecommerce.currency", "type": "Data Layer Variable", "value": "ecommerce.currency", "scope": "User-Defined"},
        {"id": "var-012", "name": "DL — ecommerce.items", "type": "Data Layer Variable", "value": "ecommerce.items", "scope": "User-Defined"},
        {"id": "var-013", "name": "DL — user.id", "type": "Data Layer Variable", "value": "user.id", "scope": "User-Defined"},
        {"id": "var-014", "name": "DL — user.membership", "type": "Data Layer Variable", "value": "user.membership", "scope": "User-Defined"},
        {"id": "var-015", "name": "JS — Cookie Consent", "type": "Custom JavaScript", "value": "function(){return document.cookie.indexOf('consent=1')>-1}", "scope": "User-Defined"},
        {"id": "var-016", "name": "CJS — Timestamp", "type": "Custom JavaScript", "value": "function(){return Date.now()}", "scope": "User-Defined"},
        {"id": "var-017", "name": "Referrer", "type": "HTTP Referrer", "value": "{{Referrer}}", "scope": "Built-in"},
        {"id": "var-018", "name": "Container ID", "type": "Container ID", "value": "GTM-WX4R7N2", "scope": "Built-in"},
        {"id": "var-019", "name": "Lookup — Page Category", "type": "Lookup Table", "value": "/product → Shop | /blog → Content | / → Home", "scope": "User-Defined"},
        {"id": "var-020", "name": "RegEx — UTM Source", "type": "RegEx Table", "value": "URL param utm_source", "scope": "User-Defined"},
        {"id": "var-021", "name": "1st Party Cookie — _ga", "type": "1st Party Cookie", "value": "_ga", "scope": "User-Defined"},
        {"id": "var-022", "name": "DOM — Meta Description", "type": "DOM Element", "value": "meta[name=description] → content", "scope": "User-Defined"},
        {"id": "var-023", "name": "Environment Name", "type": "Environment Name", "value": "{{Environment Name}}", "scope": "Built-in"},
    ],
}

GTM_MOCK_VERSIONS = {
    "GTM-WX4R7N2": [
        {"version": 12, "name": "v12 — Added CookieBot consent", "description": "Added consent initialization trigger and CookieBot banner tag", "published": "2026-02-05 14:30:00", "published_by": "admin@camarad.ai", "tags_added": 1, "tags_modified": 2, "tags_deleted": 0},
        {"version": 11, "name": "v11 — LinkedIn + TikTok pixels", "description": "Added LinkedIn Insight Tag and TikTok pixel for cross-platform tracking", "published": "2026-01-28 11:00:00", "published_by": "marketing@camarad.ai", "tags_added": 2, "tags_modified": 0, "tags_deleted": 0},
        {"version": 10, "name": "v10 — Schema.org JSON-LD", "description": "Added structured data tag for product pages (JSON-LD schema)", "published": "2026-01-20 16:45:00", "published_by": "dev@camarad.ai", "tags_added": 1, "tags_modified": 0, "tags_deleted": 0},
        {"version": 9, "name": "v9 — Scroll + Form tracking", "description": "Added GA4 scroll depth and form submission event tags", "published": "2026-01-15 09:20:00", "published_by": "admin@camarad.ai", "tags_added": 2, "tags_modified": 1, "tags_deleted": 0},
        {"version": 8, "name": "v8 — Google Ads phone conversion", "description": "Added phone click conversion tracking for Google Ads", "published": "2026-01-10 14:00:00", "published_by": "ppc@camarad.ai", "tags_added": 1, "tags_modified": 0, "tags_deleted": 0},
        {"version": 7, "name": "v7 — Meta Pixel upgrade", "description": "Updated Meta pixel to v2 with enhanced matching parameters", "published": "2026-01-05 10:30:00", "published_by": "marketing@camarad.ai", "tags_added": 0, "tags_modified": 2, "tags_deleted": 0},
        {"version": 6, "name": "v6 — Hotjar integration", "description": "Added Hotjar session recording and heatmap tag", "published": "2025-12-20 15:00:00", "published_by": "ux@camarad.ai", "tags_added": 1, "tags_modified": 0, "tags_deleted": 0},
        {"version": 5, "name": "v5 — GA4 ecommerce events", "description": "Added purchase, add_to_cart GA4 ecommerce event tags", "published": "2025-12-15 11:45:00", "published_by": "admin@camarad.ai", "tags_added": 2, "tags_modified": 1, "tags_deleted": 0},
        {"version": 4, "name": "v4 — Google Ads remarketing", "description": "Added Google Ads remarketing tag on all pages", "published": "2025-12-10 09:00:00", "published_by": "ppc@camarad.ai", "tags_added": 1, "tags_modified": 0, "tags_deleted": 0},
        {"version": 3, "name": "v3 — Google Ads conversion", "description": "Added Google Ads conversion tracking on purchase page", "published": "2025-12-05 14:30:00", "published_by": "ppc@camarad.ai", "tags_added": 1, "tags_modified": 0, "tags_deleted": 0},
    ],
}

GTM_MOCK_PREVIEW_EVENTS = [
    {"timestamp": "10:55:01.234", "event": "gtm.js", "tags_fired": ["CookieBot — Consent Banner", "GA4 — Page View", "Google Ads — Remarketing", "Meta Pixel — PageView", "Hotjar — Session Recording", "LinkedIn Insight Tag", "TikTok Pixel — Page View"], "tags_not_fired": ["GA4 — Purchase", "Google Ads — Conversion", "Meta Pixel — Purchase"], "data_layer": {"event": "gtm.js", "gtm.start": 1707300901234}},
    {"timestamp": "10:55:01.567", "event": "gtm.dom", "tags_fired": [], "tags_not_fired": [], "data_layer": {"event": "gtm.dom"}},
    {"timestamp": "10:55:02.100", "event": "gtm.load", "tags_fired": ["Schema.org — JSON-LD"], "tags_not_fired": [], "data_layer": {"event": "gtm.load"}},
    {"timestamp": "10:55:15.432", "event": "scroll", "tags_fired": ["GA4 — Scroll Depth"], "tags_not_fired": [], "data_layer": {"event": "scroll", "gtm.scrollThreshold": 25, "gtm.scrollUnits": "percent", "gtm.scrollDirection": "vertical"}},
    {"timestamp": "10:55:28.789", "event": "add_to_cart", "tags_fired": ["GA4 — Add to Cart"], "tags_not_fired": [], "data_layer": {"event": "add_to_cart", "ecommerce": {"currency": "RON", "value": 249.99, "items": [{"item_name": "Premium Widget", "item_id": "SKU-1234", "price": 249.99, "quantity": 1}]}}},
    {"timestamp": "10:56:03.456", "event": "gtm.formSubmit", "tags_fired": ["GA4 — Form Submit"], "tags_not_fired": [], "data_layer": {"event": "gtm.formSubmit", "gtm.elementId": "contact-form", "gtm.elementClasses": "form-main"}},
    {"timestamp": "10:56:45.123", "event": "purchase", "tags_fired": ["GA4 — Purchase", "Google Ads — Conversion", "Meta Pixel — Purchase"], "tags_not_fired": [], "data_layer": {"event": "purchase", "ecommerce": {"transaction_id": "T-20260207-001", "value": 499.98, "currency": "RON", "items": [{"item_name": "Premium Widget", "quantity": 2, "price": 249.99}]}}},
]


@app.route("/api/connectors/google-tag-manager/containers", methods=["GET"])
def gtm_containers():
    return jsonify({"containers": GTM_MOCK_CONTAINERS})


@app.route("/api/connectors/google-tag-manager/overview", methods=["GET"])
def gtm_overview():
    container_id = request.args.get('container_id', 'GTM-WX4R7N2')
    data = GTM_MOCK_OVERVIEW.get(container_id, GTM_MOCK_OVERVIEW['GTM-WX4R7N2'])
    return jsonify({"container_id": container_id, **data})


@app.route("/api/connectors/google-tag-manager/tags", methods=["GET"])
def gtm_tags():
    container_id = request.args.get('container_id', 'GTM-WX4R7N2')
    tags = GTM_MOCK_TAGS.get(container_id, GTM_MOCK_TAGS['GTM-WX4R7N2'])
    return jsonify({"container_id": container_id, "tags": tags})


@app.route("/api/connectors/google-tag-manager/triggers", methods=["GET"])
def gtm_triggers():
    container_id = request.args.get('container_id', 'GTM-WX4R7N2')
    triggers = GTM_MOCK_TRIGGERS.get(container_id, GTM_MOCK_TRIGGERS['GTM-WX4R7N2'])
    return jsonify({"container_id": container_id, "triggers": triggers})


@app.route("/api/connectors/google-tag-manager/variables", methods=["GET"])
def gtm_variables():
    container_id = request.args.get('container_id', 'GTM-WX4R7N2')
    variables = GTM_MOCK_VARIABLES.get(container_id, GTM_MOCK_VARIABLES['GTM-WX4R7N2'])
    return jsonify({"container_id": container_id, "variables": variables})


@app.route("/api/connectors/google-tag-manager/versions", methods=["GET"])
def gtm_versions():
    container_id = request.args.get('container_id', 'GTM-WX4R7N2')
    versions = GTM_MOCK_VERSIONS.get(container_id, GTM_MOCK_VERSIONS['GTM-WX4R7N2'])
    return jsonify({"container_id": container_id, "versions": versions})


@app.route("/api/connectors/google-tag-manager/preview", methods=["GET"])
def gtm_preview():
    return jsonify({"events": GTM_MOCK_PREVIEW_EVENTS, "mode": "Preview", "debug": True, "container": "GTM-WX4R7N2"})


@app.route("/api/connectors/google-tag-manager/test-call", methods=["POST"])
def gtm_test_call():
    data = request.get_json(force=True, silent=True) or {}
    endpoint = data.get('endpoint', '/tagmanager/v2/accounts/ACC/containers/GTM-WX4R7N2/workspaces/Default/tags')
    method = data.get('method', 'GET')
    import time
    start = time.time()

    if '/tags' in endpoint:
        response_body = {
            "tag": [
                {"tagId": "tag-001", "name": "GA4 — Page View", "type": "gaawc", "firingTriggerId": ["trg-001"],
                 "parameter": [{"key": "measurementId", "value": "G-ABC123DEF4", "type": "template"}],
                 "fingerprint": "1707300000001", "tagFiringOption": "ONCE_PER_EVENT"},
                {"tagId": "tag-004", "name": "Google Ads — Conversion", "type": "awct", "firingTriggerId": ["trg-003"],
                 "parameter": [{"key": "conversionId", "value": "AW-123456789", "type": "template"}],
                 "fingerprint": "1707300000004", "tagFiringOption": "ONCE_PER_EVENT"},
            ]
        }
    elif '/triggers' in endpoint:
        response_body = {
            "trigger": [
                {"triggerId": "trg-001", "name": "All Pages", "type": "PAGEVIEW",
                 "fingerprint": "1707300000010"},
                {"triggerId": "trg-003", "name": "Purchase Confirmation", "type": "PAGEVIEW",
                 "filter": [{"type": "CONTAINS", "parameter": [{"key": "arg0", "value": "{{Page URL}}"}, {"key": "arg1", "value": "/thank-you"}]}],
                 "fingerprint": "1707300000013"},
            ]
        }
    elif '/variables' in endpoint:
        response_body = {
            "variable": [
                {"variableId": "var-010", "name": "DL — ecommerce.value", "type": "v",
                 "parameter": [{"key": "dataLayerVersion", "value": "2"}, {"key": "name", "value": "ecommerce.value"}],
                 "fingerprint": "1707300000020"},
            ]
        }
    elif '/versions' in endpoint:
        response_body = {
            "containerVersion": [
                {"containerVersionId": "12", "name": "v12 — Added CookieBot consent",
                 "description": "Added consent initialization trigger and CookieBot banner tag",
                 "fingerprint": "1707321600000", "tag": [], "trigger": [], "variable": []}
            ]
        }
    else:
        response_body = {"container": GTM_MOCK_CONTAINERS[0]}

    elapsed = round((time.time() - start) * 1000 + 45, 0)

    return jsonify({
        "request": {
            "method": method, "endpoint": endpoint,
            "headers": {
                "Authorization": "Bearer ya29.a0GTM...mock_token",
                "Content-Type": "application/json",
                "x-goog-user-project": "camarad-tag-mgmt"
            },
            "body": None
        },
        "response": {
            "status_code": 200,
            "headers": {"content-type": "application/json", "x-goog-request-id": f"gtm-mock-{int(time.time())}"},
            "body": response_body
        },
        "latency_ms": elapsed,
        "quota": {"operations_remaining": 970, "daily_limit": 1000}
    })


# ─── Meta Ads (Facebook + Instagram) Mock API ───────────────────────────────
META_MOCK_AD_ACCOUNTS = [
    {"id": "act_123456789", "name": "TechStart Ads", "currency": "USD", "timezone": "America/New_York", "status": "ACTIVE", "business_name": "TechStart SRL"},
    {"id": "act_987654321", "name": "Personal Brand Ads", "currency": "EUR", "timezone": "Europe/Bucharest", "status": "ACTIVE", "business_name": "Camarad Personal"},
    {"id": "act_456789012", "name": "Ecom Shop Ads", "currency": "USD", "timezone": "America/Los_Angeles", "status": "ACTIVE", "business_name": "Ecom Direct LLC"},
]

META_MOCK_OVERVIEW = {
    "act_123456789": {
        "spend": 8245.67, "reach": 312450, "impressions": 987234, "clicks": 18934,
        "cpc": 0.44, "cpm": 8.35, "ctr": 1.92, "roas": 4.12, "conversions": 1245,
        "cost_per_conversion": 6.62, "frequency": 3.16,
        "spend_change": 12.4, "reach_change": 8.7, "conversions_change": 15.2, "roas_change": 3.1,
        "daily_spend": [
            {"date": "2026-02-01", "spend": 1102.34, "roas": 3.9, "conversions": 167},
            {"date": "2026-02-02", "spend": 1245.12, "roas": 4.3, "conversions": 189},
            {"date": "2026-02-03", "spend": 987.45, "roas": 3.7, "conversions": 142},
            {"date": "2026-02-04", "spend": 1189.23, "roas": 4.5, "conversions": 198},
            {"date": "2026-02-05", "spend": 1334.56, "roas": 4.1, "conversions": 201},
            {"date": "2026-02-06", "spend": 1156.78, "roas": 4.2, "conversions": 178},
            {"date": "2026-02-07", "spend": 1230.19, "roas": 4.0, "conversions": 170},
        ],
        "platform_breakdown": [
            {"platform": "Facebook", "spend": 5783.97, "impressions": 691364, "clicks": 13255, "conversions": 872},
            {"platform": "Instagram", "spend": 2461.70, "impressions": 295870, "clicks": 5679, "conversions": 373},
        ]
    }
}

META_MOCK_CAMPAIGNS = {
    "act_123456789": [
        {"id": "camp_001", "name": "Lead Gen — Winter Sale", "objective": "CONVERSIONS", "status": "ACTIVE",
         "spend": 2890.45, "reach": 89234, "impressions": 267891, "clicks": 5234, "ctr": 1.95, "roas": 4.8,
         "conversions": 412, "cost_per_result": 7.01, "budget_daily": 150, "budget_remaining": 1309.55,
         "start_date": "2026-01-15", "end_date": "2026-02-28"},
        {"id": "camp_002", "name": "Brand Awareness — Q1", "objective": "REACH", "status": "ACTIVE",
         "spend": 1567.23, "reach": 145678, "impressions": 432100, "clicks": 6789, "ctr": 1.57, "roas": 0,
         "conversions": 0, "cost_per_result": 0.01, "budget_daily": 80, "budget_remaining": 832.77,
         "start_date": "2026-01-01", "end_date": "2026-03-31"},
        {"id": "camp_003", "name": "Retargeting — Cart Abandoners", "objective": "CONVERSIONS", "status": "ACTIVE",
         "spend": 1987.34, "reach": 34567, "impressions": 156789, "clicks": 3456, "ctr": 2.20, "roas": 5.7,
         "conversions": 389, "cost_per_result": 5.11, "budget_daily": 100, "budget_remaining": 512.66,
         "start_date": "2026-01-20", "end_date": "2026-02-28"},
        {"id": "camp_004", "name": "Video Views — Product Demo", "objective": "VIDEO_VIEWS", "status": "ACTIVE",
         "spend": 876.54, "reach": 67890, "impressions": 198765, "clicks": 2345, "ctr": 1.18, "roas": 0,
         "conversions": 0, "cost_per_result": 0.004, "budget_daily": 50, "budget_remaining": 623.46,
         "start_date": "2026-02-01", "end_date": "2026-02-28"},
        {"id": "camp_005", "name": "App Install — Mobile Push", "objective": "APP_INSTALLS", "status": "ACTIVE",
         "spend": 543.21, "reach": 23456, "impressions": 87654, "clicks": 1876, "ctr": 2.14, "roas": 3.2,
         "conversions": 234, "cost_per_result": 2.32, "budget_daily": 30, "budget_remaining": 356.79,
         "start_date": "2026-02-01", "end_date": "2026-03-15"},
        {"id": "camp_006", "name": "Lookalike — High-Value Customers", "objective": "CONVERSIONS", "status": "ACTIVE",
         "spend": 1234.56, "reach": 45678, "impressions": 134567, "clicks": 2987, "ctr": 2.22, "roas": 4.1,
         "conversions": 187, "cost_per_result": 6.60, "budget_daily": 65, "budget_remaining": 715.44,
         "start_date": "2026-01-25", "end_date": "2026-02-28"},
        {"id": "camp_007", "name": "Messenger — Customer Support", "objective": "MESSAGES", "status": "PAUSED",
         "spend": 321.45, "reach": 12345, "impressions": 45678, "clicks": 987, "ctr": 2.16, "roas": 0,
         "conversions": 0, "cost_per_result": 0.33, "budget_daily": 20, "budget_remaining": 278.55,
         "start_date": "2026-01-10", "end_date": "2026-02-15"},
        {"id": "camp_008", "name": "Instagram Stories — Flash Sale", "objective": "CONVERSIONS", "status": "ACTIVE",
         "spend": 654.89, "reach": 34567, "impressions": 98765, "clicks": 2134, "ctr": 2.16, "roas": 3.9,
         "conversions": 123, "cost_per_result": 5.32, "budget_daily": 40, "budget_remaining": 545.11,
         "start_date": "2026-02-03", "end_date": "2026-02-14"},
    ]
}

META_MOCK_AD_SETS = {
    "camp_001": [
        {"id": "as_001", "name": "Women 25-34 — Fashion Interest", "status": "ACTIVE",
         "targeting": {"age_min": 25, "age_max": 34, "gender": "Female", "interests": ["Fashion", "Online Shopping", "Luxury Brands"]},
         "budget_daily": 50, "spend": 967.12, "reach": 29744, "clicks": 1745, "conversions": 137, "cpc": 0.55},
        {"id": "as_002", "name": "Men 25-44 — Tech Enthusiasts", "status": "ACTIVE",
         "targeting": {"age_min": 25, "age_max": 44, "gender": "Male", "interests": ["Technology", "Gadgets", "Early Adopters"]},
         "budget_daily": 50, "spend": 923.33, "reach": 29745, "clicks": 1745, "conversions": 137, "cpc": 0.53},
        {"id": "as_003", "name": "Broad — Lookalike 1%", "status": "ACTIVE",
         "targeting": {"age_min": 18, "age_max": 65, "gender": "All", "interests": ["Lookalike 1% — Purchasers"]},
         "budget_daily": 50, "spend": 1000.00, "reach": 29745, "clicks": 1744, "conversions": 138, "cpc": 0.57},
    ],
    "camp_003": [
        {"id": "as_004", "name": "Cart Abandoners — 7 days", "status": "ACTIVE",
         "targeting": {"age_min": 18, "age_max": 65, "gender": "All", "interests": ["Custom Audience — Cart 7d"]},
         "budget_daily": 60, "spend": 1190.40, "reach": 20740, "clicks": 2074, "conversions": 233, "cpc": 0.57},
        {"id": "as_005", "name": "Cart Abandoners — 30 days", "status": "ACTIVE",
         "targeting": {"age_min": 18, "age_max": 65, "gender": "All", "interests": ["Custom Audience — Cart 30d"]},
         "budget_daily": 40, "spend": 796.94, "reach": 13827, "clicks": 1382, "conversions": 156, "cpc": 0.58},
    ]
}

META_MOCK_ADS = {
    "as_001": [
        {"id": "ad_001", "name": "Carousel — Winter Collection", "format": "CAROUSEL", "status": "ACTIVE",
         "headline": "Winter Sale — Up to 50% Off", "cta": "SHOP_NOW",
         "impressions": 89234, "clicks": 582, "ctr": 0.65, "spend": 323.71, "conversions": 46,
         "thumbnail": "🖼️ 4 product images"},
        {"id": "ad_002", "name": "Video — Behind the Scenes", "format": "VIDEO", "status": "ACTIVE",
         "headline": "See How We Make It", "cta": "LEARN_MORE",
         "impressions": 67891, "clicks": 478, "ctr": 0.70, "spend": 289.45, "conversions": 38,
         "thumbnail": "🎬 15s vertical video"},
        {"id": "ad_003", "name": "Single Image — Hero Product", "format": "IMAGE", "status": "ACTIVE",
         "headline": "Best Seller — Limited Stock", "cta": "SHOP_NOW",
         "impressions": 45123, "clicks": 345, "ctr": 0.76, "spend": 198.34, "conversions": 28,
         "thumbnail": "📷 1200x628 product photo"},
        {"id": "ad_004", "name": "Stories — Countdown", "format": "STORIES", "status": "PAUSED",
         "headline": "24h Left — Flash Deal", "cta": "SHOP_NOW",
         "impressions": 23456, "clicks": 189, "ctr": 0.81, "spend": 78.90, "conversions": 12,
         "thumbnail": "📱 1080x1920 story creative"},
    ],
    "as_004": [
        {"id": "ad_005", "name": "Dynamic — Abandoned Products", "format": "DYNAMIC", "status": "ACTIVE",
         "headline": "Still interested? Come back!", "cta": "SHOP_NOW",
         "impressions": 78901, "clicks": 1234, "ctr": 1.56, "spend": 567.89, "conversions": 134,
         "thumbnail": "🔄 Dynamic product feed"},
        {"id": "ad_006", "name": "Carousel — You Left These Behind", "format": "CAROUSEL", "status": "ACTIVE",
         "headline": "Your cart is waiting", "cta": "SHOP_NOW",
         "impressions": 56789, "clicks": 890, "ctr": 1.57, "spend": 412.34, "conversions": 99,
         "thumbnail": "🖼️ Dynamic carousel"},
    ]
}

META_MOCK_BUDGET_PACING = {
    "act_123456789": {
        "total_budget": 12500, "spent": 8245.67, "remaining": 4254.33,
        "pacing_status": "ON_TRACK", "daily_avg_spend": 1177.95,
        "projected_spend": 12789.34, "days_remaining": 21,
        "campaigns": [
            {"name": "Lead Gen — Winter Sale", "budget": 4500, "spent": 2890.45, "pacing": "ON_TRACK", "pct": 64.2},
            {"name": "Brand Awareness — Q1", "budget": 2400, "spent": 1567.23, "pacing": "UNDERPACING", "pct": 65.3},
            {"name": "Retargeting — Cart Abandoners", "budget": 3000, "spent": 1987.34, "pacing": "ON_TRACK", "pct": 66.2},
            {"name": "Video Views — Product Demo", "budget": 1500, "spent": 876.54, "pacing": "UNDERPACING", "pct": 58.4},
            {"name": "Instagram Stories — Flash Sale", "budget": 1100, "spent": 654.89, "pacing": "OVERPACING", "pct": 59.5},
        ]
    }
}

@app.route("/api/connectors/meta-ads/accounts", methods=["GET"])
def meta_accounts():
    return jsonify({"accounts": META_MOCK_AD_ACCOUNTS})

@app.route("/api/connectors/meta-ads/overview", methods=["GET"])
def meta_overview():
    account_id = request.args.get('account_id', 'act_123456789')
    data = META_MOCK_OVERVIEW.get(account_id, {
        "spend": 0, "reach": 0, "impressions": 0, "clicks": 0, "cpc": 0, "cpm": 0,
        "ctr": 0, "roas": 0, "conversions": 0, "cost_per_conversion": 0, "frequency": 0,
        "spend_change": 0, "reach_change": 0, "conversions_change": 0, "roas_change": 0,
        "daily_spend": [], "platform_breakdown": []
    })
    return jsonify({"account_id": account_id, **data})

@app.route("/api/connectors/meta-ads/campaigns", methods=["GET"])
def meta_campaigns():
    account_id = request.args.get('account_id', 'act_123456789')
    campaigns = META_MOCK_CAMPAIGNS.get(account_id, [])
    return jsonify({"account_id": account_id, "campaigns": campaigns})

@app.route("/api/connectors/meta-ads/adsets", methods=["GET"])
def meta_adsets():
    campaign_id = request.args.get('campaign_id', 'camp_001')
    adsets = META_MOCK_AD_SETS.get(campaign_id, [])
    return jsonify({"campaign_id": campaign_id, "adsets": adsets})

@app.route("/api/connectors/meta-ads/ads", methods=["GET"])
def meta_ads_list():
    adset_id = request.args.get('adset_id', 'as_001')
    ads = META_MOCK_ADS.get(adset_id, [])
    return jsonify({"adset_id": adset_id, "ads": ads})

@app.route("/api/connectors/meta-ads/budget-pacing", methods=["GET"])
def meta_budget_pacing():
    account_id = request.args.get('account_id', 'act_123456789')
    data = META_MOCK_BUDGET_PACING.get(account_id, {"total_budget": 0, "spent": 0, "remaining": 0, "pacing_status": "UNKNOWN", "campaigns": []})
    return jsonify({"account_id": account_id, **data})

@app.route("/api/connectors/meta-ads/reports", methods=["GET"])
def meta_reports():
    account_id = request.args.get('account_id', 'act_123456789')
    campaigns = META_MOCK_CAMPAIGNS.get(account_id, [])
    rows = []
    for c in campaigns:
        for day_offset in range(7):
            from datetime import datetime, timedelta
            d = (datetime(2026, 2, 1) + timedelta(days=day_offset)).strftime("%Y-%m-%d")
            factor = round(0.8 + (hash(c["name"] + d) % 40) / 100, 2)
            rows.append({
                "date": d, "campaign": c["name"], "objective": c["objective"],
                "spend": round(c["spend"] / 7 * factor, 2),
                "reach": int(c["reach"] / 7 * factor),
                "impressions": int(c["impressions"] / 7 * factor),
                "clicks": int(c["clicks"] / 7 * factor),
                "conversions": int(c["conversions"] / 7 * factor),
                "ctr": round(c["ctr"] * factor, 2),
                "roas": round(c["roas"] * factor, 1) if c["roas"] > 0 else 0
            })
    return jsonify({"account_id": account_id, "rows": rows, "generated_at": "2026-02-07T17:30:00"})

@app.route("/api/connectors/meta-ads/test-call", methods=["POST"])
def meta_test_call():
    import time
    start = time.time()
    body = request.get_json(silent=True) or {}
    method = body.get("method", "GET")
    endpoint = body.get("endpoint", "campaigns")

    if endpoint == "campaigns":
        response_body = {"data": [{"id": c["id"], "name": c["name"], "status": c["status"],
                         "objective": c["objective"], "daily_budget": c["budget_daily"] * 100}
                        for c in META_MOCK_CAMPAIGNS.get("act_123456789", [])[:5]]}
    elif endpoint == "adsets":
        response_body = {"data": [{"id": a["id"], "name": a["name"], "status": a["status"],
                         "daily_budget": a["budget_daily"] * 100,
                         "targeting": {"age_min": a["targeting"]["age_min"], "age_max": a["targeting"]["age_max"]}}
                        for a in META_MOCK_AD_SETS.get("camp_001", [])]}
    elif endpoint == "ads":
        response_body = {"data": [{"id": a["id"], "name": a["name"], "status": a["status"],
                         "creative": {"title": a["headline"], "call_to_action_type": a["cta"]}}
                        for a in META_MOCK_ADS.get("as_001", [])]}
    elif endpoint == "insights":
        response_body = {"data": [{"date_start": "2026-02-01", "date_stop": "2026-02-07",
                         "spend": "8245.67", "reach": "312450", "impressions": "987234",
                         "clicks": "18934", "cpc": "0.44", "ctr": "1.92",
                         "actions": [{"action_type": "purchase", "value": "1245"}]}]}
    else:
        response_body = {"data": [{"id": META_MOCK_AD_ACCOUNTS[0]["id"], "name": META_MOCK_AD_ACCOUNTS[0]["name"]}]}

    elapsed = round((time.time() - start) * 1000 + 62, 0)
    return jsonify({
        "request": {
            "method": method, "endpoint": f"https://graph.facebook.com/v19.0/{endpoint}",
            "headers": {"Authorization": "Bearer EAAx...mock_token", "Content-Type": "application/json"},
            "body": None
        },
        "response": {"status_code": 200,
                      "headers": {"content-type": "application/json", "x-fb-request-id": f"meta-mock-{int(time.time())}"},
                      "body": response_body},
        "latency_ms": elapsed,
        "quota": {"calls_remaining": 4800, "hourly_limit": 5000, "reset_at": "2026-02-07T18:00:00"}
    })


# ═══════════════════════════════════════════════════════════════════════════
# TIKTOK ADS CONNECTOR — Mock Data & Endpoints
# ═══════════════════════════════════════════════════════════════════════════

TIKTOK_MOCK_AD_ACCOUNTS = [
    {"advertiser_id": "adv_987654321", "name": "TechStart TikTok", "currency": "USD", "timezone": "America/New_York", "status": "ACTIVE", "balance": 12450.00},
    {"advertiser_id": "adv_123456789", "name": "Personal Brand TikTok", "currency": "EUR", "timezone": "Europe/Bucharest", "status": "ACTIVE", "balance": 3200.00},
    {"advertiser_id": "adv_456789012", "name": "Ecom Shop TikTok", "currency": "USD", "timezone": "America/Los_Angeles", "status": "ACTIVE", "balance": 8900.00},
]

TIKTOK_MOCK_OVERVIEW = {
    "adv_987654321": {
        "spend": 2890.45,
        "reach": 890123,
        "impressions": 2456789,
        "video_views": 1234567,
        "video_views_p25": 987654,
        "video_views_p50": 741234,
        "video_views_p75": 512345,
        "video_views_p100": 345678,
        "completion_rate": 68.4,
        "engagement_rate": 12.1,
        "clicks": 34567,
        "cpc": 0.084,
        "ctr": 1.41,
        "roas": 3.9,
        "conversions": 312,
        "cost_per_conversion": 9.27,
        "likes": 89234,
        "comments": 12456,
        "shares": 45678,
        "daily_spend": [
            {"date": "2026-02-01", "spend": 385.20, "views": 168432},
            {"date": "2026-02-02", "spend": 412.50, "views": 182345},
            {"date": "2026-02-03", "spend": 398.70, "views": 175234},
            {"date": "2026-02-04", "spend": 445.10, "views": 195678},
            {"date": "2026-02-05", "spend": 378.90, "views": 162345},
            {"date": "2026-02-06", "spend": 435.80, "views": 189432},
            {"date": "2026-02-07", "spend": 434.25, "views": 161101},
        ],
        "placement_breakdown": [
            {"placement": "In-Feed", "spend": 1734.27, "views": 741234, "pct": 60},
            {"placement": "TopView", "spend": 578.09, "views": 246913, "pct": 20},
            {"placement": "Branded Hashtag", "spend": 289.05, "views": 123457, "pct": 10},
            {"placement": "Spark Ads", "spend": 289.04, "views": 122963, "pct": 10},
        ],
    }
}

TIKTOK_MOCK_CAMPAIGNS = [
    {"campaign_id": "camp_tt_001", "name": "Viral Dance Challenge", "objective": "VIDEO_VIEWS", "status": "ACTIVE", "budget": 4000, "spend": 1345.20, "video_views": 890000, "completion_rate": 72.1, "engagement_rate": 14.3, "roas": 4.2, "bid_strategy": "LOWEST_COST"},
    {"campaign_id": "camp_tt_002", "name": "Product Showcase Series", "objective": "CONVERSIONS", "status": "ACTIVE", "budget": 3500, "spend": 1890.50, "video_views": 456000, "completion_rate": 65.8, "engagement_rate": 9.7, "roas": 3.7, "bid_strategy": "COST_CAP"},
    {"campaign_id": "camp_tt_003", "name": "Trendy Outfit Try-On", "objective": "REACH", "status": "ACTIVE", "budget": 2000, "spend": 987.30, "video_views": 987654, "completion_rate": 61.2, "engagement_rate": 11.8, "roas": 0, "bid_strategy": "LOWEST_COST"},
    {"campaign_id": "camp_tt_004", "name": "Behind The Scenes BTS", "objective": "ENGAGEMENT", "status": "ACTIVE", "budget": 1500, "spend": 678.90, "video_views": 345678, "completion_rate": 58.9, "engagement_rate": 18.5, "roas": 0, "bid_strategy": "LOWEST_COST"},
    {"campaign_id": "camp_tt_005", "name": "Flash Sale Countdown", "objective": "CONVERSIONS", "status": "PAUSED", "budget": 2500, "spend": 2100.00, "video_views": 567890, "completion_rate": 55.3, "engagement_rate": 8.2, "roas": 5.1, "bid_strategy": "TARGET_CPA"},
    {"campaign_id": "camp_tt_006", "name": "User Generated Content", "objective": "VIDEO_VIEWS", "status": "ACTIVE", "budget": 1800, "spend": 923.45, "video_views": 723456, "completion_rate": 70.5, "engagement_rate": 16.1, "roas": 0, "bid_strategy": "LOWEST_COST"},
    {"campaign_id": "camp_tt_007", "name": "App Install Push Q1", "objective": "APP_INSTALL", "status": "ACTIVE", "budget": 5000, "spend": 3456.78, "video_views": 234567, "completion_rate": 45.2, "engagement_rate": 6.3, "roas": 2.8, "bid_strategy": "TARGET_CPA"},
    {"campaign_id": "camp_tt_008", "name": "Branded Effect Launch", "objective": "REACH", "status": "PAUSED", "budget": 3000, "spend": 1200.00, "video_views": 1123456, "completion_rate": 63.7, "engagement_rate": 13.9, "roas": 0, "bid_strategy": "LOWEST_COST"},
]

TIKTOK_MOCK_AD_GROUPS = {
    "camp_tt_001": [
        {"adgroup_id": "ag_tt_001", "name": "Women 18-24 Dance", "status": "ACTIVE", "budget": 1500, "spend": 567.80, "targeting": {"age": "18-24", "gender": "FEMALE", "interests": ["Dance", "Music", "Fashion"], "placements": ["In-Feed"], "music": "Trending sounds"}, "video_views": 345678, "completion_rate": 74.2},
        {"adgroup_id": "ag_tt_002", "name": "Men 18-34 Challenge", "status": "ACTIVE", "budget": 1200, "spend": 423.40, "targeting": {"age": "18-34", "gender": "MALE", "interests": ["Sports", "Gaming", "Comedy"], "placements": ["In-Feed", "TopView"], "music": "Custom sound"}, "video_views": 289000, "completion_rate": 69.8},
        {"adgroup_id": "ag_tt_003", "name": "All Genders 25-44 Broad", "status": "ACTIVE", "budget": 1300, "spend": 354.00, "targeting": {"age": "25-44", "gender": "ALL", "interests": ["Lifestyle", "Entertainment"], "placements": ["In-Feed"], "music": "No music"}, "video_views": 255322, "completion_rate": 71.5},
    ],
    "camp_tt_002": [
        {"adgroup_id": "ag_tt_004", "name": "Retargeting Website Visitors", "status": "ACTIVE", "budget": 2000, "spend": 1234.50, "targeting": {"age": "18-54", "gender": "ALL", "interests": ["Shopping", "E-commerce"], "placements": ["In-Feed"], "audiences": ["Website visitors 30d", "Cart abandoners 7d"]}, "video_views": 289000, "completion_rate": 62.3},
        {"adgroup_id": "ag_tt_005", "name": "Lookalike High Spenders", "status": "ACTIVE", "budget": 1500, "spend": 656.00, "targeting": {"age": "25-44", "gender": "ALL", "interests": ["Tech", "Gadgets"], "placements": ["In-Feed", "Spark Ads"], "audiences": ["Lookalike: Top 1% spenders"]}, "video_views": 167000, "completion_rate": 68.9},
    ],
    "camp_tt_003": [
        {"adgroup_id": "ag_tt_006", "name": "Fashion Enthusiasts 18-34", "status": "ACTIVE", "budget": 1000, "spend": 534.20, "targeting": {"age": "18-34", "gender": "FEMALE", "interests": ["Fashion", "Beauty", "OOTD"], "placements": ["In-Feed", "TopView"], "music": "Trending"}, "video_views": 534567, "completion_rate": 63.1},
        {"adgroup_id": "ag_tt_007", "name": "Style Broad 25-54", "status": "ACTIVE", "budget": 1000, "spend": 453.10, "targeting": {"age": "25-54", "gender": "ALL", "interests": ["Lifestyle", "Shopping"], "placements": ["In-Feed"], "music": "Original"}, "video_views": 453087, "completion_rate": 59.4},
    ],
}

TIKTOK_MOCK_ADS = {
    "ag_tt_001": [
        {"ad_id": "ad_tt_001", "name": "Dance Challenge Main Video", "format": "In-Feed Video", "status": "ACTIVE", "video_duration": "15s", "headline": "Can you do THE move? 💃🕺", "cta": "Learn More", "thumbnail": "🎬", "video_views": 198432, "completion_rate": 76.3, "engagement_rate": 15.8, "likes": 12345, "shares": 3456, "comments": 1234},
        {"ad_id": "ad_tt_002", "name": "Dance Tutorial Remix", "format": "Spark Ad", "status": "ACTIVE", "video_duration": "30s", "headline": "Learn the viral dance in 30s 🔥", "cta": "Watch More", "thumbnail": "🎵", "video_views": 147246, "completion_rate": 72.1, "engagement_rate": 13.2, "likes": 8765, "shares": 2345, "comments": 987},
    ],
    "ag_tt_002": [
        {"ad_id": "ad_tt_003", "name": "Challenge Duet Version", "format": "In-Feed Video", "status": "ACTIVE", "video_duration": "15s", "headline": "Duet with us! 🎯", "cta": "Join Challenge", "thumbnail": "🤝", "video_views": 156789, "completion_rate": 70.5, "engagement_rate": 14.1, "likes": 9876, "shares": 2789, "comments": 1098},
        {"ad_id": "ad_tt_004", "name": "TopView Challenge Opener", "format": "TopView", "status": "ACTIVE", "video_duration": "60s", "headline": "THE challenge everyone's talking about", "cta": "Participate", "thumbnail": "⭐", "video_views": 132211, "completion_rate": 68.8, "engagement_rate": 11.9, "likes": 7654, "shares": 1987, "comments": 876},
    ],
    "ag_tt_004": [
        {"ad_id": "ad_tt_005", "name": "Product Demo Vertical", "format": "In-Feed Video", "status": "ACTIVE", "video_duration": "20s", "headline": "Watch this transform 🛍️✨", "cta": "Shop Now", "thumbnail": "🛒", "video_views": 167890, "completion_rate": 64.5, "engagement_rate": 10.3, "likes": 5432, "shares": 1234, "comments": 567},
        {"ad_id": "ad_tt_006", "name": "Customer Testimonial UGC", "format": "Spark Ad", "status": "ACTIVE", "video_duration": "45s", "headline": "Real people, real results 💯", "cta": "Shop Now", "thumbnail": "💬", "video_views": 121110, "completion_rate": 60.1, "engagement_rate": 9.1, "likes": 4321, "shares": 987, "comments": 432},
    ],
    "ag_tt_006": [
        {"ad_id": "ad_tt_007", "name": "OOTD Transition Video", "format": "In-Feed Video", "status": "ACTIVE", "video_duration": "15s", "headline": "Outfit transitions that hit different 🔥", "cta": "See Collection", "thumbnail": "👗", "video_views": 289345, "completion_rate": 67.8, "engagement_rate": 16.2, "likes": 15678, "shares": 5432, "comments": 2345},
        {"ad_id": "ad_tt_008", "name": "Try-On Haul Extended", "format": "In-Feed Video", "status": "PAUSED", "video_duration": "60s", "headline": "Full try-on haul — which is YOUR fave?", "cta": "Shop Now", "thumbnail": "🛍️", "video_views": 245222, "completion_rate": 58.4, "engagement_rate": 12.5, "likes": 11234, "shares": 3456, "comments": 1876},
    ],
}

TIKTOK_MOCK_BUDGET_PACING = {
    "adv_987654321": {
        "overall_budget": 6000,
        "overall_spent": 4320.45,
        "overall_remaining": 1679.55,
        "daily_budget": 200,
        "daily_spent": 144.02,
        "days_remaining": 11,
        "pacing_status": "ON_TRACK",
        "campaigns": [
            {"name": "Viral Dance Challenge", "budget": 4000, "spent": 1345.20, "pacing": "ON_TRACK", "daily_avg": 192.17},
            {"name": "Product Showcase Series", "budget": 3500, "spent": 1890.50, "pacing": "OVERPACING", "daily_avg": 270.07},
            {"name": "Trendy Outfit Try-On", "budget": 2000, "spent": 987.30, "pacing": "ON_TRACK", "daily_avg": 141.04},
            {"name": "Behind The Scenes BTS", "budget": 1500, "spent": 678.90, "pacing": "UNDERPACING", "daily_avg": 97.00},
            {"name": "Flash Sale Countdown", "budget": 2500, "spent": 2100.00, "pacing": "OVERPACING", "daily_avg": 300.00},
            {"name": "User Generated Content", "budget": 1800, "spent": 923.45, "pacing": "ON_TRACK", "daily_avg": 131.92},
            {"name": "App Install Push Q1", "budget": 5000, "spent": 3456.78, "pacing": "ON_TRACK", "daily_avg": 493.83},
            {"name": "Branded Effect Launch", "budget": 3000, "spent": 1200.00, "pacing": "PAUSED", "daily_avg": 0},
        ]
    }
}


@app.route("/api/connectors/tiktok-ads/accounts", methods=["GET"])
def tiktok_accounts():
    """List available TikTok ad accounts"""
    return jsonify({"accounts": TIKTOK_MOCK_AD_ACCOUNTS})


@app.route("/api/connectors/tiktok-ads/overview", methods=["GET"])
def tiktok_overview():
    """Overview KPIs for a TikTok ad account"""
    acct = request.args.get("advertiser_id", "adv_987654321")
    data = TIKTOK_MOCK_OVERVIEW.get(acct, {
        "spend": 0, "reach": 0, "impressions": 0, "video_views": 0,
        "completion_rate": 0, "engagement_rate": 0, "clicks": 0, "cpc": 0, "ctr": 0,
        "roas": 0, "conversions": 0, "cost_per_conversion": 0,
        "likes": 0, "comments": 0, "shares": 0,
        "daily_spend": [], "placement_breakdown": []
    })
    return jsonify({"advertiser_id": acct, "overview": data})


@app.route("/api/connectors/tiktok-ads/campaigns", methods=["GET"])
def tiktok_campaigns():
    """List campaigns for a TikTok ad account"""
    return jsonify({"campaigns": TIKTOK_MOCK_CAMPAIGNS, "total": len(TIKTOK_MOCK_CAMPAIGNS)})


@app.route("/api/connectors/tiktok-ads/adgroups", methods=["GET"])
def tiktok_adgroups():
    """List ad groups for a campaign"""
    cid = request.args.get("campaign_id", "camp_tt_001")
    groups = TIKTOK_MOCK_AD_GROUPS.get(cid, TIKTOK_MOCK_AD_GROUPS["camp_tt_001"])
    return jsonify({"ad_groups": groups, "campaign_id": cid, "total": len(groups)})


@app.route("/api/connectors/tiktok-ads/ads", methods=["GET"])
def tiktok_ads():
    """List ads for an ad group"""
    agid = request.args.get("adgroup_id", "ag_tt_001")
    ads = TIKTOK_MOCK_ADS.get(agid, TIKTOK_MOCK_ADS["ag_tt_001"])
    return jsonify({"ads": ads, "adgroup_id": agid, "total": len(ads)})


@app.route("/api/connectors/tiktok-ads/budget-pacing", methods=["GET"])
def tiktok_budget_pacing():
    """Budget pacing data for a TikTok ad account"""
    acct = request.args.get("advertiser_id", "adv_987654321")
    data = TIKTOK_MOCK_BUDGET_PACING.get(acct, TIKTOK_MOCK_BUDGET_PACING["adv_987654321"])
    return jsonify({"advertiser_id": acct, "pacing": data})


@app.route("/api/connectors/tiktok-ads/reports", methods=["GET"])
def tiktok_reports():
    """Generate report data for TikTok ad account"""
    import datetime
    acct = request.args.get("advertiser_id", "adv_987654321")
    rows = []
    base = datetime.date(2026, 1, 31)
    for i in range(7):
        d = base + datetime.timedelta(days=i + 1)
        for c in TIKTOK_MOCK_CAMPAIGNS:
            daily_spend = round(c["spend"] / 7, 2)
            daily_views = int(c["video_views"] / 7)
            rows.append({
                "date": d.isoformat(),
                "campaign": c["name"],
                "objective": c["objective"],
                "spend": daily_spend,
                "video_views": daily_views,
                "completion_rate": c["completion_rate"],
                "engagement_rate": c["engagement_rate"],
                "roas": c["roas"],
            })
    return jsonify({"advertiser_id": acct, "rows": rows, "total_rows": len(rows)})


@app.route("/api/connectors/tiktok-ads/test-call", methods=["POST"])
def tiktok_test_call():
    """Simulate a TikTok Marketing API call"""
    import time
    start = time.time()
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint", "campaign/get")

    if "campaign" in endpoint:
        response_body = {"data": {"list": [{"campaign_id": c["campaign_id"], "campaign_name": c["name"],
                                            "objective_type": c["objective"], "budget": c["budget"],
                                            "status": c["status"]} for c in TIKTOK_MOCK_CAMPAIGNS[:3]]},
                         "code": 0, "message": "OK", "request_id": "tiktok-mock-req-001"}
    elif "adgroup" in endpoint:
        groups = TIKTOK_MOCK_AD_GROUPS["camp_tt_001"]
        response_body = {"data": {"list": [{"adgroup_id": g["adgroup_id"], "adgroup_name": g["name"],
                                            "budget": g["budget"], "status": g["status"]} for g in groups]},
                         "code": 0, "message": "OK", "request_id": "tiktok-mock-req-002"}
    elif "ad/get" in endpoint:
        ads = TIKTOK_MOCK_ADS["ag_tt_001"]
        response_body = {"data": {"list": [{"ad_id": a["ad_id"], "ad_name": a["name"],
                                            "ad_format": a["format"], "status": a["status"]} for a in ads]},
                         "code": 0, "message": "OK", "request_id": "tiktok-mock-req-003"}
    elif "report" in endpoint or "insight" in endpoint:
        response_body = {"data": {"list": [
            {"dimensions": {"stat_time_day": "2026-02-07"}, "metrics": {"spend": "434.25", "impressions": "351234",
             "video_views_p100": "49382", "clicks": "4938", "conversion": "44", "cost_per_conversion": "9.87"}},
        ]}, "code": 0, "message": "OK", "request_id": "tiktok-mock-req-004"}
    else:
        response_body = {"data": {"list": []}, "code": 0, "message": "OK", "request_id": "tiktok-mock-req-default"}

    elapsed = round((time.time() - start) * 1000, 1)
    return jsonify({
        "endpoint": endpoint,
        "method": data.get("method", "GET"),
        "request": {"advertiser_id": "adv_987654321", "endpoint": endpoint},
        "response": {"status_code": 200,
                      "headers": {"content-type": "application/json", "x-tt-logid": f"tiktok-mock-{int(time.time())}"},
                      "body": response_body},
        "latency_ms": elapsed,
        "quota": {"calls_remaining": 9500, "daily_limit": 10000, "reset_at": "2026-02-08T00:00:00"}
    })


# ═══════════════════════════════════════════════════════════════════════════
# LINKEDIN ADS CONNECTOR — Mock Data & Endpoints
# ═══════════════════════════════════════════════════════════════════════════

LINKEDIN_MOCK_AD_ACCOUNTS = [
    {"account_id": "li_acc_987654321", "name": "TechStart B2B", "currency": "USD", "status": "ACTIVE", "type": "BUSINESS", "company": "TechStart Inc."},
    {"account_id": "li_acc_123456789", "name": "Consulting Firm Ads", "currency": "EUR", "status": "ACTIVE", "type": "BUSINESS", "company": "Apex Consulting GmbH"},
    {"account_id": "li_acc_456789012", "name": "Startup Founders Ads", "currency": "USD", "status": "ACTIVE", "type": "BUSINESS", "company": "FounderHub LLC"},
]

LINKEDIN_MOCK_OVERVIEW = {
    "li_acc_987654321": {
        "spend": 3195.40,
        "impressions": 156789,
        "clicks": 2345,
        "ctr": 1.50,
        "cpc": 1.36,
        "leads": 89,
        "cost_per_lead": 35.90,
        "lead_form_completions": 73,
        "roas": 3.2,
        "conversions": 67,
        "social_actions": 1234,
        "follows": 312,
        "engagement_rate": 2.8,
        "video_views": 45678,
        "daily_spend": [
            {"date": "2026-02-01", "spend": 412.30, "leads": 11},
            {"date": "2026-02-02", "spend": 478.50, "leads": 14},
            {"date": "2026-02-03", "spend": 445.20, "leads": 12},
            {"date": "2026-02-04", "spend": 501.10, "leads": 16},
            {"date": "2026-02-05", "spend": 389.70, "leads": 10},
            {"date": "2026-02-06", "spend": 467.80, "leads": 13},
            {"date": "2026-02-07", "spend": 500.80, "leads": 13},
        ],
        "audience_breakdown": [
            {"segment": "Marketing Managers", "spend": 1277.16, "leads": 38, "pct": 40},
            {"segment": "C-Suite Executives", "spend": 958.62, "leads": 22, "pct": 30},
            {"segment": "IT Decision Makers", "spend": 639.08, "leads": 18, "pct": 20},
            {"segment": "HR Directors", "spend": 320.54, "leads": 11, "pct": 10},
        ],
    }
}

LINKEDIN_MOCK_CAMPAIGNS = [
    {"campaign_id": "li_camp_001", "name": "B2B Lead Gen Q1", "objective": "LEAD_GENERATION", "status": "ACTIVE", "budget": 3000, "spend": 1230.50, "impressions": 56789, "clicks": 823, "ctr": 1.45, "leads": 51, "cost_per_lead": 24.13, "roas": 4.1, "format": "SINGLE_IMAGE"},
    {"campaign_id": "li_camp_002", "name": "Thought Leadership Series", "objective": "BRAND_AWARENESS", "status": "ACTIVE", "budget": 2000, "spend": 987.30, "impressions": 89000, "clicks": 712, "ctr": 0.80, "leads": 0, "cost_per_lead": 0, "roas": 0, "format": "VIDEO"},
    {"campaign_id": "li_camp_003", "name": "Job Posting Boost", "objective": "WEBSITE_VISITS", "status": "ACTIVE", "budget": 1500, "spend": 678.20, "impressions": 21000, "clicks": 456, "ctr": 2.17, "leads": 18, "cost_per_lead": 37.68, "roas": 2.8, "format": "SINGLE_IMAGE"},
    {"campaign_id": "li_camp_004", "name": "Webinar Registration Drive", "objective": "LEAD_GENERATION", "status": "ACTIVE", "budget": 2500, "spend": 1456.78, "impressions": 45678, "clicks": 678, "ctr": 1.48, "leads": 42, "cost_per_lead": 34.69, "roas": 3.5, "format": "CAROUSEL"},
    {"campaign_id": "li_camp_005", "name": "Case Study Promotion", "objective": "ENGAGEMENT", "status": "PAUSED", "budget": 1000, "spend": 543.20, "impressions": 23456, "clicks": 345, "ctr": 1.47, "leads": 8, "cost_per_lead": 67.90, "roas": 1.9, "format": "DOCUMENT"},
    {"campaign_id": "li_camp_006", "name": "Product Launch Video", "objective": "VIDEO_VIEWS", "status": "ACTIVE", "budget": 1800, "spend": 892.45, "impressions": 67890, "clicks": 512, "ctr": 0.75, "leads": 0, "cost_per_lead": 0, "roas": 0, "format": "VIDEO"},
    {"campaign_id": "li_camp_007", "name": "Retargeting Decision Makers", "objective": "LEAD_GENERATION", "status": "ACTIVE", "budget": 2200, "spend": 1789.30, "impressions": 34567, "clicks": 567, "ctr": 1.64, "leads": 38, "cost_per_lead": 47.09, "roas": 3.8, "format": "MESSAGE_AD"},
    {"campaign_id": "li_camp_008", "name": "InMail Sales Outreach", "objective": "LEAD_GENERATION", "status": "PAUSED", "budget": 1200, "spend": 1100.00, "impressions": 12345, "clicks": 234, "ctr": 1.90, "leads": 19, "cost_per_lead": 57.89, "roas": 2.1, "format": "MESSAGE_AD"},
]

LINKEDIN_MOCK_AD_SETS = {
    "li_camp_001": [
        {"adset_id": "li_as_001", "name": "Marketing Managers 50-500 emp", "status": "ACTIVE", "budget": 1200, "spend": 534.20, "targeting": {"job_titles": ["Marketing Manager", "Head of Marketing", "VP Marketing"], "company_size": "51-500", "industries": ["Technology", "SaaS", "B2B Services"], "seniority": "Manager+", "locations": ["United States", "Canada"]}, "leads": 22, "ctr": 1.52},
        {"adset_id": "li_as_002", "name": "C-Suite Tech Companies", "status": "ACTIVE", "budget": 1000, "spend": 412.30, "targeting": {"job_titles": ["CEO", "CTO", "CMO", "CFO"], "company_size": "11-200", "industries": ["Technology", "Software"], "seniority": "C-Suite", "locations": ["United States"]}, "leads": 18, "ctr": 1.38},
        {"adset_id": "li_as_003", "name": "Broad Decision Makers", "status": "ACTIVE", "budget": 800, "spend": 284.00, "targeting": {"job_functions": ["Marketing", "Business Development", "Sales"], "company_size": "201-1000", "industries": ["All"], "seniority": "Director+", "locations": ["United States", "United Kingdom"]}, "leads": 11, "ctr": 1.45},
    ],
    "li_camp_004": [
        {"adset_id": "li_as_004", "name": "SaaS Founders & Executives", "status": "ACTIVE", "budget": 1500, "spend": 867.50, "targeting": {"job_titles": ["Founder", "Co-Founder", "CEO", "Product Manager"], "company_size": "1-50", "industries": ["SaaS", "Technology", "Startups"], "seniority": "Owner/C-Suite", "skills": ["B2B Marketing", "SaaS", "Growth Hacking"]}, "leads": 28, "ctr": 1.61},
        {"adset_id": "li_as_005", "name": "Agency Decision Makers", "status": "ACTIVE", "budget": 1000, "spend": 589.28, "targeting": {"job_titles": ["Agency Director", "Account Director", "Managing Director"], "company_size": "11-200", "industries": ["Advertising", "Marketing Agencies", "Digital Marketing"], "seniority": "Director+", "locations": ["United States", "Europe"]}, "leads": 14, "ctr": 1.33},
    ],
    "li_camp_007": [
        {"adset_id": "li_as_006", "name": "Retarget Website Visitors", "status": "ACTIVE", "budget": 1200, "spend": 978.30, "targeting": {"audiences": ["Website visitors 30d", "LinkedIn page visitors 90d"], "company_size": "51-500", "seniority": "Manager+", "matched_audiences": True}, "leads": 24, "ctr": 1.78},
        {"adset_id": "li_as_007", "name": "Lookalike Top Leads", "status": "ACTIVE", "budget": 1000, "spend": 811.00, "targeting": {"audiences": ["Lookalike: Top 1% converters", "Lookalike: CRM high-value"], "seniority": "Director+", "matched_audiences": True}, "leads": 14, "ctr": 1.50},
    ],
}

LINKEDIN_MOCK_ADS = {
    "li_as_001": [
        {"ad_id": "li_ad_001", "name": "Lead Gen Form - Main CTA", "format": "Single Image", "status": "ACTIVE", "headline": "Ready to Scale Your B2B Pipeline?", "description": "Join 500+ companies using our platform to generate qualified leads. Download our free playbook.", "cta": "Download", "thumbnail": "📊", "impressions": 23456, "clicks": 345, "ctr": 1.47, "leads": 12, "cost_per_lead": 22.50},
        {"ad_id": "li_ad_002", "name": "Lead Gen Form - Social Proof", "format": "Single Image", "status": "ACTIVE", "headline": "\"We 3x'd Our Pipeline in 90 Days\"", "description": "See how TechStart helped marketing teams close more deals. Real case study inside.", "cta": "Learn More", "thumbnail": "🏆", "impressions": 18234, "clicks": 267, "ctr": 1.46, "leads": 10, "cost_per_lead": 26.80},
    ],
    "li_as_002": [
        {"ad_id": "li_ad_003", "name": "Executive Whitepaper", "format": "Document Ad", "status": "ACTIVE", "headline": "2026 B2B Marketing Report — CEO Edition", "description": "The data-driven report every executive needs. Download your copy now.", "cta": "Download", "thumbnail": "📄", "impressions": 15678, "clicks": 198, "ctr": 1.26, "leads": 9, "cost_per_lead": 29.40},
        {"ad_id": "li_ad_004", "name": "Video Testimonial", "format": "Video", "status": "ACTIVE", "headline": "How Our CTO Transformed Lead Quality", "description": "Watch how enterprise teams use AI to qualify leads 5x faster.", "cta": "Watch Video", "thumbnail": "🎬", "impressions": 12345, "clicks": 156, "ctr": 1.26, "leads": 9, "cost_per_lead": 31.20},
    ],
    "li_as_004": [
        {"ad_id": "li_ad_005", "name": "Webinar Carousel", "format": "Carousel", "status": "ACTIVE", "headline": "5 Strategies That Actually Work in 2026", "description": "Swipe through our top B2B growth strategies. Register for the live deep-dive.", "cta": "Register", "thumbnail": "📱", "impressions": 19876, "clicks": 312, "ctr": 1.57, "leads": 16, "cost_per_lead": 28.90},
        {"ad_id": "li_ad_006", "name": "Webinar Single Image", "format": "Single Image", "status": "PAUSED", "headline": "Free Webinar: B2B Lead Gen Masterclass", "description": "Limited spots! Learn from industry experts how to build a predictable pipeline.", "cta": "Register", "thumbnail": "🎓", "impressions": 8765, "clicks": 123, "ctr": 1.40, "leads": 7, "cost_per_lead": 34.50},
    ],
    "li_as_006": [
        {"ad_id": "li_ad_007", "name": "Retarget - InMail Direct", "format": "Message Ad", "status": "ACTIVE", "headline": "Hey {{firstName}}, let's connect", "description": "I noticed you visited our platform. Would love to show you how we help teams like yours.", "cta": "Send Message", "thumbnail": "💬", "impressions": 5678, "clicks": 234, "ctr": 4.12, "leads": 15, "cost_per_lead": 42.30},
        {"ad_id": "li_ad_008", "name": "Retarget - Case Study", "format": "Single Image", "status": "ACTIVE", "headline": "Back by popular demand: Our #1 Case Study", "description": "You were interested before — here's the full story of how we helped a $10M ARR SaaS scale.", "cta": "Read More", "thumbnail": "📈", "impressions": 4567, "clicks": 189, "ctr": 4.14, "leads": 9, "cost_per_lead": 51.20},
    ],
}

LINKEDIN_MOCK_BUDGET_PACING = {
    "li_acc_987654321": {
        "overall_budget": 4500,
        "overall_spent": 3195.40,
        "overall_remaining": 1304.60,
        "daily_budget": 150,
        "daily_spent": 106.51,
        "days_remaining": 12,
        "pacing_status": "ON_TRACK",
        "campaigns": [
            {"name": "B2B Lead Gen Q1", "budget": 3000, "spent": 1230.50, "pacing": "ON_TRACK", "daily_avg": 175.79},
            {"name": "Thought Leadership Series", "budget": 2000, "spent": 987.30, "pacing": "ON_TRACK", "daily_avg": 141.04},
            {"name": "Job Posting Boost", "budget": 1500, "spent": 678.20, "pacing": "UNDERPACING", "daily_avg": 96.89},
            {"name": "Webinar Registration Drive", "budget": 2500, "spent": 1456.78, "pacing": "OVERPACING", "daily_avg": 208.11},
            {"name": "Case Study Promotion", "budget": 1000, "spent": 543.20, "pacing": "PAUSED", "daily_avg": 0},
            {"name": "Product Launch Video", "budget": 1800, "spent": 892.45, "pacing": "ON_TRACK", "daily_avg": 127.49},
            {"name": "Retargeting Decision Makers", "budget": 2200, "spent": 1789.30, "pacing": "OVERPACING", "daily_avg": 255.61},
            {"name": "InMail Sales Outreach", "budget": 1200, "spent": 1100.00, "pacing": "PAUSED", "daily_avg": 0},
        ]
    }
}


@app.route("/api/connectors/linkedin-ads/accounts", methods=["GET"])
def linkedin_accounts():
    """List available LinkedIn ad accounts"""
    return jsonify({"accounts": LINKEDIN_MOCK_AD_ACCOUNTS})


@app.route("/api/connectors/linkedin-ads/overview", methods=["GET"])
def linkedin_overview():
    """Overview KPIs for a LinkedIn ad account"""
    acct = request.args.get("account_id", "li_acc_987654321")
    data = LINKEDIN_MOCK_OVERVIEW.get(acct, {
        "spend": 0, "impressions": 0, "clicks": 0, "ctr": 0, "cpc": 0,
        "leads": 0, "cost_per_lead": 0, "lead_form_completions": 0,
        "roas": 0, "conversions": 0, "social_actions": 0, "follows": 0,
        "engagement_rate": 0, "video_views": 0,
        "daily_spend": [], "audience_breakdown": []
    })
    return jsonify({"account_id": acct, "overview": data})


@app.route("/api/connectors/linkedin-ads/campaigns", methods=["GET"])
def linkedin_campaigns():
    """List campaigns for a LinkedIn ad account"""
    return jsonify({"campaigns": LINKEDIN_MOCK_CAMPAIGNS, "total": len(LINKEDIN_MOCK_CAMPAIGNS)})


@app.route("/api/connectors/linkedin-ads/adsets", methods=["GET"])
def linkedin_adsets():
    """List ad sets for a campaign"""
    cid = request.args.get("campaign_id", "li_camp_001")
    sets = LINKEDIN_MOCK_AD_SETS.get(cid, LINKEDIN_MOCK_AD_SETS["li_camp_001"])
    return jsonify({"ad_sets": sets, "campaign_id": cid, "total": len(sets)})


@app.route("/api/connectors/linkedin-ads/ads", methods=["GET"])
def linkedin_ads():
    """List ads for an ad set"""
    asid = request.args.get("adset_id", "li_as_001")
    ads = LINKEDIN_MOCK_ADS.get(asid, LINKEDIN_MOCK_ADS["li_as_001"])
    return jsonify({"ads": ads, "adset_id": asid, "total": len(ads)})


@app.route("/api/connectors/linkedin-ads/budget-pacing", methods=["GET"])
def linkedin_budget_pacing():
    """Budget pacing data for a LinkedIn ad account"""
    acct = request.args.get("account_id", "li_acc_987654321")
    data = LINKEDIN_MOCK_BUDGET_PACING.get(acct, LINKEDIN_MOCK_BUDGET_PACING["li_acc_987654321"])
    return jsonify({"account_id": acct, "pacing": data})


@app.route("/api/connectors/linkedin-ads/reports", methods=["GET"])
def linkedin_reports():
    """Generate report data for LinkedIn ad account"""
    import datetime
    acct = request.args.get("account_id", "li_acc_987654321")
    rows = []
    base = datetime.date(2026, 1, 31)
    for i in range(7):
        d = base + datetime.timedelta(days=i + 1)
        for c in LINKEDIN_MOCK_CAMPAIGNS:
            daily_spend = round(c["spend"] / 7, 2)
            daily_leads = max(0, round(c["leads"] / 7))
            daily_impressions = int(c["impressions"] / 7)
            rows.append({
                "date": d.isoformat(),
                "campaign": c["name"],
                "objective": c["objective"],
                "format": c["format"],
                "spend": daily_spend,
                "impressions": daily_impressions,
                "clicks": int(c["clicks"] / 7),
                "ctr": c["ctr"],
                "leads": daily_leads,
                "cost_per_lead": c["cost_per_lead"],
                "roas": c["roas"],
            })
    return jsonify({"account_id": acct, "rows": rows, "total_rows": len(rows)})


@app.route("/api/connectors/linkedin-ads/test-call", methods=["POST"])
def linkedin_test_call():
    """Simulate a LinkedIn Marketing API call"""
    import time
    start = time.time()
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint", "adCampaignsV2")

    if "campaign" in endpoint.lower():
        response_body = {"elements": [
            {"id": f"urn:li:sponsoredCampaign:{c['campaign_id']}", "name": c["name"],
             "status": c["status"], "objectiveType": c["objective"],
             "dailyBudget": {"amount": str(round(c["budget"]/30, 2)), "currencyCode": "USD"},
             "costType": "CPM", "format": c["format"]}
            for c in LINKEDIN_MOCK_CAMPAIGNS[:3]
        ], "paging": {"count": 3, "start": 0, "total": len(LINKEDIN_MOCK_CAMPAIGNS)}}
    elif "creative" in endpoint.lower() or "adset" in endpoint.lower():
        sets = LINKEDIN_MOCK_AD_SETS["li_camp_001"]
        response_body = {"elements": [
            {"id": f"urn:li:sponsoredCreative:{s['adset_id']}", "name": s["name"],
             "status": s["status"], "campaign": "urn:li:sponsoredCampaign:li_camp_001"}
            for s in sets
        ], "paging": {"count": len(sets), "start": 0, "total": len(sets)}}
    elif "analytic" in endpoint.lower() or "insight" in endpoint.lower():
        response_body = {"elements": [
            {"dateRange": {"start": {"year": 2026, "month": 2, "day": 7}, "end": {"year": 2026, "month": 2, "day": 7}},
             "impressions": 22398, "clicks": 335, "costInLocalCurrency": "456.23",
             "leads": 13, "landingPageClicks": 289, "totalEngagements": 567,
             "videoViews": 6543, "shares": 45, "likes": 234, "comments": 67}
        ], "paging": {"count": 1, "start": 0, "total": 1}}
    else:
        response_body = {"elements": [], "paging": {"count": 0, "start": 0, "total": 0}}

    elapsed = round((time.time() - start) * 1000, 1)
    return jsonify({
        "endpoint": endpoint,
        "method": data.get("method", "GET"),
        "request": {"account_id": "li_acc_987654321", "endpoint": endpoint},
        "response": {"status_code": 200,
                      "headers": {"content-type": "application/json", "x-li-uuid": f"linkedin-mock-{int(time.time())}",
                                  "x-restli-protocol-version": "2.0.0"},
                      "body": response_body},
        "latency_ms": elapsed,
        "quota": {"calls_remaining": 4500, "daily_limit": 5000, "reset_at": "2026-02-08T00:00:00"}
    })


# ═══════════════════════════════════════════════════════════════════════════
# STRIPE  –  Mock Data & Endpoints (Phase 18)
# ═══════════════════════════════════════════════════════════════════════════

STRIPE_MOCK_ACCOUNTS = [
    {"account_id": "acct_1J7xQR2eZvKYlo2C", "name": "TechStart Live", "mode": "live", "currency": "USD", "status": "ACTIVE", "country": "US", "business_type": "company"},
    {"account_id": "acct_1K8yRS3fAwLZmp3D", "name": "TechStart Test", "mode": "test", "currency": "USD", "status": "ACTIVE", "country": "US", "business_type": "company"},
]

STRIPE_MOCK_OVERVIEW = {
    "acct_1J7xQR2eZvKYlo2C": {
        "mrr": 4812,
        "arr": 57744,
        "revenue_today": 1236.50,
        "revenue_this_month": 14236,
        "revenue_last_month": 12890,
        "revenue_growth": 10.5,
        "active_subscriptions": 231,
        "new_subscriptions": 18,
        "churned_subscriptions": 9,
        "churn_rate": 4.2,
        "net_revenue": 12890,
        "gross_volume": 16450,
        "refunds": 560,
        "fees": 1000,
        "average_revenue_per_user": 20.83,
        "lifetime_value": 294,
        "cac": 85,
        "ltv_cac_ratio": 3.46,
        "runway_months": 18,
        "monthly_burn": 8200,
        "cash_balance": 147600,
        "mrr_trend": [
            {"month": "2025-09", "mrr": 3120},
            {"month": "2025-10", "mrr": 3450},
            {"month": "2025-11", "mrr": 3890},
            {"month": "2025-12", "mrr": 4120},
            {"month": "2026-01", "mrr": 4510},
            {"month": "2026-02", "mrr": 4812},
        ],
        "revenue_by_product": [
            {"product": "Pro Monthly", "revenue": 3920, "subscribers": 80, "pct": 43},
            {"product": "Basic Monthly", "revenue": 892, "subscribers": 89, "pct": 10},
            {"product": "Pro Annual", "revenue": 5880, "subscribers": 42, "pct": 34},
            {"product": "Enterprise", "revenue": 3544, "subscribers": 20, "pct": 13},
        ],
    }
}

STRIPE_MOCK_SUBSCRIPTIONS = [
    {"sub_id": "sub_1N3abc001", "customer_id": "cus_Q1a001", "customer_email": "john@techstart.com", "plan": "Pro Monthly", "amount": 49.00, "currency": "USD", "status": "active", "interval": "month", "current_period_start": "2026-01-07", "current_period_end": "2026-02-07", "created": "2025-06-15", "cancel_at_period_end": False},
    {"sub_id": "sub_1N3abc002", "customer_id": "cus_Q1a002", "customer_email": "sarah@designhub.io", "plan": "Pro Annual", "amount": 468.00, "currency": "USD", "status": "active", "interval": "year", "current_period_start": "2025-08-01", "current_period_end": "2026-08-01", "created": "2025-08-01", "cancel_at_period_end": False},
    {"sub_id": "sub_1N3abc003", "customer_id": "cus_Q1a003", "customer_email": "mike@acmecorp.com", "plan": "Enterprise", "amount": 199.00, "currency": "USD", "status": "active", "interval": "month", "current_period_start": "2026-01-15", "current_period_end": "2026-02-15", "created": "2025-09-20", "cancel_at_period_end": False},
    {"sub_id": "sub_1N3abc004", "customer_id": "cus_Q1a004", "customer_email": "lisa@startup.co", "plan": "Basic Monthly", "amount": 9.00, "currency": "USD", "status": "active", "interval": "month", "current_period_start": "2026-02-01", "current_period_end": "2026-03-01", "created": "2026-01-01", "cancel_at_period_end": False},
    {"sub_id": "sub_1N3abc005", "customer_id": "cus_Q1a005", "customer_email": "alex@bigcorp.com", "plan": "Pro Monthly", "amount": 49.00, "currency": "USD", "status": "trialing", "interval": "month", "current_period_start": "2026-02-01", "current_period_end": "2026-02-14", "created": "2026-02-01", "cancel_at_period_end": False},
    {"sub_id": "sub_1N3abc006", "customer_id": "cus_Q1a006", "customer_email": "nina@freelance.dev", "plan": "Pro Monthly", "amount": 49.00, "currency": "USD", "status": "canceled", "interval": "month", "current_period_start": "2026-01-05", "current_period_end": "2026-02-05", "created": "2025-11-05", "cancel_at_period_end": True},
    {"sub_id": "sub_1N3abc007", "customer_id": "cus_Q1a007", "customer_email": "tom@agency.io", "plan": "Enterprise", "amount": 199.00, "currency": "USD", "status": "active", "interval": "month", "current_period_start": "2026-01-20", "current_period_end": "2026-02-20", "created": "2025-10-20", "cancel_at_period_end": False},
    {"sub_id": "sub_1N3abc008", "customer_id": "cus_Q1a008", "customer_email": "emma@consultfirm.com", "plan": "Pro Annual", "amount": 468.00, "currency": "USD", "status": "past_due", "interval": "year", "current_period_start": "2025-12-01", "current_period_end": "2026-12-01", "created": "2025-12-01", "cancel_at_period_end": False},
    {"sub_id": "sub_1N3abc009", "customer_id": "cus_Q1a009", "customer_email": "dave@devshop.net", "plan": "Basic Monthly", "amount": 9.00, "currency": "USD", "status": "active", "interval": "month", "current_period_start": "2026-02-03", "current_period_end": "2026-03-03", "created": "2025-07-03", "cancel_at_period_end": False},
    {"sub_id": "sub_1N3abc010", "customer_id": "cus_Q1a010", "customer_email": "olivia@marketinghq.com", "plan": "Pro Monthly", "amount": 49.00, "currency": "USD", "status": "active", "interval": "month", "current_period_start": "2026-01-28", "current_period_end": "2026-02-28", "created": "2025-04-28", "cancel_at_period_end": False},
    {"sub_id": "sub_1N3abc011", "customer_id": "cus_Q1a011", "customer_email": "brad@ecommerce.store", "plan": "Enterprise", "amount": 199.00, "currency": "USD", "status": "active", "interval": "month", "current_period_start": "2026-02-01", "current_period_end": "2026-03-01", "created": "2025-05-01", "cancel_at_period_end": False},
    {"sub_id": "sub_1N3abc012", "customer_id": "cus_Q1a012", "customer_email": "grace@analytics.co", "plan": "Basic Monthly", "amount": 9.00, "currency": "USD", "status": "canceled", "interval": "month", "current_period_start": "2026-01-10", "current_period_end": "2026-02-10", "created": "2025-08-10", "cancel_at_period_end": True},
]

STRIPE_MOCK_PAYMENTS = [
    {"payment_id": "ch_3P1abc001", "amount": 49.00, "currency": "USD", "status": "succeeded", "customer_id": "cus_Q1a001", "customer_email": "john@techstart.com", "description": "Pro Monthly subscription", "created": "2026-02-07T09:15:00", "payment_method": "card", "card_last4": "4242"},
    {"payment_id": "ch_3P1abc002", "amount": 199.00, "currency": "USD", "status": "succeeded", "customer_id": "cus_Q1a003", "customer_email": "mike@acmecorp.com", "description": "Enterprise subscription", "created": "2026-02-06T14:30:00", "payment_method": "card", "card_last4": "5555"},
    {"payment_id": "ch_3P1abc003", "amount": 468.00, "currency": "USD", "status": "succeeded", "customer_id": "cus_Q1a002", "customer_email": "sarah@designhub.io", "description": "Pro Annual subscription", "created": "2026-02-05T11:00:00", "payment_method": "card", "card_last4": "1234"},
    {"payment_id": "ch_3P1abc004", "amount": 49.00, "currency": "USD", "status": "refunded", "customer_id": "cus_Q1a006", "customer_email": "nina@freelance.dev", "description": "Pro Monthly — refund", "created": "2026-02-05T08:45:00", "payment_method": "card", "card_last4": "9876"},
    {"payment_id": "ch_3P1abc005", "amount": 9.00, "currency": "USD", "status": "succeeded", "customer_id": "cus_Q1a004", "customer_email": "lisa@startup.co", "description": "Basic Monthly subscription", "created": "2026-02-04T16:20:00", "payment_method": "card", "card_last4": "0000"},
    {"payment_id": "ch_3P1abc006", "amount": 199.00, "currency": "USD", "status": "succeeded", "customer_id": "cus_Q1a007", "customer_email": "tom@agency.io", "description": "Enterprise subscription", "created": "2026-02-03T10:00:00", "payment_method": "card", "card_last4": "3333"},
    {"payment_id": "ch_3P1abc007", "amount": 49.00, "currency": "USD", "status": "succeeded", "customer_id": "cus_Q1a010", "customer_email": "olivia@marketinghq.com", "description": "Pro Monthly subscription", "created": "2026-02-02T13:30:00", "payment_method": "card", "card_last4": "7777"},
    {"payment_id": "ch_3P1abc008", "amount": 468.00, "currency": "USD", "status": "failed", "customer_id": "cus_Q1a008", "customer_email": "emma@consultfirm.com", "description": "Pro Annual — payment failed", "created": "2026-02-01T09:00:00", "payment_method": "card", "card_last4": "6666"},
    {"payment_id": "ch_3P1abc009", "amount": 199.00, "currency": "USD", "status": "succeeded", "customer_id": "cus_Q1a011", "customer_email": "brad@ecommerce.store", "description": "Enterprise subscription", "created": "2026-02-01T07:00:00", "payment_method": "card", "card_last4": "8888"},
    {"payment_id": "ch_3P1abc010", "amount": 9.00, "currency": "USD", "status": "succeeded", "customer_id": "cus_Q1a009", "customer_email": "dave@devshop.net", "description": "Basic Monthly subscription", "created": "2026-01-31T15:45:00", "payment_method": "card", "card_last4": "2222"},
]

STRIPE_MOCK_CUSTOMERS = [
    {"customer_id": "cus_Q1a001", "email": "john@techstart.com", "name": "John Mitchell", "created": "2025-06-15", "status": "active", "ltv": 490.00, "total_spent": 490.00, "subscriptions": 1, "plan": "Pro Monthly", "country": "US"},
    {"customer_id": "cus_Q1a002", "email": "sarah@designhub.io", "name": "Sarah Chen", "created": "2025-08-01", "status": "active", "ltv": 468.00, "total_spent": 468.00, "subscriptions": 1, "plan": "Pro Annual", "country": "US"},
    {"customer_id": "cus_Q1a003", "email": "mike@acmecorp.com", "name": "Mike Rodriguez", "created": "2025-09-20", "status": "active", "ltv": 995.00, "total_spent": 995.00, "subscriptions": 1, "plan": "Enterprise", "country": "US"},
    {"customer_id": "cus_Q1a004", "email": "lisa@startup.co", "name": "Lisa Park", "created": "2026-01-01", "status": "active", "ltv": 18.00, "total_spent": 18.00, "subscriptions": 1, "plan": "Basic Monthly", "country": "CA"},
    {"customer_id": "cus_Q1a005", "email": "alex@bigcorp.com", "name": "Alex Thompson", "created": "2026-02-01", "status": "trialing", "ltv": 0, "total_spent": 0, "subscriptions": 1, "plan": "Pro Monthly", "country": "US"},
    {"customer_id": "cus_Q1a006", "email": "nina@freelance.dev", "name": "Nina Kowalski", "created": "2025-11-05", "status": "canceled", "ltv": 147.00, "total_spent": 147.00, "subscriptions": 0, "plan": "Pro Monthly", "country": "DE"},
    {"customer_id": "cus_Q1a007", "email": "tom@agency.io", "name": "Tom Barnes", "created": "2025-10-20", "status": "active", "ltv": 796.00, "total_spent": 796.00, "subscriptions": 1, "plan": "Enterprise", "country": "UK"},
    {"customer_id": "cus_Q1a008", "email": "emma@consultfirm.com", "name": "Emma Davis", "created": "2025-12-01", "status": "past_due", "ltv": 468.00, "total_spent": 468.00, "subscriptions": 1, "plan": "Pro Annual", "country": "US"},
    {"customer_id": "cus_Q1a009", "email": "dave@devshop.net", "name": "Dave Wilson", "created": "2025-07-03", "status": "active", "ltv": 63.00, "total_spent": 63.00, "subscriptions": 1, "plan": "Basic Monthly", "country": "US"},
    {"customer_id": "cus_Q1a010", "email": "olivia@marketinghq.com", "name": "Olivia Martinez", "created": "2025-04-28", "status": "active", "ltv": 490.00, "total_spent": 490.00, "subscriptions": 1, "plan": "Pro Monthly", "country": "US"},
    {"customer_id": "cus_Q1a011", "email": "brad@ecommerce.store", "name": "Brad Johnson", "created": "2025-05-01", "status": "active", "ltv": 1791.00, "total_spent": 1791.00, "subscriptions": 1, "plan": "Enterprise", "country": "US"},
    {"customer_id": "cus_Q1a012", "email": "grace@analytics.co", "name": "Grace Kim", "created": "2025-08-10", "status": "canceled", "ltv": 54.00, "total_spent": 54.00, "subscriptions": 0, "plan": "Basic Monthly", "country": "KR"},
]

STRIPE_MOCK_BUDGET_PACING = {
    "acct_1J7xQR2eZvKYlo2C": {
        "monthly_revenue_goal": 18000,
        "current_revenue": 14236,
        "projected_revenue": 16800,
        "goal_pct": 79.1,
        "projected_pct": 93.3,
        "days_elapsed": 7,
        "days_remaining": 21,
        "daily_run_rate": 2033.71,
        "needed_daily_rate": 1179.24,
        "pacing_status": "AHEAD",
        "cash_runway_months": 18,
        "monthly_burn": 8200,
        "cash_balance": 147600,
        "products": [
            {"name": "Pro Monthly", "goal": 5000, "current": 3920, "pacing": "ON_TRACK", "daily_avg": 560.00},
            {"name": "Basic Monthly", "goal": 1500, "current": 892, "pacing": "UNDERPACING", "daily_avg": 127.43},
            {"name": "Pro Annual", "goal": 7000, "current": 5880, "pacing": "AHEAD", "daily_avg": 840.00},
            {"name": "Enterprise", "goal": 4500, "current": 3544, "pacing": "ON_TRACK", "daily_avg": 506.29},
        ]
    }
}


def _stripe_gateway_fetch(path_candidates, params=None, timeout=20):
    if not COOLBITS_GATEWAY_ENABLED:
        return None, {"enabled": False, "reason": "disabled"}

    last_error = None
    for path in path_candidates:
        try:
            status, payload, text = _coolbits_request("GET", path, params=params, timeout=timeout)
            if 200 <= int(status) < 300:
                return payload, {"enabled": True, "path": path, "status": int(status)}
            last_error = f"{path} -> HTTP {status}"
            if payload is None and text:
                last_error += f" ({text[:180]})"
        except Exception as e:
            last_error = f"{path} -> {e}"
    return None, {"enabled": True, "error": last_error or "gateway_unavailable"}


def _stripe_billing_summary():
    payload, gw = _stripe_gateway_fetch([
        "/api/billing/summary",
        "/api/connectors/stripe/overview",
        "/api/connectors/stripe/summary",
    ], timeout=15)
    if isinstance(payload, dict) and isinstance(payload.get("stripe"), dict):
        return payload, gw
    return None, gw


def _stripe_currency_from_summary(summary):
    return "EUR"


def _stripe_account_id_from_summary(summary):
    if not isinstance(summary, dict):
        return "acct_coolbits_live"
    stripe = summary.get("stripe") if isinstance(summary.get("stripe"), dict) else {}
    cid = str(stripe.get("customerId") or "").strip()
    if cid:
        return cid
    mode = str(stripe.get("mode") or "live").strip().lower() or "live"
    return f"acct_coolbits_{mode}"


def _stripe_accounts_from_summary(summary):
    if not isinstance(summary, dict):
        return []
    stripe = summary.get("stripe") if isinstance(summary.get("stripe"), dict) else {}
    mode = str(stripe.get("mode") or "live").strip().lower()
    mode_label = "Live" if mode == "live" else ("Test" if mode == "test" else mode.title() or "Live")
    account_id = _stripe_account_id_from_summary(summary)
    return [{
        "account_id": account_id,
        "name": f"Coolbits Billing ({mode_label})",
        "mode": mode_label,
        "currency": _stripe_currency_from_summary(summary),
        "country": "RO",
    }]


def _stripe_overview_from_summary(summary):
    if not isinstance(summary, dict):
        return None
    plan = summary.get("plan") if isinstance(summary.get("plan"), dict) else {}
    price = plan.get("price") if isinstance(plan.get("price"), dict) else {}
    stripe = summary.get("stripe") if isinstance(summary.get("stripe"), dict) else {}
    usage = summary.get("usage") if isinstance(summary.get("usage"), dict) else {}
    mrr = _amount_to_eur(price.get("amount") or 0, price.get("currency"))
    arr = round(mrr * 12, 2)
    status = str(stripe.get("status") or "").strip().lower()
    has_sub = status in ("active", "trialing", "past_due", "incomplete")
    usage_pct = float(usage.get("usagePct") or 0)
    fees = round(mrr * 0.029 + 0.3, 2) if has_sub and mrr > 0 else 0
    net_revenue = round(max(0, mrr - fees), 2)

    return {
        "mrr": round(mrr, 2),
        "arr": arr,
        "revenue_today": 0,
        "revenue_this_month": round(mrr, 2),
        "revenue_last_month": round(mrr, 2),
        "revenue_growth": 0,
        "active_subscriptions": 1 if has_sub else 0,
        "new_subscriptions": 0,
        "churned_subscriptions": 0 if has_sub else 1,
        "churn_rate": 0 if has_sub else 100,
        "net_revenue": net_revenue,
        "gross_volume": round(mrr, 2),
        "refunds": 0,
        "fees": fees,
        "average_revenue_per_user": round(mrr, 2) if has_sub else 0,
        "lifetime_value": round(mrr * 6, 2) if has_sub else 0,
        "cac": 0,
        "ltv_cac_ratio": 0,
        "runway_months": 0,
        "monthly_burn": 0,
        "cash_balance": 0,
        "mrr_trend": [
            {"month": "Sep", "mrr": round(mrr, 2)},
            {"month": "Oct", "mrr": round(mrr, 2)},
            {"month": "Nov", "mrr": round(mrr, 2)},
            {"month": "Dec", "mrr": round(mrr, 2)},
            {"month": "Jan", "mrr": round(mrr, 2)},
            {"month": "Feb", "mrr": round(mrr, 2)},
        ],
        "revenue_by_product": [
            {"product": str(plan.get("label") or "Plan"), "revenue": round(mrr, 2), "pct": 100, "subscribers": 1 if has_sub else 0},
        ],
        "usage_pct": usage_pct,
    }


def _stripe_subscriptions_from_summary(summary):
    if not isinstance(summary, dict):
        return []
    stripe = summary.get("stripe") if isinstance(summary.get("stripe"), dict) else {}
    plan = summary.get("plan") if isinstance(summary.get("plan"), dict) else {}
    price = plan.get("price") if isinstance(plan.get("price"), dict) else {}
    sub_id = str(stripe.get("subscriptionId") or "").strip()
    status = str(stripe.get("status") or "").strip().lower()
    if not sub_id and status not in ("active", "trialing", "past_due", "incomplete"):
        return []
    customer_id = _stripe_account_id_from_summary(summary)
    return [{
        "sub_id": sub_id or "sub_coolbits_current",
        "customer_id": customer_id,
        "customer_email": COOLBITS_GATEWAY_EMAIL,
        "plan": str(plan.get("label") or "Plan"),
        "amount": _amount_to_eur(price.get("amount") or 0, price.get("currency")),
        "currency": _stripe_currency_from_summary(summary),
        "status": status or "active",
        "interval": str((price.get("interval") or "month")).strip().lower() or "month",
        "current_period_start": stripe.get("currentPeriodStart"),
        "current_period_end": stripe.get("currentPeriodEnd"),
        "created": stripe.get("currentPeriodStart"),
        "cancel_at_period_end": bool(stripe.get("cancelAtPeriodEnd")),
    }]


def _stripe_customers_from_summary(summary):
    if not isinstance(summary, dict):
        return []
    plan = summary.get("plan") if isinstance(summary.get("plan"), dict) else {}
    price = plan.get("price") if isinstance(plan.get("price"), dict) else {}
    stripe = summary.get("stripe") if isinstance(summary.get("stripe"), dict) else {}
    customer_id = _stripe_account_id_from_summary(summary)
    amount = _amount_to_eur(price.get("amount") or 0, price.get("currency"))
    status = str(stripe.get("status") or "inactive").strip().lower() or "inactive"
    return [{
        "customer_id": customer_id,
        "email": COOLBITS_GATEWAY_EMAIL,
        "name": "Coolbits Workspace",
        "created": stripe.get("currentPeriodStart"),
        "status": status,
        "ltv": round(amount * 6, 2) if status in ("active", "trialing", "past_due", "incomplete") else 0,
        "total_spent": round(amount, 2) if status in ("active", "trialing", "past_due", "incomplete") else 0,
        "subscriptions": 1 if status in ("active", "trialing", "past_due", "incomplete") else 0,
        "plan": str(plan.get("label") or "Plan"),
        "country": "RO",
    }]


def _stripe_payments_from_summary(summary):
    if not isinstance(summary, dict):
        return []
    plan = summary.get("plan") if isinstance(summary.get("plan"), dict) else {}
    price = plan.get("price") if isinstance(plan.get("price"), dict) else {}
    stripe = summary.get("stripe") if isinstance(summary.get("stripe"), dict) else {}
    amount = _amount_to_eur(price.get("amount") or 0, price.get("currency"))
    if amount <= 0:
        return []
    status = str(stripe.get("status") or "").strip().lower()
    return [{
        "payment_id": str(stripe.get("subscriptionId") or "ch_coolbits_latest"),
        "amount": round(amount, 2),
        "currency": _stripe_currency_from_summary(summary),
        "status": "succeeded" if status in ("active", "trialing", "past_due", "incomplete") else "pending",
        "customer_id": _stripe_account_id_from_summary(summary),
        "customer_email": COOLBITS_GATEWAY_EMAIL,
        "description": f"{plan.get('label') or 'Plan'} subscription",
        "created": stripe.get("currentPeriodStart"),
        "payment_method": "card",
        "card_last4": "****",
    }]


def _stripe_budget_pacing_from_summary(summary):
    if not isinstance(summary, dict):
        return None
    overview = _stripe_overview_from_summary(summary) or {}
    mrr = float(overview.get("mrr") or 0)
    current = float(overview.get("revenue_this_month") or 0)
    goal = mrr if mrr > 0 else 1
    goal_pct = round((current / goal) * 100, 1) if goal > 0 else 0
    return {
        "monthly_revenue_goal": round(goal, 2),
        "current_revenue": round(current, 2),
        "projected_revenue": round(current, 2),
        "goal_pct": goal_pct,
        "projected_pct": goal_pct,
        "days_elapsed": 0,
        "days_remaining": 0,
        "daily_run_rate": round(current / 30, 2) if current else 0,
        "needed_daily_rate": 0,
        "pacing_status": "ON_TRACK" if goal_pct >= 90 else "UNDERPACING",
        "cash_runway_months": 0,
        "monthly_burn": 0,
        "cash_balance": 0,
        "products": [{
            "name": "Subscription",
            "goal": round(goal, 2),
            "current": round(current, 2),
            "pacing": "ON_TRACK" if goal_pct >= 90 else "UNDERPACING",
            "daily_avg": round(current / 30, 2) if current else 0,
        }],
    }


def _stripe_report_rows_from_summary(summary):
    if not isinstance(summary, dict):
        return []
    plan = summary.get("plan") if isinstance(summary.get("plan"), dict) else {}
    price = plan.get("price") if isinstance(plan.get("price"), dict) else {}
    amount = _amount_to_eur(price.get("amount") or 0, price.get("currency"))
    if amount <= 0:
        return []
    from datetime import date, timedelta
    base = date.today() - timedelta(days=29)
    daily = round(amount / 30, 2)
    rows = []
    for i in range(30):
        d = base + timedelta(days=i)
        rows.append({
            "date": d.isoformat(),
            "plan": str(plan.get("label") or "Plan"),
            "revenue": daily,
            "new_subscriptions": 0,
            "churned_subscriptions": 0,
            "active_subscriptions": 1,
            "refunds": 0,
            "net_revenue": daily,
        })
    return rows


def _billing_payload_to_eur(payload):
    if not isinstance(payload, dict):
        return payload
    out = copy.deepcopy(payload)
    plan = out.get("plan") if isinstance(out.get("plan"), dict) else None
    if plan and isinstance(plan.get("price"), dict):
        price = plan.get("price")
        price["amount"] = _amount_to_eur(price.get("amount") or 0, price.get("currency"))
        price["currency"] = "eur"
    return out


def _stripe_subscription_status(summary):
    if not isinstance(summary, dict):
        return ""
    stripe = summary.get("stripe") if isinstance(summary.get("stripe"), dict) else {}
    return str(stripe.get("status") or "").strip().lower()


def _stripe_subscription_active(summary):
    return _stripe_subscription_status(summary) in ("active", "trialing", "past_due", "incomplete")


def _apply_economy_preset(conn, user_id, preset_code):
    preset = _normalize_plan_code(preset_code)
    if preset == "starter":
        preset = "free"
    if preset not in VALID_ECONOMY_PRESETS:
        raise ValueError("invalid_preset")
    current = _load_user_settings(conn, user_id)
    economy_patch = {"preset": preset}
    base = PRICING_PRESETS[preset]
    for econ_key in ("cost_multiplier", "monthly_grant", "max_per_message", "daily_limit", "monthly_reset_day", "monthly_reset_hour", "monthly_reset_minute"):
        economy_patch[econ_key] = base[econ_key]
    merged = _deep_merge_dict(current, {"economy": economy_patch})
    return _save_user_settings(conn, user_id, merged)


@app.route("/api/connectors/stripe/accounts", methods=["GET"])
def stripe_accounts():
    """List available Stripe accounts (Live + Test)"""
    summary, gw = _stripe_billing_summary()
    if summary is not None:
        accounts = _stripe_accounts_from_summary(summary)
        if accounts:
            return jsonify({"accounts": accounts, "source": "coolbits", "gateway": gw})
    return jsonify({"accounts": STRIPE_MOCK_ACCOUNTS, "source": "mock"})


@app.route("/api/connectors/stripe/overview", methods=["GET"])
def stripe_overview():
    """Overview KPIs for a Stripe account"""
    default_mock_acct = "acct_1J7xQR2eZvKYlo2C"
    acct = request.args.get("account_id", default_mock_acct)
    summary, gw = _stripe_billing_summary()
    if summary is not None:
        live_acct = _stripe_account_id_from_summary(summary)
        if not acct or acct == live_acct or acct == default_mock_acct:
            overview = _stripe_overview_from_summary(summary)
            if overview:
                return jsonify({"account_id": live_acct, "overview": overview, "source": "coolbits", "gateway": gw})
    data = STRIPE_MOCK_OVERVIEW.get(acct, {
        "mrr": 0, "arr": 0, "revenue_today": 0, "revenue_this_month": 0,
        "revenue_last_month": 0, "revenue_growth": 0, "active_subscriptions": 0,
        "new_subscriptions": 0, "churned_subscriptions": 0, "churn_rate": 0,
        "net_revenue": 0, "gross_volume": 0, "refunds": 0, "fees": 0,
        "average_revenue_per_user": 0, "lifetime_value": 0, "cac": 0,
        "ltv_cac_ratio": 0, "runway_months": 0, "monthly_burn": 0,
        "cash_balance": 0, "mrr_trend": [], "revenue_by_product": []
    })
    mock_overview = dict(data)
    for k in ("mrr", "arr", "revenue_today", "revenue_this_month", "revenue_last_month", "net_revenue", "gross_volume", "refunds", "fees", "average_revenue_per_user", "lifetime_value", "cac", "monthly_burn", "cash_balance"):
        mock_overview[k] = _amount_to_eur(mock_overview.get(k) or 0, "USD")
    if isinstance(mock_overview.get("mrr_trend"), list):
        mock_overview["mrr_trend"] = [
            {**m, "mrr": _amount_to_eur((m or {}).get("mrr") or 0, "USD")}
            for m in mock_overview.get("mrr_trend")
            if isinstance(m, dict)
        ]
    if isinstance(mock_overview.get("revenue_by_product"), list):
        mock_overview["revenue_by_product"] = [
            {**p, "revenue": _amount_to_eur((p or {}).get("revenue") or 0, "USD")}
            for p in mock_overview.get("revenue_by_product")
            if isinstance(p, dict)
        ]
    return jsonify({"account_id": acct, "overview": mock_overview, "source": "mock", "currency": "EUR"})


@app.route("/api/connectors/stripe/subscriptions", methods=["GET"])
def stripe_subscriptions():
    """List subscriptions with optional filters"""
    status = request.args.get("status", "")
    plan = request.args.get("plan", "")
    summary, gw = _stripe_billing_summary()
    source = "mock"
    subs = _stripe_subscriptions_to_eur(STRIPE_MOCK_SUBSCRIPTIONS)
    if summary is not None:
        source = "coolbits"
        subs = _stripe_subscriptions_from_summary(summary)
    if status:
        subs = [s for s in subs if s["status"] == status]
    if plan:
        subs = [s for s in subs if s["plan"] == plan]
    out = {"subscriptions": subs, "total": len(subs), "source": source}
    if source == "coolbits":
        out["gateway"] = gw
    return jsonify(out)


@app.route("/api/connectors/stripe/payments", methods=["GET"])
def stripe_payments():
    """List recent payments / charges"""
    status = request.args.get("status", "")
    summary, gw = _stripe_billing_summary()
    source = "mock"
    payments = _stripe_payments_to_eur(STRIPE_MOCK_PAYMENTS)
    if summary is not None:
        source = "coolbits"
        payments = _stripe_payments_from_summary(summary)
    if status:
        payments = [p for p in payments if p["status"] == status]
    out = {"payments": payments, "total": len(payments), "source": source}
    if source == "coolbits":
        out["gateway"] = gw
    return jsonify(out)


@app.route("/api/connectors/stripe/customers", methods=["GET"])
def stripe_customers():
    """List customers with LTV and status"""
    status = request.args.get("status", "")
    summary, gw = _stripe_billing_summary()
    source = "mock"
    customers = STRIPE_MOCK_CUSTOMERS
    if summary is not None:
        source = "coolbits"
        customers = _stripe_customers_from_summary(summary)
    if status:
        customers = [c for c in customers if c["status"] == status]
    out = {"customers": customers, "total": len(customers), "source": source}
    if source == "coolbits":
        out["gateway"] = gw
    return jsonify(out)


@app.route("/api/connectors/stripe/budget-pacing", methods=["GET"])
def stripe_budget_pacing():
    """Revenue pacing & cash runway"""
    default_mock_acct = "acct_1J7xQR2eZvKYlo2C"
    acct = request.args.get("account_id", default_mock_acct)
    summary, gw = _stripe_billing_summary()
    if summary is not None:
        live_acct = _stripe_account_id_from_summary(summary)
        if not acct or acct == live_acct or acct == default_mock_acct:
            pacing = _stripe_budget_pacing_from_summary(summary)
            if pacing:
                return jsonify({"account_id": live_acct, "pacing": pacing, "source": "coolbits", "gateway": gw})
    data = STRIPE_MOCK_BUDGET_PACING.get(acct, STRIPE_MOCK_BUDGET_PACING["acct_1J7xQR2eZvKYlo2C"])
    pacing = dict(data)
    for k in ("monthly_revenue_goal", "current_revenue", "projected_revenue", "daily_run_rate", "needed_daily_rate", "monthly_burn", "cash_balance"):
        pacing[k] = _amount_to_eur(pacing.get(k) or 0, "USD")
    if isinstance(pacing.get("products"), list):
        pacing["products"] = [
            {
                **p,
                "goal": _amount_to_eur((p or {}).get("goal") or 0, "USD"),
                "current": _amount_to_eur((p or {}).get("current") or 0, "USD"),
                "daily_avg": _amount_to_eur((p or {}).get("daily_avg") or 0, "USD"),
            }
            for p in pacing.get("products")
            if isinstance(p, dict)
        ]
    return jsonify({"account_id": acct, "pacing": pacing, "source": "mock", "currency": "EUR"})


@app.route("/api/connectors/stripe/reports", methods=["GET"])
def stripe_reports():
    """Generate revenue report data"""
    import datetime
    default_mock_acct = "acct_1J7xQR2eZvKYlo2C"
    acct = request.args.get("account_id", default_mock_acct)
    summary, gw = _stripe_billing_summary()
    if summary is not None:
        live_acct = _stripe_account_id_from_summary(summary)
        if not acct or acct == live_acct or acct == default_mock_acct:
            rows = _stripe_report_rows_from_summary(summary)
            return jsonify({"account_id": live_acct, "rows": rows, "total_rows": len(rows), "source": "coolbits", "gateway": gw})
    rows = []
    base = datetime.date(2026, 1, 1)
    plans = ["Pro Monthly", "Basic Monthly", "Pro Annual", "Enterprise"]
    plan_mrrs = {"Pro Monthly": 3920, "Basic Monthly": 892, "Pro Annual": 5880, "Enterprise": 3544}
    plan_subs = {"Pro Monthly": 80, "Basic Monthly": 89, "Pro Annual": 42, "Enterprise": 20}
    for i in range(31):
        d = base + datetime.timedelta(days=i)
        for plan in plans:
            base_rev = plan_mrrs[plan] / 30
            import random
            random.seed(hash(f"{d.isoformat()}-{plan}"))
            daily_rev = round(base_rev * random.uniform(0.8, 1.2), 2)
            new_s = random.randint(0, 3)
            churned = random.randint(0, 1)
            rows.append({
                "date": d.isoformat(),
                "plan": plan,
                "revenue": daily_rev,
                "new_subscriptions": new_s,
                "churned_subscriptions": churned,
                "active_subscriptions": plan_subs[plan] + new_s - churned,
                "refunds": round(daily_rev * random.uniform(0, 0.05), 2),
                "net_revenue": round(daily_rev * 0.97, 2),
            })
    rows_eur = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        x = dict(r)
        for k in ("revenue", "refunds", "net_revenue"):
            x[k] = _amount_to_eur(x.get(k) or 0, "USD")
        rows_eur.append(x)
    return jsonify({"account_id": acct, "rows": rows_eur, "total_rows": len(rows_eur), "source": "mock", "currency": "EUR"})


@app.route("/api/connectors/stripe/test-call", methods=["POST"])
def stripe_test_call():
    """Simulate a Stripe API call"""
    import time
    start = time.time()
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint", "customers")

    if "customer" in endpoint.lower():
        response_body = {"object": "list", "has_more": True, "url": "/v1/customers", "data": [
            {"id": c["customer_id"], "object": "customer", "email": c["email"], "name": c["name"],
             "created": 1718409600 + i * 86400, "currency": "usd", "livemode": True,
             "metadata": {}, "subscriptions": {"object": "list", "total_count": c["subscriptions"],
             "data": [{"id": f"sub_mock_{i}", "plan": {"amount": int(c["ltv"]/max(c["subscriptions"],1)*100), "currency": "usd", "interval": "month"}}] if c["subscriptions"] > 0 else []}}
            for i, c in enumerate(STRIPE_MOCK_CUSTOMERS[:3])
        ]}
    elif "charge" in endpoint.lower() or "payment" in endpoint.lower():
        response_body = {"object": "list", "has_more": True, "url": "/v1/charges", "data": [
            {"id": p["payment_id"], "object": "charge", "amount": int(p["amount"] * 100),
             "currency": p["currency"].lower(), "status": p["status"],
             "customer": p["customer_id"], "description": p["description"],
             "created": 1738900000 + i * 3600, "payment_method_details": {"type": "card", "card": {"last4": p["card_last4"], "brand": "visa"}}}
            for i, p in enumerate(STRIPE_MOCK_PAYMENTS[:3])
        ]}
    elif "subscription" in endpoint.lower():
        response_body = {"object": "list", "has_more": True, "url": "/v1/subscriptions", "data": [
            {"id": s["sub_id"], "object": "subscription", "customer": s["customer_id"],
             "status": s["status"], "current_period_start": 1738368000 + i * 86400,
             "current_period_end": 1740960000 + i * 86400,
             "items": {"data": [{"price": {"unit_amount": int(s["amount"] * 100), "currency": "usd", "recurring": {"interval": s["interval"]}}}]},
             "cancel_at_period_end": s["cancel_at_period_end"]}
            for i, s in enumerate(STRIPE_MOCK_SUBSCRIPTIONS[:3])
        ]}
    elif "balance" in endpoint.lower():
        response_body = {"object": "balance", "available": [{"amount": 14723600, "currency": "usd"}],
                         "pending": [{"amount": 312400, "currency": "usd"}], "livemode": True}
    else:
        response_body = {"object": "list", "data": [], "has_more": False, "url": f"/v1/{endpoint}"}

    elapsed = round((time.time() - start) * 1000, 1)
    return jsonify({
        "endpoint": endpoint,
        "method": data.get("method", "GET"),
        "request": {"account_id": "acct_1J7xQR2eZvKYlo2C", "endpoint": f"/v1/{endpoint}"},
        "response": {"status_code": 200,
                      "headers": {"content-type": "application/json", "request-id": f"req_mock_{int(time.time())}",
                                  "stripe-version": "2024-12-18.acacia"},
                      "body": response_body},
        "latency_ms": elapsed,
        "quota": {"rate_limit": "100/sec", "remaining": 97, "test_mode": False}
    })


# ═══════════════════════════════════════════════════════════════════════════
# SHOPIFY  –  Mock Data & Endpoints (Phase 19)
# ═══════════════════════════════════════════════════════════════════════════

SHOPIFY_MOCK_STORES = [
    {"store_id": "techstart-store.myshopify.com", "name": "TechStart Store", "currency": "USD", "status": "ACTIVE", "plan": "Shopify Plus", "country": "US", "timezone": "America/New_York"},
    {"store_id": "lifestyle-brand.myshopify.com", "name": "Lifestyle Brand Store", "currency": "EUR", "status": "ACTIVE", "plan": "Shopify", "country": "DE", "timezone": "Europe/Berlin"},
    {"store_id": "creative-merch.myshopify.com", "name": "Creative Merch Shop", "currency": "GBP", "status": "ACTIVE", "plan": "Basic Shopify", "country": "UK", "timezone": "Europe/London"},
]

SHOPIFY_MOCK_OVERVIEW = {
    "techstart-store.myshopify.com": {
        "revenue_today": 1842.50,
        "revenue_this_month": 28472,
        "revenue_last_month": 24890,
        "revenue_growth": 14.4,
        "orders_today": 23,
        "orders_this_month": 312,
        "aov": 91.26,
        "conversion_rate": 2.8,
        "sessions_today": 1245,
        "sessions_this_month": 18670,
        "new_customers": 134,
        "returning_customers": 178,
        "abandoned_carts": 87,
        "abandoned_cart_value": 12456,
        "recovery_rate": 18.4,
        "top_products": [
            {"title": "Premium Wireless Headphones", "price": 199.00, "sold": 87, "revenue": 17313, "inventory": 43},
            {"title": "Ergonomic Wireless Mouse", "price": 49.99, "sold": 156, "revenue": 7798, "inventory": 234},
            {"title": "USB-C Hub 7-in-1", "price": 39.99, "sold": 198, "revenue": 7918, "inventory": 112},
            {"title": "Mechanical Keyboard RGB", "price": 129.00, "sold": 64, "revenue": 8256, "inventory": 78},
            {"title": "Laptop Stand Adjustable", "price": 69.99, "sold": 103, "revenue": 7209, "inventory": 167},
        ],
        "daily_revenue": [
            {"date": "2026-02-01", "revenue": 3210.50, "orders": 41},
            {"date": "2026-02-02", "revenue": 4125.20, "orders": 48},
            {"date": "2026-02-03", "revenue": 3890.00, "orders": 44},
            {"date": "2026-02-04", "revenue": 4567.30, "orders": 52},
            {"date": "2026-02-05", "revenue": 4012.80, "orders": 46},
            {"date": "2026-02-06", "revenue": 4823.70, "orders": 58},
            {"date": "2026-02-07", "revenue": 3842.50, "orders": 23},
        ],
        "sales_by_channel": [
            {"channel": "Online Store", "revenue": 18507, "pct": 65},
            {"channel": "Facebook & Instagram", "revenue": 5694, "pct": 20},
            {"channel": "Google Shopping", "revenue": 2847, "pct": 10},
            {"channel": "Buy Button", "revenue": 1424, "pct": 5},
        ],
    }
}

SHOPIFY_MOCK_PRODUCTS = [
    {"product_id": "prod_001", "title": "Premium Wireless Headphones", "price": 199.00, "compare_at_price": 249.00, "inventory": 43, "status": "active", "vendor": "TechStart Audio", "product_type": "Electronics", "collection": "Best Sellers", "variants": 3, "images": 5, "created": "2025-06-15"},
    {"product_id": "prod_002", "title": "Ergonomic Wireless Mouse", "price": 49.99, "compare_at_price": 69.99, "inventory": 234, "status": "active", "vendor": "TechStart", "product_type": "Accessories", "collection": "Work From Home", "variants": 2, "images": 4, "created": "2025-07-01"},
    {"product_id": "prod_003", "title": "USB-C Hub 7-in-1", "price": 39.99, "compare_at_price": None, "inventory": 112, "status": "active", "vendor": "TechStart", "product_type": "Accessories", "collection": "Best Sellers", "variants": 1, "images": 3, "created": "2025-08-20"},
    {"product_id": "prod_004", "title": "Mechanical Keyboard RGB", "price": 129.00, "compare_at_price": 159.00, "inventory": 78, "status": "active", "vendor": "TechStart Gaming", "product_type": "Electronics", "collection": "Gaming", "variants": 4, "images": 6, "created": "2025-09-10"},
    {"product_id": "prod_005", "title": "Laptop Stand Adjustable", "price": 69.99, "compare_at_price": 89.99, "inventory": 167, "status": "active", "vendor": "TechStart", "product_type": "Accessories", "collection": "Work From Home", "variants": 2, "images": 3, "created": "2025-10-01"},
    {"product_id": "prod_006", "title": "Webcam 4K Pro", "price": 149.00, "compare_at_price": 179.00, "inventory": 56, "status": "active", "vendor": "TechStart", "product_type": "Electronics", "collection": "Work From Home", "variants": 1, "images": 4, "created": "2025-11-15"},
    {"product_id": "prod_007", "title": "Desk Organizer Bamboo", "price": 34.99, "compare_at_price": None, "inventory": 312, "status": "active", "vendor": "TechStart Home", "product_type": "Home Office", "collection": "Work From Home", "variants": 1, "images": 2, "created": "2025-12-01"},
    {"product_id": "prod_008", "title": "Noise Cancelling Earbuds", "price": 89.00, "compare_at_price": 119.00, "inventory": 0, "status": "draft", "vendor": "TechStart Audio", "product_type": "Electronics", "collection": "Coming Soon", "variants": 3, "images": 4, "created": "2026-01-20"},
    {"product_id": "prod_009", "title": "Monitor Light Bar", "price": 59.99, "compare_at_price": None, "inventory": 89, "status": "active", "vendor": "TechStart", "product_type": "Accessories", "collection": "Best Sellers", "variants": 1, "images": 3, "created": "2025-07-15"},
    {"product_id": "prod_010", "title": "Cable Management Kit", "price": 24.99, "compare_at_price": 29.99, "inventory": 456, "status": "active", "vendor": "TechStart Home", "product_type": "Home Office", "collection": "Under $30", "variants": 1, "images": 2, "created": "2025-08-01"},
    {"product_id": "prod_011", "title": "Gaming Mouse Pad XL", "price": 29.99, "compare_at_price": None, "inventory": 198, "status": "active", "vendor": "TechStart Gaming", "product_type": "Gaming", "collection": "Gaming", "variants": 3, "images": 3, "created": "2025-09-20"},
    {"product_id": "prod_012", "title": "Smart Power Strip", "price": 44.99, "compare_at_price": 54.99, "inventory": 145, "status": "archived", "vendor": "TechStart Home", "product_type": "Home Office", "collection": "Clearance", "variants": 1, "images": 2, "created": "2025-04-10"},
]

SHOPIFY_MOCK_ORDERS = [
    {"order_id": "#1001", "customer_email": "john@techstart.com", "customer_name": "John Mitchell", "total": 249.00, "subtotal": 238.99, "tax": 10.01, "shipping": 0, "status": "fulfilled", "payment_status": "paid", "items": 2, "created": "2026-02-07T09:15:00", "shipping_method": "Free Shipping"},
    {"order_id": "#1002", "customer_email": "sarah@designhub.io", "customer_name": "Sarah Chen", "total": 199.00, "subtotal": 199.00, "tax": 0, "shipping": 0, "status": "fulfilled", "payment_status": "paid", "items": 1, "created": "2026-02-07T08:30:00", "shipping_method": "Free Shipping"},
    {"order_id": "#1003", "customer_email": "mike@acmecorp.com", "customer_name": "Mike Rodriguez", "total": 89.98, "subtotal": 84.98, "tax": 4.99, "shipping": 0, "status": "unfulfilled", "payment_status": "paid", "items": 2, "created": "2026-02-06T16:45:00", "shipping_method": "Standard"},
    {"order_id": "#1004", "customer_email": "lisa@startup.co", "customer_name": "Lisa Park", "total": 129.00, "subtotal": 129.00, "tax": 0, "shipping": 5.99, "status": "fulfilled", "payment_status": "paid", "items": 1, "created": "2026-02-06T14:20:00", "shipping_method": "Express"},
    {"order_id": "#1005", "customer_email": "alex@bigcorp.com", "customer_name": "Alex Thompson", "total": 349.98, "subtotal": 328.00, "tax": 21.98, "shipping": 0, "status": "unfulfilled", "payment_status": "paid", "items": 3, "created": "2026-02-06T11:00:00", "shipping_method": "Free Shipping"},
    {"order_id": "#1006", "customer_email": "nina@freelance.dev", "customer_name": "Nina Kowalski", "total": 69.99, "subtotal": 69.99, "tax": 0, "shipping": 4.99, "status": "fulfilled", "payment_status": "paid", "items": 1, "created": "2026-02-05T17:30:00", "shipping_method": "Standard"},
    {"order_id": "#1007", "customer_email": "tom@agency.io", "customer_name": "Tom Barnes", "total": 478.97, "subtotal": 447.98, "tax": 30.99, "shipping": 0, "status": "fulfilled", "payment_status": "paid", "items": 4, "created": "2026-02-05T10:15:00", "shipping_method": "Free Shipping"},
    {"order_id": "#1008", "customer_email": "emma@consultfirm.com", "customer_name": "Emma Davis", "total": 49.99, "subtotal": 49.99, "tax": 0, "shipping": 0, "status": "cancelled", "payment_status": "refunded", "items": 1, "created": "2026-02-04T09:00:00", "shipping_method": "Free Shipping"},
    {"order_id": "#1009", "customer_email": "dave@devshop.net", "customer_name": "Dave Wilson", "total": 164.98, "subtotal": 154.98, "tax": 10.00, "shipping": 0, "status": "fulfilled", "payment_status": "paid", "items": 2, "created": "2026-02-03T14:45:00", "shipping_method": "Free Shipping"},
    {"order_id": "#1010", "customer_email": "olivia@marketinghq.com", "customer_name": "Olivia Martinez", "total": 259.99, "subtotal": 239.00, "tax": 15.00, "shipping": 5.99, "status": "partially_fulfilled", "payment_status": "paid", "items": 3, "created": "2026-02-02T16:00:00", "shipping_method": "Express"},
]

SHOPIFY_MOCK_ABANDONED_CARTS = [
    {"cart_id": "cart_001", "customer_email": "prospect1@gmail.com", "items": [{"title": "Premium Wireless Headphones", "qty": 1, "price": 199.00}], "total_value": 199.00, "created": "2026-02-07T10:30:00", "recovery_email_sent": False, "recovered": False},
    {"cart_id": "cart_002", "customer_email": "prospect2@outlook.com", "items": [{"title": "Mechanical Keyboard RGB", "qty": 1, "price": 129.00}, {"title": "Gaming Mouse Pad XL", "qty": 1, "price": 29.99}], "total_value": 158.99, "created": "2026-02-07T08:15:00", "recovery_email_sent": True, "recovered": False},
    {"cart_id": "cart_003", "customer_email": "buyer3@yahoo.com", "items": [{"title": "USB-C Hub 7-in-1", "qty": 2, "price": 39.99}], "total_value": 79.98, "created": "2026-02-06T19:45:00", "recovery_email_sent": True, "recovered": True},
    {"cart_id": "cart_004", "customer_email": "shopper4@hotmail.com", "items": [{"title": "Webcam 4K Pro", "qty": 1, "price": 149.00}, {"title": "Monitor Light Bar", "qty": 1, "price": 59.99}], "total_value": 208.99, "created": "2026-02-06T14:00:00", "recovery_email_sent": True, "recovered": False},
    {"cart_id": "cart_005", "customer_email": "user5@proton.me", "items": [{"title": "Laptop Stand Adjustable", "qty": 1, "price": 69.99}], "total_value": 69.99, "created": "2026-02-05T22:30:00", "recovery_email_sent": False, "recovered": False},
    {"cart_id": "cart_006", "customer_email": "lead6@company.com", "items": [{"title": "Ergonomic Wireless Mouse", "qty": 3, "price": 49.99}], "total_value": 149.97, "created": "2026-02-05T11:00:00", "recovery_email_sent": True, "recovered": True},
    {"cart_id": "cart_007", "customer_email": "visitor7@mail.com", "items": [{"title": "Premium Wireless Headphones", "qty": 1, "price": 199.00}, {"title": "Noise Cancelling Earbuds", "qty": 1, "price": 89.00}], "total_value": 288.00, "created": "2026-02-04T16:20:00", "recovery_email_sent": True, "recovered": False},
    {"cart_id": "cart_008", "customer_email": "browsing8@web.org", "items": [{"title": "Cable Management Kit", "qty": 2, "price": 24.99}, {"title": "Desk Organizer Bamboo", "qty": 1, "price": 34.99}], "total_value": 84.97, "created": "2026-02-04T09:00:00", "recovery_email_sent": False, "recovered": False},
]

SHOPIFY_MOCK_CUSTOMERS = [
    {"customer_id": "cust_001", "email": "john@techstart.com", "name": "John Mitchell", "orders_count": 8, "total_spent": 1456.92, "aov": 182.12, "status": "active", "country": "US", "city": "New York", "created": "2025-06-15", "last_order": "2026-02-07", "tags": ["VIP", "Repeat Buyer"]},
    {"customer_id": "cust_002", "email": "sarah@designhub.io", "name": "Sarah Chen", "orders_count": 5, "total_spent": 867.50, "aov": 173.50, "status": "active", "country": "US", "city": "San Francisco", "created": "2025-08-01", "last_order": "2026-02-07", "tags": ["Repeat Buyer"]},
    {"customer_id": "cust_003", "email": "mike@acmecorp.com", "name": "Mike Rodriguez", "orders_count": 3, "total_spent": 345.97, "aov": 115.32, "status": "active", "country": "US", "city": "Austin", "created": "2025-09-20", "last_order": "2026-02-06", "tags": []},
    {"customer_id": "cust_004", "email": "lisa@startup.co", "name": "Lisa Park", "orders_count": 2, "total_spent": 198.99, "aov": 99.50, "status": "active", "country": "CA", "city": "Toronto", "created": "2026-01-01", "last_order": "2026-02-06", "tags": ["New"]},
    {"customer_id": "cust_005", "email": "alex@bigcorp.com", "name": "Alex Thompson", "orders_count": 6, "total_spent": 1234.87, "aov": 205.81, "status": "active", "country": "US", "city": "Chicago", "created": "2025-07-10", "last_order": "2026-02-06", "tags": ["VIP", "Wholesale"]},
    {"customer_id": "cust_006", "email": "nina@freelance.dev", "name": "Nina Kowalski", "orders_count": 4, "total_spent": 456.96, "aov": 114.24, "status": "active", "country": "DE", "city": "Berlin", "created": "2025-11-05", "last_order": "2026-02-05", "tags": ["International"]},
    {"customer_id": "cust_007", "email": "tom@agency.io", "name": "Tom Barnes", "orders_count": 12, "total_spent": 2890.45, "aov": 240.87, "status": "active", "country": "UK", "city": "London", "created": "2025-04-20", "last_order": "2026-02-05", "tags": ["VIP", "Repeat Buyer", "Wholesale"]},
    {"customer_id": "cust_008", "email": "emma@consultfirm.com", "name": "Emma Davis", "orders_count": 1, "total_spent": 49.99, "aov": 49.99, "status": "inactive", "country": "US", "city": "Miami", "created": "2025-12-01", "last_order": "2026-02-04", "tags": []},
    {"customer_id": "cust_009", "email": "dave@devshop.net", "name": "Dave Wilson", "orders_count": 7, "total_spent": 978.93, "aov": 139.85, "status": "active", "country": "US", "city": "Seattle", "created": "2025-05-15", "last_order": "2026-02-03", "tags": ["Repeat Buyer"]},
    {"customer_id": "cust_010", "email": "olivia@marketinghq.com", "name": "Olivia Martinez", "orders_count": 9, "total_spent": 1678.91, "aov": 186.55, "status": "active", "country": "US", "city": "Los Angeles", "created": "2025-03-28", "last_order": "2026-02-02", "tags": ["VIP", "Repeat Buyer"]},
]

SHOPIFY_MOCK_REVENUE_PACING = {
    "techstart-store.myshopify.com": {
        "monthly_goal": 35000,
        "current_revenue": 28472,
        "projected_revenue": 32800,
        "goal_pct": 81.3,
        "projected_pct": 93.7,
        "days_elapsed": 7,
        "days_remaining": 21,
        "daily_run_rate": 4067.43,
        "needed_daily_rate": 2310.86,
        "pacing_status": "AHEAD",
        "collections": [
            {"name": "Best Sellers", "goal": 15000, "current": 12890, "pacing": "AHEAD", "daily_avg": 1841.43},
            {"name": "Work From Home", "goal": 10000, "current": 7450, "pacing": "UNDERPACING", "daily_avg": 1064.29},
            {"name": "Gaming", "goal": 6000, "current": 5234, "pacing": "ON_TRACK", "daily_avg": 747.71},
            {"name": "Under $30", "goal": 4000, "current": 2898, "pacing": "UNDERPACING", "daily_avg": 414.00},
        ]
    }
}


@app.route("/api/connectors/shopify/stores", methods=["GET"])
def shopify_stores():
    """List available Shopify stores"""
    return jsonify({"stores": SHOPIFY_MOCK_STORES})


@app.route("/api/connectors/shopify/overview", methods=["GET"])
def shopify_overview():
    """Overview KPIs for a Shopify store"""
    store = request.args.get("store_id", "techstart-store.myshopify.com")
    data = SHOPIFY_MOCK_OVERVIEW.get(store, {
        "revenue_today": 0, "revenue_this_month": 0, "revenue_last_month": 0,
        "revenue_growth": 0, "orders_today": 0, "orders_this_month": 0,
        "aov": 0, "conversion_rate": 0, "sessions_today": 0, "sessions_this_month": 0,
        "new_customers": 0, "returning_customers": 0, "abandoned_carts": 0,
        "abandoned_cart_value": 0, "recovery_rate": 0, "top_products": [],
        "daily_revenue": [], "sales_by_channel": []
    })
    return jsonify({"store_id": store, "overview": data})


@app.route("/api/connectors/shopify/products", methods=["GET"])
def shopify_products():
    """List products with optional filters"""
    status = request.args.get("status", "")
    collection = request.args.get("collection", "")
    products = SHOPIFY_MOCK_PRODUCTS
    if status:
        products = [p for p in products if p["status"] == status]
    if collection:
        products = [p for p in products if p["collection"] == collection]
    return jsonify({"products": products, "total": len(products)})


@app.route("/api/connectors/shopify/orders", methods=["GET"])
def shopify_orders():
    """List recent orders with optional filters"""
    status = request.args.get("status", "")
    orders = SHOPIFY_MOCK_ORDERS
    if status:
        orders = [o for o in orders if o["status"] == status]
    return jsonify({"orders": orders, "total": len(orders)})


@app.route("/api/connectors/shopify/abandoned-carts", methods=["GET"])
def shopify_abandoned_carts():
    """List abandoned carts"""
    return jsonify({"carts": SHOPIFY_MOCK_ABANDONED_CARTS, "total": len(SHOPIFY_MOCK_ABANDONED_CARTS),
                     "total_value": sum(c["total_value"] for c in SHOPIFY_MOCK_ABANDONED_CARTS),
                     "recovered": sum(1 for c in SHOPIFY_MOCK_ABANDONED_CARTS if c["recovered"]),
                     "recovery_rate": round(sum(1 for c in SHOPIFY_MOCK_ABANDONED_CARTS if c["recovered"]) / len(SHOPIFY_MOCK_ABANDONED_CARTS) * 100, 1)})


@app.route("/api/connectors/shopify/customers", methods=["GET"])
def shopify_customers():
    """List customers with LTV data"""
    status = request.args.get("status", "")
    customers = SHOPIFY_MOCK_CUSTOMERS
    if status:
        customers = [c for c in customers if c["status"] == status]
    return jsonify({"customers": customers, "total": len(customers)})


@app.route("/api/connectors/shopify/reports", methods=["GET"])
def shopify_reports():
    """Generate daily store report data"""
    import datetime, random
    store = request.args.get("store_id", "techstart-store.myshopify.com")
    rows = []
    base = datetime.date(2026, 1, 1)
    for i in range(31):
        d = base + datetime.timedelta(days=i)
        random.seed(hash(f"shopify-{d.isoformat()}"))
        rev = round(random.uniform(2800, 5200), 2)
        orders = random.randint(28, 58)
        new_cust = random.randint(8, 22)
        abandoned = random.randint(5, 15)
        rows.append({
            "date": d.isoformat(),
            "revenue": rev,
            "orders": orders,
            "aov": round(rev / orders, 2),
            "new_customers": new_cust,
            "returning_customers": orders - new_cust,
            "abandoned_carts": abandoned,
            "sessions": random.randint(800, 2200),
            "conversion_rate": round(orders / random.randint(800, 2200) * 100, 2),
        })
    return jsonify({"store_id": store, "rows": rows, "total_rows": len(rows)})


@app.route("/api/connectors/shopify/test-call", methods=["POST"])
def shopify_test_call():
    """Simulate a Shopify Admin API call"""
    import time
    start = time.time()
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint", "products")

    if "product" in endpoint.lower():
        response_body = {"products": [
            {"id": int(p["product_id"].replace("prod_", "")) + 7000000000, "title": p["title"],
             "status": p["status"], "vendor": p["vendor"], "product_type": p["product_type"],
             "variants": [{"id": i + 40000000000, "price": str(p["price"]), "inventory_quantity": p["inventory"]}],
             "images": [{"src": f"https://cdn.shopify.com/s/files/mock/{p['product_id']}.jpg"}]}
            for i, p in enumerate(SHOPIFY_MOCK_PRODUCTS[:3])
        ]}
    elif "order" in endpoint.lower():
        response_body = {"orders": [
            {"id": int(o["order_id"].replace("#", "")) + 5000000000, "order_number": int(o["order_id"].replace("#", "")),
             "email": o["customer_email"], "total_price": str(o["total"]),
             "subtotal_price": str(o["subtotal"]), "total_tax": str(o["tax"]),
             "financial_status": o["payment_status"], "fulfillment_status": o["status"],
             "created_at": o["created"], "line_items": [{"title": "Product", "quantity": o["items"], "price": str(round(o["subtotal"] / o["items"], 2))}]}
            for o in SHOPIFY_MOCK_ORDERS[:3]
        ]}
    elif "customer" in endpoint.lower():
        response_body = {"customers": [
            {"id": int(c["customer_id"].replace("cust_", "")) + 6000000000, "email": c["email"],
             "first_name": c["name"].split()[0], "last_name": c["name"].split()[-1],
             "orders_count": c["orders_count"], "total_spent": str(c["total_spent"]),
             "tags": ", ".join(c["tags"]), "created_at": c["created"],
             "default_address": {"country": c["country"], "city": c["city"]}}
            for c in SHOPIFY_MOCK_CUSTOMERS[:3]
        ]}
    else:
        response_body = {"data": [], "errors": None}

    elapsed = round((time.time() - start) * 1000, 1)
    return jsonify({
        "endpoint": endpoint,
        "method": data.get("method", "GET"),
        "request": {"store": "techstart-store.myshopify.com", "endpoint": f"/admin/api/2026-01/{endpoint}.json"},
        "response": {"status_code": 200,
                      "headers": {"content-type": "application/json", "x-request-id": f"shopify-mock-{int(time.time())}",
                                  "x-shopify-shop-api-call-limit": "4/40"},
                      "body": response_body},
        "latency_ms": elapsed,
        "quota": {"api_call_limit": "4/40", "retry_after": None}
    })


# ═══════════════════════════════════════════════════════════════════════════
# HUBSPOT MOCK DATA & ENDPOINTS (Phase 20)
# ═══════════════════════════════════════════════════════════════════════════

HUBSPOT_MOCK_PORTALS = [
    {"portal_id": "techstart-crm", "name": "TechStart CRM", "hub_domain": "techstart.hubspot.com", "plan": "Professional", "timezone": "America/New_York", "currency": "USD", "status": "ACTIVE"},
    {"portal_id": "lifestyle-crm", "name": "Lifestyle Brand CRM", "hub_domain": "lifestyle.hubspot.com", "plan": "Starter", "timezone": "Europe/Berlin", "currency": "EUR", "status": "ACTIVE"},
    {"portal_id": "agency-crm", "name": "Digital Agency CRM", "hub_domain": "agency.hubspot.com", "plan": "Enterprise", "timezone": "America/Los_Angeles", "currency": "USD", "status": "ACTIVE"},
]

HUBSPOT_MOCK_OVERVIEW = {
    "techstart-crm": {
        "total_contacts": 1234, "new_contacts_this_month": 134, "total_companies": 287,
        "total_deals": 89, "deals_won_this_month": 12, "deals_lost_this_month": 3,
        "open_deals_value": 156800, "won_revenue_this_month": 42350, "won_revenue_last_month": 38700,
        "revenue_growth": 9.4, "pipeline_value": 312500, "avg_deal_size": 4750,
        "open_tasks": 45, "overdue_tasks": 8, "email_sends_this_month": 12450,
        "email_open_rate": 33.2, "email_click_rate": 4.8, "email_bounce_rate": 1.2,
        "form_submissions": 267, "meetings_booked": 34, "calls_logged": 156,
        "monthly_deals": [
            {"month": "2025-09", "won": 8, "lost": 2, "revenue": 32400},
            {"month": "2025-10", "won": 10, "lost": 4, "revenue": 36800},
            {"month": "2025-11", "won": 11, "lost": 2, "revenue": 38200},
            {"month": "2025-12", "won": 9, "lost": 5, "revenue": 35600},
            {"month": "2026-01", "won": 14, "lost": 3, "revenue": 38700},
            {"month": "2026-02", "won": 12, "lost": 3, "revenue": 42350},
        ],
        "deal_stage_distribution": [
            {"stage": "Appointment Scheduled", "count": 18, "value": 54000},
            {"stage": "Qualified to Buy", "count": 14, "value": 42800},
            {"stage": "Presentation Scheduled", "count": 11, "value": 38500},
            {"stage": "Decision Maker Bought-In", "count": 8, "value": 28700},
            {"stage": "Contract Sent", "count": 5, "value": 19200},
            {"stage": "Closed Won", "count": 12, "value": 42350},
            {"stage": "Closed Lost", "count": 3, "value": 8400},
        ],
    }
}

HUBSPOT_MOCK_CONTACTS = [
    {"contact_id": "c-001", "name": "John Doe", "email": "john.doe@techstart.io", "phone": "+1-555-0101", "company": "Acme Corp", "lifecycle_stage": "Customer", "lead_status": "Connected", "owner": "Sarah Chen", "last_activity": "2026-02-06", "created": "2025-06-15", "city": "New York", "country": "US"},
    {"contact_id": "c-002", "name": "Jane Smith", "email": "jane.smith@acmecorp.com", "phone": "+1-555-0102", "company": "Acme Corp", "lifecycle_stage": "Customer", "lead_status": "Connected", "owner": "Sarah Chen", "last_activity": "2026-02-05", "created": "2025-07-20", "city": "San Francisco", "country": "US"},
    {"contact_id": "c-003", "name": "Michael Brown", "email": "m.brown@globaltech.de", "phone": "+49-555-0103", "company": "GlobalTech GmbH", "lifecycle_stage": "Sales Qualified Lead", "lead_status": "In Progress", "owner": "Alex Müller", "last_activity": "2026-02-07", "created": "2025-11-10", "city": "Berlin", "country": "DE"},
    {"contact_id": "c-004", "name": "Emily Wilson", "email": "emily.w@startupx.co", "phone": "+1-555-0104", "company": "StartupX", "lifecycle_stage": "Marketing Qualified Lead", "lead_status": "New", "owner": "Sarah Chen", "last_activity": "2026-02-04", "created": "2026-01-05", "city": "Austin", "country": "US"},
    {"contact_id": "c-005", "name": "Carlos Rivera", "email": "carlos@mediapro.mx", "phone": "+52-555-0105", "company": "MediaPro LATAM", "lifecycle_stage": "Opportunity", "lead_status": "Open Deal", "owner": "Diego Santos", "last_activity": "2026-02-06", "created": "2025-09-22", "city": "Mexico City", "country": "MX"},
    {"contact_id": "c-006", "name": "Lisa Anderson", "email": "lisa.a@enterprise.com", "phone": "+1-555-0106", "company": "Enterprise Solutions Inc", "lifecycle_stage": "Customer", "lead_status": "Connected", "owner": "Sarah Chen", "last_activity": "2026-02-03", "created": "2025-03-14", "city": "Chicago", "country": "US"},
    {"contact_id": "c-007", "name": "Thomas König", "email": "t.konig@finserve.de", "phone": "+49-555-0107", "company": "FinServe AG", "lifecycle_stage": "Sales Qualified Lead", "lead_status": "Attempting to Reach", "owner": "Alex Müller", "last_activity": "2026-02-07", "created": "2025-12-01", "city": "Munich", "country": "DE"},
    {"contact_id": "c-008", "name": "Priya Sharma", "email": "priya@cloudnative.in", "phone": "+91-555-0108", "company": "CloudNative India", "lifecycle_stage": "Lead", "lead_status": "New", "owner": "Diego Santos", "last_activity": "2026-02-01", "created": "2026-01-28", "city": "Mumbai", "country": "IN"},
    {"contact_id": "c-009", "name": "Robert Taylor", "email": "rob.taylor@retailpro.co.uk", "phone": "+44-555-0109", "company": "RetailPro UK", "lifecycle_stage": "Opportunity", "lead_status": "Open Deal", "owner": "Sarah Chen", "last_activity": "2026-02-06", "created": "2025-10-15", "city": "London", "country": "UK"},
    {"contact_id": "c-010", "name": "Yuki Tanaka", "email": "yuki@digimarket.jp", "phone": "+81-555-0110", "company": "DigiMarket Japan", "lifecycle_stage": "Marketing Qualified Lead", "lead_status": "Open", "owner": "Alex Müller", "last_activity": "2026-02-02", "created": "2025-11-20", "city": "Tokyo", "country": "JP"},
    {"contact_id": "c-011", "name": "Sophie Martin", "email": "sophie@creativelab.fr", "phone": "+33-555-0111", "company": "Creative Lab Paris", "lifecycle_stage": "Subscriber", "lead_status": "New", "owner": "Diego Santos", "last_activity": "2026-01-30", "created": "2026-01-25", "city": "Paris", "country": "FR"},
    {"contact_id": "c-012", "name": "Ahmed Hassan", "email": "ahmed@techbridge.ae", "phone": "+971-555-0112", "company": "TechBridge UAE", "lifecycle_stage": "Lead", "lead_status": "New", "owner": "Sarah Chen", "last_activity": "2026-02-05", "created": "2026-01-15", "city": "Dubai", "country": "AE"},
    {"contact_id": "c-013", "name": "Maria Garcia", "email": "maria@saasflow.es", "phone": "+34-555-0113", "company": "SaaSFlow Spain", "lifecycle_stage": "Sales Qualified Lead", "lead_status": "In Progress", "owner": "Alex Müller", "last_activity": "2026-02-07", "created": "2025-08-30", "city": "Madrid", "country": "ES"},
    {"contact_id": "c-014", "name": "David Chen", "email": "david.c@innovate.sg", "phone": "+65-555-0114", "company": "Innovate SG", "lifecycle_stage": "Customer", "lead_status": "Connected", "owner": "Diego Santos", "last_activity": "2026-02-04", "created": "2025-05-10", "city": "Singapore", "country": "SG"},
    {"contact_id": "c-015", "name": "Anna Kowalski", "email": "anna@digitalpulse.pl", "phone": "+48-555-0115", "company": "DigitalPulse Poland", "lifecycle_stage": "Evangelist", "lead_status": "Connected", "owner": "Sarah Chen", "last_activity": "2026-02-06", "created": "2025-01-20", "city": "Warsaw", "country": "PL"},
]

HUBSPOT_MOCK_COMPANIES = [
    {"company_id": "comp-001", "name": "Acme Corp", "domain": "acmecorp.com", "industry": "Technology", "annual_revenue": 5200000, "employees": 120, "deals_count": 8, "contacts_count": 15, "city": "New York", "country": "US", "owner": "Sarah Chen", "lifecycle_stage": "Customer", "created": "2025-03-10"},
    {"company_id": "comp-002", "name": "GlobalTech GmbH", "domain": "globaltech.de", "industry": "IT Services", "annual_revenue": 3800000, "employees": 85, "deals_count": 5, "contacts_count": 8, "city": "Berlin", "country": "DE", "owner": "Alex Müller", "lifecycle_stage": "Customer", "created": "2025-04-22"},
    {"company_id": "comp-003", "name": "StartupX", "domain": "startupx.co", "industry": "SaaS", "annual_revenue": 890000, "employees": 22, "deals_count": 2, "contacts_count": 4, "city": "Austin", "country": "US", "owner": "Sarah Chen", "lifecycle_stage": "Opportunity", "created": "2025-11-05"},
    {"company_id": "comp-004", "name": "Enterprise Solutions Inc", "domain": "enterprise.com", "industry": "Consulting", "annual_revenue": 12500000, "employees": 340, "deals_count": 12, "contacts_count": 22, "city": "Chicago", "country": "US", "owner": "Sarah Chen", "lifecycle_stage": "Customer", "created": "2025-01-15"},
    {"company_id": "comp-005", "name": "MediaPro LATAM", "domain": "mediapro.mx", "industry": "Media & Entertainment", "annual_revenue": 1600000, "employees": 45, "deals_count": 3, "contacts_count": 6, "city": "Mexico City", "country": "MX", "owner": "Diego Santos", "lifecycle_stage": "Opportunity", "created": "2025-08-18"},
    {"company_id": "comp-006", "name": "FinServe AG", "domain": "finserve.de", "industry": "Financial Services", "annual_revenue": 8900000, "employees": 210, "deals_count": 6, "contacts_count": 9, "city": "Munich", "country": "DE", "owner": "Alex Müller", "lifecycle_stage": "Sales Qualified Lead", "created": "2025-10-30"},
    {"company_id": "comp-007", "name": "RetailPro UK", "domain": "retailpro.co.uk", "industry": "Retail", "annual_revenue": 4200000, "employees": 95, "deals_count": 4, "contacts_count": 7, "city": "London", "country": "UK", "owner": "Sarah Chen", "lifecycle_stage": "Opportunity", "created": "2025-06-14"},
    {"company_id": "comp-008", "name": "CloudNative India", "domain": "cloudnative.in", "industry": "Cloud Computing", "annual_revenue": 2100000, "employees": 60, "deals_count": 1, "contacts_count": 3, "city": "Mumbai", "country": "IN", "owner": "Diego Santos", "lifecycle_stage": "Lead", "created": "2026-01-10"},
    {"company_id": "comp-009", "name": "DigiMarket Japan", "domain": "digimarket.jp", "industry": "Digital Marketing", "annual_revenue": 6700000, "employees": 150, "deals_count": 3, "contacts_count": 5, "city": "Tokyo", "country": "JP", "owner": "Alex Müller", "lifecycle_stage": "Marketing Qualified Lead", "created": "2025-09-20"},
    {"company_id": "comp-010", "name": "SaaSFlow Spain", "domain": "saasflow.es", "industry": "SaaS", "annual_revenue": 1400000, "employees": 35, "deals_count": 2, "contacts_count": 4, "city": "Madrid", "country": "ES", "owner": "Alex Müller", "lifecycle_stage": "Sales Qualified Lead", "created": "2025-07-25"},
]

HUBSPOT_MOCK_DEALS = [
    {"deal_id": "d-001", "name": "Enterprise Contract — Acme Corp", "amount": 12000, "stage": "Closed Won", "pipeline": "Sales Pipeline", "close_date": "2026-02-01", "probability": 100, "company": "Acme Corp", "contact": "John Doe", "owner": "Sarah Chen", "created": "2025-11-15", "deal_type": "New Business"},
    {"deal_id": "d-002", "name": "Agency Retainer Q2 — GlobalTech", "amount": 8000, "stage": "Contract Sent", "pipeline": "Sales Pipeline", "close_date": "2026-03-01", "probability": 90, "company": "GlobalTech GmbH", "contact": "Michael Brown", "owner": "Alex Müller", "created": "2026-01-10", "deal_type": "New Business"},
    {"deal_id": "d-003", "name": "Startup Pilot — StartupX", "amount": 3500, "stage": "Presentation Scheduled", "pipeline": "Sales Pipeline", "close_date": "2026-02-28", "probability": 50, "company": "StartupX", "contact": "Emily Wilson", "owner": "Sarah Chen", "created": "2026-01-20", "deal_type": "New Business"},
    {"deal_id": "d-004", "name": "Enterprise Expansion — ESI", "amount": 24000, "stage": "Closed Won", "pipeline": "Sales Pipeline", "close_date": "2026-01-20", "probability": 100, "company": "Enterprise Solutions Inc", "contact": "Lisa Anderson", "owner": "Sarah Chen", "created": "2025-10-05", "deal_type": "Existing Business"},
    {"deal_id": "d-005", "name": "LatAm Partnership — MediaPro", "amount": 6500, "stage": "Qualified to Buy", "pipeline": "Sales Pipeline", "close_date": "2026-03-15", "probability": 40, "company": "MediaPro LATAM", "contact": "Carlos Rivera", "owner": "Diego Santos", "created": "2026-01-08", "deal_type": "New Business"},
    {"deal_id": "d-006", "name": "FinServe Premium — FinServe AG", "amount": 18500, "stage": "Decision Maker Bought-In", "pipeline": "Sales Pipeline", "close_date": "2026-02-20", "probability": 75, "company": "FinServe AG", "contact": "Thomas König", "owner": "Alex Müller", "created": "2025-12-15", "deal_type": "New Business"},
    {"deal_id": "d-007", "name": "UK Retail Suite — RetailPro", "amount": 9200, "stage": "Appointment Scheduled", "pipeline": "Sales Pipeline", "close_date": "2026-04-01", "probability": 20, "company": "RetailPro UK", "contact": "Robert Taylor", "owner": "Sarah Chen", "created": "2026-01-25", "deal_type": "New Business"},
    {"deal_id": "d-008", "name": "Cloud Migration — CloudNative", "amount": 5800, "stage": "Qualified to Buy", "pipeline": "Sales Pipeline", "close_date": "2026-03-10", "probability": 40, "company": "CloudNative India", "contact": "Priya Sharma", "owner": "Diego Santos", "created": "2026-02-01", "deal_type": "New Business"},
    {"deal_id": "d-009", "name": "Renewal 2026 — Acme Corp", "amount": 14400, "stage": "Closed Won", "pipeline": "Sales Pipeline", "close_date": "2026-01-31", "probability": 100, "company": "Acme Corp", "contact": "Jane Smith", "owner": "Sarah Chen", "created": "2025-12-01", "deal_type": "Existing Business"},
    {"deal_id": "d-010", "name": "SaaS Expansion — SaaSFlow", "amount": 4200, "stage": "Closed Lost", "pipeline": "Sales Pipeline", "close_date": "2026-01-25", "probability": 0, "company": "SaaSFlow Spain", "contact": "Maria Garcia", "owner": "Alex Müller", "created": "2025-10-20", "deal_type": "New Business"},
]

HUBSPOT_MOCK_CAMPAIGNS = [
    {"campaign_id": "em-001", "name": "Winter Product Launch", "subject": "Introducing Our New Platform Features", "status": "sent", "sent": 5678, "delivered": 5540, "opens": 1890, "clicks": 312, "bounces": 68, "unsubscribes": 12, "open_rate": 34.1, "click_rate": 5.6, "send_date": "2026-01-15", "type": "Marketing Email"},
    {"campaign_id": "em-002", "name": "February Newsletter", "subject": "Monthly Insights & Updates", "status": "sent", "sent": 4890, "delivered": 4780, "opens": 1534, "clicks": 245, "bounces": 45, "unsubscribes": 8, "open_rate": 32.1, "click_rate": 5.1, "send_date": "2026-02-01", "type": "Marketing Email"},
    {"campaign_id": "em-003", "name": "Enterprise Case Study", "subject": "How Acme Corp Grew 300% with Our Platform", "status": "sent", "sent": 2340, "delivered": 2295, "opens": 987, "clicks": 198, "bounces": 22, "unsubscribes": 3, "open_rate": 43.0, "click_rate": 8.6, "send_date": "2026-01-28", "type": "Marketing Email"},
    {"campaign_id": "em-004", "name": "Webinar Invite: Q1 Strategy", "subject": "Join Us: 2026 Growth Strategy Webinar", "status": "sent", "sent": 3200, "delivered": 3140, "opens": 1256, "clicks": 412, "bounces": 30, "unsubscribes": 5, "open_rate": 40.0, "click_rate": 13.1, "send_date": "2026-02-03", "type": "Marketing Email"},
    {"campaign_id": "em-005", "name": "Re-engagement Campaign", "subject": "We Miss You — Here's 20% Off", "status": "sent", "sent": 1890, "delivered": 1834, "opens": 456, "clicks": 89, "bounces": 34, "unsubscribes": 22, "open_rate": 24.9, "click_rate": 4.9, "send_date": "2026-01-20", "type": "Marketing Email"},
    {"campaign_id": "em-006", "name": "Deal Closing Sequence", "subject": "Your Custom Proposal is Ready", "status": "active", "sent": 145, "delivered": 142, "opens": 98, "clicks": 45, "bounces": 2, "unsubscribes": 0, "open_rate": 69.0, "click_rate": 31.7, "send_date": "2026-02-05", "type": "Sales Sequence"},
    {"campaign_id": "em-007", "name": "Onboarding Welcome Series", "subject": "Welcome to the Platform!", "status": "active", "sent": 890, "delivered": 878, "opens": 645, "clicks": 234, "bounces": 8, "unsubscribes": 2, "open_rate": 73.5, "click_rate": 26.7, "send_date": "2026-02-06", "type": "Automated Workflow"},
    {"campaign_id": "em-008", "name": "Spring Promo Draft", "subject": "Exclusive Spring Deals Inside", "status": "draft", "sent": 0, "delivered": 0, "opens": 0, "clicks": 0, "bounces": 0, "unsubscribes": 0, "open_rate": 0, "click_rate": 0, "send_date": "2026-03-01", "type": "Marketing Email"},
]


@app.route("/api/connectors/hubspot/portals", methods=["GET"])
def hubspot_portals():
    """List available HubSpot portals"""
    return jsonify({"portals": HUBSPOT_MOCK_PORTALS})


@app.route("/api/connectors/hubspot/overview", methods=["GET"])
def hubspot_overview():
    """Overview KPIs for a HubSpot portal"""
    portal = request.args.get("portal_id", "techstart-crm")
    data = HUBSPOT_MOCK_OVERVIEW.get(portal, {
        "total_contacts": 0, "new_contacts_this_month": 0, "total_companies": 0,
        "total_deals": 0, "deals_won_this_month": 0, "deals_lost_this_month": 0,
        "open_deals_value": 0, "won_revenue_this_month": 0, "won_revenue_last_month": 0,
        "revenue_growth": 0, "pipeline_value": 0, "avg_deal_size": 0,
        "open_tasks": 0, "overdue_tasks": 0, "email_sends_this_month": 0,
        "email_open_rate": 0, "email_click_rate": 0, "email_bounce_rate": 0,
        "form_submissions": 0, "meetings_booked": 0, "calls_logged": 0,
        "monthly_deals": [], "deal_stage_distribution": []
    })
    return jsonify({"portal_id": portal, "overview": data})


@app.route("/api/connectors/hubspot/contacts", methods=["GET"])
def hubspot_contacts():
    """List HubSpot contacts with optional filters"""
    stage = request.args.get("lifecycle_stage", "")
    owner = request.args.get("owner", "")
    filtered = HUBSPOT_MOCK_CONTACTS
    if stage:
        filtered = [c for c in filtered if c["lifecycle_stage"].lower() == stage.lower()]
    if owner:
        filtered = [c for c in filtered if owner.lower() in c["owner"].lower()]
    return jsonify({"contacts": filtered, "total": len(filtered)})


@app.route("/api/connectors/hubspot/companies", methods=["GET"])
def hubspot_companies():
    """List HubSpot companies with optional industry filter"""
    industry = request.args.get("industry", "")
    filtered = HUBSPOT_MOCK_COMPANIES
    if industry:
        filtered = [c for c in filtered if industry.lower() in c["industry"].lower()]
    return jsonify({"companies": filtered, "total": len(filtered)})


@app.route("/api/connectors/hubspot/deals", methods=["GET"])
def hubspot_deals():
    """List HubSpot deals with optional stage filter"""
    stage = request.args.get("stage", "")
    filtered = HUBSPOT_MOCK_DEALS
    if stage:
        filtered = [d for d in filtered if stage.lower() in d["stage"].lower()]
    return jsonify({"deals": filtered, "total": len(filtered)})


@app.route("/api/connectors/hubspot/campaigns", methods=["GET"])
def hubspot_campaigns():
    """List HubSpot email campaigns with optional status filter"""
    status = request.args.get("status", "")
    filtered = HUBSPOT_MOCK_CAMPAIGNS
    if status:
        filtered = [c for c in filtered if c["status"] == status]
    return jsonify({"campaigns": filtered, "total": len(filtered)})


@app.route("/api/connectors/hubspot/reports", methods=["GET"])
def hubspot_reports():
    """Generate daily CRM report rows (last 31 days)"""
    import random
    from datetime import datetime, timedelta
    rows = []
    base = datetime(2026, 2, 7)
    for i in range(31):
        d = base - timedelta(days=i)
        rows.append({
            "date": d.strftime("%Y-%m-%d"),
            "contacts_added": random.randint(2, 18),
            "deals_created": random.randint(0, 5),
            "deals_closed": random.randint(0, 3),
            "revenue": round(random.uniform(800, 4500), 2),
            "emails_sent": random.randint(50, 650),
            "email_opens": random.randint(20, 300),
            "form_submissions": random.randint(1, 20),
            "meetings_booked": random.randint(0, 4),
        })
    return jsonify({"rows": rows, "total": len(rows)})


@app.route("/api/connectors/hubspot/test-call", methods=["POST"])
def hubspot_test_call():
    """Simulate HubSpot API v3 calls"""
    import time
    data = request.get_json() or {}
    endpoint = data.get("endpoint", "contacts")
    start = time.time()

    if endpoint == "contacts":
        response_body = {
            "results": [
                {"id": "c-001", "properties": {"email": "john.doe@techstart.io", "firstname": "John", "lastname": "Doe", "lifecyclestage": "customer", "hs_lead_status": "Connected"}},
                {"id": "c-002", "properties": {"email": "jane.smith@acmecorp.com", "firstname": "Jane", "lastname": "Smith", "lifecyclestage": "customer", "hs_lead_status": "Connected"}},
                {"id": "c-003", "properties": {"email": "m.brown@globaltech.de", "firstname": "Michael", "lastname": "Brown", "lifecyclestage": "salesqualifiedlead", "hs_lead_status": "In Progress"}},
            ],
            "paging": {"next": {"after": "3", "link": "https://api.hubapi.com/crm/v3/objects/contacts?after=3"}}
        }
    elif endpoint == "deals":
        response_body = {
            "results": [
                {"id": "d-001", "properties": {"dealname": "Enterprise Contract — Acme Corp", "amount": "12000", "dealstage": "closedwon", "closedate": "2026-02-01"}},
                {"id": "d-002", "properties": {"dealname": "Agency Retainer Q2", "amount": "8000", "dealstage": "contractsent", "closedate": "2026-03-01"}},
            ],
            "paging": {"next": {"after": "2", "link": "https://api.hubapi.com/crm/v3/objects/deals?after=2"}}
        }
    elif endpoint == "companies":
        response_body = {
            "results": [
                {"id": "comp-001", "properties": {"name": "Acme Corp", "domain": "acmecorp.com", "industry": "Technology", "annualrevenue": "5200000"}},
                {"id": "comp-002", "properties": {"name": "GlobalTech GmbH", "domain": "globaltech.de", "industry": "IT Services", "annualrevenue": "3800000"}},
            ],
            "paging": {"next": {"after": "2", "link": "https://api.hubapi.com/crm/v3/objects/companies?after=2"}}
        }
    else:
        response_body = {"results": [], "paging": None}

    elapsed = round((time.time() - start) * 1000, 1)
    return jsonify({
        "endpoint": endpoint,
        "method": data.get("method", "GET"),
        "request": {"portal": "techstart-crm", "endpoint": f"https://api.hubapi.com/crm/v3/objects/{endpoint}"},
        "response": {"status_code": 200,
                      "headers": {"content-type": "application/json", "x-hubspot-ratelimit-daily": "250000",
                                  "x-hubspot-ratelimit-daily-remaining": "249847"},
                      "body": response_body},
        "latency_ms": elapsed,
        "quota": {"daily_limit": 250000, "remaining": 249847}
    })


# ═══════════════════════════════════════════════════════════════════════════
# SALESFORCE MOCK DATA & ENDPOINTS (Phase 21)
# ═══════════════════════════════════════════════════════════════════════════

SALESFORCE_MOCK_ORGS = [
    {"org_id": "00D5g000008XYZABC", "name": "TechStart Production", "instance_url": "https://techstart.my.salesforce.com", "edition": "Enterprise", "api_version": "v59.0", "currency": "USD", "status": "ACTIVE"},
    {"org_id": "00D5g000008XYZDEF", "name": "TechStart Sandbox", "instance_url": "https://techstart--sandbox.my.salesforce.com", "edition": "Developer", "api_version": "v59.0", "currency": "USD", "status": "ACTIVE"},
    {"org_id": "00D5g000008XYZGHI", "name": "EU Operations Org", "instance_url": "https://euops.my.salesforce.com", "edition": "Professional", "api_version": "v59.0", "currency": "EUR", "status": "ACTIVE"},
]

SALESFORCE_MOCK_OVERVIEW = {
    "00D5g000008XYZABC": {
        "total_leads": 456, "new_leads_this_month": 78, "converted_leads": 34,
        "lead_conversion_rate": 43.6,
        "total_opportunities": 134, "open_opportunities": 67, "won_opportunities": 42,
        "lost_opportunities": 25, "win_rate": 62.7,
        "pipeline_value": 1845000, "closed_won_this_month": 287500,
        "closed_won_last_month": 245000, "revenue_growth": 17.3,
        "avg_deal_size": 6845, "avg_sales_cycle_days": 32,
        "total_accounts": 312, "active_accounts": 189,
        "open_tasks": 67, "overdue_tasks": 12,
        "open_cases": 23, "avg_case_resolution_hours": 18.4,
        "monthly_pipeline": [
            {"month": "2025-09", "won": 198000, "lost": 45000, "pipeline": 890000},
            {"month": "2025-10", "won": 224000, "lost": 62000, "pipeline": 1120000},
            {"month": "2025-11", "won": 256000, "lost": 38000, "pipeline": 1340000},
            {"month": "2025-12", "won": 210000, "lost": 72000, "pipeline": 1250000},
            {"month": "2026-01", "won": 245000, "lost": 55000, "pipeline": 1560000},
            {"month": "2026-02", "won": 287500, "lost": 41000, "pipeline": 1845000},
        ],
        "opportunity_stage_distribution": [
            {"stage": "Prospecting", "count": 15, "value": 187500},
            {"stage": "Qualification", "count": 12, "value": 234000},
            {"stage": "Needs Analysis", "count": 10, "value": 312000},
            {"stage": "Value Proposition", "count": 8, "value": 256000},
            {"stage": "Id. Decision Makers", "count": 7, "value": 189000},
            {"stage": "Perception Analysis", "count": 5, "value": 167000},
            {"stage": "Proposal/Price Quote", "count": 6, "value": 245000},
            {"stage": "Negotiation/Review", "count": 4, "value": 254500},
        ],
    }
}

SALESFORCE_MOCK_LEADS = [
    {"lead_id": "00Q5g000009A001", "name": "Sarah Mitchell", "email": "sarah.m@innovate.io", "company": "InnovateTech", "title": "VP Marketing", "status": "Working - Contacted", "source": "Web", "rating": "Hot", "owner": "James Wilson", "created": "2026-01-28", "last_activity": "2026-02-07", "country": "US", "industry": "Technology"},
    {"lead_id": "00Q5g000009A002", "name": "Marco Rossi", "email": "m.rossi@euromed.it", "company": "EuroMed Solutions", "title": "CTO", "status": "Open - Not Contacted", "source": "Partner Referral", "rating": "Hot", "owner": "Lisa Park", "created": "2026-02-05", "last_activity": "2026-02-05", "country": "IT", "industry": "Healthcare"},
    {"lead_id": "00Q5g000009A003", "name": "David Chang", "email": "d.chang@scale.ai", "company": "ScaleAI Corp", "title": "Director of Engineering", "status": "Working - Contacted", "source": "Organic Search", "rating": "Warm", "owner": "James Wilson", "created": "2026-01-15", "last_activity": "2026-02-06", "country": "US", "industry": "AI/ML"},
    {"lead_id": "00Q5g000009A004", "name": "Aisha Khan", "email": "aisha@finpro.ae", "company": "FinPro Middle East", "title": "Head of Digital", "status": "Working - Contacted", "source": "Trade Show", "rating": "Warm", "owner": "Lisa Park", "created": "2026-01-20", "last_activity": "2026-02-04", "country": "AE", "industry": "Financial Services"},
    {"lead_id": "00Q5g000009A005", "name": "Henrik Larsson", "email": "henrik@nordcloud.se", "company": "NordCloud AB", "title": "CEO", "status": "Open - Not Contacted", "source": "Web", "rating": "Cold", "owner": "James Wilson", "created": "2026-02-06", "last_activity": "2026-02-06", "country": "SE", "industry": "Cloud Computing"},
    {"lead_id": "00Q5g000009A006", "name": "Rachel Green", "email": "rachel@retailmax.com", "company": "RetailMax Inc", "title": "CMO", "status": "Converted", "source": "Advertisement", "rating": "Hot", "owner": "Lisa Park", "created": "2025-12-10", "last_activity": "2026-01-28", "country": "US", "industry": "Retail"},
    {"lead_id": "00Q5g000009A007", "name": "Takeshi Yamamoto", "email": "takeshi@jptech.co.jp", "company": "JP Tech Systems", "title": "Engineering Manager", "status": "Working - Contacted", "source": "Webinar", "rating": "Warm", "owner": "James Wilson", "created": "2026-01-10", "last_activity": "2026-02-03", "country": "JP", "industry": "Technology"},
    {"lead_id": "00Q5g000009A008", "name": "Ana Petrova", "email": "ana@datastream.bg", "company": "DataStream EU", "title": "Product Manager", "status": "Unqualified", "source": "Web", "rating": "Cold", "owner": "Lisa Park", "created": "2026-01-02", "last_activity": "2026-01-15", "country": "BG", "industry": "Data Analytics"},
    {"lead_id": "00Q5g000009A009", "name": "Carlos Mendez", "email": "carlos@latamcloud.br", "company": "LatAm Cloud Services", "title": "VP Sales", "status": "Open - Not Contacted", "source": "Partner Referral", "rating": "Hot", "owner": "James Wilson", "created": "2026-02-04", "last_activity": "2026-02-04", "country": "BR", "industry": "Cloud Computing"},
    {"lead_id": "00Q5g000009A010", "name": "Emma Watson", "email": "emma@greentech.co.uk", "company": "GreenTech UK", "title": "Sustainability Director", "status": "Working - Contacted", "source": "Event", "rating": "Warm", "owner": "Lisa Park", "created": "2026-01-18", "last_activity": "2026-02-07", "country": "UK", "industry": "CleanTech"},
    {"lead_id": "00Q5g000009A011", "name": "Pierre Dubois", "email": "pierre@mediafr.fr", "company": "MediaFrance SA", "title": "Digital Director", "status": "Converted", "source": "Organic Search", "rating": "Hot", "owner": "James Wilson", "created": "2025-11-20", "last_activity": "2026-01-10", "country": "FR", "industry": "Media"},
    {"lead_id": "00Q5g000009A012", "name": "Kim Soo-yeon", "email": "kim@apactech.kr", "company": "APAC Technologies", "title": "Business Development", "status": "Working - Contacted", "source": "LinkedIn", "rating": "Warm", "owner": "Lisa Park", "created": "2026-01-25", "last_activity": "2026-02-06", "country": "KR", "industry": "Technology"},
]

SALESFORCE_MOCK_OPPORTUNITIES = [
    {"opp_id": "006Dg000009B001", "name": "InnovateTech Platform License", "amount": 45000, "stage": "Negotiation/Review", "probability": 85, "close_date": "2026-02-28", "type": "New Business", "account": "InnovateTech", "owner": "James Wilson", "next_step": "Send final proposal", "created": "2025-12-15", "forecast_category": "Commit"},
    {"opp_id": "006Dg000009B002", "name": "EuroMed Digital Transformation", "amount": 125000, "stage": "Proposal/Price Quote", "probability": 70, "close_date": "2026-03-15", "type": "New Business", "account": "EuroMed Solutions", "owner": "Lisa Park", "next_step": "Present to board", "created": "2026-01-05", "forecast_category": "Best Case"},
    {"opp_id": "006Dg000009B003", "name": "ScaleAI Annual Renewal", "amount": 32000, "stage": "Closed Won", "probability": 100, "close_date": "2026-02-01", "type": "Existing Business", "account": "ScaleAI Corp", "owner": "James Wilson", "next_step": "Complete", "created": "2025-11-20", "forecast_category": "Closed"},
    {"opp_id": "006Dg000009B004", "name": "FinPro Enterprise Suite", "amount": 78000, "stage": "Value Proposition", "probability": 50, "close_date": "2026-04-01", "type": "New Business", "account": "FinPro Middle East", "owner": "Lisa Park", "next_step": "Schedule demo", "created": "2026-01-22", "forecast_category": "Pipeline"},
    {"opp_id": "006Dg000009B005", "name": "RetailMax Upgrade Q2", "amount": 18500, "stage": "Closed Won", "probability": 100, "close_date": "2026-01-28", "type": "Existing Business", "account": "RetailMax Inc", "owner": "Lisa Park", "next_step": "Complete", "created": "2025-10-12", "forecast_category": "Closed"},
    {"opp_id": "006Dg000009B006", "name": "JP Tech Cloud Migration", "amount": 92000, "stage": "Needs Analysis", "probability": 35, "close_date": "2026-05-01", "type": "New Business", "account": "JP Tech Systems", "owner": "James Wilson", "next_step": "Requirements workshop", "created": "2026-01-12", "forecast_category": "Pipeline"},
    {"opp_id": "006Dg000009B007", "name": "NordCloud Pilot Program", "amount": 15000, "stage": "Qualification", "probability": 25, "close_date": "2026-04-15", "type": "New Business", "account": "NordCloud AB", "owner": "James Wilson", "next_step": "Discovery call", "created": "2026-02-06", "forecast_category": "Pipeline"},
    {"opp_id": "006Dg000009B008", "name": "DataStream Analytics — Lost", "amount": 28000, "stage": "Closed Lost", "probability": 0, "close_date": "2026-01-20", "type": "New Business", "account": "DataStream EU", "owner": "Lisa Park", "next_step": "N/A", "created": "2025-09-15", "forecast_category": "Omitted"},
    {"opp_id": "006Dg000009B009", "name": "LatAm Enterprise Bundle", "amount": 67000, "stage": "Id. Decision Makers", "probability": 45, "close_date": "2026-03-30", "type": "New Business", "account": "LatAm Cloud Services", "owner": "James Wilson", "next_step": "Meet CFO", "created": "2026-02-04", "forecast_category": "Best Case"},
    {"opp_id": "006Dg000009B010", "name": "GreenTech Sustainability Suite", "amount": 55000, "stage": "Perception Analysis", "probability": 55, "close_date": "2026-03-20", "type": "New Business", "account": "GreenTech UK", "owner": "Lisa Park", "next_step": "Proof of concept", "created": "2026-01-18", "forecast_category": "Best Case"},
]

SALESFORCE_MOCK_ACCOUNTS = [
    {"account_id": "001Dg000007C001", "name": "InnovateTech", "industry": "Technology", "annual_revenue": 8500000, "employees": 180, "type": "Customer", "rating": "Hot", "owner": "James Wilson", "website": "innovate.io", "phone": "+1-555-1001", "billing_country": "US", "open_opportunities": 2, "total_won": 145000, "created": "2024-06-15"},
    {"account_id": "001Dg000007C002", "name": "EuroMed Solutions", "industry": "Healthcare", "annual_revenue": 12000000, "employees": 320, "type": "Prospect", "rating": "Hot", "owner": "Lisa Park", "website": "euromed.it", "phone": "+39-555-1002", "billing_country": "IT", "open_opportunities": 1, "total_won": 0, "created": "2025-08-22"},
    {"account_id": "001Dg000007C003", "name": "ScaleAI Corp", "industry": "AI/ML", "annual_revenue": 25000000, "employees": 450, "type": "Customer", "rating": "Warm", "owner": "James Wilson", "website": "scale.ai", "phone": "+1-555-1003", "billing_country": "US", "open_opportunities": 0, "total_won": 96000, "created": "2024-03-10"},
    {"account_id": "001Dg000007C004", "name": "FinPro Middle East", "industry": "Financial Services", "annual_revenue": 6200000, "employees": 140, "type": "Prospect", "rating": "Warm", "owner": "Lisa Park", "website": "finpro.ae", "phone": "+971-555-1004", "billing_country": "AE", "open_opportunities": 1, "total_won": 0, "created": "2025-11-05"},
    {"account_id": "001Dg000007C005", "name": "RetailMax Inc", "industry": "Retail", "annual_revenue": 45000000, "employees": 890, "type": "Customer", "rating": "Hot", "owner": "Lisa Park", "website": "retailmax.com", "phone": "+1-555-1005", "billing_country": "US", "open_opportunities": 0, "total_won": 287500, "created": "2024-01-20"},
    {"account_id": "001Dg000007C006", "name": "JP Tech Systems", "industry": "Technology", "annual_revenue": 18000000, "employees": 380, "type": "Prospect", "rating": "Warm", "owner": "James Wilson", "website": "jptech.co.jp", "phone": "+81-555-1006", "billing_country": "JP", "open_opportunities": 1, "total_won": 0, "created": "2025-10-15"},
    {"account_id": "001Dg000007C007", "name": "NordCloud AB", "industry": "Cloud Computing", "annual_revenue": 3400000, "employees": 75, "type": "Prospect", "rating": "Cold", "owner": "James Wilson", "website": "nordcloud.se", "phone": "+46-555-1007", "billing_country": "SE", "open_opportunities": 1, "total_won": 0, "created": "2026-01-10"},
    {"account_id": "001Dg000007C008", "name": "GreenTech UK", "industry": "CleanTech", "annual_revenue": 9800000, "employees": 210, "type": "Prospect", "rating": "Warm", "owner": "Lisa Park", "website": "greentech.co.uk", "phone": "+44-555-1008", "billing_country": "UK", "open_opportunities": 1, "total_won": 0, "created": "2025-12-01"},
    {"account_id": "001Dg000007C009", "name": "LatAm Cloud Services", "industry": "Cloud Computing", "annual_revenue": 5600000, "employees": 120, "type": "Prospect", "rating": "Hot", "owner": "James Wilson", "website": "latamcloud.br", "phone": "+55-555-1009", "billing_country": "BR", "open_opportunities": 1, "total_won": 0, "created": "2026-01-15"},
    {"account_id": "001Dg000007C010", "name": "MediaFrance SA", "industry": "Media", "annual_revenue": 14000000, "employees": 280, "type": "Customer", "rating": "Warm", "owner": "James Wilson", "website": "mediafr.fr", "phone": "+33-555-1010", "billing_country": "FR", "open_opportunities": 0, "total_won": 68000, "created": "2024-09-05"},
]

SALESFORCE_MOCK_CAMPAIGNS = [
    {"campaign_id": "701Dg000004D001", "name": "Q1 2026 Product Launch", "type": "Product Launch", "status": "Active", "start_date": "2026-01-15", "end_date": "2026-03-31", "budget": 25000, "actual_cost": 12400, "members": 1245, "responses": 312, "converted": 45, "roi": 187, "owner": "James Wilson"},
    {"campaign_id": "701Dg000004D002", "name": "Enterprise Webinar Series", "type": "Webinar", "status": "Active", "start_date": "2026-01-01", "end_date": "2026-06-30", "budget": 15000, "actual_cost": 4800, "members": 890, "responses": 234, "converted": 28, "roi": 245, "owner": "Lisa Park"},
    {"campaign_id": "701Dg000004D003", "name": "Partner Referral Program", "type": "Referral", "status": "Active", "start_date": "2025-10-01", "end_date": "2026-09-30", "budget": 50000, "actual_cost": 18200, "members": 156, "responses": 67, "converted": 22, "roi": 312, "owner": "James Wilson"},
    {"campaign_id": "701Dg000004D004", "name": "LinkedIn ABM Campaign", "type": "ABM", "status": "Active", "start_date": "2026-02-01", "end_date": "2026-04-30", "budget": 35000, "actual_cost": 5600, "members": 450, "responses": 89, "converted": 8, "roi": 78, "owner": "Lisa Park"},
    {"campaign_id": "701Dg000004D005", "name": "Holiday Promo 2025", "type": "Promotion", "status": "Completed", "start_date": "2025-11-15", "end_date": "2025-12-31", "budget": 20000, "actual_cost": 19800, "members": 3456, "responses": 567, "converted": 89, "roi": 156, "owner": "James Wilson"},
    {"campaign_id": "701Dg000004D006", "name": "Industry Conference 2026", "type": "Trade Show", "status": "Planned", "start_date": "2026-05-15", "end_date": "2026-05-18", "budget": 45000, "actual_cost": 0, "members": 0, "responses": 0, "converted": 0, "roi": 0, "owner": "Lisa Park"},
]


@app.route("/api/connectors/salesforce/orgs", methods=["GET"])
def salesforce_orgs():
    """List available Salesforce orgs"""
    return jsonify({"orgs": SALESFORCE_MOCK_ORGS})


@app.route("/api/connectors/salesforce/overview", methods=["GET"])
def salesforce_overview():
    """Overview KPIs for a Salesforce org"""
    org = request.args.get("org_id", "00D5g000008XYZABC")
    data = SALESFORCE_MOCK_OVERVIEW.get(org, {
        "total_leads": 0, "new_leads_this_month": 0, "converted_leads": 0, "lead_conversion_rate": 0,
        "total_opportunities": 0, "open_opportunities": 0, "won_opportunities": 0, "lost_opportunities": 0, "win_rate": 0,
        "pipeline_value": 0, "closed_won_this_month": 0, "closed_won_last_month": 0, "revenue_growth": 0,
        "avg_deal_size": 0, "avg_sales_cycle_days": 0, "total_accounts": 0, "active_accounts": 0,
        "open_tasks": 0, "overdue_tasks": 0, "open_cases": 0, "avg_case_resolution_hours": 0,
        "monthly_pipeline": [], "opportunity_stage_distribution": []
    })
    return jsonify({"org_id": org, "overview": data})


@app.route("/api/connectors/salesforce/leads", methods=["GET"])
def salesforce_leads():
    """List Salesforce leads with optional filters"""
    status = request.args.get("status", "")
    rating = request.args.get("rating", "")
    filtered = SALESFORCE_MOCK_LEADS
    if status:
        filtered = [l for l in filtered if status.lower() in l["status"].lower()]
    if rating:
        filtered = [l for l in filtered if l["rating"].lower() == rating.lower()]
    return jsonify({"leads": filtered, "total": len(filtered)})


@app.route("/api/connectors/salesforce/opportunities", methods=["GET"])
def salesforce_opportunities():
    """List Salesforce opportunities with optional stage filter"""
    stage = request.args.get("stage", "")
    filtered = SALESFORCE_MOCK_OPPORTUNITIES
    if stage:
        filtered = [o for o in filtered if stage.lower() in o["stage"].lower()]
    return jsonify({"opportunities": filtered, "total": len(filtered)})


@app.route("/api/connectors/salesforce/accounts", methods=["GET"])
def salesforce_accounts():
    """List Salesforce accounts with optional type filter"""
    acct_type = request.args.get("type", "")
    filtered = SALESFORCE_MOCK_ACCOUNTS
    if acct_type:
        filtered = [a for a in filtered if a["type"].lower() == acct_type.lower()]
    return jsonify({"accounts": filtered, "total": len(filtered)})


@app.route("/api/connectors/salesforce/campaigns", methods=["GET"])
def salesforce_campaigns():
    """List Salesforce campaigns with optional status filter"""
    status = request.args.get("status", "")
    filtered = SALESFORCE_MOCK_CAMPAIGNS
    if status:
        filtered = [c for c in filtered if c["status"].lower() == status.lower()]
    return jsonify({"campaigns": filtered, "total": len(filtered)})


@app.route("/api/connectors/salesforce/reports", methods=["GET"])
def salesforce_reports():
    """Generate daily sales report rows (last 31 days)"""
    import random
    from datetime import datetime, timedelta
    rows = []
    base = datetime(2026, 2, 7)
    for i in range(31):
        d = base - timedelta(days=i)
        rows.append({
            "date": d.strftime("%Y-%m-%d"),
            "new_leads": random.randint(1, 12),
            "converted_leads": random.randint(0, 5),
            "opps_created": random.randint(0, 4),
            "opps_closed_won": random.randint(0, 3),
            "revenue": round(random.uniform(2000, 18000), 2),
            "pipeline_added": round(random.uniform(5000, 45000), 2),
            "activities": random.randint(15, 80),
            "cases_closed": random.randint(0, 8),
        })
    return jsonify({"rows": rows, "total": len(rows)})


@app.route("/api/connectors/salesforce/test-call", methods=["POST"])
def salesforce_test_call():
    """Simulate Salesforce REST API calls"""
    import time
    data = request.get_json() or {}
    endpoint = data.get("endpoint", "leads")
    start = time.time()

    if endpoint == "leads":
        response_body = {
            "totalSize": 3, "done": True,
            "records": [
                {"attributes": {"type": "Lead", "url": "/services/data/v59.0/sobjects/Lead/00Q5g000009A001"}, "Id": "00Q5g000009A001", "Name": "Sarah Mitchell", "Company": "InnovateTech", "Status": "Working - Contacted", "Rating": "Hot"},
                {"attributes": {"type": "Lead", "url": "/services/data/v59.0/sobjects/Lead/00Q5g000009A002"}, "Id": "00Q5g000009A002", "Name": "Marco Rossi", "Company": "EuroMed Solutions", "Status": "Open - Not Contacted", "Rating": "Hot"},
                {"attributes": {"type": "Lead", "url": "/services/data/v59.0/sobjects/Lead/00Q5g000009A003"}, "Id": "00Q5g000009A003", "Name": "David Chang", "Company": "ScaleAI Corp", "Status": "Working - Contacted", "Rating": "Warm"},
            ]
        }
    elif endpoint == "opportunities":
        response_body = {
            "totalSize": 2, "done": True,
            "records": [
                {"attributes": {"type": "Opportunity", "url": "/services/data/v59.0/sobjects/Opportunity/006Dg000009B001"}, "Id": "006Dg000009B001", "Name": "InnovateTech Platform License", "Amount": 45000, "StageName": "Negotiation/Review", "CloseDate": "2026-02-28"},
                {"attributes": {"type": "Opportunity", "url": "/services/data/v59.0/sobjects/Opportunity/006Dg000009B002"}, "Id": "006Dg000009B002", "Name": "EuroMed Digital Transformation", "Amount": 125000, "StageName": "Proposal/Price Quote", "CloseDate": "2026-03-15"},
            ]
        }
    elif endpoint == "accounts":
        response_body = {
            "totalSize": 2, "done": True,
            "records": [
                {"attributes": {"type": "Account", "url": "/services/data/v59.0/sobjects/Account/001Dg000007C001"}, "Id": "001Dg000007C001", "Name": "InnovateTech", "Industry": "Technology", "AnnualRevenue": 8500000},
                {"attributes": {"type": "Account", "url": "/services/data/v59.0/sobjects/Account/001Dg000007C005"}, "Id": "001Dg000007C005", "Name": "RetailMax Inc", "Industry": "Retail", "AnnualRevenue": 45000000},
            ]
        }
    else:
        response_body = {"totalSize": 0, "done": True, "records": []}

    elapsed = round((time.time() - start) * 1000, 1)
    return jsonify({
        "endpoint": endpoint,
        "method": data.get("method", "GET"),
        "request": {"instance": "techstart.my.salesforce.com", "endpoint": f"/services/data/v59.0/query/?q=SELECT+Id,Name+FROM+{endpoint.title()}"},
        "response": {"status_code": 200,
                      "headers": {"content-type": "application/json;charset=UTF-8", "sforce-limit-info": "api-usage=148/15000"},
                      "body": response_body},
        "latency_ms": elapsed,
        "quota": {"api_usage": "148/15000", "daily_remaining": 14852}
    })


# ═══════════════════════════════════════════════════════════════════════════
# QUICKBOOKS MOCK DATA & ENDPOINTS (Phase 22)
# ═══════════════════════════════════════════════════════════════════════════

QUICKBOOKS_MOCK_COMPANIES = [
    {"company_id": "123456789", "name": "TechStart Agency", "legal_name": "TechStart Digital Agency LLC", "industry": "Technology", "fiscal_year_start": "January", "currency": "USD", "country": "US", "status": "ACTIVE"},
    {"company_id": "987654321", "name": "Personal Brand", "legal_name": "Alex Johnson Consulting", "industry": "Consulting", "fiscal_year_start": "January", "currency": "USD", "country": "US", "status": "ACTIVE"},
    {"company_id": "456789012", "name": "Ecom Shop EU", "legal_name": "EcomShop Europe GmbH", "industry": "E-Commerce", "fiscal_year_start": "April", "currency": "EUR", "country": "DE", "status": "ACTIVE"},
]

QUICKBOOKS_MOCK_OVERVIEW = {
    "123456789": {
        "total_revenue": 48120, "total_expenses": 32450, "net_profit": 15670,
        "profit_margin": 32.6, "cash_on_hand": 67890, "cash_flow": 8912,
        "accounts_receivable": 18450, "accounts_payable": 7230,
        "total_invoices": 87, "paid_invoices": 62, "overdue_invoices": 8, "open_invoices": 17,
        "total_bills": 34, "paid_bills": 28, "overdue_bills": 3,
        "yoy_revenue_growth": 23.4, "yoy_expense_growth": 12.1,
        "current_ratio": 2.8, "quick_ratio": 2.1,
        "monthly_pnl": [
            {"month": "2025-09", "revenue": 41200, "expenses": 28900, "profit": 12300},
            {"month": "2025-10", "revenue": 43800, "expenses": 30100, "profit": 13700},
            {"month": "2025-11", "revenue": 46500, "expenses": 31200, "profit": 15300},
            {"month": "2025-12", "revenue": 44900, "expenses": 33800, "profit": 11100},
            {"month": "2026-01", "revenue": 47200, "expenses": 31900, "profit": 15300},
            {"month": "2026-02", "revenue": 48120, "expenses": 32450, "profit": 15670},
        ],
        "expense_by_category": [
            {"category": "Cloud Services", "amount": 8450, "pct": 26.0},
            {"category": "Salaries & Wages", "amount": 12800, "pct": 39.4},
            {"category": "Marketing & Ads", "amount": 4200, "pct": 12.9},
            {"category": "Office & Rent", "amount": 3100, "pct": 9.6},
            {"category": "Software Licenses", "amount": 2150, "pct": 6.6},
            {"category": "Professional Services", "amount": 1750, "pct": 5.4},
        ],
    }
}

QUICKBOOKS_MOCK_INVOICES = [
    {"invoice_id": "INV-2026-001", "customer": "Acme Corp", "amount": 4500.00, "balance_due": 0, "status": "Paid", "due_date": "2026-01-15", "issue_date": "2025-12-16", "terms": "Net 30", "items": "Web Dev Retainer (Jan)", "payment_date": "2026-01-10"},
    {"invoice_id": "INV-2026-002", "customer": "Global Media Inc", "amount": 2800.00, "balance_due": 2800.00, "status": "Overdue", "due_date": "2026-01-30", "issue_date": "2025-12-31", "terms": "Net 30", "items": "SEO Campaign Q1", "payment_date": None},
    {"invoice_id": "INV-2026-003", "customer": "Bright Ideas LLC", "amount": 6200.00, "balance_due": 0, "status": "Paid", "due_date": "2026-02-01", "issue_date": "2026-01-02", "terms": "Net 30", "items": "App Development Phase 2", "payment_date": "2026-01-28"},
    {"invoice_id": "INV-2026-004", "customer": "NexGen Solutions", "amount": 3400.00, "balance_due": 3400.00, "status": "Open", "due_date": "2026-02-28", "issue_date": "2026-01-29", "terms": "Net 30", "items": "Cloud Migration Consulting", "payment_date": None},
    {"invoice_id": "INV-2026-005", "customer": "FreshStart Co", "amount": 1950.00, "balance_due": 0, "status": "Paid", "due_date": "2026-01-20", "issue_date": "2025-12-21", "terms": "Net 30", "items": "Brand Strategy Workshop", "payment_date": "2026-01-18"},
    {"invoice_id": "INV-2026-006", "customer": "Summit Enterprises", "amount": 8750.00, "balance_due": 8750.00, "status": "Open", "due_date": "2026-03-10", "issue_date": "2026-02-08", "terms": "Net 30", "items": "Enterprise Platform License Q1", "payment_date": None},
    {"invoice_id": "INV-2026-007", "customer": "DataFlow Analytics", "amount": 2100.00, "balance_due": 2100.00, "status": "Overdue", "due_date": "2026-01-25", "issue_date": "2025-12-26", "terms": "Net 30", "items": "Dashboard Development", "payment_date": None},
    {"invoice_id": "INV-2026-008", "customer": "Acme Corp", "amount": 4500.00, "balance_due": 4500.00, "status": "Open", "due_date": "2026-02-15", "issue_date": "2026-01-16", "terms": "Net 30", "items": "Web Dev Retainer (Feb)", "payment_date": None},
    {"invoice_id": "INV-2026-009", "customer": "Pixel Perfect Studio", "amount": 3600.00, "balance_due": 0, "status": "Paid", "due_date": "2026-02-05", "issue_date": "2026-01-06", "terms": "Net 30", "items": "UI/UX Redesign", "payment_date": "2026-02-03"},
    {"invoice_id": "INV-2026-010", "customer": "CloudNine SaaS", "amount": 5200.00, "balance_due": 5200.00, "status": "Open", "due_date": "2026-03-01", "issue_date": "2026-01-30", "terms": "Net 30", "items": "API Integration Project", "payment_date": None},
    {"invoice_id": "INV-2026-011", "customer": "Global Media Inc", "amount": 1800.00, "balance_due": 0, "status": "Paid", "due_date": "2025-12-30", "issue_date": "2025-11-30", "terms": "Net 30", "items": "Content Strategy Dec", "payment_date": "2025-12-28"},
    {"invoice_id": "INV-2026-012", "customer": "Bright Ideas LLC", "amount": 3900.00, "balance_due": 3900.00, "status": "Open", "due_date": "2026-03-05", "issue_date": "2026-02-03", "terms": "Net 30", "items": "App Maintenance Q1", "payment_date": None},
]

QUICKBOOKS_MOCK_EXPENSES = [
    {"expense_id": "EXP-001", "vendor": "Amazon Web Services", "category": "Cloud Services", "amount": 2340.00, "date": "2026-02-01", "payment_method": "Credit Card", "status": "Paid", "description": "EC2 + S3 + RDS — Feb 2026"},
    {"expense_id": "EXP-002", "vendor": "Google Cloud", "category": "Cloud Services", "amount": 1890.00, "date": "2026-02-01", "payment_method": "Credit Card", "status": "Paid", "description": "GCP Compute + BigQuery — Feb"},
    {"expense_id": "EXP-003", "vendor": "Meta Platforms", "category": "Marketing & Ads", "amount": 1850.00, "date": "2026-02-03", "payment_method": "Credit Card", "status": "Paid", "description": "Facebook/Instagram Ads — Week 1"},
    {"expense_id": "EXP-004", "vendor": "WeWork", "category": "Office & Rent", "amount": 3100.00, "date": "2026-02-01", "payment_method": "Bank Transfer", "status": "Paid", "description": "Office Space — Feb 2026"},
    {"expense_id": "EXP-005", "vendor": "Figma Inc", "category": "Software Licenses", "amount": 450.00, "date": "2026-02-01", "payment_method": "Credit Card", "status": "Paid", "description": "Figma Business Plan — 10 seats"},
    {"expense_id": "EXP-006", "vendor": "Slack Technologies", "category": "Software Licenses", "amount": 280.00, "date": "2026-02-01", "payment_method": "Credit Card", "status": "Paid", "description": "Slack Pro — 25 users"},
    {"expense_id": "EXP-007", "vendor": "Johnson & Associates", "category": "Professional Services", "amount": 1750.00, "date": "2026-01-28", "payment_method": "Bank Transfer", "status": "Paid", "description": "Legal review — contract templates"},
    {"expense_id": "EXP-008", "vendor": "Google Ads", "category": "Marketing & Ads", "amount": 2350.00, "date": "2026-02-05", "payment_method": "Credit Card", "status": "Pending", "description": "Google Ads — Feb campaign"},
    {"expense_id": "EXP-009", "vendor": "Vercel Inc", "category": "Cloud Services", "amount": 320.00, "date": "2026-02-01", "payment_method": "Credit Card", "status": "Paid", "description": "Vercel Pro — hosting"},
    {"expense_id": "EXP-010", "vendor": "Adobe Systems", "category": "Software Licenses", "amount": 540.00, "date": "2026-02-01", "payment_method": "Credit Card", "status": "Paid", "description": "Creative Cloud — 5 licenses"},
    {"expense_id": "EXP-011", "vendor": "DataDog", "category": "Cloud Services", "amount": 680.00, "date": "2026-02-01", "payment_method": "Credit Card", "status": "Paid", "description": "Monitoring & APM — Feb"},
    {"expense_id": "EXP-012", "vendor": "FedEx", "category": "Office & Rent", "amount": 125.00, "date": "2026-02-04", "payment_method": "Credit Card", "status": "Paid", "description": "Shipping — client hardware"},
]

QUICKBOOKS_MOCK_BANKING = [
    {"txn_id": "TXN-001", "date": "2026-02-07", "description": "Payment from Acme Corp", "amount": 4500.00, "type": "Credit", "account": "Business Checking", "categorized": True, "category": "Sales Income"},
    {"txn_id": "TXN-002", "date": "2026-02-06", "description": "AWS Monthly Bill", "amount": -2340.00, "type": "Debit", "account": "Business Checking", "categorized": True, "category": "Cloud Services"},
    {"txn_id": "TXN-003", "date": "2026-02-05", "description": "Google Ads Payment", "amount": -2350.00, "type": "Debit", "account": "Business Credit Card", "categorized": False, "category": None},
    {"txn_id": "TXN-004", "date": "2026-02-05", "description": "Payment from Pixel Perfect Studio", "amount": 3600.00, "type": "Credit", "account": "Business Checking", "categorized": True, "category": "Sales Income"},
    {"txn_id": "TXN-005", "date": "2026-02-04", "description": "FedEx Shipping", "amount": -125.00, "type": "Debit", "account": "Business Credit Card", "categorized": False, "category": None},
    {"txn_id": "TXN-006", "date": "2026-02-03", "description": "Meta Ads Payment", "amount": -1850.00, "type": "Debit", "account": "Business Credit Card", "categorized": True, "category": "Marketing & Ads"},
    {"txn_id": "TXN-007", "date": "2026-02-03", "description": "Payment from Bright Ideas LLC", "amount": 6200.00, "type": "Credit", "account": "Business Checking", "categorized": True, "category": "Sales Income"},
    {"txn_id": "TXN-008", "date": "2026-02-02", "description": "Figma Subscription", "amount": -450.00, "type": "Debit", "account": "Business Credit Card", "categorized": True, "category": "Software Licenses"},
    {"txn_id": "TXN-009", "date": "2026-02-01", "description": "WeWork Office Rent", "amount": -3100.00, "type": "Debit", "account": "Business Checking", "categorized": True, "category": "Office & Rent"},
    {"txn_id": "TXN-010", "date": "2026-02-01", "description": "GCP Monthly Bill", "amount": -1890.00, "type": "Debit", "account": "Business Checking", "categorized": True, "category": "Cloud Services"},
    {"txn_id": "TXN-011", "date": "2026-01-31", "description": "ATM Cash Withdrawal", "amount": -200.00, "type": "Debit", "account": "Business Checking", "categorized": False, "category": None},
    {"txn_id": "TXN-012", "date": "2026-01-30", "description": "Interest Income", "amount": 42.50, "type": "Credit", "account": "Business Savings", "categorized": True, "category": "Interest Income"},
]


@app.route("/api/connectors/quickbooks/companies", methods=["GET"])
def quickbooks_companies():
    """List available QuickBooks companies"""
    return jsonify({"companies": QUICKBOOKS_MOCK_COMPANIES})


@app.route("/api/connectors/quickbooks/overview", methods=["GET"])
def quickbooks_overview():
    """Financial overview KPIs for a company"""
    cid = request.args.get("company_id", "123456789")
    data = QUICKBOOKS_MOCK_OVERVIEW.get(cid, {
        "total_revenue": 0, "total_expenses": 0, "net_profit": 0, "profit_margin": 0,
        "cash_on_hand": 0, "cash_flow": 0, "accounts_receivable": 0, "accounts_payable": 0,
        "total_invoices": 0, "paid_invoices": 0, "overdue_invoices": 0, "open_invoices": 0,
        "total_bills": 0, "paid_bills": 0, "overdue_bills": 0,
        "yoy_revenue_growth": 0, "yoy_expense_growth": 0, "current_ratio": 0, "quick_ratio": 0,
        "monthly_pnl": [], "expense_by_category": []
    })
    return jsonify({"company_id": cid, "overview": data})


@app.route("/api/connectors/quickbooks/invoices", methods=["GET"])
def quickbooks_invoices():
    """List invoices with optional status filter"""
    status = request.args.get("status", "")
    filtered = QUICKBOOKS_MOCK_INVOICES
    if status:
        filtered = [inv for inv in filtered if inv["status"].lower() == status.lower()]
    return jsonify({"invoices": filtered, "total": len(filtered)})


@app.route("/api/connectors/quickbooks/expenses", methods=["GET"])
def quickbooks_expenses():
    """List expenses with optional category filter"""
    category = request.args.get("category", "")
    filtered = QUICKBOOKS_MOCK_EXPENSES
    if category:
        filtered = [e for e in filtered if category.lower() in e["category"].lower()]
    return jsonify({"expenses": filtered, "total": len(filtered)})


@app.route("/api/connectors/quickbooks/banking", methods=["GET"])
def quickbooks_banking():
    """List bank transactions with optional type filter"""
    txn_type = request.args.get("type", "")
    filtered = QUICKBOOKS_MOCK_BANKING
    if txn_type:
        filtered = [t for t in filtered if t["type"].lower() == txn_type.lower()]
    return jsonify({"transactions": filtered, "total": len(filtered)})


@app.route("/api/connectors/quickbooks/reports", methods=["GET"])
def quickbooks_reports():
    """Generate monthly P&L report rows"""
    import random
    from datetime import datetime, timedelta
    rows = []
    base = datetime(2026, 2, 7)
    for i in range(31):
        d = base - timedelta(days=i)
        rev = round(random.uniform(800, 3200), 2)
        exp = round(random.uniform(500, 2100), 2)
        rows.append({
            "date": d.strftime("%Y-%m-%d"),
            "revenue": rev,
            "cost_of_goods": round(rev * random.uniform(0.15, 0.30), 2),
            "gross_profit": round(rev * random.uniform(0.70, 0.85), 2),
            "operating_expenses": exp,
            "net_income": round(rev - exp, 2),
            "invoices_sent": random.randint(0, 5),
            "payments_received": random.randint(0, 4),
            "bills_paid": random.randint(0, 3),
        })
    return jsonify({"rows": rows, "total": len(rows)})


@app.route("/api/connectors/quickbooks/test-call", methods=["POST"])
def quickbooks_test_call():
    """Simulate QuickBooks API calls"""
    import time
    data = request.get_json() or {}
    endpoint = data.get("endpoint", "invoices")
    start = time.time()

    if endpoint == "invoices":
        response_body = {
            "QueryResponse": {
                "Invoice": [
                    {"Id": "INV-2026-001", "DocNumber": "1001", "TotalAmt": 4500.00, "Balance": 0, "CustomerRef": {"name": "Acme Corp"}, "DueDate": "2026-01-15", "TxnDate": "2025-12-16"},
                    {"Id": "INV-2026-002", "DocNumber": "1002", "TotalAmt": 2800.00, "Balance": 2800.00, "CustomerRef": {"name": "Global Media Inc"}, "DueDate": "2026-01-30", "TxnDate": "2025-12-31"},
                    {"Id": "INV-2026-003", "DocNumber": "1003", "TotalAmt": 6200.00, "Balance": 0, "CustomerRef": {"name": "Bright Ideas LLC"}, "DueDate": "2026-02-01", "TxnDate": "2026-01-02"},
                ],
                "startPosition": 1, "maxResults": 3, "totalCount": 12
            }, "time": "2026-02-07T10:15:30.123-08:00"
        }
    elif endpoint == "expenses":
        response_body = {
            "QueryResponse": {
                "Purchase": [
                    {"Id": "EXP-001", "TotalAmt": 2340.00, "PaymentType": "CreditCard", "EntityRef": {"name": "Amazon Web Services"}, "TxnDate": "2026-02-01", "AccountRef": {"name": "Cloud Services"}},
                    {"Id": "EXP-002", "DocNumber": "EXP-002", "TotalAmt": 1890.00, "PaymentType": "CreditCard", "EntityRef": {"name": "Google Cloud"}, "TxnDate": "2026-02-01", "AccountRef": {"name": "Cloud Services"}},
                ],
                "startPosition": 1, "maxResults": 2, "totalCount": 12
            }, "time": "2026-02-07T10:15:30.456-08:00"
        }
    elif endpoint == "pnl":
        response_body = {
            "Header": {"ReportName": "ProfitAndLoss", "StartPeriod": "2026-01-01", "EndPeriod": "2026-02-07", "Currency": "USD"},
            "Rows": {
                "Row": [
                    {"type": "Section", "group": "Income", "Summary": {"ColData": [{"value": "Total Income"}, {"value": "48120.00"}]}},
                    {"type": "Section", "group": "COGS", "Summary": {"ColData": [{"value": "Total COGS"}, {"value": "12030.00"}]}},
                    {"type": "Section", "group": "GrossProfit", "Summary": {"ColData": [{"value": "Gross Profit"}, {"value": "36090.00"}]}},
                    {"type": "Section", "group": "Expenses", "Summary": {"ColData": [{"value": "Total Expenses"}, {"value": "20420.00"}]}},
                    {"type": "Section", "group": "NetIncome", "Summary": {"ColData": [{"value": "Net Income"}, {"value": "15670.00"}]}},
                ]
            }
        }
    else:
        response_body = {"QueryResponse": {}, "time": "2026-02-07T10:15:30.000-08:00"}

    elapsed = round((time.time() - start) * 1000, 1)
    return jsonify({
        "endpoint": endpoint,
        "method": data.get("method", "GET"),
        "request": {"base_url": "https://quickbooks.api.intuit.com", "endpoint": f"/v3/company/123456789/{endpoint}"},
        "response": {"status_code": 200,
                      "headers": {"content-type": "application/json;charset=UTF-8", "intuit-tid": "abc123-def456-ghi789"},
                      "body": response_body},
        "latency_ms": elapsed,
        "quota": {"throttle_remaining": 500, "daily_limit": 500}
    })


# ═══════════════════════════════════════════════════════════════════════════════
# MAILCHIMP  –  Email Marketing & Automation
# ═══════════════════════════════════════════════════════════════════════════════

MAILCHIMP_MOCK_AUDIENCES = [
    {"id": "aud_001", "name": "Main Newsletter",       "member_count": 24850, "open_rate": 28.4, "click_rate": 4.2, "unsubscribe_rate": 0.3, "campaign_count": 142, "created": "2023-06-15"},
    {"id": "aud_002", "name": "Product Updates",        "member_count": 18320, "open_rate": 32.1, "click_rate": 5.8, "unsubscribe_rate": 0.2, "campaign_count": 87,  "created": "2023-09-01"},
    {"id": "aud_003", "name": "VIP Customers",          "member_count": 4210,  "open_rate": 45.6, "click_rate": 12.3, "unsubscribe_rate": 0.1, "campaign_count": 56, "created": "2024-01-20"},
    {"id": "aud_004", "name": "Leads & Prospects",      "member_count": 31400, "open_rate": 22.7, "click_rate": 3.1, "unsubscribe_rate": 0.5, "campaign_count": 64,  "created": "2024-03-10"},
]

MAILCHIMP_MOCK_OVERVIEW = {
    "kpis": [
        {"label": "Total Subscribers",  "value": "78,780",  "change": "+3.2%", "trend": "up"},
        {"label": "Avg Open Rate",      "value": "31.2%",   "change": "+1.8%", "trend": "up"},
        {"label": "Avg Click Rate",     "value": "5.6%",    "change": "+0.4%", "trend": "up"},
        {"label": "Campaigns Sent (30d)","value": "18",     "change": "+5",    "trend": "up"},
        {"label": "Revenue Attributed", "value": "$34,560", "change": "+12.4%","trend": "up"},
        {"label": "Unsubscribe Rate",   "value": "0.28%",   "change": "-0.05%","trend": "down"},
    ],
    "monthly_trend": [
        {"month": "Sep 2025", "sent": 14, "opens": 9840,  "clicks": 1420, "revenue": 18200},
        {"month": "Oct 2025", "sent": 16, "opens": 11200, "clicks": 1680, "revenue": 22400},
        {"month": "Nov 2025", "sent": 19, "opens": 13500, "clicks": 2100, "revenue": 28900},
        {"month": "Dec 2025", "sent": 22, "opens": 15800, "clicks": 2540, "revenue": 36100},
        {"month": "Jan 2026", "sent": 18, "opens": 12400, "clicks": 1960, "revenue": 34560},
    ]
}

MAILCHIMP_MOCK_CAMPAIGNS = [
    {"id": "cmp_001", "type": "regular",   "subject": "🎉 New Year Sale — 30% Off Everything",       "status": "sent",      "audience": "Main Newsletter",  "recipients": 24200, "opens": 7984, "clicks": 1210, "revenue": 8420.00, "send_time": "2026-01-02 09:00"},
    {"id": "cmp_002", "type": "regular",   "subject": "Product Update: AI Dashboard v3.0",            "status": "sent",      "audience": "Product Updates",  "recipients": 18100, "opens": 6534, "clicks": 1450, "revenue": 0,       "send_time": "2026-01-05 14:00"},
    {"id": "cmp_003", "type": "regular",   "subject": "VIP Early Access — Spring Collection",         "status": "sent",      "audience": "VIP Customers",    "recipients": 4180,  "opens": 2340, "clicks": 680,  "revenue": 12300.00,"send_time": "2026-01-08 10:00"},
    {"id": "cmp_004", "type": "plaintext", "subject": "Quick Note: System Maintenance Jan 15",        "status": "sent",      "audience": "Main Newsletter",  "recipients": 24500, "opens": 5880, "clicks": 245,  "revenue": 0,       "send_time": "2026-01-12 08:00"},
    {"id": "cmp_005", "type": "regular",   "subject": "📊 Your Weekly Analytics Digest",              "status": "sent",      "audience": "Product Updates",  "recipients": 18200, "opens": 6370, "clicks": 1820, "revenue": 2100.00, "send_time": "2026-01-14 07:00"},
    {"id": "cmp_006", "type": "regular",   "subject": "Exclusive Webinar: Growth Hacking 2026",       "status": "sent",      "audience": "Leads & Prospects","recipients": 31000, "opens": 8060, "clicks": 2480, "revenue": 0,       "send_time": "2026-01-18 11:00"},
    {"id": "cmp_007", "type": "regular",   "subject": "Case Study: How Acme 3x'd Revenue",           "status": "sent",      "audience": "Leads & Prospects","recipients": 30800, "opens": 7392, "clicks": 1848, "revenue": 0,       "send_time": "2026-01-22 13:00"},
    {"id": "cmp_008", "type": "regular",   "subject": "February Feature Highlights",                  "status": "sent",      "audience": "Product Updates",  "recipients": 18300, "opens": 6588, "clicks": 1464, "revenue": 3200.00, "send_time": "2026-01-28 09:00"},
    {"id": "cmp_009", "type": "regular",   "subject": "Valentine's Special — Treat Your Team",        "status": "sent",      "audience": "Main Newsletter",  "recipients": 24600, "opens": 8364, "clicks": 1722, "revenue": 5840.00, "send_time": "2026-02-01 10:00"},
    {"id": "cmp_010", "type": "regular",   "subject": "🚀 March Kickoff — New Pricing Plans",         "status": "draft",     "audience": "Main Newsletter",  "recipients": 0,     "opens": 0,    "clicks": 0,    "revenue": 0,       "send_time": None},
    {"id": "cmp_011", "type": "regular",   "subject": "Spring Webinar Series Invite",                 "status": "scheduled", "audience": "Leads & Prospects","recipients": 31400, "opens": 0,    "clicks": 0,    "revenue": 0,       "send_time": "2026-02-15 11:00"},
]

MAILCHIMP_MOCK_AUTOMATIONS = [
    {"id": "auto_001", "name": "Welcome Series",                "trigger": "subscriber_added",  "status": "active",  "emails_in_series": 5, "emails_sent": 12450, "open_rate": 48.2, "click_rate": 12.8, "audience": "Main Newsletter"},
    {"id": "auto_002", "name": "Abandoned Cart Recovery",       "trigger": "cart_abandoned",    "status": "active",  "emails_in_series": 3, "emails_sent": 8320,  "open_rate": 38.6, "click_rate": 8.4,  "audience": "Main Newsletter"},
    {"id": "auto_003", "name": "Post-Purchase Follow-Up",       "trigger": "purchase_made",     "status": "active",  "emails_in_series": 4, "emails_sent": 6180,  "open_rate": 42.1, "click_rate": 9.2,  "audience": "VIP Customers"},
    {"id": "auto_004", "name": "Re-Engagement Campaign",        "trigger": "inactive_90_days",  "status": "active",  "emails_in_series": 3, "emails_sent": 4560,  "open_rate": 18.4, "click_rate": 3.6,  "audience": "Main Newsletter"},
    {"id": "auto_005", "name": "Birthday Rewards",              "trigger": "birthday",          "status": "active",  "emails_in_series": 1, "emails_sent": 2890,  "open_rate": 52.3, "click_rate": 15.1, "audience": "VIP Customers"},
    {"id": "auto_006", "name": "Lead Nurture Sequence",         "trigger": "tag_added",         "status": "paused",  "emails_in_series": 7, "emails_sent": 9640,  "open_rate": 26.8, "click_rate": 5.2,  "audience": "Leads & Prospects"},
    {"id": "auto_007", "name": "Product Onboarding",            "trigger": "subscriber_added",  "status": "active",  "emails_in_series": 6, "emails_sent": 7200,  "open_rate": 44.5, "click_rate": 11.6, "audience": "Product Updates"},
    {"id": "auto_008", "name": "Win-Back (Churned)",            "trigger": "inactive_180_days", "status": "paused",  "emails_in_series": 4, "emails_sent": 3100,  "open_rate": 14.2, "click_rate": 2.8,  "audience": "Main Newsletter"},
]

MAILCHIMP_MOCK_SEGMENTS = [
    {"id": "seg_001", "name": "Highly Engaged",        "audience": "Main Newsletter",   "member_count": 6420,  "conditions": "open_rate > 50%"},
    {"id": "seg_002", "name": "Purchased Last 30d",     "audience": "VIP Customers",     "member_count": 1280,  "conditions": "purchase_date > 30d_ago"},
    {"id": "seg_003", "name": "Clicked Any Link (7d)",  "audience": "Main Newsletter",   "member_count": 3540,  "conditions": "clicked_any last 7 days"},
    {"id": "seg_004", "name": "New Subscribers (30d)",   "audience": "Main Newsletter",   "member_count": 1890,  "conditions": "signup_date > 30d_ago"},
    {"id": "seg_005", "name": "Enterprise Leads",       "audience": "Leads & Prospects", "member_count": 4200,  "conditions": "tag = enterprise"},
    {"id": "seg_006", "name": "Inactive 60d+",          "audience": "Main Newsletter",   "member_count": 5230,  "conditions": "last_open > 60d_ago"},
    {"id": "seg_007", "name": "High-Value Buyers",      "audience": "VIP Customers",     "member_count": 820,   "conditions": "lifetime_revenue > $500"},
    {"id": "seg_008", "name": "Webinar Attendees",      "audience": "Leads & Prospects", "member_count": 2640,  "conditions": "tag = webinar_attended"},
]


@app.route("/api/connectors/mailchimp/audiences")
def mailchimp_audiences():
    return jsonify(MAILCHIMP_MOCK_AUDIENCES)


@app.route("/api/connectors/mailchimp/overview")
def mailchimp_overview():
    audience = request.args.get("audience")
    if audience and audience != "all":
        match = [a for a in MAILCHIMP_MOCK_AUDIENCES if a["name"] == audience]
        if not match:
            return jsonify(MAILCHIMP_MOCK_OVERVIEW)
        a = match[0]
        return jsonify({
            "kpis": [
                {"label": "Subscribers",      "value": f'{a["member_count"]:,}', "change": "+2.1%", "trend": "up"},
                {"label": "Open Rate",        "value": f'{a["open_rate"]}%',     "change": "+0.8%", "trend": "up"},
                {"label": "Click Rate",       "value": f'{a["click_rate"]}%',    "change": "+0.3%", "trend": "up"},
                {"label": "Campaigns",        "value": str(a["campaign_count"]), "change": "+4",    "trend": "up"},
                {"label": "Unsubscribe Rate", "value": f'{a["unsubscribe_rate"]}%', "change": "-0.02%","trend": "down"},
                {"label": "List Age",         "value": a["created"],             "change": "",      "trend": "neutral"},
            ],
            "monthly_trend": MAILCHIMP_MOCK_OVERVIEW["monthly_trend"]
        })
    return jsonify(MAILCHIMP_MOCK_OVERVIEW)


@app.route("/api/connectors/mailchimp/campaigns")
def mailchimp_campaigns():
    status   = request.args.get("status")
    audience = request.args.get("audience")
    ctype    = request.args.get("type")
    rows = MAILCHIMP_MOCK_CAMPAIGNS[:]
    if status and status != "all":
        rows = [r for r in rows if r["status"] == status]
    if audience and audience != "all":
        rows = [r for r in rows if r["audience"] == audience]
    if ctype and ctype != "all":
        rows = [r for r in rows if r["type"] == ctype]
    return jsonify(rows)


@app.route("/api/connectors/mailchimp/automations")
def mailchimp_automations():
    status   = request.args.get("status")
    audience = request.args.get("audience")
    rows = MAILCHIMP_MOCK_AUTOMATIONS[:]
    if status and status != "all":
        rows = [r for r in rows if r["status"] == status]
    if audience and audience != "all":
        rows = [r for r in rows if r["audience"] == audience]
    return jsonify(rows)


@app.route("/api/connectors/mailchimp/segments")
def mailchimp_segments():
    audience = request.args.get("audience")
    rows = MAILCHIMP_MOCK_SEGMENTS[:]
    if audience and audience != "all":
        rows = [r for r in rows if r["audience"] == audience]
    return jsonify(rows)


@app.route("/api/connectors/mailchimp/reports")
def mailchimp_reports():
    """Unified report: campaigns + automations + segments – 31+ rows"""
    rows = []
    for c in MAILCHIMP_MOCK_CAMPAIGNS:
        open_rate  = round(c["opens"]  / c["recipients"] * 100, 1) if c["recipients"] else 0
        click_rate = round(c["clicks"] / c["recipients"] * 100, 1) if c["recipients"] else 0
        rows.append({"type": "Campaign", "name": c["subject"][:50], "status": c["status"],
                      "audience": c["audience"], "recipients": c["recipients"],
                      "open_rate": open_rate, "click_rate": click_rate,
                      "revenue": c["revenue"]})
    for a in MAILCHIMP_MOCK_AUTOMATIONS:
        rows.append({"type": "Automation", "name": a["name"], "status": a["status"],
                      "audience": a["audience"], "recipients": a["emails_sent"],
                      "open_rate": a["open_rate"], "click_rate": a["click_rate"],
                      "revenue": 0})
    for s in MAILCHIMP_MOCK_SEGMENTS:
        rows.append({"type": "Segment", "name": s["name"], "status": "active",
                      "audience": s["audience"], "recipients": s["member_count"],
                      "open_rate": 0, "click_rate": 0, "revenue": 0})
    return jsonify(rows)


@app.route("/api/connectors/mailchimp/test-call", methods=["POST"])
def mailchimp_test_call():
    """Simulate Mailchimp API calls"""
    import time
    data = request.get_json() or {}
    endpoint = data.get("endpoint", "campaigns")
    start = time.time()

    if endpoint == "campaigns":
        response_body = {
            "campaigns": [
                {"id": "cmp_001", "type": "regular", "status": "sent",
                 "recipients": {"list_id": "aud_001", "recipient_count": 24200},
                 "settings": {"subject_line": "🎉 New Year Sale", "from_name": "Camarad"},
                 "report_summary": {"opens": 7984, "unique_opens": 6820, "clicks": 1210, "subscriber_clicks": 980}},
            ],
            "total_items": 11
        }
    elif endpoint == "lists":
        response_body = {
            "lists": [
                {"id": "aud_001", "name": "Main Newsletter", "stats": {"member_count": 24850, "open_rate": 28.4, "click_rate": 4.2}},
                {"id": "aud_002", "name": "Product Updates", "stats": {"member_count": 18320, "open_rate": 32.1, "click_rate": 5.8}},
            ],
            "total_items": 4
        }
    elif endpoint == "automations":
        response_body = {
            "automations": [
                {"id": "auto_001", "status": "active", "settings": {"title": "Welcome Series"},
                 "recipients": {"list_id": "aud_001"}, "emails_sent": 12450},
            ],
            "total_items": 8
        }
    else:
        response_body = {"total_items": 0}

    elapsed = round((time.time() - start) * 1000, 1)
    return jsonify({
        "endpoint": endpoint,
        "method": data.get("method", "GET"),
        "request": {"base_url": "https://us1.api.mailchimp.com", "endpoint": f"/3.0/{endpoint}"},
        "response": {"status_code": 200,
                      "headers": {"content-type": "application/json;charset=utf-8", "x-mc-api-version": "3.0"},
                      "body": response_body},
        "latency_ms": elapsed,
        "quota": {"concurrent_limit": 10, "daily_limit": 100000}
    })


# ═══════════════════════════════════════════════════════════════════════════════
# PAYPAL  –  Payments, Payouts & Disputes
# ═══════════════════════════════════════════════════════════════════════════════

PAYPAL_MOCK_ACCOUNTS = [
    {"id": "acc_pp_001", "email": "business@techstart.com",  "name": "TechStart Agency",    "currency": "USD", "balance": 18420.50, "status": "active", "type": "BUSINESS"},
    {"id": "acc_pp_002", "email": "payments@brandboost.com", "name": "BrandBoost Payments",  "currency": "EUR", "balance": 12860.30, "status": "active", "type": "BUSINESS"},
    {"id": "acc_pp_003", "email": "shop@ecompromo.com",      "name": "EcomPromo Shop",       "currency": "USD", "balance": 7340.90,  "status": "active", "type": "BUSINESS"},
]

PAYPAL_MOCK_OVERVIEW = {
    "kpis": [
        {"label": "Total Payments",     "value": "$42,680",  "change": "+8.2%",  "trend": "up"},
        {"label": "Net Revenue",         "value": "$40,120",  "change": "+7.8%",  "trend": "up"},
        {"label": "Total Fees",          "value": "$2,560",   "change": "+3.1%",  "trend": "up"},
        {"label": "Payouts Sent",        "value": "$28,400",  "change": "+12.5%", "trend": "up"},
        {"label": "Open Disputes",       "value": "4",        "change": "-2",     "trend": "down"},
        {"label": "Dispute Rate",        "value": "0.18%",    "change": "-0.04%", "trend": "down"},
        {"label": "Avg Transaction",     "value": "$186.50",  "change": "+$12",   "trend": "up"},
        {"label": "Refund Rate",         "value": "2.1%",     "change": "-0.3%",  "trend": "down"},
    ],
    "monthly_trend": [
        {"month": "Sep 2025", "payments": 186, "revenue": 31200, "fees": 1870, "payouts": 22400, "disputes": 5},
        {"month": "Oct 2025", "payments": 214, "revenue": 35600, "fees": 2140, "payouts": 25800, "disputes": 3},
        {"month": "Nov 2025", "payments": 248, "revenue": 38900, "fees": 2340, "payouts": 27100, "disputes": 6},
        {"month": "Dec 2025", "payments": 276, "revenue": 44200, "fees": 2650, "payouts": 31500, "disputes": 4},
        {"month": "Jan 2026", "payments": 229, "revenue": 40120, "fees": 2560, "payouts": 28400, "disputes": 4},
    ]
}

PAYPAL_MOCK_TRANSACTIONS = [
    {"id": "PAY-5NJ23849KF012345A", "type": "sale",     "status": "completed",  "amount": 450.00,  "fee": 13.35, "net": 436.65,  "currency": "USD", "payer": "john@acme.com",        "description": "Annual Plan Subscription",       "date": "2026-02-07 14:23"},
    {"id": "PAY-8KL45678MN901234B", "type": "sale",     "status": "completed",  "amount": 1200.00, "fee": 35.10, "net": 1164.90, "currency": "USD", "payer": "sarah@globalmedia.com", "description": "Enterprise Dashboard License",   "date": "2026-02-07 11:05"},
    {"id": "PAY-2AB78901CD345678E", "type": "sale",     "status": "completed",  "amount": 89.99,   "fee": 2.90,  "net": 87.09,   "currency": "USD", "payer": "mike@startup.io",      "description": "Starter Plan Monthly",           "date": "2026-02-06 16:42"},
    {"id": "PAY-9FG12345HI678901J", "type": "sale",     "status": "pending",    "amount": 320.00,  "fee": 9.58,  "net": 310.42,  "currency": "USD", "payer": "lisa@retail.co",       "description": "Pro Plan Quarterly",             "date": "2026-02-06 09:18"},
    {"id": "PAY-3KL56789MN012345O", "type": "refund",   "status": "completed",  "amount": -175.00, "fee": 0,     "net": -175.00, "currency": "USD", "payer": "alex@designlab.com",   "description": "Refund: Duplicate charge",       "date": "2026-02-05 22:30"},
    {"id": "PAY-7PQ90123RS456789T", "type": "sale",     "status": "completed",  "amount": 650.00,  "fee": 19.15, "net": 630.85,  "currency": "USD", "payer": "emma@techcorp.com",    "description": "Team Plan Annual",               "date": "2026-02-05 13:10"},
    {"id": "PAY-4UV34567WX890123Y", "type": "sale",     "status": "denied",     "amount": 220.00,  "fee": 0,     "net": 0,       "currency": "USD", "payer": "tom@invalid.test",     "description": "Starter Plan Annual",            "date": "2026-02-04 18:55"},
    {"id": "PAY-6AB78901CD234567F", "type": "payout",   "status": "completed",  "amount": -5000.00,"fee": 0.25,  "net": -5000.25,"currency": "USD", "payer": "→ Bank ****4521",      "description": "Weekly payout to bank",          "date": "2026-02-04 06:00"},
    {"id": "PAY-1EF23456GH789012K", "type": "sale",     "status": "completed",  "amount": 540.00,  "fee": 15.91, "net": 524.09,  "currency": "USD", "payer": "nina@agency.co",       "description": "Growth Plan Semi-Annual",        "date": "2026-02-03 11:22"},
    {"id": "PAY-8IJ56789KL012345P", "type": "refund",   "status": "completed",  "amount": -89.99,  "fee": 0,     "net": -89.99,  "currency": "USD", "payer": "mark@freelance.dev",   "description": "Refund: Service cancellation",   "date": "2026-02-03 08:44"},
    {"id": "PAY-5MN89012OP345678U", "type": "sale",     "status": "completed",  "amount": 780.00,  "fee": 22.92, "net": 757.08,  "currency": "USD", "payer": "julia@enterprise.io",  "description": "Enterprise Add-on Pack",         "date": "2026-02-02 15:33"},
    {"id": "PAY-2QR12345ST678901Z", "type": "sale",     "status": "completed",  "amount": 150.00,  "fee": 4.65,  "net": 145.35,  "currency": "USD", "payer": "dave@smallbiz.com",    "description": "Starter Plan Monthly",           "date": "2026-02-01 10:10"},
]

PAYPAL_MOCK_PAYOUTS = [
    {"id": "POUT-2026-001", "amount": 5000.00, "fee": 0.25, "currency": "USD", "status": "completed",  "bank": "Chase ****4521",          "batch_id": "BATCH-001", "items": 1,  "date": "2026-02-04 06:00"},
    {"id": "POUT-2026-002", "amount": 8200.00, "fee": 0.25, "currency": "USD", "status": "completed",  "bank": "Chase ****4521",          "batch_id": "BATCH-002", "items": 1,  "date": "2026-01-28 06:00"},
    {"id": "POUT-2026-003", "amount": 3400.00, "fee": 0.25, "currency": "EUR", "status": "completed",  "bank": "ING ****8834",            "batch_id": "BATCH-003", "items": 1,  "date": "2026-01-21 06:00"},
    {"id": "POUT-2026-004", "amount": 6100.00, "fee": 0.25, "currency": "USD", "status": "completed",  "bank": "Chase ****4521",          "batch_id": "BATCH-004", "items": 1,  "date": "2026-01-14 06:00"},
    {"id": "POUT-2026-005", "amount": 2500.00, "fee": 0.25, "currency": "USD", "status": "pending",    "bank": "Chase ****4521",          "batch_id": "BATCH-005", "items": 1,  "date": "2026-02-07 06:00"},
    {"id": "POUT-2026-006", "amount": 4800.00, "fee": 0.25, "currency": "USD", "status": "completed",  "bank": "Chase ****4521",          "batch_id": "BATCH-006", "items": 1,  "date": "2026-01-07 06:00"},
    {"id": "POUT-2026-007", "amount": 1900.00, "fee": 0.25, "currency": "EUR", "status": "completed",  "bank": "ING ****8834",            "batch_id": "BATCH-007", "items": 1,  "date": "2025-12-31 06:00"},
]

PAYPAL_MOCK_DISPUTES = [
    {"id": "DISP-2026-001", "reason": "ITEM_NOT_RECEIVED",           "status": "open",              "amount": 320.00, "currency": "USD", "buyer": "tom@buyer.com",        "transaction": "PAY-9FG12345HI678901J", "created": "2026-02-06", "respond_by": "2026-02-20"},
    {"id": "DISP-2026-002", "reason": "UNAUTHORISED",                "status": "under_review",      "amount": 450.00, "currency": "USD", "buyer": "unknown@fraud.test",   "transaction": "PAY-FRAUD-001",         "created": "2026-02-04", "respond_by": "2026-02-18"},
    {"id": "DISP-2026-003", "reason": "NOT_AS_DESCRIBED",            "status": "open",              "amount": 89.99,  "currency": "USD", "buyer": "mark@freelance.dev",   "transaction": "PAY-2AB78901CD345678E", "created": "2026-02-03", "respond_by": "2026-02-17"},
    {"id": "DISP-2026-004", "reason": "DUPLICATE_TRANSACTION",       "status": "resolved_buyer",    "amount": 175.00, "currency": "USD", "buyer": "alex@designlab.com",   "transaction": "PAY-3KL56789MN012345O", "created": "2026-01-28", "respond_by": "2026-02-11"},
    {"id": "DISP-2026-005", "reason": "ITEM_NOT_RECEIVED",           "status": "resolved_seller",   "amount": 220.00, "currency": "USD", "buyer": "claire@shop.co",       "transaction": "PAY-RES-001",           "created": "2026-01-22", "respond_by": "2026-02-05"},
    {"id": "DISP-2026-006", "reason": "NOT_AS_DESCRIBED",            "status": "resolved_buyer",    "amount": 150.00, "currency": "EUR", "buyer": "hans@destore.de",      "transaction": "PAY-RES-002",           "created": "2026-01-15", "respond_by": "2026-01-29"},
]


@app.route("/api/connectors/paypal/accounts")
def paypal_accounts():
    return jsonify(PAYPAL_MOCK_ACCOUNTS)


@app.route("/api/connectors/paypal/overview")
def paypal_overview():
    account = request.args.get("account")
    if account and account != "all":
        match = [a for a in PAYPAL_MOCK_ACCOUNTS if a["email"] == account]
        if not match:
            return jsonify(PAYPAL_MOCK_OVERVIEW)
        a = match[0]
        return jsonify({
            "kpis": [
                {"label": "Balance",         "value": f'${a["balance"]:,.2f}', "change": "+4.2%", "trend": "up"},
                {"label": "Currency",        "value": a["currency"],          "change": "",      "trend": "neutral"},
                {"label": "Account Type",    "value": a["type"],              "change": "",      "trend": "neutral"},
                {"label": "Status",          "value": a["status"].title(),    "change": "",      "trend": "neutral"},
                {"label": "Open Disputes",   "value": "2",                    "change": "-1",    "trend": "down"},
                {"label": "Avg Transaction", "value": "$192.40",              "change": "+$8",   "trend": "up"},
            ],
            "monthly_trend": PAYPAL_MOCK_OVERVIEW["monthly_trend"]
        })
    return jsonify(PAYPAL_MOCK_OVERVIEW)


@app.route("/api/connectors/paypal/transactions")
def paypal_transactions():
    status = request.args.get("status")
    ttype  = request.args.get("type")
    rows = PAYPAL_MOCK_TRANSACTIONS[:]
    if status and status != "all":
        rows = [r for r in rows if r["status"] == status]
    if ttype and ttype != "all":
        rows = [r for r in rows if r["type"] == ttype]
    return jsonify(rows)


@app.route("/api/connectors/paypal/payouts")
def paypal_payouts():
    status = request.args.get("status")
    rows = PAYPAL_MOCK_PAYOUTS[:]
    if status and status != "all":
        rows = [r for r in rows if r["status"] == status]
    return jsonify(rows)


@app.route("/api/connectors/paypal/disputes")
def paypal_disputes():
    status = request.args.get("status")
    reason = request.args.get("reason")
    rows = PAYPAL_MOCK_DISPUTES[:]
    if status and status != "all":
        rows = [r for r in rows if r["status"] == status]
    if reason and reason != "all":
        rows = [r for r in rows if r["reason"] == reason]
    return jsonify(rows)


@app.route("/api/connectors/paypal/reports")
def paypal_reports():
    """Unified report: transactions + payouts + disputes – 25+ rows"""
    rows = []
    for t in PAYPAL_MOCK_TRANSACTIONS:
        rows.append({"type": "Transaction", "name": t["description"][:45], "status": t["status"],
                      "amount": t["amount"], "fee": t["fee"], "net": t["net"],
                      "currency": t["currency"], "counterparty": t["payer"], "date": t["date"]})
    for p in PAYPAL_MOCK_PAYOUTS:
        rows.append({"type": "Payout", "name": f'Payout to {p["bank"]}', "status": p["status"],
                      "amount": -p["amount"], "fee": p["fee"], "net": -(p["amount"] + p["fee"]),
                      "currency": p["currency"], "counterparty": p["bank"], "date": p["date"]})
    for d in PAYPAL_MOCK_DISPUTES:
        rows.append({"type": "Dispute", "name": d["reason"].replace("_", " ").title(), "status": d["status"],
                      "amount": d["amount"], "fee": 0, "net": 0,
                      "currency": d["currency"], "counterparty": d["buyer"], "date": d["created"]})
    return jsonify(rows)


@app.route("/api/connectors/paypal/test-call", methods=["POST"])
def paypal_test_call():
    """Simulate PayPal REST API calls"""
    import time
    data = request.get_json() or {}
    endpoint = data.get("endpoint", "payments")
    start = time.time()

    if endpoint == "payments":
        response_body = {
            "transactions": [
                {"transaction_info": {"transaction_id": "PAY-5NJ23849KF012345A", "transaction_amount": {"value": "450.00", "currency_code": "USD"},
                 "transaction_status": "S", "transaction_subject": "Annual Plan Subscription", "transaction_updated_date": "2026-02-07T14:23:00+0000"}},
                {"transaction_info": {"transaction_id": "PAY-8KL45678MN901234B", "transaction_amount": {"value": "1200.00", "currency_code": "USD"},
                 "transaction_status": "S", "transaction_subject": "Enterprise Dashboard License", "transaction_updated_date": "2026-02-07T11:05:00+0000"}},
            ],
            "total_items": 12, "total_pages": 1
        }
    elif endpoint == "payouts":
        response_body = {
            "batch_header": {"payout_batch_id": "BATCH-005", "batch_status": "PENDING",
                             "amount": {"value": "2500.00", "currency": "USD"},
                             "time_created": "2026-02-07T06:00:00Z", "time_completed": None,
                             "sender_batch_header": {"sender_batch_id": "weekly-2026-02-07"}},
            "items": [{"payout_item_id": "ITEM-001", "transaction_status": "PENDING",
                       "payout_item_fee": {"value": "0.25", "currency": "USD"},
                       "payout_batch_id": "BATCH-005", "amount": {"value": "2500.00", "currency": "USD"}}]
        }
    elif endpoint == "disputes":
        response_body = {
            "items": [
                {"dispute_id": "DISP-2026-001", "reason": "ITEM_NOT_RECEIVED", "status": "OPEN",
                 "dispute_amount": {"value": "320.00", "currency_code": "USD"},
                 "create_time": "2026-02-06T00:00:00Z",
                 "disputed_transactions": [{"seller_transaction_id": "PAY-9FG12345HI678901J"}]},
            ],
            "total_items": 6, "total_pages": 1
        }
    else:
        response_body = {"total_items": 0}

    elapsed = round((time.time() - start) * 1000, 1)
    return jsonify({
        "endpoint": endpoint,
        "method": data.get("method", "GET"),
        "request": {"base_url": "https://api.paypal.com", "endpoint": f"/v1/reporting/{endpoint}"},
        "response": {"status_code": 200,
                      "headers": {"content-type": "application/json", "paypal-debug-id": "abc123xyz456"},
                      "body": response_body},
        "latency_ms": elapsed,
        "quota": {"rate_limit": 50, "remaining": 48}
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  NOTION – Mock Data & Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

NOTION_MOCK_WORKSPACES = [
    {"id": "ws-abc123-def456", "name": "TechStart Team", "icon": "🚀", "plan": "Team", "members": 12,
     "pages": 1234, "databases": 45, "created": "2024-06-15"},
    {"id": "ws-ghi789-jkl012", "name": "Personal Journal", "icon": "📓", "plan": "Personal Pro", "members": 1,
     "pages": 312, "databases": 8, "created": "2024-01-10"},
    {"id": "ws-mno345-pqr678", "name": "Project Wiki", "icon": "📚", "plan": "Team", "members": 7,
     "pages": 567, "databases": 22, "created": "2025-03-20"},
]

NOTION_MOCK_OVERVIEW = {
    "all": {
        "total_pages": 2113, "total_databases": 75, "total_blocks": 189234,
        "collaborators": 20, "active_integrations": 6, "api_calls_today": 1845,
        "monthly_trend": [
            {"month": "2025-10", "pages_created": 87, "blocks_added": 4230},
            {"month": "2025-11", "pages_created": 102, "blocks_added": 5120},
            {"month": "2025-12", "pages_created": 95, "blocks_added": 4890},
            {"month": "2026-01", "pages_created": 118, "blocks_added": 6340},
            {"month": "2026-02", "pages_created": 34, "blocks_added": 1820},
        ],
    },
    "ws-abc123-def456": {
        "total_pages": 1234, "total_databases": 45, "total_blocks": 89234,
        "collaborators": 12, "active_integrations": 4, "api_calls_today": 1120,
    },
    "ws-ghi789-jkl012": {
        "total_pages": 312, "total_databases": 8, "total_blocks": 23400,
        "collaborators": 1, "active_integrations": 1, "api_calls_today": 245,
    },
    "ws-mno345-pqr678": {
        "total_pages": 567, "total_databases": 22, "total_blocks": 76600,
        "collaborators": 7, "active_integrations": 3, "api_calls_today": 480,
    },
}

NOTION_MOCK_PAGES = [
    {"id": "pg-001", "title": "Weekly SOPs", "workspace": "TechStart Team", "status": "shared",
     "last_edited": "2026-02-08", "author": "Alice Chen", "icon": "📋", "parent": "Operations"},
    {"id": "pg-002", "title": "Q1 Goals & OKRs", "workspace": "TechStart Team", "status": "shared",
     "last_edited": "2026-02-07", "author": "Bob Martinez", "icon": "🎯", "parent": "Strategy"},
    {"id": "pg-003", "title": "Team Meeting Notes – Feb 7", "workspace": "TechStart Team", "status": "shared",
     "last_edited": "2026-02-07", "author": "You", "icon": "📝", "parent": "Meetings"},
    {"id": "pg-004", "title": "Product Roadmap 2026", "workspace": "TechStart Team", "status": "shared",
     "last_edited": "2026-02-06", "author": "Carol Davis", "icon": "🗺️", "parent": "Product"},
    {"id": "pg-005", "title": "Engineering Wiki – Auth Module", "workspace": "Project Wiki", "status": "shared",
     "last_edited": "2026-02-06", "author": "Dan Kim", "icon": "⚙️", "parent": "Engineering"},
    {"id": "pg-006", "title": "Customer Feedback Tracker", "workspace": "TechStart Team", "status": "shared",
     "last_edited": "2026-02-05", "author": "Eve Johnson", "icon": "💬", "parent": "Support"},
    {"id": "pg-007", "title": "Morning Routine Checklist", "workspace": "Personal Journal", "status": "private",
     "last_edited": "2026-02-08", "author": "You", "icon": "☀️", "parent": "Daily"},
    {"id": "pg-008", "title": "Budget Planning FY2026", "workspace": "TechStart Team", "status": "shared",
     "last_edited": "2026-02-04", "author": "Frank Lee", "icon": "💰", "parent": "Finance"},
    {"id": "pg-009", "title": "Hiring Pipeline – Q1", "workspace": "TechStart Team", "status": "shared",
     "last_edited": "2026-02-03", "author": "Alice Chen", "icon": "👥", "parent": "HR"},
    {"id": "pg-010", "title": "Gratitude Journal – Week 6", "workspace": "Personal Journal", "status": "private",
     "last_edited": "2026-02-07", "author": "You", "icon": "🙏", "parent": "Journals"},
    {"id": "pg-011", "title": "API Documentation v3", "workspace": "Project Wiki", "status": "shared",
     "last_edited": "2026-02-05", "author": "Dan Kim", "icon": "📖", "parent": "Docs"},
    {"id": "pg-012", "title": "Sprint Retrospective – Jan", "workspace": "TechStart Team", "status": "shared",
     "last_edited": "2026-02-01", "author": "Carol Davis", "icon": "🔄", "parent": "Engineering"},
    {"id": "pg-013", "title": "Content Calendar – Feb", "workspace": "TechStart Team", "status": "shared",
     "last_edited": "2026-02-02", "author": "Grace Park", "icon": "📅", "parent": "Marketing"},
    {"id": "pg-014", "title": "Reading List 2026", "workspace": "Personal Journal", "status": "private",
     "last_edited": "2026-02-06", "author": "You", "icon": "📚", "parent": "Learning"},
    {"id": "pg-015", "title": "Incident Postmortem – Jan 28", "workspace": "Project Wiki", "status": "shared",
     "last_edited": "2026-01-30", "author": "Dan Kim", "icon": "🔥", "parent": "Engineering"},
]

NOTION_MOCK_DATABASES = [
    {"id": "db-001", "title": "Tasks", "workspace": "TechStart Team", "type": "kanban",
     "items": 156, "last_edited": "2026-02-08", "properties": ["Status", "Assignee", "Priority", "Due Date"]},
    {"id": "db-002", "title": "Projects", "workspace": "TechStart Team", "type": "table",
     "items": 23, "last_edited": "2026-02-07", "properties": ["Status", "Lead", "Timeline", "Budget"]},
    {"id": "db-003", "title": "Contacts CRM", "workspace": "TechStart Team", "type": "table",
     "items": 342, "last_edited": "2026-02-06", "properties": ["Company", "Role", "Email", "Last Contact"]},
    {"id": "db-004", "title": "Bug Tracker", "workspace": "Project Wiki", "type": "board",
     "items": 89, "last_edited": "2026-02-08", "properties": ["Severity", "Assignee", "Status", "Module"]},
    {"id": "db-005", "title": "Content Pipeline", "workspace": "TechStart Team", "type": "calendar",
     "items": 67, "last_edited": "2026-02-05", "properties": ["Type", "Author", "Publish Date", "Channel"]},
    {"id": "db-006", "title": "Meeting Notes", "workspace": "TechStart Team", "type": "list",
     "items": 128, "last_edited": "2026-02-07", "properties": ["Date", "Attendees", "Action Items", "Tags"]},
    {"id": "db-007", "title": "Habit Tracker", "workspace": "Personal Journal", "type": "table",
     "items": 45, "last_edited": "2026-02-08", "properties": ["Habit", "Streak", "Category", "Daily Check"]},
    {"id": "db-008", "title": "Knowledge Base", "workspace": "Project Wiki", "type": "gallery",
     "items": 234, "last_edited": "2026-02-04", "properties": ["Topic", "Category", "Author", "Last Updated"]},
    {"id": "db-009", "title": "Sprint Board", "workspace": "TechStart Team", "type": "kanban",
     "items": 34, "last_edited": "2026-02-08", "properties": ["Story Points", "Assignee", "Sprint", "Epic"]},
    {"id": "db-010", "title": "Expenses", "workspace": "TechStart Team", "type": "table",
     "items": 198, "last_edited": "2026-02-03", "properties": ["Amount", "Category", "Vendor", "Date"]},
]

NOTION_MOCK_BLOCKS = [
    {"id": "blk-001", "type": "heading_1", "page": "Q1 Goals & OKRs", "content": "Increase MRR by 30% to $150K",
     "created": "2026-01-15", "last_edited": "2026-02-07"},
    {"id": "blk-002", "type": "to_do", "page": "Weekly SOPs", "content": "Review KPI dashboard every Monday",
     "created": "2026-01-20", "last_edited": "2026-02-08", "checked": True},
    {"id": "blk-003", "type": "paragraph", "page": "Team Meeting Notes – Feb 7",
     "content": "Discussed Q1 roadmap priorities. Alice to finalize budget by Friday.",
     "created": "2026-02-07", "last_edited": "2026-02-07"},
    {"id": "blk-004", "type": "callout", "page": "Product Roadmap 2026",
     "content": "⚠️ Critical: Auth module needs refactor before v3 launch",
     "created": "2026-01-28", "last_edited": "2026-02-06"},
    {"id": "blk-005", "type": "heading_2", "page": "Engineering Wiki – Auth Module",
     "content": "OAuth 2.0 Implementation Guide",
     "created": "2025-11-10", "last_edited": "2026-02-06"},
    {"id": "blk-006", "type": "to_do", "page": "Weekly SOPs", "content": "Send weekly report to stakeholders",
     "created": "2026-01-20", "last_edited": "2026-02-08", "checked": False},
    {"id": "blk-007", "type": "bulleted_list_item", "page": "Customer Feedback Tracker",
     "content": "User requests: dark mode, API export, mobile app",
     "created": "2026-02-01", "last_edited": "2026-02-05"},
    {"id": "blk-008", "type": "code", "page": "API Documentation v3",
     "content": "GET /v1/pages/{page_id} → Returns page object with properties",
     "created": "2026-01-22", "last_edited": "2026-02-05"},
    {"id": "blk-009", "type": "quote", "page": "Gratitude Journal – Week 6",
     "content": "The only way to do great work is to love what you do. – Steve Jobs",
     "created": "2026-02-07", "last_edited": "2026-02-07"},
    {"id": "blk-010", "type": "heading_3", "page": "Budget Planning FY2026",
     "content": "Q1 Allocation: Engineering 45%, Marketing 25%, Operations 30%",
     "created": "2026-01-10", "last_edited": "2026-02-04"},
    {"id": "blk-011", "type": "toggle", "page": "Sprint Retrospective – Jan",
     "content": "What went well: Shipped 3 major features, 0 critical bugs",
     "created": "2026-02-01", "last_edited": "2026-02-01"},
    {"id": "blk-012", "type": "table_row", "page": "Hiring Pipeline – Q1",
     "content": "Senior Backend Engineer | Interview Stage | Starts Mar 1",
     "created": "2026-01-25", "last_edited": "2026-02-03"},
]

NOTION_MOCK_COLLABORATORS = [
    {"id": "usr-001", "name": "Alice Chen", "email": "alice@techstart.io", "role": "Admin",
     "avatar": "AC", "last_active": "2026-02-08", "pages_edited": 234},
    {"id": "usr-002", "name": "Bob Martinez", "email": "bob@techstart.io", "role": "Admin",
     "avatar": "BM", "last_active": "2026-02-07", "pages_edited": 189},
    {"id": "usr-003", "name": "Carol Davis", "email": "carol@techstart.io", "role": "Member",
     "avatar": "CD", "last_active": "2026-02-08", "pages_edited": 156},
    {"id": "usr-004", "name": "Dan Kim", "email": "dan@techstart.io", "role": "Member",
     "avatar": "DK", "last_active": "2026-02-08", "pages_edited": 312},
    {"id": "usr-005", "name": "Eve Johnson", "email": "eve@techstart.io", "role": "Member",
     "avatar": "EJ", "last_active": "2026-02-06", "pages_edited": 98},
    {"id": "usr-006", "name": "Frank Lee", "email": "frank@techstart.io", "role": "Member",
     "avatar": "FL", "last_active": "2026-02-05", "pages_edited": 67},
    {"id": "usr-007", "name": "Grace Park", "email": "grace@techstart.io", "role": "Member",
     "avatar": "GP", "last_active": "2026-02-07", "pages_edited": 145},
    {"id": "usr-008", "name": "Henry Nguyen", "email": "henry@techstart.io", "role": "Guest",
     "avatar": "HN", "last_active": "2026-02-04", "pages_edited": 23},
    {"id": "usr-009", "name": "Ivy Watson", "email": "ivy@techstart.io", "role": "Guest",
     "avatar": "IW", "last_active": "2026-02-03", "pages_edited": 15},
    {"id": "usr-010", "name": "Jack Torres", "email": "jack@techstart.io", "role": "Member",
     "avatar": "JT", "last_active": "2026-02-08", "pages_edited": 201},
]


@app.route("/api/connectors/notion/workspaces")
def notion_workspaces():
    return jsonify(NOTION_MOCK_WORKSPACES)


@app.route("/api/connectors/notion/overview")
def notion_overview():
    ws = request.args.get("workspace", "all")
    data = NOTION_MOCK_OVERVIEW.get(ws)
    if data:
        return jsonify(data)
    return jsonify({"total_pages": 0, "total_databases": 0, "total_blocks": 0,
                    "collaborators": 0, "active_integrations": 0, "api_calls_today": 0})


@app.route("/api/connectors/notion/pages")
def notion_pages():
    status = request.args.get("status", "").lower()
    workspace = request.args.get("workspace", "")
    results = NOTION_MOCK_PAGES[:]
    if status:
        results = [p for p in results if p["status"] == status]
    if workspace:
        results = [p for p in results if p["workspace"] == workspace]
    return jsonify(results)


@app.route("/api/connectors/notion/databases")
def notion_databases():
    db_type = request.args.get("type", "").lower()
    workspace = request.args.get("workspace", "")
    results = NOTION_MOCK_DATABASES[:]
    if db_type:
        results = [d for d in results if d["type"] == db_type]
    if workspace:
        results = [d for d in results if d["workspace"] == workspace]
    return jsonify(results)


@app.route("/api/connectors/notion/blocks")
def notion_blocks():
    block_type = request.args.get("type", "")
    query = request.args.get("q", "").lower()
    results = NOTION_MOCK_BLOCKS[:]
    if block_type:
        results = [b for b in results if b["type"] == block_type]
    if query:
        results = [b for b in results if query in b["content"].lower() or query in b["page"].lower()]
    return jsonify(results)


@app.route("/api/connectors/notion/collaborators")
def notion_collaborators():
    role = request.args.get("role", "")
    results = NOTION_MOCK_COLLABORATORS[:]
    if role:
        results = [c for c in results if c["role"] == role]
    return jsonify(results)


@app.route("/api/connectors/notion/reports")
def notion_reports():
    """Unified report: pages + databases + blocks combined."""
    rows = []
    for p in NOTION_MOCK_PAGES:
        rows.append({"type": "Page", "title": p["title"], "workspace": p["workspace"],
                      "detail": f"Status: {p['status']} | Parent: {p['parent']}",
                      "date": p["last_edited"], "author": p["author"]})
    for d in NOTION_MOCK_DATABASES:
        rows.append({"type": "Database", "title": d["title"], "workspace": d["workspace"],
                      "detail": f"Type: {d['type']} | Items: {d['items']}",
                      "date": d["last_edited"], "author": "—"})
    for b in NOTION_MOCK_BLOCKS[:8]:
        rows.append({"type": "Block", "title": b["page"], "workspace": "—",
                      "detail": f"[{b['type']}] {b['content'][:60]}",
                      "date": b["last_edited"], "author": "—"})
    rows.sort(key=lambda r: r["date"], reverse=True)
    return jsonify(rows)


@app.route("/api/connectors/notion/test-call", methods=["POST"])
def notion_test_call():
    """Simulate Notion API calls."""
    import time
    data = request.get_json() or {}
    endpoint = data.get("endpoint", "pages")
    start = time.time()

    if endpoint == "pages":
        response_body = {
            "object": "list",
            "results": [
                {"object": "page", "id": "pg-001", "created_time": "2026-02-08T10:00:00.000Z",
                 "last_edited_time": "2026-02-08T14:30:00.000Z",
                 "properties": {"title": {"title": [{"plain_text": "Weekly SOPs"}]},
                                "Status": {"select": {"name": "Active"}}},
                 "parent": {"type": "database_id", "database_id": "db-001"},
                 "url": "https://www.notion.so/Weekly-SOPs-pg001"},
                {"object": "page", "id": "pg-002", "created_time": "2026-01-15T08:00:00.000Z",
                 "last_edited_time": "2026-02-07T11:20:00.000Z",
                 "properties": {"title": {"title": [{"plain_text": "Q1 Goals & OKRs"}]},
                                "Status": {"select": {"name": "In Progress"}}},
                 "parent": {"type": "workspace", "workspace": True},
                 "url": "https://www.notion.so/Q1-Goals-pg002"},
            ],
            "has_more": True, "next_cursor": "abc123"
        }
    elif endpoint == "databases":
        response_body = {
            "object": "list",
            "results": [
                {"object": "database", "id": "db-001", "title": [{"plain_text": "Tasks"}],
                 "created_time": "2024-06-20T10:00:00.000Z",
                 "last_edited_time": "2026-02-08T16:00:00.000Z",
                 "properties": {"Status": {"select": {"options": [
                     {"name": "To Do", "color": "red"}, {"name": "In Progress", "color": "yellow"},
                     {"name": "Done", "color": "green"}]}},
                     "Assignee": {"people": {}}, "Priority": {"select": {}}}},
            ],
            "has_more": False
        }
    elif endpoint == "blocks":
        response_body = {
            "object": "list",
            "results": [
                {"object": "block", "id": "blk-001", "type": "heading_1",
                 "heading_1": {"rich_text": [{"plain_text": "Increase MRR by 30% to $150K"}]},
                 "created_time": "2026-01-15T10:00:00.000Z"},
                {"object": "block", "id": "blk-002", "type": "to_do",
                 "to_do": {"rich_text": [{"plain_text": "Review KPI dashboard every Monday"}], "checked": True},
                 "created_time": "2026-01-20T08:00:00.000Z"},
            ],
            "has_more": False
        }
    else:
        response_body = {"object": "list", "results": []}

    elapsed = round((time.time() - start) * 1000, 1)
    return jsonify({
        "endpoint": endpoint,
        "method": data.get("method", "GET"),
        "request": {"base_url": "https://api.notion.com", "endpoint": f"/v1/{endpoint}",
                     "headers": {"Notion-Version": "2022-06-28"}},
        "response": {"status_code": 200,
                      "headers": {"content-type": "application/json"},
                      "body": response_body},
        "latency_ms": elapsed,
        "quota": {"rate_limit": 3, "remaining": 2, "unit": "requests/second"}
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  GITHUB – Mock Data & Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

GITHUB_MOCK_ACCOUNTS = [
    {"id": "usr-gh-001", "login": "alexcto", "type": "User", "name": "Alex CTO",
     "avatar": "AC", "plan": "Pro", "repos": 28, "followers": 312, "following": 87},
    {"id": "org-gh-001", "login": "TechStartHQ", "type": "Organization", "name": "TechStart",
     "avatar": "TS", "plan": "Team", "repos": 45, "followers": 1890, "following": 0},
    {"id": "org-gh-002", "login": "DevOpsLab", "type": "Organization", "name": "DevOps Lab",
     "avatar": "DL", "plan": "Enterprise", "repos": 112, "followers": 4230, "following": 0},
]

GITHUB_MOCK_OVERVIEW = {
    "all": {
        "total_repos": 185, "total_stars": 8734, "total_forks": 2156, "open_issues": 67,
        "open_prs": 23, "total_commits_30d": 1842, "contributors": 34, "actions_runs_30d": 567,
        "weekly_commits": [
            {"week": "2026-W02", "commits": 312},
            {"week": "2026-W03", "commits": 287},
            {"week": "2026-W04", "commits": 345},
            {"week": "2026-W05", "commits": 401},
            {"week": "2026-W06", "commits": 497},
        ],
    },
    "usr-gh-001": {
        "total_repos": 28, "total_stars": 456, "total_forks": 89, "open_issues": 12,
        "open_prs": 5, "total_commits_30d": 234, "contributors": 1, "actions_runs_30d": 45,
    },
    "org-gh-001": {
        "total_repos": 45, "total_stars": 3278, "total_forks": 867, "open_issues": 23,
        "open_prs": 8, "total_commits_30d": 678, "contributors": 12, "actions_runs_30d": 189,
    },
    "org-gh-002": {
        "total_repos": 112, "total_stars": 5000, "total_forks": 1200, "open_issues": 32,
        "open_prs": 10, "total_commits_30d": 930, "contributors": 21, "actions_runs_30d": 333,
    },
}

GITHUB_MOCK_REPOS = [
    {"id": "repo-001", "name": "camarad-ai", "full_name": "TechStartHQ/camarad-ai", "owner": "TechStartHQ",
     "language": "Python", "stars": 892, "forks": 134, "open_issues": 8, "visibility": "public",
     "default_branch": "main", "last_push": "2026-02-08", "description": "AI-powered agency management platform",
     "topics": ["ai", "flask", "saas", "agents"]},
    {"id": "repo-002", "name": "frontend-dashboard", "full_name": "TechStartHQ/frontend-dashboard", "owner": "TechStartHQ",
     "language": "TypeScript", "stars": 567, "forks": 89, "open_issues": 5, "visibility": "public",
     "default_branch": "main", "last_push": "2026-02-07", "description": "React dashboard with real-time analytics",
     "topics": ["react", "typescript", "dashboard"]},
    {"id": "repo-003", "name": "api-gateway", "full_name": "TechStartHQ/api-gateway", "owner": "TechStartHQ",
     "language": "Go", "stars": 345, "forks": 67, "open_issues": 3, "visibility": "public",
     "default_branch": "main", "last_push": "2026-02-06", "description": "High-performance API gateway with rate limiting",
     "topics": ["go", "api", "microservices"]},
    {"id": "repo-004", "name": "ml-pipeline", "full_name": "TechStartHQ/ml-pipeline", "owner": "TechStartHQ",
     "language": "Python", "stars": 234, "forks": 45, "open_issues": 2, "visibility": "public",
     "default_branch": "main", "last_push": "2026-02-05", "description": "ML training and inference pipeline",
     "topics": ["machine-learning", "python", "pytorch"]},
    {"id": "repo-005", "name": "infra-terraform", "full_name": "DevOpsLab/infra-terraform", "owner": "DevOpsLab",
     "language": "HCL", "stars": 189, "forks": 34, "open_issues": 1, "visibility": "private",
     "default_branch": "main", "last_push": "2026-02-08", "description": "Infrastructure as Code for GCP + AWS",
     "topics": ["terraform", "devops", "iac"]},
    {"id": "repo-006", "name": "k8s-manifests", "full_name": "DevOpsLab/k8s-manifests", "owner": "DevOpsLab",
     "language": "YAML", "stars": 78, "forks": 12, "open_issues": 0, "visibility": "private",
     "default_branch": "main", "last_push": "2026-02-07", "description": "Kubernetes deployment manifests",
     "topics": ["kubernetes", "devops", "helm"]},
    {"id": "repo-007", "name": "auth-service", "full_name": "TechStartHQ/auth-service", "owner": "TechStartHQ",
     "language": "Rust", "stars": 156, "forks": 23, "open_issues": 4, "visibility": "public",
     "default_branch": "main", "last_push": "2026-02-04", "description": "OAuth2 + OIDC authentication microservice",
     "topics": ["rust", "auth", "security"]},
    {"id": "repo-008", "name": "mobile-app", "full_name": "TechStartHQ/mobile-app", "owner": "TechStartHQ",
     "language": "Dart", "stars": 123, "forks": 19, "open_issues": 6, "visibility": "public",
     "default_branch": "develop", "last_push": "2026-02-03", "description": "Cross-platform mobile app (Flutter)",
     "topics": ["flutter", "dart", "mobile"]},
    {"id": "repo-009", "name": "data-warehouse", "full_name": "DevOpsLab/data-warehouse", "owner": "DevOpsLab",
     "language": "SQL", "stars": 67, "forks": 8, "open_issues": 2, "visibility": "private",
     "default_branch": "main", "last_push": "2026-02-02", "description": "BigQuery + dbt data warehouse models",
     "topics": ["sql", "dbt", "bigquery", "analytics"]},
    {"id": "repo-010", "name": "design-system", "full_name": "TechStartHQ/design-system", "owner": "TechStartHQ",
     "language": "TypeScript", "stars": 98, "forks": 15, "open_issues": 3, "visibility": "public",
     "default_branch": "main", "last_push": "2026-02-01", "description": "Shared UI component library (Storybook)",
     "topics": ["storybook", "react", "design-system"]},
    {"id": "repo-011", "name": "dotfiles", "full_name": "alexcto/dotfiles", "owner": "alexcto",
     "language": "Shell", "stars": 45, "forks": 7, "open_issues": 0, "visibility": "public",
     "default_branch": "main", "last_push": "2026-01-28", "description": "Personal dev environment configs",
     "topics": ["dotfiles", "zsh", "neovim"]},
    {"id": "repo-012", "name": "blog", "full_name": "alexcto/blog", "owner": "alexcto",
     "language": "MDX", "stars": 23, "forks": 3, "open_issues": 1, "visibility": "public",
     "default_branch": "main", "last_push": "2026-01-25", "description": "Personal tech blog (Astro + MDX)",
     "topics": ["blog", "astro", "mdx"]},
]

GITHUB_MOCK_COMMITS = [
    {"sha": "a1b2c3d", "repo": "camarad-ai", "author": "Alice Chen", "message": "feat: add PayPal connector with 8 tabs",
     "date": "2026-02-08T14:30:00Z", "additions": 487, "deletions": 12, "files_changed": 3},
    {"sha": "d4e5f6g", "repo": "camarad-ai", "author": "Bob Martinez", "message": "fix: resolve race condition in chat WebSocket",
     "date": "2026-02-08T11:15:00Z", "additions": 23, "deletions": 8, "files_changed": 2},
    {"sha": "h7i8j9k", "repo": "frontend-dashboard", "author": "Carol Davis", "message": "feat: implement real-time KPI dashboard widgets",
     "date": "2026-02-07T16:45:00Z", "additions": 312, "deletions": 45, "files_changed": 8},
    {"sha": "l0m1n2o", "repo": "api-gateway", "author": "Dan Kim", "message": "perf: optimize rate limiter with sliding window",
     "date": "2026-02-07T09:20:00Z", "additions": 89, "deletions": 34, "files_changed": 4},
    {"sha": "p3q4r5s", "repo": "camarad-ai", "author": "Alice Chen", "message": "test: add 18 Notion connector tests",
     "date": "2026-02-06T20:00:00Z", "additions": 156, "deletions": 0, "files_changed": 1},
    {"sha": "t6u7v8w", "repo": "infra-terraform", "author": "Eve Johnson", "message": "infra: add GCP Cloud Run service definitions",
     "date": "2026-02-06T13:30:00Z", "additions": 234, "deletions": 67, "files_changed": 6},
    {"sha": "x9y0z1a", "repo": "auth-service", "author": "Frank Lee", "message": "security: upgrade JWT validation to RS256",
     "date": "2026-02-05T15:00:00Z", "additions": 78, "deletions": 45, "files_changed": 5},
    {"sha": "b2c3d4e", "repo": "ml-pipeline", "author": "Grace Park", "message": "feat: add ONNX export for production inference",
     "date": "2026-02-05T10:45:00Z", "additions": 145, "deletions": 23, "files_changed": 3},
    {"sha": "f5g6h7i", "repo": "frontend-dashboard", "author": "Carol Davis", "message": "fix: dark mode toggle persistence in localStorage",
     "date": "2026-02-04T17:30:00Z", "additions": 12, "deletions": 5, "files_changed": 2},
    {"sha": "j8k9l0m", "repo": "k8s-manifests", "author": "Henry Nguyen", "message": "ops: scale API pods to 5 replicas for peak traffic",
     "date": "2026-02-04T08:00:00Z", "additions": 8, "deletions": 3, "files_changed": 1},
    {"sha": "n1o2p3q", "repo": "camarad-ai", "author": "Bob Martinez", "message": "refactor: extract connector engine into separate module",
     "date": "2026-02-03T14:20:00Z", "additions": 567, "deletions": 432, "files_changed": 12},
    {"sha": "r4s5t6u", "repo": "design-system", "author": "Ivy Watson", "message": "feat: add DataTable and KPICard components",
     "date": "2026-02-02T11:00:00Z", "additions": 234, "deletions": 0, "files_changed": 4},
    {"sha": "v7w8x9y", "repo": "mobile-app", "author": "Jack Torres", "message": "feat: implement push notification handler",
     "date": "2026-02-01T16:15:00Z", "additions": 189, "deletions": 34, "files_changed": 7},
    {"sha": "z0a1b2c", "repo": "data-warehouse", "author": "Dan Kim", "message": "data: add MRR cohort analysis dbt model",
     "date": "2026-01-31T09:30:00Z", "additions": 98, "deletions": 12, "files_changed": 3},
    {"sha": "d3e4f5g", "repo": "dotfiles", "author": "alexcto", "message": "config: update neovim LSP settings for Rust",
     "date": "2026-01-28T20:00:00Z", "additions": 34, "deletions": 12, "files_changed": 2},
]

GITHUB_MOCK_ISSUES = [
    {"number": 234, "repo": "camarad-ai", "title": "Add dark mode support for connector panels", "state": "open",
     "kind": "issue", "labels": ["enhancement", "frontend"], "assignee": "Carol Davis",
     "created": "2026-02-07", "updated": "2026-02-08", "comments": 5},
    {"number": 231, "repo": "camarad-ai", "title": "WebSocket disconnects after 30min idle", "state": "open",
     "kind": "issue", "labels": ["bug", "backend"], "assignee": "Bob Martinez",
     "created": "2026-02-06", "updated": "2026-02-07", "comments": 3},
    {"number": 89, "repo": "frontend-dashboard", "title": "KPI cards not updating on filter change", "state": "open",
     "kind": "issue", "labels": ["bug", "high-priority"], "assignee": "Carol Davis",
     "created": "2026-02-05", "updated": "2026-02-06", "comments": 7},
    {"number": 45, "repo": "api-gateway", "title": "Rate limiter bypass with concurrent requests", "state": "closed",
     "kind": "issue", "labels": ["security", "critical"], "assignee": "Dan Kim",
     "created": "2026-02-02", "updated": "2026-02-04", "comments": 12},
    {"number": 12, "repo": "auth-service", "title": "JWT refresh token rotation not working", "state": "open",
     "kind": "issue", "labels": ["bug", "security"], "assignee": "Frank Lee",
     "created": "2026-02-01", "updated": "2026-02-05", "comments": 4},
    {"number": 233, "repo": "camarad-ai", "title": "feat: Notion connector integration", "state": "closed",
     "kind": "pr", "labels": ["feature", "connectors"], "assignee": "Alice Chen",
     "created": "2026-02-06", "updated": "2026-02-07", "comments": 8, "merged": True},
    {"number": 232, "repo": "camarad-ai", "title": "fix: PayPal dispute filter regression", "state": "closed",
     "kind": "pr", "labels": ["bugfix", "backend"], "assignee": "Bob Martinez",
     "created": "2026-02-05", "updated": "2026-02-06", "comments": 3, "merged": True},
    {"number": 88, "repo": "frontend-dashboard", "title": "feat: add chart zoom and pan controls", "state": "open",
     "kind": "pr", "labels": ["feature", "frontend"], "assignee": "Carol Davis",
     "created": "2026-02-07", "updated": "2026-02-08", "comments": 6, "merged": False},
    {"number": 44, "repo": "api-gateway", "title": "perf: implement connection pooling", "state": "open",
     "kind": "pr", "labels": ["performance", "backend"], "assignee": "Dan Kim",
     "created": "2026-02-06", "updated": "2026-02-07", "comments": 4, "merged": False},
    {"number": 11, "repo": "auth-service", "title": "feat: add PKCE flow for mobile clients", "state": "open",
     "kind": "pr", "labels": ["feature", "security"], "assignee": "Frank Lee",
     "created": "2026-02-04", "updated": "2026-02-08", "comments": 9, "merged": False},
    {"number": 230, "repo": "camarad-ai", "title": "chore: bump Flask to 2.3.4", "state": "closed",
     "kind": "pr", "labels": ["dependencies"], "assignee": "Alice Chen",
     "created": "2026-02-03", "updated": "2026-02-03", "comments": 1, "merged": True},
    {"number": 7, "repo": "infra-terraform", "title": "Add CloudSQL failover configuration", "state": "open",
     "kind": "issue", "labels": ["infrastructure", "reliability"], "assignee": "Eve Johnson",
     "created": "2026-02-01", "updated": "2026-02-06", "comments": 2},
]

GITHUB_MOCK_ACTIONS = [
    {"id": "run-001", "repo": "camarad-ai", "workflow": "CI/CD Pipeline", "event": "push",
     "branch": "main", "status": "completed", "conclusion": "success",
     "started": "2026-02-08T14:35:00Z", "duration_sec": 252, "commit_sha": "a1b2c3d"},
    {"id": "run-002", "repo": "camarad-ai", "workflow": "Test Suite", "event": "pull_request",
     "branch": "feat/notion-connector", "status": "completed", "conclusion": "success",
     "started": "2026-02-08T11:20:00Z", "duration_sec": 187, "commit_sha": "d4e5f6g"},
    {"id": "run-003", "repo": "frontend-dashboard", "workflow": "Build & Deploy Preview", "event": "pull_request",
     "branch": "feat/chart-zoom", "status": "completed", "conclusion": "success",
     "started": "2026-02-07T16:50:00Z", "duration_sec": 145, "commit_sha": "h7i8j9k"},
    {"id": "run-004", "repo": "api-gateway", "workflow": "Security Scan", "event": "schedule",
     "branch": "main", "status": "completed", "conclusion": "failure",
     "started": "2026-02-07T03:00:00Z", "duration_sec": 89, "commit_sha": "l0m1n2o"},
    {"id": "run-005", "repo": "infra-terraform", "workflow": "Terraform Plan", "event": "push",
     "branch": "main", "status": "completed", "conclusion": "success",
     "started": "2026-02-06T13:35:00Z", "duration_sec": 312, "commit_sha": "t6u7v8w"},
    {"id": "run-006", "repo": "auth-service", "workflow": "Rust CI", "event": "push",
     "branch": "main", "status": "completed", "conclusion": "success",
     "started": "2026-02-05T15:05:00Z", "duration_sec": 423, "commit_sha": "x9y0z1a"},
    {"id": "run-007", "repo": "ml-pipeline", "workflow": "Model Training", "event": "workflow_dispatch",
     "branch": "main", "status": "in_progress", "conclusion": None,
     "started": "2026-02-08T09:00:00Z", "duration_sec": None, "commit_sha": "b2c3d4e"},
    {"id": "run-008", "repo": "camarad-ai", "workflow": "Deploy Production", "event": "release",
     "branch": "main", "status": "completed", "conclusion": "success",
     "started": "2026-02-07T20:00:00Z", "duration_sec": 178, "commit_sha": "p3q4r5s"},
    {"id": "run-009", "repo": "design-system", "workflow": "Storybook Deploy", "event": "push",
     "branch": "main", "status": "completed", "conclusion": "success",
     "started": "2026-02-02T11:10:00Z", "duration_sec": 95, "commit_sha": "r4s5t6u"},
    {"id": "run-010", "repo": "mobile-app", "workflow": "Flutter Build", "event": "push",
     "branch": "develop", "status": "completed", "conclusion": "cancelled",
     "started": "2026-02-01T16:20:00Z", "duration_sec": 45, "commit_sha": "v7w8x9y"},
]


@app.route("/api/connectors/github/accounts")
def github_accounts():
    return jsonify(GITHUB_MOCK_ACCOUNTS)


@app.route("/api/connectors/github/overview")
def github_overview():
    acct = request.args.get("account", "all")
    data = GITHUB_MOCK_OVERVIEW.get(acct)
    if data:
        return jsonify(data)
    return jsonify({"total_repos": 0, "total_stars": 0, "total_forks": 0,
                    "open_issues": 0, "open_prs": 0, "total_commits_30d": 0,
                    "contributors": 0, "actions_runs_30d": 0})


@app.route("/api/connectors/github/repos")
def github_repos():
    visibility = request.args.get("visibility", "").lower()
    language = request.args.get("language", "")
    owner = request.args.get("owner", "")
    results = GITHUB_MOCK_REPOS[:]
    if visibility:
        results = [r for r in results if r["visibility"] == visibility]
    if language:
        results = [r for r in results if r["language"] == language]
    if owner:
        results = [r for r in results if r["owner"] == owner]
    return jsonify(results)


@app.route("/api/connectors/github/commits")
def github_commits():
    repo = request.args.get("repo", "")
    author = request.args.get("author", "")
    results = GITHUB_MOCK_COMMITS[:]
    if repo:
        results = [c for c in results if c["repo"] == repo]
    if author:
        results = [c for c in results if c["author"] == author]
    return jsonify(results)


@app.route("/api/connectors/github/issues")
def github_issues():
    state = request.args.get("state", "").lower()
    kind = request.args.get("kind", "").lower()
    repo = request.args.get("repo", "")
    results = GITHUB_MOCK_ISSUES[:]
    if state:
        results = [i for i in results if i["state"] == state]
    if kind:
        results = [i for i in results if i["kind"] == kind]
    if repo:
        results = [i for i in results if i["repo"] == repo]
    return jsonify(results)


@app.route("/api/connectors/github/actions")
def github_actions():
    conclusion = request.args.get("conclusion", "").lower()
    repo = request.args.get("repo", "")
    results = GITHUB_MOCK_ACTIONS[:]
    if conclusion:
        results = [a for a in results if (a["conclusion"] or "").lower() == conclusion]
    if repo:
        results = [a for a in results if a["repo"] == repo]
    return jsonify(results)


@app.route("/api/connectors/github/reports")
def github_reports():
    """Unified report: repos + commits + issues + actions combined."""
    rows = []
    for r in GITHUB_MOCK_REPOS:
        rows.append({"type": "Repository", "title": r["full_name"], "detail": f"{r['language']} | ⭐{r['stars']} | 🍴{r['forks']}",
                      "status": r["visibility"], "date": r["last_push"]})
    for c in GITHUB_MOCK_COMMITS:
        rows.append({"type": "Commit", "title": f"{c['repo']}/{c['sha']}", "detail": c["message"],
                      "status": "merged", "date": c["date"][:10]})
    for i in GITHUB_MOCK_ISSUES:
        label = "PR" if i["kind"] == "pr" else "Issue"
        rows.append({"type": label, "title": f"{i['repo']}#{i['number']}", "detail": i["title"],
                      "status": i["state"], "date": i["updated"]})
    for a in GITHUB_MOCK_ACTIONS:
        rows.append({"type": "Action", "title": f"{a['repo']}/{a['workflow']}", "detail": f"Branch: {a['branch']} | Event: {a['event']}",
                      "status": a["conclusion"] or "running", "date": a["started"][:10]})
    rows.sort(key=lambda r: r["date"], reverse=True)
    return jsonify(rows)


@app.route("/api/connectors/github/test-call", methods=["POST"])
def github_test_call():
    """Simulate GitHub REST API calls."""
    import time
    data = request.get_json() or {}
    endpoint = data.get("endpoint", "repos")
    start = time.time()

    if endpoint == "repos":
        response_body = [
            {"id": 123456789, "name": "camarad-ai", "full_name": "TechStartHQ/camarad-ai",
             "private": False, "owner": {"login": "TechStartHQ", "type": "Organization"},
             "description": "AI-powered agency management platform",
             "stargazers_count": 892, "forks_count": 134, "open_issues_count": 8,
             "language": "Python", "default_branch": "main",
             "pushed_at": "2026-02-08T14:30:00Z", "topics": ["ai", "flask", "saas"]},
        ]
    elif endpoint == "commits":
        response_body = [
            {"sha": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
             "commit": {"message": "feat: add PayPal connector with 8 tabs",
                        "author": {"name": "Alice Chen", "email": "alice@techstart.io", "date": "2026-02-08T14:30:00Z"}},
             "stats": {"additions": 487, "deletions": 12, "total": 499},
             "files": [{"filename": "app.py", "status": "modified", "additions": 180, "deletions": 0}]},
            {"sha": "d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3",
             "commit": {"message": "fix: resolve race condition in chat WebSocket",
                        "author": {"name": "Bob Martinez", "email": "bob@techstart.io", "date": "2026-02-08T11:15:00Z"}},
             "stats": {"additions": 23, "deletions": 8, "total": 31},
             "files": [{"filename": "websocket.py", "status": "modified", "additions": 23, "deletions": 8}]},
        ]
    elif endpoint == "issues":
        response_body = [
            {"number": 234, "title": "Add dark mode support for connector panels",
             "state": "open", "user": {"login": "carol-davis"},
             "labels": [{"name": "enhancement", "color": "a2eeef"}, {"name": "frontend", "color": "d4c5f9"}],
             "assignee": {"login": "carol-davis"}, "comments": 5,
             "created_at": "2026-02-07T10:00:00Z", "updated_at": "2026-02-08T09:30:00Z"},
        ]
    else:
        response_body = []

    elapsed = round((time.time() - start) * 1000, 1)
    return jsonify({
        "endpoint": endpoint,
        "method": data.get("method", "GET"),
        "request": {"base_url": "https://api.github.com", "endpoint": f"/{endpoint}",
                     "headers": {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}},
        "response": {"status_code": 200,
                      "headers": {"content-type": "application/json", "x-ratelimit-remaining": "4998"},
                      "body": response_body},
        "latency_ms": elapsed,
        "quota": {"rate_limit": 5000, "remaining": 4998, "reset": "2026-02-08T15:00:00Z"}
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  TODOIST – Mock Data & Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

TODOIST_MOCK_PROJECTS = [
    {"id": "2331476591", "name": "Daily Tasks",   "color": "berry_red",  "order": 1, "is_favorite": True,  "view_style": "list",  "task_count": 34, "comment_count": 5},
    {"id": "2331476602", "name": "Marketing Q1",  "color": "blue",       "order": 2, "is_favorite": True,  "view_style": "board", "task_count": 28, "comment_count": 12},
    {"id": "2331476613", "name": "Personal Goals", "color": "green",     "order": 3, "is_favorite": False, "view_style": "list",  "task_count": 19, "comment_count": 3},
]

TODOIST_MOCK_OVERVIEW = {
    "total_projects": 3,
    "kpis": {
        "tasks_today": 12, "overdue": 3, "completed_this_week": 45,
        "productivity_streak": 8, "open_tasks": 81, "completed_total": 312,
        "avg_completion_rate": 87.4, "recurring_active": 6
    },
    "daily_completed": [
        {"day": "Mon", "count": 8},  {"day": "Tue", "count": 11},
        {"day": "Wed", "count": 7},  {"day": "Thu", "count": 9},
        {"day": "Fri", "count": 5},  {"day": "Sat", "count": 3},
        {"day": "Sun", "count": 2},
    ],
    "priority_breakdown": {"p1": 8, "p2": 22, "p3": 31, "p4": 20},
    "project_stats": [
        {"project": "Daily Tasks",    "open": 34, "completed": 142, "overdue": 2},
        {"project": "Marketing Q1",   "open": 28, "completed": 96,  "overdue": 1},
        {"project": "Personal Goals", "open": 19, "completed": 74,  "overdue": 0},
    ]
}

TODOIST_MOCK_TASKS = [
    {"id": "6543210001", "content": "Review PPC report",             "description": "Check Q1 PPC metrics and update dashboard",   "priority": 1, "project": "Daily Tasks",    "labels": ["urgent", "work"],       "due": "2026-02-08", "is_completed": False, "assignee": "Alex Popescu",   "created_at": "2026-02-01T09:00:00Z"},
    {"id": "6543210002", "content": "Daily workout",                 "description": "30 min cardio + strength training",            "priority": 2, "project": "Personal Goals", "labels": ["health", "habit"],      "due": "2026-02-08", "is_completed": True,  "assignee": "Alex Popescu",   "created_at": "2026-01-01T07:00:00Z"},
    {"id": "6543210003", "content": "Call client — MedTech deal",    "description": "Discuss contract terms for Q2",                "priority": 1, "project": "Marketing Q1",   "labels": ["urgent", "sales"],      "due": "2026-02-08", "is_completed": False, "assignee": "Maria Ionescu",  "created_at": "2026-02-05T10:30:00Z"},
    {"id": "6543210004", "content": "Update landing page copy",      "description": "A/B test new headlines",                       "priority": 2, "project": "Marketing Q1",   "labels": ["content", "marketing"], "due": "2026-02-09", "is_completed": False, "assignee": "Andrei Radu",    "created_at": "2026-02-03T14:00:00Z"},
    {"id": "6543210005", "content": "Prepare weekly review slides",  "description": "Summarize KPIs for Friday standup",            "priority": 2, "project": "Daily Tasks",    "labels": ["work", "recurring"],    "due": "2026-02-07", "is_completed": False, "assignee": "Alex Popescu",   "created_at": "2026-02-01T08:00:00Z"},
    {"id": "6543210006", "content": "Read 30 min — Atomic Habits",   "description": "Chapter 7-8",                                  "priority": 3, "project": "Personal Goals", "labels": ["reading", "habit"],     "due": "2026-02-08", "is_completed": False, "assignee": "Alex Popescu",   "created_at": "2026-01-15T20:00:00Z"},
    {"id": "6543210007", "content": "Deploy v2.3 to staging",        "description": "Run full test suite before merge",             "priority": 1, "project": "Daily Tasks",    "labels": ["urgent", "dev"],        "due": "2026-02-08", "is_completed": False, "assignee": "Andrei Radu",    "created_at": "2026-02-07T16:00:00Z"},
    {"id": "6543210008", "content": "Write blog post — SEO tips",    "description": "Target 1500 words, include infographic",       "priority": 3, "project": "Marketing Q1",   "labels": ["content", "seo"],       "due": "2026-02-10", "is_completed": False, "assignee": "Maria Ionescu",  "created_at": "2026-02-04T11:00:00Z"},
    {"id": "6543210009", "content": "Grocery shopping",              "description": "Veggies, protein, snacks for the week",        "priority": 4, "project": "Personal Goals", "labels": ["personal"],             "due": "2026-02-08", "is_completed": True,  "assignee": "Alex Popescu",   "created_at": "2026-02-07T18:00:00Z"},
    {"id": "6543210010", "content": "Review PR #347 — auth module",  "description": "Security review for OAuth2 flow",             "priority": 1, "project": "Daily Tasks",    "labels": ["urgent", "dev"],        "due": "2026-02-08", "is_completed": False, "assignee": "Alex Popescu",   "created_at": "2026-02-07T09:00:00Z"},
    {"id": "6543210011", "content": "Send invoice to ClientX",       "description": "January retainer + ad spend overage",          "priority": 2, "project": "Marketing Q1",   "labels": ["finance", "work"],      "due": "2026-02-06", "is_completed": False, "assignee": "Maria Ionescu",  "created_at": "2026-02-01T12:00:00Z"},
    {"id": "6543210012", "content": "Meditate 15 min",               "description": "Guided session — Headspace",                   "priority": 3, "project": "Personal Goals", "labels": ["health", "habit"],      "due": "2026-02-08", "is_completed": True,  "assignee": "Alex Popescu",   "created_at": "2026-01-10T06:30:00Z"},
    {"id": "6543210013", "content": "Fix Lighthouse score < 90",     "description": "Optimize images + lazy load below fold",       "priority": 2, "project": "Daily Tasks",    "labels": ["dev", "performance"],   "due": "2026-02-09", "is_completed": False, "assignee": "Andrei Radu",    "created_at": "2026-02-06T15:00:00Z"},
    {"id": "6543210014", "content": "Plan team offsite agenda",      "description": "2-day agenda, book venue, catering",           "priority": 3, "project": "Marketing Q1",   "labels": ["team", "planning"],     "due": "2026-02-14", "is_completed": False, "assignee": "Alex Popescu",   "created_at": "2026-02-02T10:00:00Z"},
    {"id": "6543210015", "content": "Backup photos to cloud",        "description": "Sync January photos to Google Photos",         "priority": 4, "project": "Personal Goals", "labels": ["personal", "tech"],     "due": "2026-02-11", "is_completed": False, "assignee": "Alex Popescu",   "created_at": "2026-02-05T19:00:00Z"},
]

TODOIST_MOCK_LABELS = [
    {"id": "2171234001", "name": "urgent",      "color": "red",        "order": 1, "is_favorite": True,  "task_count": 8},
    {"id": "2171234002", "name": "work",         "color": "blue",       "order": 2, "is_favorite": True,  "task_count": 14},
    {"id": "2171234003", "name": "health",       "color": "green",      "order": 3, "is_favorite": True,  "task_count": 6},
    {"id": "2171234004", "name": "habit",         "color": "violet",     "order": 4, "is_favorite": False, "task_count": 5},
    {"id": "2171234005", "name": "dev",           "color": "orange",     "order": 5, "is_favorite": False, "task_count": 7},
    {"id": "2171234006", "name": "content",       "color": "teal",       "order": 6, "is_favorite": False, "task_count": 4},
    {"id": "2171234007", "name": "personal",      "color": "charcoal",   "order": 7, "is_favorite": False, "task_count": 3},
    {"id": "2171234008", "name": "marketing",     "color": "magenta",    "order": 8, "is_favorite": False, "task_count": 2},
    {"id": "2171234009", "name": "finance",        "color": "yellow",     "order": 9, "is_favorite": False, "task_count": 1},
    {"id": "2171234010", "name": "recurring",      "color": "lime_green", "order": 10,"is_favorite": False, "task_count": 3},
]

TODOIST_MOCK_HABITS = [
    {"id": "8881000001", "content": "Daily workout",       "frequency": "daily",   "streak": 8,  "last_done": "2026-02-08", "next_due": "2026-02-09", "priority": 2, "project": "Personal Goals", "labels": ["health", "habit"]},
    {"id": "8881000002", "content": "Read 30 min",         "frequency": "daily",   "streak": 5,  "last_done": "2026-02-07", "next_due": "2026-02-08", "priority": 3, "project": "Personal Goals", "labels": ["reading", "habit"]},
    {"id": "8881000003", "content": "Meditate 15 min",     "frequency": "daily",   "streak": 12, "last_done": "2026-02-08", "next_due": "2026-02-09", "priority": 3, "project": "Personal Goals", "labels": ["health", "habit"]},
    {"id": "8881000004", "content": "Weekly review",       "frequency": "weekly",  "streak": 4,  "last_done": "2026-02-07", "next_due": "2026-02-14", "priority": 2, "project": "Daily Tasks",    "labels": ["work", "recurring"]},
    {"id": "8881000005", "content": "Inbox zero",          "frequency": "daily",   "streak": 3,  "last_done": "2026-02-08", "next_due": "2026-02-09", "priority": 2, "project": "Daily Tasks",    "labels": ["work", "habit"]},
    {"id": "8881000006", "content": "Journal — gratitude", "frequency": "daily",   "streak": 15, "last_done": "2026-02-08", "next_due": "2026-02-09", "priority": 4, "project": "Personal Goals", "labels": ["personal", "habit"]},
]


@app.route("/api/connectors/todoist/projects", methods=["GET"])
def todoist_projects():
    return jsonify(TODOIST_MOCK_PROJECTS)


@app.route("/api/connectors/todoist/overview", methods=["GET"])
def todoist_overview():
    proj = request.args.get("project", "").strip()
    data = dict(TODOIST_MOCK_OVERVIEW)
    if proj:
        matched = [p for p in data.get("project_stats", []) if p["project"].lower() == proj.lower()]
        if not matched:
            return jsonify({"error": f"Unknown project: {proj}"}), 404
        data["project_stats"] = matched
    return jsonify(data)


@app.route("/api/connectors/todoist/tasks", methods=["GET"])
def todoist_tasks():
    rows = list(TODOIST_MOCK_TASKS)
    status = request.args.get("status", "").strip().lower()
    if status == "open":
        rows = [r for r in rows if not r["is_completed"]]
    elif status == "completed":
        rows = [r for r in rows if r["is_completed"]]
    priority = request.args.get("priority", "").strip()
    if priority:
        try:
            rows = [r for r in rows if r["priority"] == int(priority)]
        except ValueError:
            pass
    project = request.args.get("project", "").strip()
    if project:
        rows = [r for r in rows if r["project"].lower() == project.lower()]
    label = request.args.get("label", "").strip().lower()
    if label:
        rows = [r for r in rows if label in [l.lower() for l in r["labels"]]]
    return jsonify(rows)


@app.route("/api/connectors/todoist/projects-detail", methods=["GET"])
def todoist_projects_detail():
    result = []
    for p in TODOIST_MOCK_PROJECTS:
        tasks = [t for t in TODOIST_MOCK_TASKS if t["project"] == p["name"]]
        p_copy = dict(p)
        p_copy["open_tasks"]      = len([t for t in tasks if not t["is_completed"]])
        p_copy["completed_tasks"] = len([t for t in tasks if t["is_completed"]])
        p_copy["overdue_tasks"]   = len([t for t in tasks if not t["is_completed"] and t["due"] < "2026-02-08"])
        p_copy["labels_used"]     = sorted(set(l for t in tasks for l in t["labels"]))
        result.append(p_copy)
    return jsonify(result)


@app.route("/api/connectors/todoist/labels", methods=["GET"])
def todoist_labels():
    search = request.args.get("search", "").strip().lower()
    rows = list(TODOIST_MOCK_LABELS)
    if search:
        rows = [r for r in rows if search in r["name"].lower()]
    return jsonify(rows)


@app.route("/api/connectors/todoist/habits", methods=["GET"])
def todoist_habits():
    freq = request.args.get("frequency", "").strip().lower()
    rows = list(TODOIST_MOCK_HABITS)
    if freq:
        rows = [r for r in rows if r["frequency"] == freq]
    return jsonify(rows)


@app.route("/api/connectors/todoist/reports", methods=["GET"])
def todoist_reports():
    rows = []
    for t in TODOIST_MOCK_TASKS:
        rows.append({"type": "Task", "id": t["id"], "name": t["content"], "project": t["project"],
                      "priority": f"P{t['priority']}", "status": "Completed" if t["is_completed"] else "Open",
                      "due": t["due"], "labels": ", ".join(t["labels"])})
    for p in TODOIST_MOCK_PROJECTS:
        rows.append({"type": "Project", "id": p["id"], "name": p["name"], "project": p["name"],
                      "priority": "-", "status": f"{p['task_count']} tasks",
                      "due": "-", "labels": p["color"]})
    for lb in TODOIST_MOCK_LABELS:
        rows.append({"type": "Label", "id": lb["id"], "name": lb["name"], "project": "-",
                      "priority": "-", "status": f"{lb['task_count']} tasks",
                      "due": "-", "labels": lb["color"]})
    for h in TODOIST_MOCK_HABITS:
        rows.append({"type": "Habit", "id": h["id"], "name": h["content"], "project": h["project"],
                      "priority": f"P{h['priority']}", "status": f"Streak {h['streak']}d",
                      "due": h["next_due"], "labels": ", ".join(h["labels"])})
    return jsonify(rows)


@app.route("/api/connectors/todoist/test-call", methods=["POST"])
def todoist_test_call():
    import time, random
    body = request.get_json(force=True) or {}
    endpoint = body.get("endpoint", "tasks")
    start = time.time()
    time.sleep(random.uniform(0.05, 0.15))
    elapsed = round((time.time() - start) * 1000, 1)
    if endpoint == "tasks":
        response_body = TODOIST_MOCK_TASKS[:3]
    elif endpoint == "projects":
        response_body = TODOIST_MOCK_PROJECTS
    elif endpoint == "labels":
        response_body = TODOIST_MOCK_LABELS[:5]
    else:
        response_body = TODOIST_MOCK_TASKS[:3]
    return jsonify({
        "ok": True,
        "endpoint": f"https://api.todoist.com/rest/v2/{endpoint}",
        "method": "GET",
        "response": {"status_code": 200,
                      "headers": {"content-type": "application/json", "x-request-id": "a1b2c3d4-5678-90ab-cdef"},
                      "body": response_body},
        "latency_ms": elapsed,
        "quota": {"rate_limit": 450, "remaining": 447, "reset": "2026-02-08T15:15:00Z"}
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  TELEGRAM – Mock Data & Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

TELEGRAM_MOCK_CHATS = [
    {"id": "-1001234567890", "title": "Personal Journal",       "type": "private",  "unread": 0,  "last_message": "Finished evening meditation 🧘",                "last_time": "2026-02-08T21:30:00Z", "pinned": True},
    {"id": "-1009876543210", "title": "Team Marketing",         "type": "group",    "unread": 5,  "last_message": "Campaign Q1 approved! 🎯",                      "last_time": "2026-02-08T14:20:00Z", "pinned": True},
    {"id": "-1004567890123", "title": "Personal Motivation",    "type": "group",    "unread": 0,  "last_message": "Daily quote: 'The best time to start is now.'", "last_time": "2026-02-08T07:00:00Z", "pinned": False},
    {"id": "-1001112223334", "title": "Alice",                  "type": "private",  "unread": 3,  "last_message": "Hey, check this task — it's urgent!",            "last_time": "2026-02-08T16:45:00Z", "pinned": False},
    {"id": "-1002223334445", "title": "Andrei Radu",            "type": "private",  "unread": 0,  "last_message": "PR #347 merged, deploying now.",                 "last_time": "2026-02-08T13:10:00Z", "pinned": False},
    {"id": "-1003334445556", "title": "Maria Ionescu",          "type": "private",  "unread": 1,  "last_message": "Invoice sent to ClientX ✅",                     "last_time": "2026-02-08T11:30:00Z", "pinned": False},
    {"id": "-1005556667778", "title": "DevOps Alerts",          "type": "group",    "unread": 12, "last_message": "⚠️ CPU spike on prod-01 (87%)",                  "last_time": "2026-02-08T15:55:00Z", "pinned": True},
    {"id": "-1006667778889", "title": "Fitness Accountability", "type": "group",    "unread": 0,  "last_message": "Who's running tomorrow morning?",                "last_time": "2026-02-07T20:00:00Z", "pinned": False},
    {"id": "-1007778889990", "title": "Book Club 📚",           "type": "group",    "unread": 2,  "last_message": "Next pick: 'Deep Work' by Cal Newport",          "last_time": "2026-02-07T18:30:00Z", "pinned": False},
    {"id": "-1008889990001", "title": "Family Group",           "type": "group",    "unread": 0,  "last_message": "Sunday dinner at 7? 🍕",                         "last_time": "2026-02-07T12:00:00Z", "pinned": False},
]

TELEGRAM_MOCK_CHANNELS = [
    {"id": "-1001001001001", "title": "Marketing Tips",         "username": "@marketingtips",    "subscribers": 8912,  "posts_today": 3, "last_post": "5 SEO Hacks for 2026",                     "last_time": "2026-02-08T10:00:00Z", "type": "public"},
    {"id": "-1001001001002", "title": "Tech News Daily",        "username": "@technewsdaily",    "subscribers": 24301, "posts_today": 7, "last_post": "Apple Vision Pro 3 announced",              "last_time": "2026-02-08T14:30:00Z", "type": "public"},
    {"id": "-1001001001003", "title": "Startup Digest",         "username": "@startupdigest",    "subscribers": 15678, "posts_today": 2, "last_post": "Series A: AI startup raises $45M",          "last_time": "2026-02-08T09:15:00Z", "type": "public"},
    {"id": "-1001001001004", "title": "Product Hunt RO",        "username": "@producthuntro",    "subscribers": 3456,  "posts_today": 1, "last_post": "Top 5 launches of the week",                "last_time": "2026-02-08T08:00:00Z", "type": "public"},
    {"id": "-1001001001005", "title": "Internal Announcements", "username": None,                "subscribers": 47,    "posts_today": 1, "last_post": "New PTO policy effective March 1",          "last_time": "2026-02-08T11:00:00Z", "type": "private"},
    {"id": "-1001001001006", "title": "AI & ML Research",       "username": "@aimlresearch",     "subscribers": 42100, "posts_today": 4, "last_post": "GPT-5 benchmark results leaked",            "last_time": "2026-02-08T16:00:00Z", "type": "public"},
]

TELEGRAM_MOCK_BOTS = [
    {"id": "bot_001", "username": "@TaskReminderBot",   "name": "Task Reminder",   "status": "active",  "commands": ["/set_reminder", "/list", "/done", "/snooze"],           "messages_sent": 342, "last_active": "2026-02-08T16:00:00Z", "description": "Sends task reminders from Todoist"},
    {"id": "bot_002", "username": "@MotivationBot",     "name": "Daily Motivation", "status": "active", "commands": ["/quote", "/affirmation", "/streak", "/subscribe"],      "messages_sent": 187, "last_active": "2026-02-08T07:00:00Z", "description": "Daily motivational quotes & affirmations"},
    {"id": "bot_003", "username": "@ExpenseTrackerBot", "name": "Expense Tracker",  "status": "paused", "commands": ["/add", "/report", "/budget", "/export"],               "messages_sent": 98,  "last_active": "2026-02-05T10:00:00Z", "description": "Track expenses via quick commands"},
    {"id": "bot_004", "username": "@StandupBot",        "name": "Standup Reporter", "status": "active", "commands": ["/standup", "/yesterday", "/blockers", "/team"],         "messages_sent": 256, "last_active": "2026-02-08T09:30:00Z", "description": "Collects daily standup reports from team"},
    {"id": "bot_005", "username": "@DeployNotifyBot",   "name": "Deploy Notifier",  "status": "active", "commands": ["/status", "/deploy", "/rollback", "/logs"],             "messages_sent": 412, "last_active": "2026-02-08T15:55:00Z", "description": "Notifies on deployments & CI/CD events"},
]

TELEGRAM_MOCK_OVERVIEW = {
    "kpis": {
        "messages_sent": 1234, "messages_received": 987, "unread": 23,
        "active_chats": 10, "active_bots": 4, "channels_subscribed": 6,
    },
    "daily_messages": [
        {"day": "Mon", "sent": 45, "received": 38},
        {"day": "Tue", "sent": 52, "received": 41},
        {"day": "Wed", "sent": 38, "received": 35},
        {"day": "Thu", "sent": 61, "received": 48},
        {"day": "Fri", "sent": 33, "received": 29},
        {"day": "Sat", "sent": 18, "received": 12},
        {"day": "Sun", "sent": 11, "received": 8},
    ],
    "chat_type_breakdown": {"private": 4, "group": 6},
}

TELEGRAM_MOCK_MESSAGES = [
    {"id": "msg_001", "chat": "Alice",               "from": "Alice",         "text": "Hey, check this task — it's urgent!",               "date": "2026-02-08T16:45:00Z", "type": "text",    "reply_to": None},
    {"id": "msg_002", "chat": "Alice",               "from": "You",           "text": "On it! Will review in 30 min.",                      "date": "2026-02-08T16:46:00Z", "type": "text",    "reply_to": "msg_001"},
    {"id": "msg_003", "chat": "Team Marketing",      "from": "Maria Ionescu", "text": "Campaign Q1 approved! 🎯",                           "date": "2026-02-08T14:20:00Z", "type": "text",    "reply_to": None},
    {"id": "msg_004", "chat": "Team Marketing",      "from": "You",           "text": "Great news! Let's schedule the launch.",              "date": "2026-02-08T14:22:00Z", "type": "text",    "reply_to": "msg_003"},
    {"id": "msg_005", "chat": "DevOps Alerts",       "from": "@DeployNotifyBot", "text": "⚠️ CPU spike on prod-01 (87%)",                   "date": "2026-02-08T15:55:00Z", "type": "alert",   "reply_to": None},
    {"id": "msg_006", "chat": "DevOps Alerts",       "from": "Andrei Radu",   "text": "Scaling up, should stabilize in 5 min.",              "date": "2026-02-08T15:57:00Z", "type": "text",    "reply_to": "msg_005"},
    {"id": "msg_007", "chat": "Personal Journal",    "from": "You",           "text": "Finished evening meditation 🧘",                      "date": "2026-02-08T21:30:00Z", "type": "text",    "reply_to": None},
    {"id": "msg_008", "chat": "Personal Motivation", "from": "@MotivationBot","text": "Daily quote: 'The best time to start is now.'",       "date": "2026-02-08T07:00:00Z", "type": "text",    "reply_to": None},
    {"id": "msg_009", "chat": "Andrei Radu",         "from": "Andrei Radu",   "text": "PR #347 merged, deploying now.",                      "date": "2026-02-08T13:10:00Z", "type": "text",    "reply_to": None},
    {"id": "msg_010", "chat": "Maria Ionescu",       "from": "Maria Ionescu", "text": "Invoice sent to ClientX ✅",                          "date": "2026-02-08T11:30:00Z", "type": "text",    "reply_to": None},
    {"id": "msg_011", "chat": "Book Club 📚",        "from": "Alice",         "text": "Next pick: 'Deep Work' by Cal Newport",               "date": "2026-02-07T18:30:00Z", "type": "text",    "reply_to": None},
    {"id": "msg_012", "chat": "Family Group",        "from": "Mom",           "text": "Sunday dinner at 7? 🍕",                              "date": "2026-02-07T12:00:00Z", "type": "text",    "reply_to": None},
    {"id": "msg_013", "chat": "Fitness Accountability","from": "You",          "text": "5K done this morning! 🏃",                            "date": "2026-02-08T07:30:00Z", "type": "text",    "reply_to": None},
    {"id": "msg_014", "chat": "Team Marketing",      "from": "@StandupBot",   "text": "Standup reminder: What did you do yesterday?",         "date": "2026-02-08T09:00:00Z", "type": "text",    "reply_to": None},
    {"id": "msg_015", "chat": "DevOps Alerts",       "from": "@DeployNotifyBot","text": "✅ Deploy v2.3.1 to production — success",           "date": "2026-02-08T13:15:00Z", "type": "alert",   "reply_to": None},
]


@app.route("/api/connectors/telegram/chats", methods=["GET"])
def telegram_chats():
    chat_type = request.args.get("type", "").strip().lower()
    rows = list(TELEGRAM_MOCK_CHATS)
    if chat_type:
        rows = [r for r in rows if r["type"] == chat_type]
    return jsonify(rows)


@app.route("/api/connectors/telegram/overview", methods=["GET"])
def telegram_overview():
    return jsonify(TELEGRAM_MOCK_OVERVIEW)


@app.route("/api/connectors/telegram/channels", methods=["GET"])
def telegram_channels():
    ch_type = request.args.get("type", "").strip().lower()
    rows = list(TELEGRAM_MOCK_CHANNELS)
    if ch_type:
        rows = [r for r in rows if r["type"] == ch_type]
    return jsonify(rows)


@app.route("/api/connectors/telegram/bots", methods=["GET"])
def telegram_bots():
    status = request.args.get("status", "").strip().lower()
    rows = list(TELEGRAM_MOCK_BOTS)
    if status:
        rows = [r for r in rows if r["status"] == status]
    return jsonify(rows)


@app.route("/api/connectors/telegram/messages", methods=["GET"])
def telegram_messages():
    rows = list(TELEGRAM_MOCK_MESSAGES)
    chat = request.args.get("chat", "").strip()
    if chat:
        rows = [r for r in rows if r["chat"].lower() == chat.lower()]
    sender = request.args.get("from", "").strip()
    if sender:
        rows = [r for r in rows if sender.lower() in r["from"].lower()]
    search = request.args.get("search", "").strip().lower()
    if search:
        rows = [r for r in rows if search in r["text"].lower()]
    return jsonify(rows)


@app.route("/api/connectors/telegram/reports", methods=["GET"])
def telegram_reports():
    rows = []
    for c in TELEGRAM_MOCK_CHATS:
        rows.append({"type": "Chat", "id": c["id"], "name": c["title"], "detail": c["type"],
                      "status": f"{c['unread']} unread", "last_activity": c["last_time"]})
    for ch in TELEGRAM_MOCK_CHANNELS:
        rows.append({"type": "Channel", "id": ch["id"], "name": ch["title"], "detail": f"{ch['subscribers']} subs",
                      "status": f"{ch['posts_today']} posts today", "last_activity": ch["last_time"]})
    for b in TELEGRAM_MOCK_BOTS:
        rows.append({"type": "Bot", "id": b["id"], "name": b["name"], "detail": b["username"],
                      "status": b["status"], "last_activity": b["last_active"]})
    for m in TELEGRAM_MOCK_MESSAGES:
        rows.append({"type": "Message", "id": m["id"], "name": m["text"][:50], "detail": m["chat"],
                      "status": m["type"], "last_activity": m["date"]})
    return jsonify(rows)


@app.route("/api/connectors/telegram/test-call", methods=["POST"])
def telegram_test_call():
    import time, random
    body = request.get_json(force=True) or {}
    endpoint = body.get("endpoint", "getUpdates")
    start = time.time()
    time.sleep(random.uniform(0.05, 0.15))
    elapsed = round((time.time() - start) * 1000, 1)
    if endpoint == "sendMessage":
        response_body = {"ok": True, "result": {"message_id": 123456, "chat": {"id": -1001234567890, "title": "Personal Journal"}, "text": "Test message sent!", "date": 1739001600}}
    elif endpoint == "getUpdates":
        response_body = {"ok": True, "result": [{"update_id": 900001, "message": {"message_id": 999, "from": {"first_name": "Alice"}, "text": "Hello!", "date": 1739001500}}]}
    elif endpoint == "getMe":
        response_body = {"ok": True, "result": {"id": 7654321, "is_bot": True, "first_name": "CamaradBot", "username": "CamaradAIBot"}}
    else:
        response_body = {"ok": True, "result": []}
    return jsonify({
        "ok": True,
        "endpoint": f"https://api.telegram.org/bot<token>/{endpoint}",
        "method": "POST" if endpoint == "sendMessage" else "GET",
        "response": {"status_code": 200,
                      "headers": {"content-type": "application/json"},
                      "body": response_body},
        "latency_ms": elapsed,
        "quota": {"rate_limit": 30, "remaining": 28, "reset": "2026-02-08T15:15:01Z"}
    })


# ═══════════════════════════════════════════════════════════════════════════════
# AWS  (Phase 29 – DevOps & Infra)
# ═══════════════════════════════════════════════════════════════════════════════

AWS_MOCK_EC2_INSTANCES = [
    {"instance_id": "i-0a1b2c3d4e5f60001", "name": "web-server-01",      "type": "t3.medium",  "status": "running",    "az": "us-east-1a", "cpu_pct": 45,  "ram_gb": 4,  "storage_gb": 80,   "public_ip": "54.210.100.11",  "launch_date": "2025-11-15"},
    {"instance_id": "i-0a1b2c3d4e5f60002", "name": "web-server-02",      "type": "t3.medium",  "status": "running",    "az": "us-east-1b", "cpu_pct": 38,  "ram_gb": 4,  "storage_gb": 80,   "public_ip": "54.210.100.12",  "launch_date": "2025-11-15"},
    {"instance_id": "i-0a1b2c3d4e5f60003", "name": "api-gateway-01",     "type": "t3.large",   "status": "running",    "az": "us-east-1a", "cpu_pct": 62,  "ram_gb": 8,  "storage_gb": 120,  "public_ip": "54.210.100.20",  "launch_date": "2025-12-01"},
    {"instance_id": "i-0a1b2c3d4e5f60004", "name": "api-gateway-02",     "type": "t3.large",   "status": "running",    "az": "us-east-1c", "cpu_pct": 55,  "ram_gb": 8,  "storage_gb": 120,  "public_ip": "54.210.100.21",  "launch_date": "2025-12-01"},
    {"instance_id": "i-0a1b2c3d4e5f60005", "name": "db-primary",         "type": "r5.xlarge",  "status": "running",    "az": "us-east-1a", "cpu_pct": 72,  "ram_gb": 32, "storage_gb": 500,  "public_ip": None,             "launch_date": "2025-09-20"},
    {"instance_id": "i-0a1b2c3d4e5f60006", "name": "db-replica",         "type": "r5.xlarge",  "status": "running",    "az": "us-east-1b", "cpu_pct": 28,  "ram_gb": 32, "storage_gb": 500,  "public_ip": None,             "launch_date": "2025-09-20"},
    {"instance_id": "i-0a1b2c3d4e5f60007", "name": "worker-01",          "type": "c5.xlarge",  "status": "running",    "az": "us-east-1a", "cpu_pct": 88,  "ram_gb": 8,  "storage_gb": 200,  "public_ip": None,             "launch_date": "2026-01-05"},
    {"instance_id": "i-0a1b2c3d4e5f60008", "name": "worker-02",          "type": "c5.xlarge",  "status": "running",    "az": "us-east-1b", "cpu_pct": 91,  "ram_gb": 8,  "storage_gb": 200,  "public_ip": None,             "launch_date": "2026-01-05"},
    {"instance_id": "i-0a1b2c3d4e5f60009", "name": "staging-server",     "type": "t3.small",   "status": "stopped",    "az": "us-east-1a", "cpu_pct": 0,   "ram_gb": 2,  "storage_gb": 40,   "public_ip": None,             "launch_date": "2025-10-10"},
    {"instance_id": "i-0a1b2c3d4e5f60010", "name": "ci-runner-01",       "type": "t3.xlarge",  "status": "running",    "az": "us-east-1c", "cpu_pct": 35,  "ram_gb": 16, "storage_gb": 160,  "public_ip": "54.210.100.30",  "launch_date": "2026-01-12"},
    {"instance_id": "i-0a1b2c3d4e5f60011", "name": "ml-training",        "type": "p3.2xlarge", "status": "stopped",    "az": "us-east-1a", "cpu_pct": 0,   "ram_gb": 61, "storage_gb": 1000, "public_ip": None,             "launch_date": "2025-08-01"},
    {"instance_id": "i-0a1b2c3d4e5f60012", "name": "bastion-host",       "type": "t3.nano",    "status": "running",    "az": "us-east-1a", "cpu_pct": 5,   "ram_gb": 0.5,"storage_gb": 8,    "public_ip": "54.210.100.99",  "launch_date": "2025-07-01"},
]

AWS_MOCK_S3_BUCKETS = [
    {"name": "camarad-app-assets",      "region": "us-east-1", "objects": 12345, "size_gb": 180.5, "storage_class": "STANDARD",            "versioning": True,  "created": "2025-06-15", "last_modified": "2026-02-08"},
    {"name": "camarad-user-uploads",    "region": "us-east-1", "objects": 89012, "size_gb": 45.2,  "storage_class": "STANDARD",            "versioning": True,  "created": "2025-07-01", "last_modified": "2026-02-08"},
    {"name": "camarad-backups",         "region": "us-east-1", "objects": 2340,  "size_gb": 320.8, "storage_class": "STANDARD_IA",         "versioning": True,  "created": "2025-06-15", "last_modified": "2026-02-07"},
    {"name": "camarad-logs",            "region": "us-east-1", "objects": 456789,"size_gb": 78.3,  "storage_class": "STANDARD",            "versioning": False, "created": "2025-06-15", "last_modified": "2026-02-08"},
    {"name": "camarad-ml-datasets",     "region": "us-east-1", "objects": 5670,  "size_gb": 512.0, "storage_class": "INTELLIGENT_TIERING", "versioning": True,  "created": "2025-08-10", "last_modified": "2026-02-05"},
    {"name": "camarad-static-website",  "region": "us-east-1", "objects": 890,   "size_gb": 2.1,   "storage_class": "STANDARD",            "versioning": False, "created": "2025-09-01", "last_modified": "2026-01-28"},
    {"name": "camarad-terraform-state", "region": "us-east-1", "objects": 45,    "size_gb": 0.1,   "storage_class": "STANDARD",            "versioning": True,  "created": "2025-06-15", "last_modified": "2026-02-06"},
    {"name": "camarad-archive",         "region": "us-east-1", "objects": 12000, "size_gb": 1024.0,"storage_class": "GLACIER",             "versioning": False, "created": "2025-06-15", "last_modified": "2025-12-31"},
]

AWS_MOCK_LAMBDA_FUNCTIONS = [
    {"name": "process-image",       "runtime": "python3.12",  "memory_mb": 512,  "timeout_s": 60,  "invocations_30d": 145678, "avg_duration_ms": 320, "errors_30d": 234,  "last_invoked": "2026-02-08T14:32:00Z", "status": "active"},
    {"name": "send-notification",   "runtime": "nodejs20.x",  "memory_mb": 256,  "timeout_s": 30,  "invocations_30d": 89012,  "avg_duration_ms": 85,  "errors_30d": 12,   "last_invoked": "2026-02-08T14:45:00Z", "status": "active"},
    {"name": "generate-report",     "runtime": "python3.12",  "memory_mb": 1024, "timeout_s": 300, "invocations_30d": 3400,   "avg_duration_ms": 4500,"errors_30d": 56,   "last_invoked": "2026-02-08T06:00:00Z", "status": "active"},
    {"name": "process-payment",     "runtime": "nodejs20.x",  "memory_mb": 512,  "timeout_s": 30,  "invocations_30d": 67890,  "avg_duration_ms": 150, "errors_30d": 8,    "last_invoked": "2026-02-08T14:50:00Z", "status": "active"},
    {"name": "sync-crm-data",      "runtime": "python3.12",  "memory_mb": 768,  "timeout_s": 120, "invocations_30d": 12000,  "avg_duration_ms": 2200,"errors_30d": 145,  "last_invoked": "2026-02-08T12:00:00Z", "status": "active"},
    {"name": "cleanup-temp",       "runtime": "python3.12",  "memory_mb": 256,  "timeout_s": 60,  "invocations_30d": 720,    "avg_duration_ms": 800, "errors_30d": 3,    "last_invoked": "2026-02-08T03:00:00Z", "status": "active"},
    {"name": "resize-thumbnails",  "runtime": "nodejs20.x",  "memory_mb": 1024, "timeout_s": 90,  "invocations_30d": 34567,  "avg_duration_ms": 450, "errors_30d": 89,   "last_invoked": "2026-02-08T14:20:00Z", "status": "active"},
    {"name": "legacy-migrator",    "runtime": "python3.9",   "memory_mb": 512,  "timeout_s": 300, "invocations_30d": 0,      "avg_duration_ms": 0,   "errors_30d": 0,    "last_invoked": "2025-12-15T10:00:00Z", "status": "inactive"},
]

AWS_MOCK_OVERVIEW = {
    "account_id": "123456789012",
    "region": "us-east-1",
    "ec2_instances_total": 12,
    "ec2_instances_running": 10,
    "s3_buckets": 8,
    "s3_total_storage_gb": 2162.9,
    "lambda_functions": 8,
    "lambda_invocations_30d": 353267,
    "monthly_cost_current": 4287.50,
    "monthly_cost_forecast": 4450.00,
    "iam_users": 18,
    "active_alarms": 3,
    "monthly_cost_trend": [
        {"month": "Sep 2025", "cost": 3120.00},
        {"month": "Oct 2025", "cost": 3340.00},
        {"month": "Nov 2025", "cost": 3580.00},
        {"month": "Dec 2025", "cost": 3890.00},
        {"month": "Jan 2026", "cost": 4150.00},
        {"month": "Feb 2026", "cost": 4287.50}
    ],
    "service_breakdown": [
        {"service": "EC2",         "cost": 1876.40, "pct": 43.8},
        {"service": "S3",          "cost": 812.30,  "pct": 18.9},
        {"service": "Lambda",      "cost": 345.60,  "pct": 8.1},
        {"service": "RDS",         "cost": 567.80,  "pct": 13.2},
        {"service": "CloudFront",  "cost": 234.50,  "pct": 5.5},
        {"service": "Other",       "cost": 450.90,  "pct": 10.5}
    ]
}

AWS_MOCK_COST_EXPLORER = [
    {"month": "Sep 2025", "ec2": 1320.00, "s3": 650.00, "lambda": 210.00, "rds": 480.00, "cloudfront": 180.00, "other": 280.00, "total": 3120.00},
    {"month": "Oct 2025", "ec2": 1420.00, "s3": 680.00, "lambda": 230.00, "rds": 490.00, "cloudfront": 195.00, "other": 325.00, "total": 3340.00},
    {"month": "Nov 2025", "ec2": 1520.00, "s3": 710.00, "lambda": 260.00, "rds": 510.00, "cloudfront": 210.00, "other": 370.00, "total": 3580.00},
    {"month": "Dec 2025", "ec2": 1650.00, "s3": 740.00, "lambda": 290.00, "rds": 530.00, "cloudfront": 220.00, "other": 460.00, "total": 3890.00},
    {"month": "Jan 2026", "ec2": 1780.00, "s3": 780.00, "lambda": 320.00, "rds": 550.00, "cloudfront": 225.00, "other": 495.00, "total": 4150.00},
    {"month": "Feb 2026", "ec2": 1876.40, "s3": 812.30, "lambda": 345.60, "rds": 567.80, "cloudfront": 234.50, "other": 450.90, "total": 4287.50},
]


@app.route("/api/connectors/aws/ec2", methods=["GET"])
def api_aws_ec2():
    status = request.args.get("status", "").lower()
    az = request.args.get("az", "").lower()
    data = AWS_MOCK_EC2_INSTANCES
    if status:
        data = [i for i in data if i["status"] == status]
    if az:
        data = [i for i in data if i["az"] == az]
    return jsonify(data)


@app.route("/api/connectors/aws/s3", methods=["GET"])
def api_aws_s3():
    storage_class = request.args.get("storage_class", "").upper()
    data = AWS_MOCK_S3_BUCKETS
    if storage_class:
        data = [b for b in data if b["storage_class"] == storage_class]
    return jsonify(data)


@app.route("/api/connectors/aws/lambda", methods=["GET"])
def api_aws_lambda():
    runtime = request.args.get("runtime", "").lower()
    status = request.args.get("status", "").lower()
    data = AWS_MOCK_LAMBDA_FUNCTIONS
    if runtime:
        data = [f for f in data if runtime in f["runtime"].lower()]
    if status:
        data = [f for f in data if f["status"] == status]
    return jsonify(data)


@app.route("/api/connectors/aws/overview", methods=["GET"])
def api_aws_overview():
    return jsonify(AWS_MOCK_OVERVIEW)


@app.route("/api/connectors/aws/cost-explorer", methods=["GET"])
def api_aws_cost_explorer():
    service = request.args.get("service", "").lower()
    data = AWS_MOCK_COST_EXPLORER
    if service:
        result = []
        for row in data:
            if service in row:
                result.append({"month": row["month"], "service": service, "cost": row[service]})
        return jsonify(result)
    return jsonify(data)


@app.route("/api/connectors/aws/reports", methods=["GET"])
def api_aws_reports():
    rows = []
    for i in AWS_MOCK_EC2_INSTANCES:
        rows.append({"type": "EC2 Instance", "name": i["name"], "detail": f'{i["type"]} | {i["az"]}', "status": i["status"], "metric": f'CPU {i["cpu_pct"]}%'})
    for b in AWS_MOCK_S3_BUCKETS:
        rows.append({"type": "S3 Bucket", "name": b["name"], "detail": f'{b["storage_class"]} | {b["region"]}', "status": "active", "metric": f'{b["size_gb"]} GB'})
    for f in AWS_MOCK_LAMBDA_FUNCTIONS:
        rows.append({"type": "Lambda Function", "name": f["name"], "detail": f'{f["runtime"]} | {f["memory_mb"]}MB', "status": f["status"], "metric": f'{f["invocations_30d"]:,} invocations'})
    for c in AWS_MOCK_COST_EXPLORER:
        rows.append({"type": "Cost", "name": c["month"], "detail": f'EC2: ${c["ec2"]:,.0f} | S3: ${c["s3"]:,.0f} | Lambda: ${c["lambda"]:,.0f}', "status": "billed", "metric": f'${c["total"]:,.2f}'})
    return jsonify(rows)


@app.route("/api/connectors/aws/test-call", methods=["POST"])
def api_aws_test_call():
    import time
    payload = request.get_json(force=True) or {}
    endpoint = payload.get("endpoint", "ec2-describe-instances")
    start = time.time()
    if endpoint == "ec2-describe-instances":
        response_body = {"Reservations": [{"Instances": [{"InstanceId": i["instance_id"], "InstanceType": i["type"], "State": {"Name": i["status"]}, "PublicIpAddress": i["public_ip"]} for i in AWS_MOCK_EC2_INSTANCES[:3]]}]}
    elif endpoint == "s3-list-buckets":
        response_body = {"Buckets": [{"Name": b["name"], "CreationDate": b["created"]} for b in AWS_MOCK_S3_BUCKETS[:4]]}
    elif endpoint == "lambda-list-functions":
        response_body = {"Functions": [{"FunctionName": f["name"], "Runtime": f["runtime"], "MemorySize": f["memory_mb"], "Timeout": f["timeout_s"]} for f in AWS_MOCK_LAMBDA_FUNCTIONS[:4]]}
    elif endpoint == "cloudwatch-get-alarms":
        response_body = {"MetricAlarms": [{"AlarmName": "HighCPU-worker-01", "StateValue": "ALARM", "MetricName": "CPUUtilization", "Threshold": 85.0}, {"AlarmName": "LowDiskSpace-db", "StateValue": "ALARM", "MetricName": "DiskSpaceUtilization", "Threshold": 90.0}, {"AlarmName": "LambdaErrors-High", "StateValue": "ALARM", "MetricName": "Errors", "Threshold": 50}]}
    else:
        response_body = {"error": "Unknown endpoint", "available": ["ec2-describe-instances", "s3-list-buckets", "lambda-list-functions", "cloudwatch-get-alarms"]}
    elapsed = round((time.time() - start) * 1000, 1)
    return jsonify({
        "endpoint": endpoint,
        "method": "POST" if endpoint == "lambda-invoke" else "GET",
        "response": {"status_code": 200, "headers": {"content-type": "application/json"}, "body": response_body},
        "latency_ms": elapsed,
        "quota": {"api_calls_today": 4821, "daily_limit": 10000, "reset": "2026-02-09T00:00:00Z"}
    })


# ═══════════════════════════════════════════════════════════════════════════════
# VERCEL  (Phase 30 – Frontend/Dev)
# ═══════════════════════════════════════════════════════════════════════════════

VERCEL_MOCK_DEPLOYMENTS = [
    {"uid": "dpl_abc001", "name": "camarad-app",      "url": "camarad-app-abc001.vercel.app", "state": "READY",    "target": "production",  "branch": "main",    "commit": "Fix auth redirect loop",         "commit_sha": "a1b2c3d", "creator": "alex@techstart.ai",  "created": "2026-02-08T14:30:00Z", "duration_s": 42,  "framework": "Next.js"},
    {"uid": "dpl_abc002", "name": "camarad-app",      "url": "camarad-app-abc002.vercel.app", "state": "READY",    "target": "production",  "branch": "main",    "commit": "Add dark mode toggle",           "commit_sha": "d4e5f6g", "creator": "alex@techstart.ai",  "created": "2026-02-08T10:15:00Z", "duration_s": 38,  "framework": "Next.js"},
    {"uid": "dpl_abc003", "name": "camarad-app",      "url": "camarad-app-abc003.vercel.app", "state": "READY",    "target": "preview",     "branch": "feat/chat","commit": "WIP: Chat widget redesign",      "commit_sha": "h7i8j9k", "creator": "maria@techstart.ai", "created": "2026-02-07T18:45:00Z", "duration_s": 55,  "framework": "Next.js"},
    {"uid": "dpl_abc004", "name": "camarad-docs",     "url": "camarad-docs-abc004.vercel.app","state": "READY",    "target": "production",  "branch": "main",    "commit": "Update API reference v3.2",      "commit_sha": "l0m1n2o", "creator": "dan@techstart.ai",   "created": "2026-02-07T12:00:00Z", "duration_s": 28,  "framework": "Astro"},
    {"uid": "dpl_abc005", "name": "camarad-app",      "url": "camarad-app-abc005.vercel.app", "state": "ERROR",    "target": "preview",     "branch": "feat/new-api","commit": "Refactor API routes (broken)",  "commit_sha": "p3q4r5s", "creator": "alex@techstart.ai",  "created": "2026-02-07T09:30:00Z", "duration_s": 72,  "framework": "Next.js"},
    {"uid": "dpl_abc006", "name": "camarad-landing",  "url": "camarad-landing-abc006.vercel.app","state": "READY", "target": "production",  "branch": "main",    "commit": "Hero section A/B test variant",  "commit_sha": "t6u7v8w", "creator": "maria@techstart.ai", "created": "2026-02-06T16:20:00Z", "duration_s": 35,  "framework": "Next.js"},
    {"uid": "dpl_abc007", "name": "camarad-app",      "url": "camarad-app-abc007.vercel.app", "state": "READY",    "target": "production",  "branch": "main",    "commit": "Performance: lazy-load images",  "commit_sha": "x9y0z1a", "creator": "dan@techstart.ai",   "created": "2026-02-06T11:10:00Z", "duration_s": 40,  "framework": "Next.js"},
    {"uid": "dpl_abc008", "name": "camarad-docs",     "url": "camarad-docs-abc008.vercel.app","state": "READY",    "target": "preview",     "branch": "docs/v4", "commit": "Draft: v4 migration guide",      "commit_sha": "b2c3d4e", "creator": "dan@techstart.ai",   "created": "2026-02-05T14:55:00Z", "duration_s": 25,  "framework": "Astro"},
    {"uid": "dpl_abc009", "name": "camarad-landing",  "url": "camarad-landing-abc009.vercel.app","state": "CANCELED","target": "preview",    "branch": "test/cta","commit": "Test CTA colors (canceled)",     "commit_sha": "f5g6h7i", "creator": "maria@techstart.ai", "created": "2026-02-05T10:30:00Z", "duration_s": 0,   "framework": "Next.js"},
    {"uid": "dpl_abc010", "name": "camarad-app",      "url": "camarad-app-abc010.vercel.app", "state": "READY",    "target": "production",  "branch": "main",    "commit": "Hotfix: SSR hydration mismatch", "commit_sha": "j8k9l0m", "creator": "alex@techstart.ai",  "created": "2026-02-04T22:00:00Z", "duration_s": 45,  "framework": "Next.js"},
    {"uid": "dpl_abc011", "name": "camarad-app",      "url": "camarad-app-abc011.vercel.app", "state": "BUILDING", "target": "preview",     "branch": "feat/i18n","commit": "Add Romanian locale strings",   "commit_sha": "n1o2p3q", "creator": "alex@techstart.ai",  "created": "2026-02-08T15:00:00Z", "duration_s": 0,   "framework": "Next.js"},
    {"uid": "dpl_abc012", "name": "camarad-api",      "url": "camarad-api-abc012.vercel.app", "state": "READY",    "target": "production",  "branch": "main",    "commit": "Edge functions: rate limiter",   "commit_sha": "r4s5t6u", "creator": "dan@techstart.ai",   "created": "2026-02-04T08:30:00Z", "duration_s": 33,  "framework": "Next.js"},
    {"uid": "dpl_abc013", "name": "camarad-landing",  "url": "camarad-landing-abc013.vercel.app","state": "ERROR", "target": "preview",     "branch": "feat/vid","commit": "Video embed (OOM build)",        "commit_sha": "v7w8x9y", "creator": "maria@techstart.ai", "created": "2026-02-03T15:45:00Z", "duration_s": 120, "framework": "Next.js"},
    {"uid": "dpl_abc014", "name": "camarad-app",      "url": "camarad-app-abc014.vercel.app", "state": "READY",    "target": "production",  "branch": "main",    "commit": "Upgrade Next.js to 15.1",       "commit_sha": "z0a1b2c", "creator": "alex@techstart.ai",  "created": "2026-02-03T10:00:00Z", "duration_s": 52,  "framework": "Next.js"},
    {"uid": "dpl_abc015", "name": "camarad-docs",     "url": "camarad-docs-abc015.vercel.app","state": "READY",    "target": "production",  "branch": "main",    "commit": "SEO: add structured data",      "commit_sha": "d3e4f5g", "creator": "dan@techstart.ai",   "created": "2026-02-02T09:15:00Z", "duration_s": 22,  "framework": "Astro"},
]

VERCEL_MOCK_DOMAINS = [
    {"name": "app.camarad.ai",       "project": "camarad-app",     "redirect": None,                  "status": "valid",   "ssl": "valid",   "ssl_expiry": "2026-08-15", "dns_type": "CNAME", "created": "2025-06-01"},
    {"name": "www.camarad.ai",       "project": "camarad-landing", "redirect": "app.camarad.ai",      "status": "valid",   "ssl": "valid",   "ssl_expiry": "2026-08-15", "dns_type": "CNAME", "created": "2025-06-01"},
    {"name": "docs.camarad.ai",      "project": "camarad-docs",    "redirect": None,                  "status": "valid",   "ssl": "valid",   "ssl_expiry": "2026-09-20", "dns_type": "CNAME", "created": "2025-07-10"},
    {"name": "api.camarad.ai",       "project": "camarad-api",     "redirect": None,                  "status": "valid",   "ssl": "valid",   "ssl_expiry": "2026-10-05", "dns_type": "A",     "created": "2025-08-15"},
    {"name": "staging.camarad.ai",   "project": "camarad-app",     "redirect": None,                  "status": "valid",   "ssl": "valid",   "ssl_expiry": "2026-07-30", "dns_type": "CNAME", "created": "2025-09-01"},
    {"name": "preview.camarad.ai",   "project": "camarad-app",     "redirect": None,                  "status": "valid",   "ssl": "valid",   "ssl_expiry": "2026-11-12", "dns_type": "CNAME", "created": "2025-10-20"},
    {"name": "old-site.techstart.com","project": "camarad-landing", "redirect": "www.camarad.ai",     "status": "expired", "ssl": "expired", "ssl_expiry": "2025-12-01", "dns_type": "CNAME", "created": "2024-06-01"},
    {"name": "beta.camarad.ai",      "project": "camarad-app",     "redirect": None,                  "status": "pending", "ssl": "pending", "ssl_expiry": None,         "dns_type": "CNAME", "created": "2026-02-07"},
    {"name": "blog.camarad.ai",      "project": "camarad-docs",    "redirect": None,                  "status": "valid",   "ssl": "valid",   "ssl_expiry": "2026-09-20", "dns_type": "CNAME", "created": "2025-11-15"},
    {"name": "demo.camarad.ai",      "project": "camarad-app",     "redirect": None,                  "status": "valid",   "ssl": "valid",   "ssl_expiry": "2026-06-18", "dns_type": "CNAME", "created": "2025-12-01"},
]

VERCEL_MOCK_LOGS = [
    {"deployment": "dpl_abc001", "timestamp": "2026-02-08T14:30:42Z", "level": "info",    "message": "Build completed successfully",              "source": "build"},
    {"deployment": "dpl_abc001", "timestamp": "2026-02-08T14:30:40Z", "level": "info",    "message": "Generating static pages (24/24)",           "source": "build"},
    {"deployment": "dpl_abc001", "timestamp": "2026-02-08T14:30:35Z", "level": "info",    "message": "Compiling TypeScript…",                     "source": "build"},
    {"deployment": "dpl_abc001", "timestamp": "2026-02-08T14:30:30Z", "level": "info",    "message": "Installing dependencies (npm ci)",          "source": "build"},
    {"deployment": "dpl_abc001", "timestamp": "2026-02-08T14:30:28Z", "level": "info",    "message": "Cloning repository…",                       "source": "build"},
    {"deployment": "dpl_abc005", "timestamp": "2026-02-07T09:31:12Z", "level": "error",   "message": "Module not found: '@/lib/newApi'",          "source": "build"},
    {"deployment": "dpl_abc005", "timestamp": "2026-02-07T09:31:10Z", "level": "error",   "message": "TypeScript error in src/pages/api/route.ts","source": "build"},
    {"deployment": "dpl_abc005", "timestamp": "2026-02-07T09:31:05Z", "level": "warning", "message": "Unused import: 'OldClient' in api.ts",      "source": "build"},
    {"deployment": "dpl_abc005", "timestamp": "2026-02-07T09:30:50Z", "level": "info",    "message": "Installing dependencies (npm ci)",          "source": "build"},
    {"deployment": "dpl_abc005", "timestamp": "2026-02-07T09:30:45Z", "level": "info",    "message": "Cloning repository…",                       "source": "build"},
    {"deployment": "dpl_abc010", "timestamp": "2026-02-04T22:00:45Z", "level": "info",    "message": "Build completed successfully",              "source": "build"},
    {"deployment": "dpl_abc010", "timestamp": "2026-02-04T22:00:40Z", "level": "warning", "message": "Large page data: /dashboard (128 kB)",      "source": "build"},
    {"deployment": "dpl_abc010", "timestamp": "2026-02-04T22:00:35Z", "level": "info",    "message": "Generating static pages (24/24)",           "source": "build"},
    {"deployment": "dpl_abc013", "timestamp": "2026-02-03T15:47:45Z", "level": "error",   "message": "FATAL: JavaScript heap out of memory",      "source": "build"},
    {"deployment": "dpl_abc013", "timestamp": "2026-02-03T15:47:30Z", "level": "warning", "message": "Memory usage: 1.8 GB / 2 GB",              "source": "build"},
    {"deployment": "dpl_abc013", "timestamp": "2026-02-03T15:46:00Z", "level": "info",    "message": "Processing video assets (12 files)…",       "source": "build"},
    {"deployment": "dpl_abc011", "timestamp": "2026-02-08T15:00:10Z", "level": "info",    "message": "Installing dependencies (npm ci)",          "source": "build"},
    {"deployment": "dpl_abc011", "timestamp": "2026-02-08T15:00:05Z", "level": "info",    "message": "Cloning repository…",                       "source": "build"},
]

VERCEL_MOCK_ANALYTICS = {
    "period": "last_7_days",
    "total_visitors": 28456,
    "unique_visitors": 12890,
    "page_views": 67234,
    "bandwidth_gb": 45.2,
    "avg_response_ms": 125,
    "cache_hit_rate": 94.2,
    "top_pages": [
        {"path": "/",           "views": 18200, "visitors": 8450, "avg_duration_s": 45},
        {"path": "/dashboard",  "views": 12300, "visitors": 5670, "avg_duration_s": 180},
        {"path": "/connectors", "views": 8900,  "visitors": 4120, "avg_duration_s": 120},
        {"path": "/chat",       "views": 7500,  "visitors": 3800, "avg_duration_s": 240},
        {"path": "/docs",       "views": 6200,  "visitors": 2900, "avg_duration_s": 90},
        {"path": "/pricing",    "views": 5100,  "visitors": 3200, "avg_duration_s": 60},
        {"path": "/blog",       "views": 4800,  "visitors": 2100, "avg_duration_s": 75},
        {"path": "/api/health", "views": 4200,  "visitors": 800,  "avg_duration_s": 2},
    ],
    "daily_visitors": [
        {"date": "2026-02-02", "visitors": 3800, "page_views": 8900},
        {"date": "2026-02-03", "visitors": 4100, "page_views": 9600},
        {"date": "2026-02-04", "visitors": 3950, "page_views": 9200},
        {"date": "2026-02-05", "visitors": 4200, "page_views": 10100},
        {"date": "2026-02-06", "visitors": 4500, "page_views": 10800},
        {"date": "2026-02-07", "visitors": 4800, "page_views": 11200},
        {"date": "2026-02-08", "visitors": 3106, "page_views": 7434},
    ],
    "top_referrers": [
        {"source": "google.com",    "visitors": 4500, "pct": 34.9},
        {"source": "twitter.com",   "visitors": 2100, "pct": 16.3},
        {"source": "github.com",    "visitors": 1800, "pct": 14.0},
        {"source": "linkedin.com",  "visitors": 1200, "pct": 9.3},
        {"source": "(direct)",      "visitors": 3290, "pct": 25.5},
    ]
}

VERCEL_MOCK_OVERVIEW = {
    "team": "TechStart Dev",
    "team_id": "team_abc123",
    "plan": "Pro",
    "projects": 4,
    "total_deployments": 156,
    "deployments_today": 3,
    "domains": 10,
    "domains_valid": 8,
    "bandwidth_gb": 45.2,
    "bandwidth_limit_gb": 100,
    "builds_this_month": 312,
    "avg_build_time_s": 41,
    "edge_functions": 8,
    "serverless_invocations_30d": 234567,
    "deploy_trend": [
        {"date": "2026-02-02", "deploys": 5, "succeeded": 5, "failed": 0},
        {"date": "2026-02-03", "deploys": 8, "succeeded": 6, "failed": 2},
        {"date": "2026-02-04", "deploys": 4, "succeeded": 4, "failed": 0},
        {"date": "2026-02-05", "deploys": 6, "succeeded": 5, "failed": 1},
        {"date": "2026-02-06", "deploys": 7, "succeeded": 7, "failed": 0},
        {"date": "2026-02-07", "deploys": 5, "succeeded": 4, "failed": 1},
        {"date": "2026-02-08", "deploys": 3, "succeeded": 2, "failed": 0},
    ]
}


@app.route("/api/connectors/vercel/deployments", methods=["GET"])
def api_vercel_deployments():
    state = request.args.get("state", "").upper()
    target = request.args.get("target", "").lower()
    project = request.args.get("project", "").lower()
    data = VERCEL_MOCK_DEPLOYMENTS
    if state:
        data = [d for d in data if d["state"] == state]
    if target:
        data = [d for d in data if d["target"] == target]
    if project:
        data = [d for d in data if project in d["name"].lower()]
    return jsonify(data)


@app.route("/api/connectors/vercel/domains", methods=["GET"])
def api_vercel_domains():
    status = request.args.get("status", "").lower()
    data = VERCEL_MOCK_DOMAINS
    if status:
        data = [d for d in data if d["status"] == status]
    return jsonify(data)


@app.route("/api/connectors/vercel/logs", methods=["GET"])
def api_vercel_logs():
    deployment = request.args.get("deployment", "")
    level = request.args.get("level", "").lower()
    search = request.args.get("search", "").lower()
    data = VERCEL_MOCK_LOGS
    if deployment:
        data = [l for l in data if l["deployment"] == deployment]
    if level:
        data = [l for l in data if l["level"] == level]
    if search:
        data = [l for l in data if search in l["message"].lower()]
    return jsonify(data)


@app.route("/api/connectors/vercel/analytics", methods=["GET"])
def api_vercel_analytics():
    return jsonify(VERCEL_MOCK_ANALYTICS)


@app.route("/api/connectors/vercel/overview", methods=["GET"])
def api_vercel_overview():
    return jsonify(VERCEL_MOCK_OVERVIEW)


@app.route("/api/connectors/vercel/reports", methods=["GET"])
def api_vercel_reports():
    rows = []
    for d in VERCEL_MOCK_DEPLOYMENTS:
        rows.append({"type": "Deployment", "name": d["uid"], "detail": f'{d["name"]} | {d["commit"][:30]}', "status": d["state"], "metric": f'{d["duration_s"]}s'})
    for dm in VERCEL_MOCK_DOMAINS:
        rows.append({"type": "Domain", "name": dm["name"], "detail": f'{dm["project"]} | {dm["dns_type"]}', "status": dm["status"], "metric": f'SSL: {dm["ssl"]}'})
    for p in VERCEL_MOCK_ANALYTICS["top_pages"]:
        rows.append({"type": "Page", "name": p["path"], "detail": f'{p["visitors"]:,} visitors', "status": "active", "metric": f'{p["views"]:,} views'})
    return jsonify(rows)


@app.route("/api/connectors/vercel/test-call", methods=["POST"])
def api_vercel_test_call():
    import time
    payload = request.get_json(force=True) or {}
    endpoint = payload.get("endpoint", "list-deployments")
    start = time.time()
    if endpoint == "list-deployments":
        response_body = {"deployments": [{"uid": d["uid"], "name": d["name"], "state": d["state"], "target": d["target"], "created": d["created"]} for d in VERCEL_MOCK_DEPLOYMENTS[:5]]}
    elif endpoint == "list-domains":
        response_body = {"domains": [{"name": dm["name"], "apexName": dm["name"].split(".")[-2]+"."+dm["name"].split(".")[-1], "verified": dm["status"]=="valid"} for dm in VERCEL_MOCK_DOMAINS[:5]]}
    elif endpoint == "get-project":
        response_body = {"id": "prj_abc123", "name": "camarad-app", "framework": "nextjs", "nodeVersion": "20.x", "buildCommand": "next build", "outputDirectory": ".next", "env": [{"key": "NEXT_PUBLIC_API_URL", "target": ["production","preview"]}, {"key": "DATABASE_URL", "target": ["production"]}]}
    elif endpoint == "create-deployment":
        response_body = {"id": "dpl_new001", "url": "camarad-app-new001.vercel.app", "name": "camarad-app", "state": "BUILDING", "target": "preview", "createdAt": 1707400000000}
    else:
        response_body = {"error": "Unknown endpoint", "available": ["list-deployments", "list-domains", "get-project", "create-deployment"]}
    elapsed = round((time.time() - start) * 1000, 1)
    return jsonify({
        "endpoint": endpoint,
        "method": "GET" if endpoint.startswith("list") or endpoint.startswith("get") else "POST",
        "response": {"status_code": 200, "headers": {"content-type": "application/json"}, "body": response_body},
        "latency_ms": elapsed,
        "quota": {"rate_limit": 100, "remaining": 87, "reset": "2026-02-08T16:00:00Z"}
    })


@app.route("/api/conversations", methods=["GET"])
@app.route("/api/chats", methods=["GET"])
def api_conversations():
    """List recent conversations for current user (for sidebar chat history)."""
    uid = get_current_user_id()
    cid = get_current_client_id()
    include_global = str(request.args.get("include_global") or "").strip().lower() in ("1", "true", "yes", "on")
    conn = get_db()
    _ensure_client_tables(conn)

    if cid is not None and not _client_owned(conn, uid, cid):
        conn.close()
        return jsonify([])

    sql = """
        SELECT c.id, c.workspace_slug, c.agent_slug, c.title, c.created_at, c.client_id,
               (SELECT content FROM messages WHERE conv_id = c.id ORDER BY timestamp DESC LIMIT 1) as last_message,
               (SELECT MAX(timestamp) FROM messages WHERE conv_id = c.id) as last_activity,
               (SELECT COUNT(*) FROM messages WHERE conv_id = c.id) as msg_count,
               ac.custom_name,
               ac.avatar_base64
        FROM conversations c
        LEFT JOIN agents_config ac ON ac.user_id = c.user_id AND ac.agent_slug = c.agent_slug
        WHERE c.user_id = ?
    """
    params = [uid]
    if cid is not None:
        if include_global:
            sql += " AND COALESCE(c.client_id, 0) IN (?, 0)"
            params.append(cid)
        else:
            sql += " AND COALESCE(c.client_id, 0) = ?"
            params.append(cid)

    sql += """
        ORDER BY COALESCE((SELECT MAX(timestamp) FROM messages WHERE conv_id = c.id), c.created_at) DESC
        LIMIT 30
    """

    rows = conn.execute(sql, tuple(params)).fetchall()
    conn.close()

    convs = []
    for r in rows:
        ws_slug = r[1] or "agency"
        agent_slug = r[2] or "agent"

        ws_name = workspaces.get(ws_slug, {}).get("name")
        if not ws_name:
            ws_name = ws_slug.replace("-", " ").title()

        custom_name = (r[9] or "").strip() if len(r) > 9 else ""
        try:
            default_agent_name = get_agent_name(ws_slug, agent_slug)
        except Exception:
            default_agent_name = agent_slug.replace("-", " ").title()

        agent_name = custom_name or default_agent_name or agent_slug.replace("-", " ").title()
        title = (r[3] or "").strip() or agent_name

        last_msg = (r[6] or "").strip()
        if len(last_msg) > 140:
            last_msg = last_msg[:140] + "…"

        convs.append({
            "id": r[0],
            "workspace_slug": ws_slug,
            "workspace_name": ws_name,
            "agent_slug": agent_slug,
            "agent_name": agent_name,
            "title": title,
            "created_at": r[4],
            "client_id": r[5],
            "last_message": last_msg,
            "last_activity": r[7] or r[4],
            "last_message_at": r[7] or r[4],
            "msg_count": int(r[8] or 0),
            "unread": 0,
            "has_photo": bool(r[10]),
            "avatar_base64": r[10] or None,
        })

    return jsonify(convs)


@app.route("/api/conversations/new", methods=["POST"])
@app.route("/api/chats", methods=["POST"])
def api_new_conversation():
    """Create a new conversation for an agent/workspace and return redirect URL."""
    uid = get_current_user_id()
    cid = get_current_client_id()
    data = request.get_json(force=True, silent=True) or {}

    conn = get_db()
    _ensure_client_tables(conn)
    if cid is not None and not _client_owned(conn, uid, cid):
        conn.close()
        return jsonify({"error": "Client not found or not owned"}), 404

    settings = _load_user_settings(conn, uid)
    conn.close()

    default_ws = str((settings.get("preferences") or {}).get("default_workspace") or "agency").strip().lower()
    if default_ws not in VALID_WORKSPACES:
        default_ws = "agency"

    ws_input = str(data.get("workspace_slug") or data.get("workspace") or default_ws).strip()
    ws_slug = ws_input.lower().replace(" ", "-")
    if ws_slug not in workspaces:
        ws_match = next((k for k, v in workspaces.items() if str(v.get("name", "")).lower() == ws_input.lower()), None)
        ws_slug = ws_match or default_ws

    agent_slug = str(data.get("agent_slug") or "").strip()
    ws_agents = list((workspaces.get(ws_slug, {}).get("agents") or {}).keys())

    known_agent_slugs = set()
    for ws_data in workspaces.values():
        known_agent_slugs.update((ws_data.get("agents") or {}).keys())

    if not agent_slug:
        agent_slug = ws_agents[0] if ws_agents else "ppc-specialist"
    elif agent_slug not in known_agent_slugs:
        conn = get_db()
        check_sql = "SELECT 1 FROM agents_config WHERE user_id = ? AND agent_slug = ?"
        check_params = [uid, agent_slug]
        if cid is not None:
            check_sql += " AND COALESCE(client_id, 0) = ?"
            check_params.append(cid)
        check_sql += " LIMIT 1"
        row = conn.execute(check_sql, tuple(check_params)).fetchone()
        conn.close()
        if not row:
            agent_slug = ws_agents[0] if ws_agents else "ppc-specialist"

    title = str(data.get("title") or "").strip()
    if len(title) > 120:
        title = title[:120]
    try:
        conv_id = create_new_conversation(uid, ws_slug, agent_slug, title, client_id=cid)
    except Exception as exc:
        if "no such table" in str(exc).lower() and "conversation" in str(exc).lower():
            init_db()
            conv_id = create_new_conversation(uid, ws_slug, agent_slug, title, client_id=cid)
        else:
            raise

    redirect_url = f"/chat/{ws_slug}/{agent_slug}?conv_id={conv_id}"

    return jsonify({
        "success": True,
        "conv_id": conv_id,
        "chat_id": conv_id,
        "redirect": redirect_url,
        "url": redirect_url,
        "client_id": cid,
    })


@app.route("/api/conversations/<int:conv_id>", methods=["DELETE"])
def api_delete_conversation(conv_id):
    """Delete a conversation and its messages"""
    uid = get_current_user_id()
    cid = get_current_client_id()
    conn = get_db()
    _ensure_client_tables(conn)

    sql = "SELECT id FROM conversations WHERE id = ? AND user_id = ?"
    params = [conv_id, uid]
    if cid is not None:
        if not _client_owned(conn, uid, cid):
            conn.close()
            return jsonify({"error": "Not found"}), 404
        sql += " AND COALESCE(client_id, 0) = ?"
        params.append(cid)

    row = conn.execute(sql, tuple(params)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404

    conn.execute("DELETE FROM messages WHERE conv_id = ?", (conv_id,))
    conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Conversation deleted"})


@app.route("/api/conversations/<int:conv_id>/messages", methods=["GET"])
def api_conversation_messages(conv_id):
    """Get all messages for a conversation"""
    uid = get_current_user_id()
    cid = get_current_client_id()
    conn = get_db()
    _ensure_client_tables(conn)

    sql = "SELECT id FROM conversations WHERE id = ? AND user_id = ?"
    params = [conv_id, uid]
    if cid is not None:
        if not _client_owned(conn, uid, cid):
            conn.close()
            return jsonify({"error": "Not found"}), 404
        sql += " AND COALESCE(client_id, 0) = ?"
        params.append(cid)

    row = conn.execute(sql, tuple(params)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404

    messages = get_messages(conv_id)
    conn.close()
    return jsonify(messages)


@app.route("/api/clients", methods=["GET", "POST"])
def api_clients():
    uid = get_current_user_id()
    conn = get_db()
    _ensure_client_tables(conn)

    if request.method == "GET":
        rows = conn.execute(
            """
            SELECT
                c.id,
                c.user_id,
                c.type,
                c.name,
                c.company_name,
                c.email,
                c.website,
                c.phone,
                c.address,
                c.notes,
                c.created_at,
                c.updated_at,
                COALESCE(COUNT(cc.id), 0) AS account_count
            FROM clients c
            LEFT JOIN client_connectors cc ON cc.client_id = c.id
            WHERE c.user_id = ?
            GROUP BY c.id
            ORDER BY c.updated_at DESC, c.id DESC
            """,
            (uid,),
        ).fetchall()
        conn.close()

        out = []
        for r in rows:
            row = dict(r)
            display_name = (row.get("company_name") or row.get("name") or f"Client {row.get('id')}").strip()
            row["display_name"] = display_name
            try:
                row["account_count"] = int(row.get("account_count") or 0)
            except Exception:
                row["account_count"] = 0
            out.append(row)
        return jsonify(out)

    data = request.get_json(force=True, silent=True) or {}
    ctype = str(data.get("type") or "person").strip().lower()
    if ctype not in ("person", "company"):
        ctype = "person"

    name = str(data.get("name") or "").strip()
    company_name = str(data.get("company_name") or "").strip()

    if ctype == "person" and not name:
        name = "New Client"
    if ctype == "company" and not company_name:
        company_name = name or "New Company"

    cursor = conn.execute(
        """
        INSERT INTO clients (user_id, type, name, company_name, email, website, phone, address, notes, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            uid,
            ctype,
            name,
            company_name,
            str(data.get("email") or "").strip(),
            str(data.get("website") or "").strip(),
            str(data.get("phone") or "").strip(),
            str(data.get("address") or "").strip(),
            str(data.get("notes") or "").strip(),
        ),
    )
    client_id = cursor.lastrowid
    conn.commit()

    row = conn.execute(
        """
        SELECT id, user_id, type, name, company_name, email, website, phone, address, notes, created_at, updated_at
        FROM clients
        WHERE id = ? AND user_id = ?
        LIMIT 1
        """,
        (client_id, uid),
    ).fetchone()
    conn.close()

    out = dict(row)
    out["display_name"] = (out.get("company_name") or out.get("name") or f"Client {out.get('id')}").strip()
    out["account_count"] = 0
    return jsonify({"success": True, "client": out})


@app.route("/api/clients/<int:client_id>", methods=["GET", "PATCH", "DELETE"])
def api_client_detail(client_id):
    uid = get_current_user_id()
    conn = get_db()
    _ensure_client_tables(conn)

    row = conn.execute(
        """
        SELECT id, user_id, type, name, company_name, email, website, phone, address, notes, created_at, updated_at
        FROM clients
        WHERE id = ? AND user_id = ?
        LIMIT 1
        """,
        (client_id, uid),
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Client not found or not owned"}), 404

    if request.method == "GET":
        out = dict(row)
        out["display_name"] = (out.get("company_name") or out.get("name") or f"Client {out.get('id')}").strip()
        try:
            count_row = conn.execute("SELECT COUNT(*) FROM client_connectors WHERE client_id = ?", (client_id,)).fetchone()
            out["account_count"] = int((count_row[0] if count_row else 0) or 0)
        except Exception:
            out["account_count"] = 0
        conn.close()
        return jsonify(out)

    if request.method == "DELETE":
        removed_links = conn.execute("DELETE FROM client_connectors WHERE client_id = ?", (client_id,)).rowcount
        try:
            conn.execute("UPDATE flows SET client_id = NULL WHERE user_id = ? AND client_id = ?", (uid, client_id))
            conn.execute("UPDATE conversations SET client_id = NULL WHERE user_id = ? AND client_id = ?", (uid, client_id))
            conn.execute("UPDATE agents_config SET client_id = 0 WHERE user_id = ? AND client_id = ?", (uid, client_id))
            conn.execute("UPDATE connectors_config SET client_id = 0 WHERE user_id = ? AND client_id = ?", (uid, client_id))
        except Exception:
            pass
        conn.execute("DELETE FROM clients WHERE id = ? AND user_id = ?", (client_id, uid))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "removed_links": int(removed_links or 0)})

    data = request.get_json(force=True, silent=True) or {}
    allowed = ["type", "name", "company_name", "email", "website", "phone", "address", "notes"]
    sets = []
    params = []
    for key in allowed:
        if key in data:
            if key == "type":
                val = str(data.get(key) or "person").strip().lower()
                if val not in ("person", "company"):
                    val = "person"
                params.append(val)
            else:
                params.append(str(data.get(key) or "").strip())
            sets.append(f"{key} = ?")

    if not sets:
        conn.close()
        return jsonify({"error": "No fields to update"}), 400

    sets.append("updated_at = datetime('now')")
    params.extend([client_id, uid])
    conn.execute(f"UPDATE clients SET {', '.join(sets)} WHERE id = ? AND user_id = ?", tuple(params))
    conn.commit()

    updated = conn.execute(
        """
        SELECT id, user_id, type, name, company_name, email, website, phone, address, notes, created_at, updated_at
        FROM clients
        WHERE id = ? AND user_id = ?
        LIMIT 1
        """,
        (client_id, uid),
    ).fetchone()

    try:
        count_row = conn.execute("SELECT COUNT(*) FROM client_connectors WHERE client_id = ?", (client_id,)).fetchone()
        account_count = int((count_row[0] if count_row else 0) or 0)
    except Exception:
        account_count = 0

    conn.close()

    out = dict(updated)
    out["display_name"] = (out.get("company_name") or out.get("name") or f"Client {out.get('id')}").strip()
    out["account_count"] = account_count
    return jsonify({"success": True, "client": out})


@app.route("/api/client_connectors", methods=["GET", "POST"])
def api_client_connectors():
    uid = get_current_user_id()
    conn = get_db()
    _ensure_client_tables(conn)

    if request.method == "GET":
        cid = request.args.get("client_id", type=int) or get_current_client_id()
        if not cid or not _client_owned(conn, uid, cid):
            conn.close()
            return jsonify([])

        rows = conn.execute(
            """
            SELECT id, client_id, connector_slug, account_id, account_name, status, config_json, last_synced, created_at, updated_at
            FROM client_connectors
            WHERE client_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (cid,),
        ).fetchall()
        conn.close()

        out = []
        for r in rows:
            row = dict(r)
            try:
                row["config"] = json.loads(row.get("config_json") or "{}")
            except Exception:
                row["config"] = {}
            out.append(row)
        return jsonify(out)

    data = request.get_json(force=True, silent=True) or {}
    cid = data.get("client_id")
    try:
        cid = int(cid)
    except (TypeError, ValueError):
        cid = None

    if not cid or not _client_owned(conn, uid, cid):
        conn.close()
        return jsonify({"error": "Client not found or not owned"}), 404

    slug = str(data.get("connector_slug") or "").strip()
    if not slug:
        conn.close()
        return jsonify({"error": "connector_slug is required"}), 400

    status = str(data.get("status") or "pending").strip().lower()
    if status not in ("pending", "connected", "error", "disconnected"):
        status = "pending"

    cfg = data.get("config")
    if not isinstance(cfg, dict):
        cfg = {}

    cursor = conn.execute(
        """
        INSERT INTO client_connectors (client_id, connector_slug, account_id, account_name, status, config_json, last_synced, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, CASE WHEN ? = 'connected' THEN datetime('now') ELSE NULL END, datetime('now'))
        """,
        (
            cid,
            slug,
            str(data.get("account_id") or "").strip(),
            str(data.get("account_name") or "").strip(),
            status,
            json.dumps(cfg),
            status,
        ),
    )
    link_id = cursor.lastrowid
    conn.commit()

    row = conn.execute(
        """
        SELECT id, client_id, connector_slug, account_id, account_name, status, config_json, last_synced, created_at, updated_at
        FROM client_connectors
        WHERE id = ?
        LIMIT 1
        """,
        (link_id,),
    ).fetchone()
    conn.close()

    out = dict(row)
    try:
        out["config"] = json.loads(out.get("config_json") or "{}")
    except Exception:
        out["config"] = {}
    return jsonify({"success": True, "client_connector": out})


@app.route("/api/client_connectors/<int:link_id>", methods=["PATCH"])
def api_patch_client_connector(link_id):
    uid = get_current_user_id()
    conn = get_db()
    _ensure_client_tables(conn)

    row = conn.execute(
        """
        SELECT cc.id, cc.client_id
        FROM client_connectors cc
        JOIN clients c ON c.id = cc.client_id
        WHERE cc.id = ? AND c.user_id = ?
        LIMIT 1
        """,
        (link_id, uid),
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Client connector not found or not owned"}), 404

    data = request.get_json(force=True, silent=True) or {}
    sets = []
    params = []

    if "status" in data:
        status = str(data.get("status") or "pending").strip().lower()
        if status not in ("pending", "connected", "error", "disconnected"):
            status = "pending"
        sets.append("status = ?")
        params.append(status)
        if status == "connected":
            sets.append("last_synced = datetime('now')")

    if "account_id" in data:
        sets.append("account_id = ?")
        params.append(str(data.get("account_id") or "").strip())

    if "account_name" in data:
        sets.append("account_name = ?")
        params.append(str(data.get("account_name") or "").strip())

    if "config" in data:
        cfg = data.get("config")
        if not isinstance(cfg, dict):
            cfg = {}
        sets.append("config_json = ?")
        params.append(json.dumps(cfg))

    if not sets:
        conn.close()
        return jsonify({"error": "No fields to update"}), 400

    sets.append("updated_at = datetime('now')")
    params.append(link_id)

    conn.execute(f"UPDATE client_connectors SET {', '.join(sets)} WHERE id = ?", tuple(params))
    conn.commit()

    updated = conn.execute(
        """
        SELECT id, client_id, connector_slug, account_id, account_name, status, config_json, last_synced, created_at, updated_at
        FROM client_connectors
        WHERE id = ?
        LIMIT 1
        """,
        (link_id,),
    ).fetchone()
    conn.close()

    out = dict(updated)
    try:
        out["config"] = json.loads(out.get("config_json") or "{}")
    except Exception:
        out["config"] = {}
    return jsonify({"success": True, "client_connector": out})


@app.route("/api/settings/user", methods=["GET", "PATCH"])
def api_user_settings():
    uid = get_current_user_id()
    conn = get_db()
    _ensure_user_settings_table(conn)

    current = _load_user_settings(conn, uid)

    if request.method == "GET":
        conn.close()
        return jsonify({"success": True, "settings": current})

    payload = request.get_json(force=True, silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}

    payload = copy.deepcopy(payload)
    economy_patch = payload.get("economy") if isinstance(payload.get("economy"), dict) else {}
    economy_patch = copy.deepcopy(economy_patch) if isinstance(economy_patch, dict) else {}

    for key in ("preset", "cost_multiplier", "monthly_grant", "max_per_message", "daily_limit", "monthly_reset_day", "monthly_reset_hour", "monthly_reset_minute"):
        if key in payload:
            economy_patch[key] = payload.pop(key)

    incoming_preset = str(economy_patch.get("preset") or "").strip().lower()
    if incoming_preset == "starter":
        incoming_preset = "free"
        economy_patch["preset"] = "free"
    if incoming_preset in VALID_ECONOMY_PRESETS:
        if incoming_preset in ("pro", "enterprise"):
            summary, _gw = _stripe_billing_summary()
            if not _stripe_subscription_active(summary):
                conn.close()
                return jsonify({
                    "success": False,
                    "error": "subscription_required",
                    "message": "Paid plans require active Stripe subscription. Open Billing to upgrade.",
                    "requires_billing": True,
                }), 402
        economy_patch["preset"] = incoming_preset
        base = PRICING_PRESETS[incoming_preset]
        for econ_key in ("cost_multiplier", "monthly_grant", "max_per_message", "daily_limit", "monthly_reset_day", "monthly_reset_hour", "monthly_reset_minute"):
            if econ_key not in economy_patch:
                economy_patch[econ_key] = base[econ_key]

    if economy_patch:
        payload["economy"] = economy_patch

    merged = _deep_merge_dict(current, payload if isinstance(payload, dict) else {})
    saved = _save_user_settings(conn, uid, merged)
    conn.commit()
    conn.close()
    return jsonify({"success": True, "settings": saved})


@app.route("/api/settings/billing/plan", methods=["POST"])
def api_settings_billing_plan():
    uid = get_current_user_id()
    data = request.get_json(force=True, silent=True) or {}
    target_plan = _normalize_plan_code(data.get("plan"))
    if target_plan == "starter":
        target_plan = "free"
    if target_plan not in VALID_ECONOMY_PRESETS:
        return jsonify({"success": False, "error": "invalid_plan"}), 400

    if target_plan in ("pro", "enterprise"):
        summary, gw = _stripe_billing_summary()
        if not _stripe_subscription_active(summary):
            checkout_url = None
            if COOLBITS_GATEWAY_ENABLED:
                for path in ("/api/billing/upgrade", "/api/billing/checkout-session", "/api/billing/checkout", "/api/billing/subscribe"):
                    try:
                        status, payload, _text = _coolbits_request("POST", path, body={"plan": target_plan}, timeout=20)
                        if 200 <= int(status) < 300 and isinstance(payload, dict):
                            checkout_url = payload.get("url") or payload.get("checkout_url") or payload.get("checkoutUrl")
                            if checkout_url:
                                break
                    except Exception:
                        pass
            return jsonify({
                "success": False,
                "error": "subscription_required",
                "message": "Paid plans require active subscription. Continue in Billing/Stripe first.",
                "requires_billing": True,
                "checkout_url": checkout_url,
                "source": "coolbits" if summary is not None else "mock",
                "gateway": gw,
            }), 402

    conn = get_db()
    _ensure_user_settings_table(conn)
    try:
        saved = _apply_economy_preset(conn, uid, target_plan)
        conn.commit()
    finally:
        conn.close()

    return jsonify({"success": True, "settings": saved, "plan": target_plan})


@app.route("/api/settings/billing/checkout", methods=["POST"])
def api_settings_billing_checkout():
    data = request.get_json(force=True, silent=True) or {}
    plan = str(data.get("plan") or "pro").strip().lower()
    if plan not in ("starter", "pro", "enterprise", "free"):
        plan = "pro"
    if not COOLBITS_GATEWAY_ENABLED:
        return jsonify({"success": False, "error": "gateway_disabled"}), 400

    last_error = None
    for path in ("/api/billing/upgrade", "/api/billing/checkout-session", "/api/billing/checkout", "/api/billing/subscribe"):
        try:
            status, payload, text = _coolbits_request("POST", path, body={"plan": plan}, timeout=25)
            if 200 <= int(status) < 300 and isinstance(payload, dict):
                checkout_url = payload.get("checkoutUrl") or payload.get("checkout_url") or payload.get("url")
                if checkout_url:
                    return jsonify({"success": True, "url": checkout_url, "source": "coolbits", "path": path})
                last_error = f"{path}: missing checkout url"
                continue
            last_error = f"{path}: http_{status}"
            if isinstance(payload, dict) and payload.get("error"):
                last_error += f" ({payload.get('error')})"
            elif text:
                last_error += f" ({text[:160]})"
        except Exception as e:
            last_error = f"{path}: {e}"

    return jsonify({"success": False, "error": "checkout_unavailable", "detail": last_error or "no_checkout_path"}), 502


@app.route("/api/settings/user/reset", methods=["POST"])
def api_user_settings_reset():
    uid = get_current_user_id()
    conn = get_db()
    _ensure_user_settings_table(conn)
    saved = _save_user_settings(conn, uid, DEFAULT_USER_SETTINGS)
    conn.commit()
    conn.close()
    return jsonify({"success": True, "settings": saved})


@app.route("/api/settings/summary", methods=["GET"])
def api_settings_summary():
    uid = get_current_user_id()
    cid = get_current_client_id()

    conn = get_db()
    cursor = conn.cursor()
    _migrate_flows_table(conn)
    _ensure_client_tables(conn)

    def _count(sql, params=()):
        try:
            row = cursor.execute(sql, params).fetchone()
            if not row:
                return 0
            return int(row[0] or 0)
        except Exception:
            return 0

    if cid is not None and not _client_owned(conn, uid, cid):
        counts = {
            "agents": 0,
            "connectors": 0,
            "connected_connectors": 0,
            "flows": 0,
            "templates": 0,
            "chats": 0,
            "clients": 0,
            "client_accounts": 0,
        }
        conn.close()
        return jsonify({"success": True, "counts": counts})

    if cid is None:
        agents_count = _count("SELECT COUNT(*) FROM agents_config WHERE user_id = ?", (uid,))
        connectors_count = _count("SELECT COUNT(*) FROM connectors_config WHERE user_id = ?", (uid,))
        connected_count = _count("SELECT COUNT(*) FROM connectors_config WHERE user_id = ? AND lower(status) = 'connected'", (uid,))
        flows_count = _count("SELECT COUNT(*) FROM flows WHERE user_id = ? AND COALESCE(is_template, 0) = 0", (uid,))
        templates_count = _count("SELECT COUNT(*) FROM flows WHERE user_id = ? AND COALESCE(is_template, 0) = 1", (uid,))
        chats_count = _count("SELECT COUNT(*) FROM conversations WHERE user_id = ?", (uid,))
        clients_count = _count("SELECT COUNT(*) FROM clients WHERE user_id = ?", (uid,))
        client_accounts = _count(
            """
            SELECT COUNT(*)
            FROM client_connectors cc
            JOIN clients c ON c.id = cc.client_id
            WHERE c.user_id = ?
            """,
            (uid,),
        )
    else:
        agents_count = _count("SELECT COUNT(*) FROM agents_config WHERE user_id = ? AND COALESCE(client_id, 0) = ?", (uid, cid))
        connectors_count = _count("SELECT COUNT(*) FROM client_connectors WHERE client_id = ?", (cid,))
        connected_count = _count("SELECT COUNT(*) FROM client_connectors WHERE client_id = ? AND lower(status) = 'connected'", (cid,))
        flows_count = _count("SELECT COUNT(*) FROM flows WHERE user_id = ? AND COALESCE(is_template, 0) = 0 AND COALESCE(client_id, 0) = ?", (uid, cid))
        templates_count = _count("SELECT COUNT(*) FROM flows WHERE user_id = ? AND COALESCE(is_template, 0) = 1 AND COALESCE(client_id, 0) = ?", (uid, cid))
        chats_count = _count("SELECT COUNT(*) FROM conversations WHERE user_id = ? AND COALESCE(client_id, 0) = ?", (uid, cid))
        clients_count = _count("SELECT COUNT(*) FROM clients WHERE user_id = ?", (uid,))
        client_accounts = _count("SELECT COUNT(*) FROM client_connectors WHERE client_id = ?", (cid,))

    conn.close()

    return jsonify({
        "success": True,
        "counts": {
            "agents": int(agents_count or 0),
            "connectors": int(connectors_count or 0),
            "connected_connectors": int(connected_count or 0),
            "flows": int(flows_count or 0),
            "templates": int(templates_count or 0),
            "chats": int(chats_count or 0),
            "clients": int(clients_count or 0),
            "client_accounts": int(client_accounts or 0),
        }
    })


@app.route("/api/settings/billing", methods=["GET"])
def api_settings_billing():
    uid = get_current_user_id()
    cid = get_current_client_id()

    conn = get_db()
    _ensure_user_settings_table(conn)
    _ensure_client_tables(conn)
    _ensure_usage_ledger_table(conn)

    if cid is not None and not _client_owned(conn, uid, cid):
        conn.close()
        return jsonify({"success": False, "error": "Client not found or not owned"}), 404

    runtime = _get_user_ct_snapshot(conn, uid, client_id=cid)
    conn.commit()
    conn.close()

    payload, gw = _stripe_billing_summary()
    if isinstance(payload, dict):
        eur_payload = _billing_payload_to_eur(payload)
        plan = eur_payload.get("plan") if isinstance(eur_payload.get("plan"), dict) else {}
        current_code = _normalize_plan_code(plan.get("code"))
        return jsonify({
            "success": True,
            "source": "coolbits",
            "gateway": gw,
            "billing": eur_payload,
            "runtime": runtime,
            "plans": PRICING_PLAN_CATALOG,
            "current_plan_code": current_code,
        })

    current_code = _normalize_plan_code(runtime.get("economy_preset") or runtime.get("plan"))
    return jsonify({
        "success": True,
        "source": "mock",
        "gateway": gw,
        "billing": {
            "plan": {
                "code": str(runtime.get("economy_preset") or "free"),
                "label": "CoolBits Starter",
                "price": {"currency": "eur", "amount": 6, "interval": "month"},
            },
            "limits": {
                "tokensPerMonth": int(runtime.get("ct_monthly_limit") or 0),
            },
            "usage": {
                "tokensRemaining": int(runtime.get("ct_balance") or 0),
                "tokensUsedThisPeriod": int(runtime.get("ct_used_month") or 0),
                "usagePct": int(runtime.get("ct_usage_pct") or 0),
                "nearCap": bool(runtime.get("low_balance") or False),
            },
            "stripe": {
                "mode": "live",
                "customerId": None,
                "subscriptionId": None,
                "status": "inactive",
                "currentPeriodEnd": None,
                "fromStripe": False,
            },
            "trial": {"active": False, "endsAt": None},
        },
        "runtime": runtime,
        "plans": PRICING_PLAN_CATALOG,
        "current_plan_code": current_code,
    })


def _billing_internal_authorized():
    expected = str(BILLING_INTERNAL_TOKEN or "").strip()
    if not expected:
        return False
    incoming = str(request.headers.get("X-Internal-Token") or "").strip()
    return bool(incoming) and incoming == expected


def _pct(values, p):
    vals = [float(v) for v in (values or []) if v is not None]
    if not vals:
        return None
    vals.sort()
    if len(vals) == 1:
        return round(vals[0], 6)
    pr = max(0.0, min(100.0, float(p)))
    idx = int(round((pr / 100.0) * (len(vals) - 1)))
    idx = max(0, min(len(vals) - 1, idx))
    return round(vals[idx], 6)


def _dist(values):
    return {
        "p50": _pct(values, 50),
        "p90": _pct(values, 90),
        "p95": _pct(values, 95),
        "p99": _pct(values, 99),
    }


def _current_ct_rate_row(conn):
    return conn.execute(
        """
        SELECT id, version, ct_value_usd, effective_from
        FROM ct_rates
        WHERE is_active = 1
          AND (effective_to IS NULL OR effective_to = '')
        ORDER BY effective_from DESC
        LIMIT 1
        """
    ).fetchone()


def _billing_calibration_proposal(conn, window_hours=48):
    try:
        wh = int(window_hours or 48)
    except Exception:
        wh = 48
    wh = max(1, min(24 * 30, wh))

    _ensure_usage_ledger_table(conn)
    current = _current_ct_rate_row(conn)
    if not current:
        _ensure_pricing_engine_tables(conn)
        current = _current_ct_rate_row(conn)

    current_ct = float(current["ct_value_usd"] or SHADOW_DEFAULT_CT_VALUE_USD) if current else float(SHADOW_DEFAULT_CT_VALUE_USD)
    current_ver = int(current["version"] or 1) if current else 1

    cov = conn.execute(
        """
        SELECT
          COALESCE(SUM(CASE WHEN (input_tokens > 0 OR output_tokens > 0) THEN 1 ELSE 0 END), 0) AS rows_with_tokens,
          COALESCE(SUM(CASE WHEN billable_usd IS NOT NULL AND billable_usd > 0 THEN 1 ELSE 0 END), 0) AS rows_with_billable,
          COALESCE(SUM(CASE WHEN status = 'ok' THEN COALESCE(ct_actual_debit, 0) ELSE 0 END), 0) AS ct_actual_sum,
          COALESCE(SUM(CASE WHEN status = 'ok' THEN COALESCE(billable_usd, 0) ELSE 0 END), 0) AS billable_sum_usd
        FROM usage_ledger
        WHERE created_at >= datetime('now', ?)
        """,
        (f"-{wh} hour",),
    ).fetchone()

    rows_with_tokens = int((cov["rows_with_tokens"] if cov else 0) or 0)
    rows_with_billable = int((cov["rows_with_billable"] if cov else 0) or 0)
    ct_actual_sum = int((cov["ct_actual_sum"] if cov else 0) or 0)
    billable_sum_usd = float((cov["billable_sum_usd"] if cov else 0) or 0)

    implied = None
    if ct_actual_sum > 0 and billable_sum_usd > 0:
        implied = float(billable_sum_usd) / float(ct_actual_sum)

    reasons = []
    if rows_with_tokens < int(CALIBRATION_MIN_ROWS_WITH_TOKENS):
        reasons.append(f"rows_with_tokens<{int(CALIBRATION_MIN_ROWS_WITH_TOKENS)}")
    if rows_with_billable < int(CALIBRATION_MIN_ROWS_WITH_BILLABLE):
        reasons.append(f"rows_with_billable<{int(CALIBRATION_MIN_ROWS_WITH_BILLABLE)}")
    if ct_actual_sum < int(CALIBRATION_MIN_CT_ACTUAL_SUM):
        reasons.append(f"ct_actual_sum<{int(CALIBRATION_MIN_CT_ACTUAL_SUM)}")
    if billable_sum_usd < float(CALIBRATION_MIN_BILLABLE_USD):
        reasons.append(f"billable_sum_usd<{float(CALIBRATION_MIN_BILLABLE_USD)}")
    if implied is None or implied <= 0:
        reasons.append("implied_ct_value_unavailable")

    lower = float(current_ct) * (1.0 - float(CALIBRATION_MAX_DELTA_PCT))
    upper = float(current_ct) * (1.0 + float(CALIBRATION_MAX_DELTA_PCT))
    clamped = None
    proposed = None
    if implied is not None and implied > 0:
        clamped = max(float(lower), min(float(upper), float(implied)))
        alpha = max(0.0, min(1.0, float(CALIBRATION_ALPHA)))
        proposed = ((1.0 - alpha) * float(current_ct)) + (alpha * float(clamped))

    insufficient = len(reasons) > 0
    base_score = 0.0
    try:
        base_score += min(1.0, rows_with_tokens / max(1.0, float(CALIBRATION_MIN_ROWS_WITH_TOKENS)))
        base_score += min(1.0, rows_with_billable / max(1.0, float(CALIBRATION_MIN_ROWS_WITH_BILLABLE)))
        base_score += min(1.0, ct_actual_sum / max(1.0, float(CALIBRATION_MIN_CT_ACTUAL_SUM)))
        base_score += min(1.0, billable_sum_usd / max(0.000001, float(CALIBRATION_MIN_BILLABLE_USD)))
        base_score = base_score / 4.0
    except Exception:
        base_score = 0.0
    confidence = round(max(0.0, min(1.0, base_score)), 3)

    return {
        "window_hours": int(wh),
        "insufficient_data": bool(insufficient),
        "reasons": reasons,
        "current_ct_value_usd": float(round(float(current_ct), 10)),
        "current_ct_rate_id": str(current["id"] or "") if current else None,
        "current_ct_rate_version": int(current_ver),
        "implied_ct_value_usd": (float(round(implied, 10)) if implied is not None else None),
        "clamped_ct_value_usd": (float(round(clamped, 10)) if clamped is not None else None),
        "proposed_ct_value_usd": (float(round(proposed, 10)) if proposed is not None else None),
        "max_delta_pct": float(CALIBRATION_MAX_DELTA_PCT),
        "alpha": float(CALIBRATION_ALPHA),
        "coverage": {
            "rows_with_tokens": int(rows_with_tokens),
            "rows_with_billable": int(rows_with_billable),
            "ct_actual_sum": int(ct_actual_sum),
            "billable_sum_usd": float(round(billable_sum_usd, 6)),
        },
        "confidence": {
            "score": confidence,
            "notes": ([] if insufficient else ["good_coverage"]),
        },
    }


@app.route("/api/billing/plan-recommendations", methods=["GET"])
def api_billing_plan_recommendations():
    if not _billing_internal_authorized():
        return jsonify({"error": "forbidden"}), 403

    try:
        window_days = int(request.args.get("window_days", 7) or 7)
    except Exception:
        window_days = 7
    window_days = max(1, min(30, window_days))

    try:
        min_rows_with_tokens = int(request.args.get("min_rows_with_tokens", 500) or 500)
    except Exception:
        min_rows_with_tokens = 500
    try:
        min_workspaces = int(request.args.get("min_workspaces", 3) or 3)
    except Exception:
        min_workspaces = 3
    min_rows_with_tokens = max(1, min(50000, min_rows_with_tokens))
    min_workspaces = max(1, min(1000, min_workspaces))

    conn = get_db()
    _ensure_usage_ledger_table(conn)

    rows = conn.execute(
        """
        SELECT
          created_at,
          COALESCE(workspace_id, '') AS workspace_id,
          COALESCE(input_tokens, 0) AS input_tokens,
          COALESCE(output_tokens, 0) AS output_tokens,
          COALESCE(cost_final_usd, 0) AS cost_final_usd,
          COALESCE(billable_usd, 0) AS billable_usd,
          COALESCE(ct_actual_debit, 0) AS ct_actual_debit,
          COALESCE(latency_ms, 0) AS latency_ms
        FROM usage_ledger
        WHERE status = 'ok'
          AND created_at >= datetime('now', ?)
        """,
        (f"-{int(window_days)} day",),
    ).fetchall()

    rows_total = len(rows or [])
    rows_with_tokens = 0
    rows_with_cost = 0
    rows_with_billable = 0
    workspaces = set()

    cost_values = []
    billable_values = []
    output_values = []
    latency_values = []

    by_ws_day = {}
    for r in (rows or []):
        ws = str(r["workspace_id"] or "").strip() or "unknown"
        workspaces.add(ws)
        input_tokens = int(r["input_tokens"] or 0)
        output_tokens = int(r["output_tokens"] or 0)
        cost_final_usd = float(r["cost_final_usd"] or 0)
        billable_usd = float(r["billable_usd"] or 0)
        ct_actual = int(r["ct_actual_debit"] or 0)
        latency_ms = int(r["latency_ms"] or 0)
        created_at = str(r["created_at"] or "")
        day = created_at[:10] if created_at else ""

        if (input_tokens + output_tokens) > 0:
            rows_with_tokens += 1
        if cost_final_usd > 0:
            rows_with_cost += 1
            cost_values.append(cost_final_usd)
        if billable_usd > 0:
            rows_with_billable += 1
            billable_values.append(billable_usd)
        if output_tokens > 0:
            output_values.append(output_tokens)
        if latency_ms > 0:
            latency_values.append(latency_ms)

        key = (ws, day)
        acc = by_ws_day.get(key)
        if not acc:
            by_ws_day[key] = {"billable_usd": 0.0, "ct_actual": 0, "calls": 0}
            acc = by_ws_day[key]
        acc["billable_usd"] += billable_usd
        acc["ct_actual"] += ct_actual
        acc["calls"] += 1

    workspace_daily_billable = [v["billable_usd"] for v in by_ws_day.values() if float(v["billable_usd"] or 0) > 0]
    workspace_daily_ct_actual = [v["ct_actual"] for v in by_ws_day.values() if int(v["ct_actual"] or 0) > 0]
    workspace_daily_calls = [v["calls"] for v in by_ws_day.values() if int(v["calls"] or 0) > 0]

    cost_dist = _dist(cost_values)
    billable_dist = _dist(billable_values)
    output_dist = _dist(output_values)
    latency_dist = _dist(latency_values)
    ws_daily_billable_dist = _dist(workspace_daily_billable)
    ws_daily_ct_dist = _dist(workspace_daily_ct_actual)
    ws_daily_calls_dist = _dist(workspace_daily_calls)

    current_rate = _current_ct_rate_row(conn)
    current_ct_value_usd = float(current_rate["ct_value_usd"] or SHADOW_DEFAULT_CT_VALUE_USD) if current_rate else float(SHADOW_DEFAULT_CT_VALUE_USD)
    conn.close()

    reasons = []
    if rows_with_tokens < int(min_rows_with_tokens):
        reasons.append(f"rows_with_tokens<{int(min_rows_with_tokens)}")
    if len(workspaces) < int(min_workspaces):
        reasons.append(f"distinct_workspaces<{int(min_workspaces)}")
    insufficient_data = len(reasons) > 0

    recommendations = None
    buffer_pct = float(SHADOW_DEFAULT_BUFFER_PCT)
    margin_pct = float(SHADOW_DEFAULT_MARGIN_PCT)
    multiplier = 1.0 + buffer_pct + margin_pct
    if not insufficient_data:
        cost_p90 = float(cost_dist.get("p90") or 0)
        cost_p95 = float(cost_dist.get("p95") or 0)
        cost_p99 = float(cost_dist.get("p99") or cost_p95 or cost_p90 or 0)
        out_p90 = int(round(float(output_dist.get("p90") or 0)))
        out_p95 = int(round(float(output_dist.get("p95") or out_p90 or 0)))
        out_p99 = int(round(float(output_dist.get("p99") or out_p95 or out_p90 or 0)))
        daily_p90 = float(ws_daily_billable_dist.get("p90") or 0)
        daily_p95 = float(ws_daily_billable_dist.get("p95") or daily_p90 or 0)

        free_cost = max(0.0005, min(cost_p90, (cost_p95 / 2.0 if cost_p95 > 0 else cost_p90)) * multiplier)
        standard_cost = max(free_cost, cost_p95 * multiplier)
        pro_cost = max(standard_cost, cost_p99 * multiplier)

        recommendations = {
            "free": {
                "max_cost_per_request_usd": round(free_cost, 6),
                "max_output_tokens": max(80, out_p90),
                "daily_burn_cap_usd": round(max(0.25, daily_p90 * 0.25), 6),
            },
            "standard": {
                "max_cost_per_request_usd": round(standard_cost, 6),
                "max_output_tokens": max(120, out_p95),
                "daily_burn_cap_usd": round(max(1.0, daily_p95 * 0.75), 6),
            },
            "pro": {
                "max_cost_per_request_usd": round(pro_cost, 6),
                "max_output_tokens": max(180, out_p99),
                "daily_burn_cap_usd": round(max(2.0, daily_p95 * 1.5), 6),
            },
        }

    return jsonify({
        "success": True,
        "read_only": True,
        "shadow_mode": True,
        "window_days": int(window_days),
        "coverage": {
            "rows_total": int(rows_total),
            "rows_with_tokens": int(rows_with_tokens),
            "rows_with_cost": int(rows_with_cost),
            "rows_with_billable": int(rows_with_billable),
            "distinct_workspaces": int(len(workspaces)),
        },
        "distributions": {
            "cost_final_usd_per_call": cost_dist,
            "billable_usd_per_call": billable_dist,
            "output_tokens_per_call": output_dist,
            "latency_ms_per_call": latency_dist,
        },
        "workspace_daily_billable_usd": ws_daily_billable_dist,
        "workspace_daily_ct_actual": ws_daily_ct_dist,
        "workspace_daily_calls": ws_daily_calls_dist,
        "insufficient_data": bool(insufficient_data),
        "reasons": reasons,
        "recommendations": recommendations,
        "current_ct_value_usd": round(current_ct_value_usd, 10),
        "buffer_pct": buffer_pct,
        "margin_pct": margin_pct,
        "generated_at": datetime.now().isoformat(),
    })


@app.route("/api/billing/calibration-proposal", methods=["GET"])
def api_billing_calibration_proposal():
    if not _billing_internal_authorized():
        return jsonify({"error": "forbidden"}), 403
    try:
        window_hours = int(request.args.get("window_hours", 48) or 48)
    except Exception:
        window_hours = 48
    conn = get_db()
    proposal = _billing_calibration_proposal(conn, window_hours=window_hours)
    conn.close()
    return jsonify({"success": True, **proposal})


@app.route("/api/billing/calibration-apply", methods=["POST"])
def api_billing_calibration_apply():
    if not _billing_internal_authorized():
        return jsonify({"error": "forbidden"}), 403
    payload = request.get_json(silent=True) or {}
    try:
        window_hours = int(payload.get("window_hours", 48) or 48)
    except Exception:
        window_hours = 48

    conn = get_db()
    _ensure_usage_ledger_table(conn)
    proposal = _billing_calibration_proposal(conn, window_hours=window_hours)
    if proposal.get("insufficient_data"):
        conn.close()
        return jsonify({"success": False, **proposal}), 409

    now_expr = "datetime('now')"
    if int(CALIBRATION_APPLY_DELAY_MINUTES) > 0:
        now_expr = f"datetime('now', '+{int(CALIBRATION_APPLY_DELAY_MINUTES)} minute')"

    current = _current_ct_rate_row(conn)
    next_version = int((current["version"] if current else 1) or 1) + 1
    new_id = str(uuid.uuid4())
    proposed = float(proposal["proposed_ct_value_usd"])

    try:
        conn.execute("BEGIN")
        if current and current["id"]:
            conn.execute(
                f"UPDATE ct_rates SET is_active = 0, effective_to = {now_expr} WHERE id = ?",
                (str(current["id"]),),
            )
        notes = json.dumps(
            {
                "scope": "shadow",
                "derived_from": f"implied_{int(proposal['window_hours'])}h",
                "max_delta_pct": float(CALIBRATION_MAX_DELTA_PCT),
                "alpha": float(CALIBRATION_ALPHA),
                "coverage": proposal.get("coverage") or {},
            },
            ensure_ascii=True,
        )
        conn.execute(
            f"""
            INSERT INTO ct_rates (id, ct_value_usd, effective_from, effective_to, version, is_active, notes)
            VALUES (?, ?, {now_expr}, NULL, ?, 1, ?)
            """,
            (new_id, float(proposed), int(next_version), notes[:1000]),
        )
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return jsonify({"success": False, "error": str(e)}), 500

    applied_row = conn.execute("SELECT id, ct_value_usd, effective_from, version FROM ct_rates WHERE id = ? LIMIT 1", (new_id,)).fetchone()
    conn.close()
    return jsonify({
        "success": True,
        "applied": True,
        "ct_rate_id": str(applied_row["id"] if applied_row else new_id),
        "effective_from": str(applied_row["effective_from"] if applied_row else ""),
        "proposed_ct_value_usd": float(applied_row["ct_value_usd"] if applied_row else proposed),
        "version": int(applied_row["version"] if applied_row else next_version),
    })


@app.route("/api/billing/cost-telemetry", methods=["GET"])
def api_billing_cost_telemetry():
    if not _billing_internal_authorized():
        return jsonify({"error": "forbidden"}), 403

    try:
        window_hours = int(request.args.get("window", 48) or 48)
    except Exception:
        window_hours = 48
    window_hours = max(1, min(24 * 30, window_hours))

    conn = get_db()
    _ensure_usage_ledger_table(conn)
    current_rate = _current_ct_rate_row(conn)
    current_ct_value_usd = float(current_rate["ct_value_usd"] or SHADOW_DEFAULT_CT_VALUE_USD) if current_rate else float(SHADOW_DEFAULT_CT_VALUE_USD)

    totals_row = conn.execute(
        """
        SELECT
          COUNT(*) AS calls,
          COALESCE(SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END), 0) AS ok_calls,
          COALESCE(SUM(CASE WHEN status <> 'ok' THEN 1 ELSE 0 END), 0) AS err_calls,
          COALESCE(SUM(cost_final_usd), 0) AS cost_final_usd,
          COALESCE(SUM(cost_estimate_usd), 0) AS cost_estimate_usd,
          COALESCE(SUM(billable_usd), 0) AS billable_usd,
          COALESCE(SUM(ct_shadow_debit), 0) AS ct_shadow_debit,
          COALESCE(SUM(ct_actual_debit), 0) AS ct_actual_debit,
          COALESCE(AVG(COALESCE(latency_ms, 0)), 0) AS avg_latency_ms
        FROM usage_ledger
        WHERE created_at >= datetime('now', ?)
        """,
        (f"-{window_hours} hour",),
    ).fetchone()

    top_models = conn.execute(
        """
        SELECT provider, model, COUNT(*) AS calls, COALESCE(SUM(cost_final_usd), 0) AS cost_final_usd
        FROM usage_ledger
        WHERE created_at >= datetime('now', ?)
        GROUP BY provider, model
        ORDER BY cost_final_usd DESC, calls DESC
        LIMIT 10
        """,
        (f"-{window_hours} hour",),
    ).fetchall()

    top_agents = conn.execute(
        """
        SELECT COALESCE(agent_id, 'n/a') AS agent_id, COUNT(*) AS calls, COALESCE(SUM(cost_final_usd), 0) AS cost_final_usd
        FROM usage_ledger
        WHERE created_at >= datetime('now', ?)
        GROUP BY COALESCE(agent_id, 'n/a')
        ORDER BY cost_final_usd DESC, calls DESC
        LIMIT 10
        """,
        (f"-{window_hours} hour",),
    ).fetchall()

    recent_rows = conn.execute(
        """
        SELECT
          created_at, request_id, workspace_id, client_id, user_id, event_type,
          agent_id, provider, model, status, error_code,
          input_tokens, output_tokens, tool_calls, connector_calls,
          latency_ms, cost_estimate_usd, cost_final_usd
        FROM usage_ledger
        ORDER BY id DESC
        LIMIT 100
        """
    ).fetchall()

    agg_24h = conn.execute(
        """
        SELECT
          COUNT(*) AS calls,
          COALESCE(SUM(cost_estimate_usd), 0) AS cost_estimate_usd,
          COALESCE(SUM(cost_final_usd), 0) AS cost_final_usd,
          COALESCE(SUM(billable_usd), 0) AS billable_usd,
          COALESCE(SUM(ct_shadow_debit), 0) AS ct_shadow_debit,
          COALESCE(SUM(ct_actual_debit), 0) AS ct_actual_debit
        FROM usage_ledger
        WHERE created_at >= datetime('now', '-24 hour')
        """
    ).fetchone()
    agg_7d = conn.execute(
        """
        SELECT
          COUNT(*) AS calls,
          COALESCE(SUM(cost_estimate_usd), 0) AS cost_estimate_usd,
          COALESCE(SUM(cost_final_usd), 0) AS cost_final_usd,
          COALESCE(SUM(billable_usd), 0) AS billable_usd,
          COALESCE(SUM(ct_shadow_debit), 0) AS ct_shadow_debit,
          COALESCE(SUM(ct_actual_debit), 0) AS ct_actual_debit
        FROM usage_ledger
        WHERE created_at >= datetime('now', '-7 day')
        """
    ).fetchone()
    delta_rows = conn.execute(
        """
        SELECT
          COALESCE(agent_id, 'unknown') AS agent_id,
          provider,
          model,
          COUNT(*) AS calls,
          COALESCE(SUM(ct_shadow_debit), 0) AS ct_shadow,
          COALESCE(SUM(ct_actual_debit), 0) AS ct_actual
        FROM usage_ledger
        WHERE created_at >= datetime('now', '-24 hour')
          AND status = 'ok'
        GROUP BY COALESCE(agent_id, 'unknown'), provider, model
        ORDER BY ABS(COALESCE(SUM(ct_shadow_debit), 0) - COALESCE(SUM(ct_actual_debit), 0)) DESC
        LIMIT 20
        """
    ).fetchall()
    implied_24h_row = conn.execute(
        """
        SELECT
          COALESCE(SUM(billable_usd), 0) AS billable_usd,
          COALESCE(SUM(ct_actual_debit), 0) AS ct_actual
        FROM usage_ledger
        WHERE created_at >= datetime('now', '-24 hour')
          AND status = 'ok'
          AND billable_usd IS NOT NULL
        """
    ).fetchone()
    implied_7d_row = conn.execute(
        """
        SELECT
          COALESCE(SUM(billable_usd), 0) AS billable_usd,
          COALESCE(SUM(ct_actual_debit), 0) AS ct_actual
        FROM usage_ledger
        WHERE created_at >= datetime('now', '-7 day')
          AND status = 'ok'
          AND billable_usd IS NOT NULL
        """
    ).fetchone()
    coverage_row = conn.execute(
        """
        SELECT
          COUNT(*) AS total_rows,
          COALESCE(SUM(CASE WHEN (input_tokens > 0 OR output_tokens > 0) THEN 1 ELSE 0 END), 0) AS token_rows,
          COALESCE(SUM(CASE WHEN cost_final_usd IS NOT NULL AND cost_final_usd > 0 THEN 1 ELSE 0 END), 0) AS cost_rows,
          COALESCE(SUM(CASE WHEN billable_usd IS NOT NULL AND billable_usd > 0 THEN 1 ELSE 0 END), 0) AS billable_rows
        FROM usage_ledger
        WHERE created_at >= datetime('now', ?)
        """,
        (f"-{window_hours} hour",),
    ).fetchone()
    proposal_48h = _billing_calibration_proposal(conn, window_hours=48)
    conn.close()

    implied_24h = None
    try:
        b = float((implied_24h_row["billable_usd"] if implied_24h_row else 0) or 0)
        c = int((implied_24h_row["ct_actual"] if implied_24h_row else 0) or 0)
        if c > 0 and b > 0:
            implied_24h = round(b / c, 10)
    except Exception:
        implied_24h = None
    implied_7d = None
    try:
        b = float((implied_7d_row["billable_usd"] if implied_7d_row else 0) or 0)
        c = int((implied_7d_row["ct_actual"] if implied_7d_row else 0) or 0)
        if c > 0 and b > 0:
            implied_7d = round(b / c, 10)
    except Exception:
        implied_7d = None

    return jsonify({
        "success": True,
        "shadow_mode": True,
        "window_hours": int(window_hours),
        "current_ct_value_usd": float(round(current_ct_value_usd, 10)),
        "totals": {
            "calls": int((totals_row["calls"] if totals_row else 0) or 0),
            "ok": int((totals_row["ok_calls"] if totals_row else 0) or 0),
            "error": int((totals_row["err_calls"] if totals_row else 0) or 0),
            "cost_estimate_usd": float((totals_row["cost_estimate_usd"] if totals_row else 0) or 0),
            "cost_final_usd": float((totals_row["cost_final_usd"] if totals_row else 0) or 0),
            "billable_usd": float((totals_row["billable_usd"] if totals_row else 0) or 0),
            "ct_shadow_debit": int((totals_row["ct_shadow_debit"] if totals_row else 0) or 0),
            "ct_actual_debit": int((totals_row["ct_actual_debit"] if totals_row else 0) or 0),
            "ct_delta": int(((totals_row["ct_shadow_debit"] if totals_row else 0) or 0) - ((totals_row["ct_actual_debit"] if totals_row else 0) or 0)),
            "avg_latency_ms": int(round(float((totals_row["avg_latency_ms"] if totals_row else 0) or 0))),
        },
        "aggregate_24h": {
            "calls": int((agg_24h["calls"] if agg_24h else 0) or 0),
            "cost_estimate_usd": float((agg_24h["cost_estimate_usd"] if agg_24h else 0) or 0),
            "cost_final_usd": float((agg_24h["cost_final_usd"] if agg_24h else 0) or 0),
            "billable_usd": float((agg_24h["billable_usd"] if agg_24h else 0) or 0),
            "ct_shadow_debit": int((agg_24h["ct_shadow_debit"] if agg_24h else 0) or 0),
            "ct_actual_debit": int((agg_24h["ct_actual_debit"] if agg_24h else 0) or 0),
            "ct_delta": int(((agg_24h["ct_shadow_debit"] if agg_24h else 0) or 0) - ((agg_24h["ct_actual_debit"] if agg_24h else 0) or 0)),
            "implied_ct_value_usd": implied_24h,
        },
        "aggregate_7d": {
            "calls": int((agg_7d["calls"] if agg_7d else 0) or 0),
            "cost_estimate_usd": float((agg_7d["cost_estimate_usd"] if agg_7d else 0) or 0),
            "cost_final_usd": float((agg_7d["cost_final_usd"] if agg_7d else 0) or 0),
            "billable_usd": float((agg_7d["billable_usd"] if agg_7d else 0) or 0),
            "ct_shadow_debit": int((agg_7d["ct_shadow_debit"] if agg_7d else 0) or 0),
            "ct_actual_debit": int((agg_7d["ct_actual_debit"] if agg_7d else 0) or 0),
            "ct_delta": int(((agg_7d["ct_shadow_debit"] if agg_7d else 0) or 0) - ((agg_7d["ct_actual_debit"] if agg_7d else 0) or 0)),
            "implied_ct_value_usd": implied_7d,
        },
        "coverage": {
            "rows_total": int((coverage_row["total_rows"] if coverage_row else 0) or 0),
            "rows_with_tokens": int((coverage_row["token_rows"] if coverage_row else 0) or 0),
            "rows_with_cost": int((coverage_row["cost_rows"] if coverage_row else 0) or 0),
            "rows_with_billable": int((coverage_row["billable_rows"] if coverage_row else 0) or 0),
        },
        "calibration": {
            "window_48h": {
                "insufficient_data": bool(proposal_48h.get("insufficient_data")),
                "reasons": proposal_48h.get("reasons") or [],
                "current_ct_value_usd": proposal_48h.get("current_ct_value_usd"),
                "implied_ct_value_usd": proposal_48h.get("implied_ct_value_usd"),
                "proposed_ct_value_usd": proposal_48h.get("proposed_ct_value_usd"),
                "coverage": proposal_48h.get("coverage") or {},
                "confidence": proposal_48h.get("confidence") or {},
            },
            "implied_ct_value_usd_24h": implied_24h,
            "implied_ct_value_usd_7d": implied_7d,
        },
        "top_models": [
            {
                "provider": str(r["provider"] or "unknown"),
                "model": str(r["model"] or "unknown"),
                "calls": int(r["calls"] or 0),
                "cost_final_usd": float(r["cost_final_usd"] or 0),
            }
            for r in (top_models or [])
        ],
        "top_agents": [
            {
                "agent_id": str(r["agent_id"] or "n/a"),
                "calls": int(r["calls"] or 0),
                "cost_final_usd": float(r["cost_final_usd"] or 0),
            }
            for r in (top_agents or [])
        ],
        "recent": [
            {
                "occurred_at": str(r["created_at"] or ""),
                "request_id": str(r["request_id"] or ""),
                "workspace_id": str(r["workspace_id"] or ""),
                "client_id": r["client_id"],
                "user_id": r["user_id"],
                "event_type": str(r["event_type"] or ""),
                "agent_id": str(r["agent_id"] or ""),
                "provider": str(r["provider"] or ""),
                "model": str(r["model"] or ""),
                "status": str(r["status"] or ""),
                "error_code": str(r["error_code"] or ""),
                "input_tokens": int(r["input_tokens"] or 0),
                "output_tokens": int(r["output_tokens"] or 0),
                "tool_calls": int(r["tool_calls"] or 0),
                "connector_calls": int(r["connector_calls"] or 0),
                "latency_ms": int(r["latency_ms"] or 0),
                "cost_estimate_usd": float(r["cost_estimate_usd"] or 0),
                "cost_final_usd": float(r["cost_final_usd"] or 0),
            }
            for r in (recent_rows or [])
        ],
        "delta_top_24h": [
            {
                "agent_id": str(r["agent_id"] or "unknown"),
                "provider": str(r["provider"] or "unknown"),
                "model": str(r["model"] or "unknown"),
                "calls": int(r["calls"] or 0),
                "ct_shadow": int(r["ct_shadow"] or 0),
                "ct_actual": int(r["ct_actual"] or 0),
                "ct_delta": int((r["ct_shadow"] or 0) - (r["ct_actual"] or 0)),
            }
            for r in (delta_rows or [])
        ],
        "plan_recommendations": {
            "endpoint": "/api/billing/plan-recommendations?window_days=7",
            "read_only": True,
            "requires_internal_token": True,
        },
    })


@app.route("/api/billing/shadow-sync", methods=["POST"])
def api_billing_shadow_sync():
    """Internal helper: seed missing pricing from observed usage and backfill shadow costs."""
    if not _billing_internal_authorized():
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    try:
        window_hours = int(payload.get("window_hours", 48) or 48)
    except Exception:
        window_hours = 48
    try:
        limit = int(payload.get("limit", 500) or 500)
    except Exception:
        limit = 500
    window_hours = max(1, min(24 * 30, window_hours))
    limit = max(1, min(5000, limit))

    conn = get_db()
    _ensure_usage_ledger_table(conn)
    seeded = 0
    backfilled = 0
    try:
        seeded = int(_shadow_seed_pricing_from_usage(conn, window_hours=window_hours) or 0)
    except Exception:
        seeded = 0
    rows = conn.execute(
        """
        SELECT request_id
        FROM usage_ledger
        WHERE created_at >= datetime('now', ?)
          AND status = 'ok'
          AND request_id IS NOT NULL
          AND request_id <> ''
          AND (input_tokens > 0 OR output_tokens > 0)
          AND (cost_final_usd IS NULL OR cost_final_usd = 0 OR billable_usd IS NULL OR ct_shadow_debit IS NULL)
        ORDER BY id DESC
        LIMIT ?
        """,
        (f"-{window_hours} hour", int(limit)),
    ).fetchall()
    for r in (rows or []):
        try:
            if _shadow_recompute_request(conn, str(r["request_id"] or "")):
                backfilled += 1
        except Exception:
            pass
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "shadow_mode": True,
        "seeded_pricing_rows": int(seeded),
        "backfilled_requests": int(backfilled),
        "window_hours": int(window_hours),
        "limit": int(limit),
    })


@app.route("/api/user/snapshot", methods=["GET"])
def api_user_snapshot():
    """Compact user/runtime snapshot for header chip and settings usage card."""
    uid = get_current_user_id()
    cid = get_current_client_id()

    conn = get_db()
    _ensure_user_settings_table(conn)
    _ensure_client_tables(conn)
    _ensure_usage_ledger_table(conn)

    username = f"user-{uid}"
    is_premium = False

    try:
        row = conn.execute(
            "SELECT username, COALESCE(is_premium, 0) AS is_premium FROM users WHERE id = ? LIMIT 1",
            (uid,),
        ).fetchone()
        if row:
            username = str(row["username"] or username).strip() or username
            is_premium = bool(row["is_premium"])
    except Exception:
        pass

    settings = _load_user_settings(conn, uid)
    profile = (settings.get("profile") or {}) if isinstance(settings, dict) else {}
    display_name = str(profile.get("display_name") or "").strip() or username
    email = str(profile.get("email") or "").strip()

    active_client = None
    if cid is not None and _client_owned(conn, uid, cid):
        c_row = conn.execute(
            "SELECT id, type, name, company_name FROM clients WHERE id = ? AND user_id = ? LIMIT 1",
            (int(cid), uid),
        ).fetchone()
        if c_row:
            active_client = {
                "id": int(c_row["id"]),
                "type": str(c_row["type"] or "person"),
                "display_name": str(c_row["company_name"] or c_row["name"] or f"Client {c_row['id']}").strip(),
            }

    usage = _get_user_ct_snapshot(conn, uid, client_id=cid)
    latest_shadow = conn.execute(
        """
        SELECT ct_shadow_debit, pricing_catalog_id, ct_rate_id, risk_buffer_pct, target_margin_pct, meta_json
        FROM usage_ledger
        WHERE user_id = ? AND request_id IS NOT NULL AND request_id <> ''
        ORDER BY id DESC
        LIMIT 1
        """,
        (int(uid),),
    ).fetchone()
    pricing_version_used = None
    ct_value_usd = None
    ct_shadow_last = None
    markup_pct = int(round(SHADOW_DEFAULT_MARGIN_PCT * 100))
    buffer_pct = int(round(SHADOW_DEFAULT_BUFFER_PCT * 100))
    if latest_shadow:
        try:
            ct_shadow_last = int(latest_shadow["ct_shadow_debit"]) if latest_shadow["ct_shadow_debit"] is not None else None
        except Exception:
            ct_shadow_last = None
        try:
            buffer_pct = int(round(float(latest_shadow["risk_buffer_pct"] or SHADOW_DEFAULT_BUFFER_PCT) * 100))
            markup_pct = int(round(float(latest_shadow["target_margin_pct"] or SHADOW_DEFAULT_MARGIN_PCT) * 100))
        except Exception:
            pass
        try:
            if latest_shadow["pricing_catalog_id"]:
                prow = conn.execute("SELECT version FROM pricing_catalog WHERE id = ? LIMIT 1", (str(latest_shadow["pricing_catalog_id"]),)).fetchone()
                if prow:
                    pricing_version_used = int(prow["version"] or 0)
            if latest_shadow["ct_rate_id"]:
                crow = conn.execute("SELECT ct_value_usd FROM ct_rates WHERE id = ? LIMIT 1", (str(latest_shadow["ct_rate_id"]),)).fetchone()
                if crow:
                    ct_value_usd = float(crow["ct_value_usd"] or 0)
        except Exception:
            pass
    if ct_value_usd is None:
        try:
            crow = conn.execute("SELECT ct_value_usd FROM ct_rates ORDER BY effective_from DESC LIMIT 1").fetchone()
            if crow:
                ct_value_usd = float(crow["ct_value_usd"] or 0)
        except Exception:
            ct_value_usd = None
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "user_id": uid,
        "username": username,
        "display_name": display_name,
        "email": email,
        "plan": usage.get("plan") or ("premium" if is_premium else "free"),
        "tier": usage.get("tier") or ("premium" if is_premium else "free"),
        "economy_preset": usage.get("economy_preset") or "free",
        "cost_multiplier": float(usage.get("cost_multiplier", 1.0) or 1.0),
        "monthly_grant": int(usage.get("monthly_grant", usage.get("ct_monthly_limit", 0)) or 0),
        "max_per_message": int(usage.get("max_per_message", 80) or 80),
        "daily_limit": int(usage.get("daily_limit", 0) or 0),
        "monthly_reset_day": int(usage.get("monthly_reset_day", 1) or 1),
        "monthly_reset_hour": int(usage.get("monthly_reset_hour", 0) or 0),
        "monthly_reset_minute": int(usage.get("monthly_reset_minute", 0) or 0),
        "is_premium": bool(usage.get("is_premium") if "is_premium" in usage else is_premium),
        "ct_balance": int(usage.get("ct_balance", 0) or 0),
        "ct_monthly_limit": int(usage.get("ct_monthly_limit", 0) or 0),
        "ct_used_month": int(usage.get("ct_used_month", 0) or 0),
        "ct_usage_pct": int(usage.get("ct_usage_pct", 0) or 0),
        "low_balance": bool(usage.get("low_balance", False)),
        "remaining_pct": int(usage.get("remaining_pct", 0) or 0),
        "requests_today": int(usage.get("requests_today", 0) or 0),
        "requests_30d": int(usage.get("requests_30d", 0) or 0),
        "usage_breakdown": usage.get("usage_breakdown") or {"chat": 40, "rag": 25, "flow": 20, "asset": 15},
        "pricing_version_used": pricing_version_used,
        "markup_pct": int(markup_pct),
        "buffer_pct": int(buffer_pct),
        "ct_value_usd": float(ct_value_usd or 0),
        "ct_debit_shadow": ct_shadow_last,
        "active_client": active_client,
        "timestamp": datetime.now().isoformat(),
    })


@app.route("/api/user/spend", methods=["POST"])
def api_user_spend():
    uid = get_current_user_id()
    cid = get_current_client_id()
    payload = request.get_json(force=True, silent=True) or {}

    try:
        amount = int(payload.get("amount", 0) or 0)
    except Exception:
        amount = 0

    event_type = str(payload.get("event_type") or "unknown").strip().lower() or "unknown"
    description = str(payload.get("description") or "").strip()
    request_id = _shadow_request_id(payload.get("request_id") or request.headers.get("X-Request-ID"))
    t0 = time.time()

    conn = get_db()
    _ensure_client_tables(conn)
    _ensure_usage_ledger_table(conn)

    if cid is not None and not _client_owned(conn, uid, cid):
        conn.close()
        return jsonify({"error": "Client not found or not owned"}), 404

    # Shadow preflight usage record (does not affect CT balance).
    try:
        _shadow_usage_preflight(
            conn,
            request_id=request_id,
            user_id=uid,
            client_id=cid,
            workspace_id=_current_workspace_slug(),
            event_type=event_type,
            amount=0,
            description=description or f"Shadow {event_type}",
            provider="camarad-internal",
            model="n/a",
            region="unknown",
            model_class="auto",
            cost_estimate_usd=0.0,
            meta={"shadow_mode": True, "source": "api_user_spend", "requested_amount": amount},
        )
    except Exception as shadow_err:
        print(f"api_user_spend_shadow_preflight_error: {shadow_err}")

    spend_result = _spend_ct(conn, uid, amount, event_type=event_type, description=description, client_id=cid)
    if not spend_result.get("success"):
        try:
            _shadow_usage_finalize(
                conn,
                request_id=request_id,
                status="error",
                error_code=str(spend_result.get("error") or "spend_failed"),
                latency_ms=int(max(0, round((time.time() - t0) * 1000))),
                cost_final_usd=0.0,
                meta={"shadow_mode": True, "source": "api_user_spend", "spend_success": False},
            )
            conn.commit()
        except Exception:
            pass
        conn.close()
        err_txt = str(spend_result.get("error") or "").lower()
        if err_txt.startswith("insufficient"):
            status_code = 402
        elif "daily" in err_txt and "limit" in err_txt:
            status_code = 429
        else:
            status_code = 400
        return jsonify(spend_result), status_code

    usage = _get_user_ct_snapshot(conn, uid, client_id=cid)
    try:
        conn.execute(
            "UPDATE usage_ledger SET ct_actual_debit = ? WHERE request_id = ?",
            (int(spend_result.get("spent", amount) or amount), str(request_id)),
        )
    except Exception:
        pass
    try:
        _shadow_usage_finalize(
            conn,
            request_id=request_id,
            status="ok",
            latency_ms=int(max(0, round((time.time() - t0) * 1000))),
            cost_final_usd=0.0,
            meta={
                "shadow_mode": True,
                "source": "api_user_spend",
                "spend_success": True,
                "ct_spent": int(spend_result.get("spent", amount) or amount),
            },
        )
    except Exception as shadow_err:
        print(f"api_user_spend_shadow_finalize_error: {shadow_err}")
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "spent": int(spend_result.get("spent", amount) or amount),
        "requested": int(spend_result.get("requested", amount) or amount),
        "cost_multiplier": float(spend_result.get("cost_multiplier", 1.0) or 1.0),
        "request_id": request_id,
        "daily_limit": int(spend_result.get("daily_limit", usage.get("daily_limit", 0)) or 0),
        "used_today": int(spend_result.get("used_today", 0) or 0),
        "new_balance": int(usage.get("ct_balance", 0) or 0),
        "ct_usage_pct": int(usage.get("ct_usage_pct", 0) or 0),
        "remaining_pct": int(usage.get("remaining_pct", 0) or 0),
        "low_balance": bool(usage.get("low_balance", False)),
    })


@app.route("/api/user/topup", methods=["POST"])
def api_user_topup():
    uid = get_current_user_id()
    cid = get_current_client_id()
    payload = request.get_json(force=True, silent=True) or {}

    try:
        amount = int(payload.get("amount", 0) or 0)
    except Exception:
        amount = 0

    description = str(payload.get("description") or "Manual top-up (mock)").strip() or "Manual top-up (mock)"

    conn = get_db()
    _ensure_client_tables(conn)
    _ensure_usage_ledger_table(conn)

    if cid is not None and not _client_owned(conn, uid, cid):
        conn.close()
        return jsonify({"error": "Client not found or not owned"}), 404

    topup = _topup_ct(conn, uid, amount, description=description, client_id=cid)
    if not topup.get("success"):
        conn.close()
        return jsonify(topup), 400

    usage = _get_user_ct_snapshot(conn, uid, client_id=cid)
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "topup": int(topup.get("topup", amount) or amount),
        "new_balance": int(usage.get("ct_balance", 0) or 0),
        "ct_usage_pct": int(usage.get("ct_usage_pct", 0) or 0),
        "remaining_pct": int(usage.get("remaining_pct", 0) or 0),
        "low_balance": bool(usage.get("low_balance", False)),
    })


@app.route("/api/users", methods=["GET"])
def get_users():
    """Return list of mock users"""
    conn = get_db()
    rows = conn.execute("SELECT id, username, is_premium FROM users ORDER BY id").fetchall()
    conn.close()
    users = [{"id": r[0], "username": r[1], "is_premium": bool(r[2])} for r in rows]
    return jsonify(users)


@app.route("/api/export", methods=["GET"])
def export_all():
    """Export all config for current user as JSON backup."""
    uid = get_current_user_id()
    cid = get_current_client_id()

    conn = get_db()
    cursor = conn.cursor()
    _migrate_flows_table(conn)
    _ensure_client_tables(conn)
    _ensure_user_settings_table(conn)

    if cid is not None and not _client_owned(conn, uid, cid):
        conn.close()
        return jsonify({"error": "Client not found or not owned"}), 404

    user_settings = _load_user_settings(conn, uid)

    def _safe_rows(sql, params=()):
        try:
            return cursor.execute(sql, params).fetchall()
        except Exception:
            return []

    # Agents config
    agent_sql = """
        SELECT agent_slug, custom_name, avatar_base64, llm_provider, llm_model, api_key,
               temperature, max_tokens, rag_enabled, status, client_id
        FROM agents_config
        WHERE user_id = ?
    """
    agent_params = [uid]
    if cid is not None:
        agent_sql += " AND COALESCE(client_id, 0) = ?"
        agent_params.append(cid)

    agents = []
    for r in _safe_rows(agent_sql, tuple(agent_params)):
        agents.append({
            "agent_slug": r[0],
            "custom_name": r[1],
            "avatar_base64": r[2],
            "llm_provider": r[3],
            "llm_model": r[4],
            "api_key": r[5],
            "temperature": r[6],
            "max_tokens": r[7],
            "rag_enabled": bool(r[8]),
            "status": r[9],
            "client_id": r[10],
        })

    # Connectors config
    connector_sql = """
        SELECT connector_slug, status, config_json, client_id
        FROM connectors_config
        WHERE user_id = ?
    """
    connector_params = [uid]
    if cid is not None:
        connector_sql += " AND COALESCE(client_id, 0) = ?"
        connector_params.append(cid)

    connectors = []
    for r in _safe_rows(connector_sql, tuple(connector_params)):
        connectors.append({
            "connector_slug": r[0],
            "status": r[1],
            "config": json.loads(r[2]) if r[2] else {},
            "client_id": r[3],
        })

    # Flows
    flow_sql = """
        SELECT id, name, flow_json, thumbnail, category, description, COALESCE(is_template, 0), created_at, updated_at, client_id
        FROM flows
        WHERE user_id = ?
    """
    flow_params = [uid]
    if cid is not None:
        flow_sql += " AND COALESCE(client_id, 0) = ?"
        flow_params.append(cid)

    flows = []
    for r in _safe_rows(flow_sql, tuple(flow_params)):
        flows.append({
            "id": r[0],
            "name": r[1],
            "flow": json.loads(r[2]) if r[2] else {},
            "thumbnail": r[3],
            "category": r[4] or "Uncategorized",
            "description": r[5] or "",
            "is_template": bool(r[6]),
            "created_at": r[7],
            "updated_at": r[8],
            "client_id": r[9],
        })

    # Chats + messages
    conv_sql = """
        SELECT id, workspace_slug, agent_slug, title, created_at, client_id
        FROM conversations
        WHERE user_id = ?
        ORDER BY created_at ASC, id ASC
    """
    conv_params = [uid]
    if cid is not None:
        conv_sql += " AND COALESCE(client_id, 0) = ?"
        conv_params.append(cid)

    chats = []
    conv_rows = _safe_rows(conv_sql, tuple(conv_params))
    for c in conv_rows:
        msg_rows = _safe_rows(
            "SELECT role, content, timestamp FROM messages WHERE conv_id = ? ORDER BY timestamp ASC, id ASC",
            (c[0],),
        )

        messages = []
        for m in msg_rows:
            messages.append({"role": m[0], "content": m[1], "timestamp": m[2]})

        chats.append({
            "id": c[0],
            "workspace_slug": c[1],
            "agent_slug": c[2],
            "title": c[3] or "",
            "created_at": c[4],
            "client_id": c[5],
            "messages": messages,
            "last_message": messages[-1]["content"] if messages else "",
            "last_message_at": messages[-1]["timestamp"] if messages else c[4],
        })

    # Clients + linked accounts
    client_sql = """
        SELECT id, type, name, company_name, email, website, phone, address, notes, created_at, updated_at
        FROM clients
        WHERE user_id = ?
        ORDER BY updated_at DESC, id DESC
    """
    client_params = [uid]
    if cid is not None:
        client_sql = """
            SELECT id, type, name, company_name, email, website, phone, address, notes, created_at, updated_at
            FROM clients
            WHERE user_id = ? AND id = ?
            LIMIT 1
        """
        client_params = [uid, cid]

    clients = []
    client_ids = []
    for r in _safe_rows(client_sql, tuple(client_params)):
        clients.append({
            "id": r[0],
            "type": r[1],
            "name": r[2],
            "company_name": r[3],
            "email": r[4],
            "website": r[5],
            "phone": r[6],
            "address": r[7],
            "notes": r[8],
            "created_at": r[9],
            "updated_at": r[10],
        })
        client_ids.append(r[0])

    client_connectors = []
    if client_ids:
        placeholders = ",".join(["?"] * len(client_ids))
        cc_rows = _safe_rows(
            f"""
            SELECT id, client_id, connector_slug, account_id, account_name, status, config_json, last_synced, created_at, updated_at
            FROM client_connectors
            WHERE client_id IN ({placeholders})
            ORDER BY updated_at DESC, id DESC
            """,
            tuple(client_ids),
        )
        for r in cc_rows:
            client_connectors.append({
                "id": r[0],
                "client_id": r[1],
                "connector_slug": r[2],
                "account_id": r[3],
                "account_name": r[4],
                "status": r[5],
                "config": json.loads(r[6]) if r[6] else {},
                "last_synced": r[7],
                "created_at": r[8],
                "updated_at": r[9],
            })

    conn.close()

    export_data = {
        "version": "1.3",
        "exported_at": __import__('datetime').datetime.now().isoformat(),
        "user_id": uid,
        "active_client_id": cid,
        "user_settings": user_settings,
        "agents": agents,
        "connectors": connectors,
        "flows": flows,
        "chats": chats,
        "clients": clients,
        "client_connectors": client_connectors,
    }
    return jsonify(export_data)
@app.route("/api/import", methods=["POST"])
def import_all():
    """Import JSON backup into current user's config (merge/overwrite)."""
    uid = get_current_user_id()
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    conn = get_db()
    cursor = conn.cursor()
    _migrate_flows_table(conn)
    _ensure_client_tables(conn)
    _ensure_user_settings_table(conn)

    counts = {
        "user_settings": 0,
        "agents": 0,
        "connectors": 0,
        "flows": 0,
        "chats": 0,
        "messages": 0,
        "clients": 0,
        "client_connectors": 0,
    }

    # Import user settings (merge over defaults/current)
    if isinstance(data.get("user_settings"), dict):
        current = _load_user_settings(conn, uid)
        merged = _deep_merge_dict(current, data.get("user_settings") or {})
        _save_user_settings(conn, uid, merged)
        counts["user_settings"] = 1

    client_id_map = {}

    # Import clients first so dependent entities can map client_id safely
    for c in data.get("clients", []):
        ctype = str(c.get("type") or "person").strip().lower()
        if ctype not in ("person", "company"):
            ctype = "person"

        cursor.execute(
            """
            INSERT INTO clients (user_id, type, name, company_name, email, website, phone, address, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                uid,
                ctype,
                str(c.get("name") or "").strip(),
                str(c.get("company_name") or "").strip(),
                str(c.get("email") or "").strip(),
                str(c.get("website") or "").strip(),
                str(c.get("phone") or "").strip(),
                str(c.get("address") or "").strip(),
                str(c.get("notes") or "").strip(),
            ),
        )
        new_id = cursor.lastrowid
        old_id = c.get("id")
        try:
            old_id = int(old_id)
        except (TypeError, ValueError):
            old_id = None
        if old_id:
            client_id_map[old_id] = new_id
        counts["clients"] += 1

    # Import agents
    for a in data.get("agents", []):
        agent_client_id = a.get("client_id")
        try:
            agent_client_id = int(agent_client_id)
        except (TypeError, ValueError):
            agent_client_id = None
        if agent_client_id is not None:
            agent_client_id = client_id_map.get(agent_client_id, agent_client_id if _client_owned(conn, uid, agent_client_id) else None)
        agent_client_id = int(agent_client_id or 0)

        cursor.execute("""
            INSERT OR REPLACE INTO agents_config
            (user_id, client_id, agent_slug, custom_name, avatar_base64, llm_provider, llm_model, api_key, temperature, max_tokens, rag_enabled, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            uid,
            agent_client_id,
            a["agent_slug"],
            a.get("custom_name"),
            a.get("avatar_base64"),
            a.get("llm_provider"),
            a.get("llm_model"),
            a.get("api_key"),
            a.get("temperature", 0.7),
            a.get("max_tokens", 2048),
            1 if a.get("rag_enabled") else 0,
            a.get("status", "Active"),
        ))
        counts["agents"] += 1

    # Import connectors
    for c in data.get("connectors", []):
        connector_client_id = c.get("client_id")
        try:
            connector_client_id = int(connector_client_id)
        except (TypeError, ValueError):
            connector_client_id = None
        if connector_client_id is not None:
            connector_client_id = client_id_map.get(connector_client_id, connector_client_id if _client_owned(conn, uid, connector_client_id) else None)
        connector_client_id = int(connector_client_id or 0)

        cursor.execute("""
            INSERT OR REPLACE INTO connectors_config
            (user_id, client_id, connector_slug, status, config_json, last_connected)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (
            uid,
            connector_client_id,
            c["connector_slug"],
            c.get("status", "Disconnected"),
            json.dumps(c.get("config", {})),
        ))
        counts["connectors"] += 1

    # Import flows
    for f in data.get("flows", []):
        flow_client_id = f.get("client_id")
        try:
            flow_client_id = int(flow_client_id)
        except (TypeError, ValueError):
            flow_client_id = None
        if flow_client_id is not None:
            flow_client_id = client_id_map.get(flow_client_id, flow_client_id if _client_owned(conn, uid, flow_client_id) else None)

        cursor.execute("""
            INSERT INTO flows (name, user_id, client_id, flow_json, thumbnail, category, description, is_template, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            f.get("name", "Imported Flow"),
            uid,
            flow_client_id,
            json.dumps(f.get("flow", {})),
            f.get("thumbnail"),
            f.get("category", "Uncategorized"),
            f.get("description", ""),
            1 if f.get("is_template") else 0,
        ))
        counts["flows"] += 1

    # Import chats/conversations (+ messages)
    chats_payload = data.get("chats") or data.get("conversations") or []
    for ch in chats_payload:
        ws_input = str(ch.get("workspace_slug") or ch.get("workspace") or "agency").strip()
        ws_slug = ws_input.lower().replace(" ", "-") or "agency"

        chat_client_id = ch.get("client_id")
        try:
            chat_client_id = int(chat_client_id)
        except (TypeError, ValueError):
            chat_client_id = None
        if chat_client_id is not None:
            chat_client_id = client_id_map.get(chat_client_id, chat_client_id if _client_owned(conn, uid, chat_client_id) else None)

        agent_slug = str(ch.get("agent_slug") or "ppc-specialist").strip() or "ppc-specialist"
        title = str(ch.get("title") or "").strip()
        created_at = ch.get("created_at")

        if created_at:
            cursor.execute(
                "INSERT INTO conversations (user_id, client_id, workspace_slug, agent_slug, title, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (uid, chat_client_id, ws_slug, agent_slug, title, created_at),
            )
        else:
            cursor.execute(
                "INSERT INTO conversations (user_id, client_id, workspace_slug, agent_slug, title) VALUES (?, ?, ?, ?, ?)",
                (uid, chat_client_id, ws_slug, agent_slug, title),
            )

        new_conv_id = cursor.lastrowid
        counts["chats"] += 1

        for m in (ch.get("messages") or []):
            role = str(m.get("role") or "user").strip().lower()
            if role not in ("user", "agent"):
                role = "user"

            content = str(m.get("content") or "").strip()
            if not content:
                continue

            timestamp = m.get("timestamp")
            if timestamp:
                cursor.execute(
                    "INSERT INTO messages (conv_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                    (new_conv_id, role, content, timestamp),
                )
            else:
                cursor.execute(
                    "INSERT INTO messages (conv_id, role, content) VALUES (?, ?, ?)",
                    (new_conv_id, role, content),
                )
            counts["messages"] += 1

    # Import client connector links
    for cc in data.get("client_connectors", []):
        target_client_id = cc.get("client_id")
        try:
            target_client_id = int(target_client_id)
        except (TypeError, ValueError):
            target_client_id = None
        if target_client_id is not None:
            target_client_id = client_id_map.get(target_client_id, target_client_id if _client_owned(conn, uid, target_client_id) else None)
        if not target_client_id:
            continue

        status = str(cc.get("status") or "pending").strip().lower()
        if status not in ("pending", "connected", "error", "disconnected"):
            status = "pending"

        cfg = cc.get("config")
        if not isinstance(cfg, dict):
            cfg = {}

        cursor.execute(
            """
            INSERT INTO client_connectors (client_id, connector_slug, account_id, account_name, status, config_json, last_synced, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                target_client_id,
                str(cc.get("connector_slug") or "").strip(),
                str(cc.get("account_id") or "").strip(),
                str(cc.get("account_name") or "").strip(),
                status,
                json.dumps(cfg),
                cc.get("last_synced"),
            ),
        )
        counts["client_connectors"] += 1

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": (
            f"Imported {counts['agents']} agents, {counts['connectors']} connectors, "
            f"{counts['flows']} flows, {counts['chats']} chats and {counts['messages']} messages"
        ),
        "counts": counts,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# BOARDROOM — Multi-Agent Meeting Room# ═══════════════════════════════════════════════════════════════════════════════
# BOARDROOM — Multi-Agent Meeting Room
# ═══════════════════════════════════════════════════════════════════════════════

import time as _time
from datetime import datetime, timedelta

# ── Meeting type templates ──
MEETING_TEMPLATES = [
    {
        "id": "strategy-review",
        "name": "Strategy Review",
        "icon": "bi-bullseye",
        "color": "primary",
        "description": "C-suite alignment on vision, goals, OKRs and quarterly strategy.",
        "suggested_agents": ["ceo-strategy", "cmo-growth", "cfo-finance", "coo-operations"],
        "complexity": "high",
        "category": "business",
        "default_rounds": 3,
        "prompt_template": "Conduct a strategic review on: {topic}. Each participant should share their perspective based on their role, challenge assumptions, and propose concrete next steps."
    },
    {
        "id": "creative-brainstorm",
        "name": "Creative Brainstorm",
        "icon": "bi-lightbulb",
        "color": "warning",
        "description": "Free-form ideation session — wild ideas welcome, then converge.",
        "suggested_agents": ["creative-director", "creative-muse", "social-media", "cmo-growth"],
        "complexity": "medium",
        "category": "agency",
        "default_rounds": 2,
        "prompt_template": "Brainstorm creative ideas for: {topic}. Start divergent (wild ideas), then converge on the top 3 with pros/cons."
    },
    {
        "id": "performance-standup",
        "name": "Performance Stand-Up",
        "icon": "bi-graph-up-arrow",
        "color": "success",
        "description": "Data-driven review of KPIs, campaigns, analytics and pipeline.",
        "suggested_agents": ["performance-analytics", "ppc-specialist", "seo-content", "cmo-growth"],
        "complexity": "medium",
        "category": "agency",
        "default_rounds": 2,
        "prompt_template": "Review current performance metrics for: {topic}. Share numbers, identify trends, flag issues, and recommend optimizations."
    },
    {
        "id": "tech-architecture",
        "name": "Tech Architecture Review",
        "icon": "bi-cpu",
        "color": "info",
        "description": "Deep-dive on system design, tech debt, scalability and security.",
        "suggested_agents": ["backend-architect", "fullstack-dev", "devops-infra", "security-quality", "cto-innovation"],
        "complexity": "high",
        "category": "development",
        "default_rounds": 3,
        "prompt_template": "Review the technical architecture for: {topic}. Discuss trade-offs, scalability concerns, security implications, and implementation plan."
    },
    {
        "id": "crisis-war-room",
        "name": "Crisis War Room",
        "icon": "bi-exclamation-triangle",
        "color": "danger",
        "description": "Urgent incident response — triage, diagnose, coordinate resolution.",
        "suggested_agents": ["cto-innovation", "devops-infra", "security-quality", "ceo-strategy", "coo-operations"],
        "complexity": "critical",
        "category": "cross-functional",
        "default_rounds": 4,
        "prompt_template": "URGENT: {topic}. Triage the situation, identify root cause, assign responsibilities, and define a resolution timeline. Each round should escalate clarity."
    },
    {
        "id": "budget-planning",
        "name": "Budget & Resource Planning",
        "icon": "bi-cash-stack",
        "color": "success",
        "description": "Allocate budget, headcount and resources across departments.",
        "suggested_agents": ["cfo-finance", "ceo-strategy", "cmo-growth", "cto-innovation", "coo-operations"],
        "complexity": "high",
        "category": "business",
        "default_rounds": 3,
        "prompt_template": "Plan budget allocation for: {topic}. Each department head should present needs, justify ROI, and negotiate priorities."
    },
    {
        "id": "campaign-kickoff",
        "name": "Campaign Kickoff",
        "icon": "bi-megaphone",
        "color": "warning",
        "description": "Launch a new campaign — brief, creative, channels, timeline, KPIs.",
        "suggested_agents": ["ppc-specialist", "seo-content", "creative-director", "social-media", "performance-analytics"],
        "complexity": "medium",
        "category": "agency",
        "default_rounds": 2,
        "prompt_template": "Kick off the campaign: {topic}. Define target audience, messaging, channel strategy, creative needs, timeline, and success KPIs."
    },
    {
        "id": "personal-growth",
        "name": "Personal Growth Circle",
        "icon": "bi-heart",
        "color": "info",
        "description": "Holistic personal development — mindset, skills, wellness, creativity.",
        "suggested_agents": ["life-coach", "psychologist", "personal-mentor", "fitness-wellness", "creative-muse"],
        "complexity": "low",
        "category": "personal",
        "default_rounds": 2,
        "prompt_template": "Help me explore personal growth around: {topic}. Each coach should offer their unique perspective and one actionable suggestion."
    },
    {
        "id": "retrospective",
        "name": "Sprint Retrospective",
        "icon": "bi-arrow-repeat",
        "color": "secondary",
        "description": "What went well, what didn't, what to improve — agile retro style.",
        "suggested_agents": ["fullstack-dev", "frontend-uiux", "devops-infra", "backend-architect"],
        "complexity": "low",
        "category": "development",
        "default_rounds": 2,
        "prompt_template": "Run a sprint retrospective on: {topic}. Format: What went well? What didn't? What should we change? Each participant contributes from their domain."
    },
    {
        "id": "custom-sandbox",
        "name": "Custom Sandbox",
        "icon": "bi-sliders",
        "color": "light",
        "description": "Fully custom meeting — you define agents, rules, format and context.",
        "suggested_agents": [],
        "complexity": "custom",
        "category": "custom",
        "default_rounds": 2,
        "prompt_template": "{topic}"
    },
]

# ── All 20 agents reference (for boardroom picker) ──
BOARDROOM_AGENTS = [
    {"slug": "ceo-strategy",          "name": "CEO / Strategy",            "ws": "business",    "icon": "bi-bullseye",         "color": "#58a6ff"},
    {"slug": "cto-innovation",        "name": "CTO / Innovation",          "ws": "business",    "icon": "bi-cpu",              "color": "#8957e5"},
    {"slug": "cmo-growth",            "name": "CMO / Growth",              "ws": "business",    "icon": "bi-graph-up",         "color": "#f0883e"},
    {"slug": "cfo-finance",           "name": "CFO / Finance",             "ws": "business",    "icon": "bi-cash-stack",       "color": "#3fb950"},
    {"slug": "coo-operations",        "name": "COO / Operations",          "ws": "business",    "icon": "bi-gear",             "color": "#79c0ff"},
    {"slug": "ppc-specialist",        "name": "PPC Specialist",            "ws": "agency",      "icon": "bi-megaphone",        "color": "#f778ba"},
    {"slug": "seo-content",           "name": "SEO & Content",             "ws": "agency",      "icon": "bi-search",           "color": "#56d364"},
    {"slug": "creative-director",     "name": "Creative Director",         "ws": "agency",      "icon": "bi-palette",          "color": "#d2a8ff"},
    {"slug": "social-media",          "name": "Social Media Manager",      "ws": "agency",      "icon": "bi-share",            "color": "#79c0ff"},
    {"slug": "performance-analytics", "name": "Performance Analytics",     "ws": "agency",      "icon": "bi-bar-chart-line",   "color": "#ffa657"},
    {"slug": "devops-infra",          "name": "DevOps & Infra",            "ws": "development", "icon": "bi-cloud-arrow-up",   "color": "#58a6ff"},
    {"slug": "fullstack-dev",         "name": "Full-Stack Dev",            "ws": "development", "icon": "bi-code-slash",       "color": "#3fb950"},
    {"slug": "backend-architect",     "name": "Backend Architect",         "ws": "development", "icon": "bi-server",           "color": "#f0883e"},
    {"slug": "frontend-uiux",         "name": "Frontend / UI-UX",          "ws": "development", "icon": "bi-window-desktop",   "color": "#d2a8ff"},
    {"slug": "security-quality",      "name": "Security & QA",             "ws": "development", "icon": "bi-shield-check",     "color": "#f85149"},
    {"slug": "life-coach",            "name": "Personal Assistant",        "ws": "personal",    "icon": "bi-heart-pulse",      "color": "#f778ba"},
    {"slug": "psychologist",          "name": "Psychologist",              "ws": "personal",    "icon": "bi-brain",            "color": "#8957e5"},
    {"slug": "personal-mentor",       "name": "Personal Mentor",           "ws": "personal",    "icon": "bi-mortarboard",      "color": "#ffa657"},
    {"slug": "fitness-wellness",      "name": "Fitness & Wellness",        "ws": "personal",    "icon": "bi-activity",         "color": "#3fb950"},
    {"slug": "creative-muse",         "name": "Creative Muse",             "ws": "personal",    "icon": "bi-stars",            "color": "#d2a8ff"},
]

# ── Mock meeting history ──
MOCK_MEETINGS = [
    {
        "id": "mtg-001",
        "template_id": "strategy-review",
        "title": "Q1 2026 Strategy Alignment",
        "status": "completed",
        "created_at": "2026-01-28T10:00:00",
        "duration_min": 12,
        "agents": ["ceo-strategy", "cmo-growth", "cfo-finance", "coo-operations"],
        "rounds": 3,
        "topic": "Review Q1 targets, pipeline health, and resource allocation for the new AI features launch.",
        "transcript": [
            {"round": 1, "agent": "ceo-strategy", "message": "Our Q1 target is $420K ARR. We're currently tracking at 78% of that with 6 weeks remaining. The AI features launch is our biggest lever — I want each of you to report readiness.", "sentiment": "focused", "confidence": 0.88},
            {"round": 1, "agent": "cmo-growth", "message": "Marketing is launch-ready. We have 3 landing pages, a 12-email drip sequence, and 47 beta testers lined up for social proof. My concern is the demo video — creative team needs 5 more days.", "sentiment": "optimistic", "confidence": 0.82},
            {"round": 1, "agent": "cfo-finance", "message": "Budget-wise, we've allocated $34K for the launch sprint — $18K in ads, $12K in content production, $4K contingency. Current burn rate is sustainable for 8 months. However, if we miss the Q1 target by more than 15%, we need to revisit hiring plans.", "sentiment": "cautious", "confidence": 0.91},
            {"round": 1, "agent": "coo-operations", "message": "Operations bottleneck: onboarding flow needs QA — there's a 23% drop-off at step 3. I've flagged this to dev. Support team is trained on new features. SLA compliance is at 94%.", "sentiment": "analytical", "confidence": 0.85},
            {"round": 2, "agent": "ceo-strategy", "message": "Good inputs. Let's prioritize: 1) Fix the onboarding drop-off (COO + Dev), 2) Accelerate the demo video (CMO), 3) Pre-allocate $5K extra from contingency to paid ads if week-1 CAC is under $28. CFO, model that scenario.", "sentiment": "decisive", "confidence": 0.92},
            {"round": 2, "agent": "cmo-growth", "message": "Agreed. I'll fast-track the video with an AI-generated draft by Monday, then polish by Wednesday. For ads, I recommend front-loading 60% of budget in week 1 to capitalize on launch momentum.", "sentiment": "proactive", "confidence": 0.87},
            {"round": 2, "agent": "cfo-finance", "message": "Modeled. If CAC stays ≤$28 and we front-load ads: projected Q1 close at $398K (95% of target). If we also fix the onboarding leak, that adds an estimated $22K uplift → $420K achievable. Approving the $5K contingency release with a week-1 review gate.", "sentiment": "supportive", "confidence": 0.89},
            {"round": 2, "agent": "coo-operations", "message": "I'll coordinate a hotfix sprint with dev starting tomorrow. Target: onboarding drop-off reduced to <12% within 10 days. Daily standups on this until resolved.", "sentiment": "committed", "confidence": 0.90},
            {"round": 3, "agent": "ceo-strategy", "message": "Excellent alignment. Action items locked: COO owns onboarding fix (10-day deadline), CMO owns video + ad front-load, CFO gates the extra $5K on week-1 metrics. Reconvene in 7 days. Meeting adjourned.", "sentiment": "confident", "confidence": 0.95},
        ],
        "summary": "Q1 target of $420K ARR is achievable with 3 coordinated actions: fix onboarding drop-off (COO), accelerate demo video (CMO), and conditionally release $5K ad contingency (CFO). Next review in 7 days.",
        "action_items": [
            {"owner": "coo-operations", "task": "Fix onboarding step-3 drop-off to <12%", "deadline": "10 days", "priority": "critical"},
            {"owner": "cmo-growth", "task": "Deliver AI demo video", "deadline": "5 days", "priority": "high"},
            {"owner": "cmo-growth", "task": "Front-load 60% ad budget in launch week 1", "deadline": "launch day", "priority": "high"},
            {"owner": "cfo-finance", "task": "Review week-1 CAC and approve $5K contingency", "deadline": "7 days", "priority": "medium"},
        ],
    },
    {
        "id": "mtg-002",
        "template_id": "tech-architecture",
        "title": "Microservices Migration Feasibility",
        "status": "completed",
        "created_at": "2026-01-25T14:30:00",
        "duration_min": 18,
        "agents": ["backend-architect", "devops-infra", "security-quality", "cto-innovation"],
        "rounds": 3,
        "topic": "Evaluate migrating the monolith to microservices. Cost, timeline, risk.",
        "transcript": [
            {"round": 1, "agent": "cto-innovation", "message": "We need to evaluate whether microservices make sense at our current scale (50K MAU, 12 services-in-monolith). I want each of you to assess from your domain: is this the right time?", "sentiment": "inquisitive", "confidence": 0.84},
            {"round": 1, "agent": "backend-architect", "message": "Technically, 3 of our 12 modules are hot spots: auth, billing, and notifications. They account for 78% of scaling issues. I'd recommend extracting these 3 first (strangler fig pattern) rather than a full rewrite. Timeline: 8-12 weeks per service.", "sentiment": "pragmatic", "confidence": 0.91},
            {"round": 1, "agent": "devops-infra", "message": "Infra readiness: we'd need to set up service mesh (Istio), container orchestration (already on K8s), distributed tracing (Jaeger), and circuit breakers. Estimated infra prep: 4-6 weeks. Monthly cost increase: ~$2.4K for additional load balancers and monitoring.", "sentiment": "detailed", "confidence": 0.88},
            {"round": 1, "agent": "security-quality", "message": "Security implications: inter-service communication needs mTLS, API gateway auth needs rework, and we'll need to handle distributed session management. Attack surface increases by ~40%. I need 3 weeks for security architecture review before any migration begins.", "sentiment": "cautious", "confidence": 0.86},
            {"round": 2, "agent": "cto-innovation", "message": "Consensus is clear: targeted extraction, not full migration. Backend, prioritize auth extraction first (it's blocking SSO). DevOps, begin infra prep in parallel. Security, start your review immediately.", "sentiment": "decisive", "confidence": 0.90},
            {"round": 2, "agent": "backend-architect", "message": "Auth extraction plan: Week 1-2 interface definition + API contracts. Week 3-6 implementation with backward-compatible facade. Week 7-8 gradual traffic migration (10% → 50% → 100%). Rollback plan included.", "sentiment": "structured", "confidence": 0.93},
            {"round": 3, "agent": "cto-innovation", "message": "Approved. Phase 1: Auth service extraction (8 weeks). Phase 2: Billing (Q2). Phase 3: Notifications (Q3). Total investment: ~$14K additional infra + 3 engineer-months. Expected payoff: 60% reduction in auth-related incidents, unblocks SSO for enterprise clients.", "sentiment": "confident", "confidence": 0.92},
        ],
        "summary": "Microservices migration approved as phased approach: extract Auth (8wk), Billing (Q2), Notifications (Q3). Strangler fig pattern, not full rewrite. $14K additional infra cost, 3 engineer-months.",
        "action_items": [
            {"owner": "security-quality", "task": "Complete security architecture review", "deadline": "3 weeks", "priority": "critical"},
            {"owner": "devops-infra", "task": "Set up service mesh + distributed tracing", "deadline": "6 weeks", "priority": "high"},
            {"owner": "backend-architect", "task": "Auth service extraction — Phase 1", "deadline": "8 weeks", "priority": "high"},
        ],
    },
    {
        "id": "mtg-003",
        "template_id": "creative-brainstorm",
        "title": "Summer Campaign '26 Ideation",
        "status": "completed",
        "created_at": "2026-02-01T09:00:00",
        "duration_min": 8,
        "agents": ["creative-director", "social-media", "cmo-growth", "creative-muse"],
        "rounds": 2,
        "topic": "Generate campaign concepts for the Summer 2026 product launch.",
        "transcript": [
            {"round": 1, "agent": "creative-muse", "message": "What if we flip the 'AI assistant' narrative? Instead of 'AI helps you work', we go with 'AI gives you your summer back' — position productivity gains as time reclaimed for living. Visual: split screen — left is work chaos, right is someone at the beach, both happening at the same time.", "sentiment": "inspired", "confidence": 0.79},
            {"round": 1, "agent": "creative-director", "message": "Love the duality concept. Visual execution: we could do a 'Day/Night' series — daytime is AI handling business (clean, minimal, blue tones), evening is the human enjoying life (warm, golden, lifestyle). Works across static, video, and social formats.", "sentiment": "excited", "confidence": 0.85},
            {"round": 1, "agent": "social-media", "message": "For social, I see a UGC challenge: #MyAISummer — users share what they do with the time Camarad saves them. We seed with 10 influencer posts, then let it spread. TikTok + Reels format. Also, interactive Stories poll: 'What would you do with 2 extra hours/day?'", "sentiment": "energetic", "confidence": 0.82},
            {"round": 1, "agent": "cmo-growth", "message": "Strong concepts. From a growth lens: the 'time reclaimed' angle maps directly to our value prop. I want to test 3 variants: emotional (beach/freedom), rational (hours saved calculator), and social proof (testimonials). A/B across channels. Budget: $24K creative production.", "sentiment": "strategic", "confidence": 0.88},
            {"round": 2, "agent": "creative-director", "message": "Final 3 concepts: 1) 'AI Gives You Summer' — lifestyle split-screen series, 2) 'The 2-Hour Gift' — calculator + testimonial hybrid, 3) '#MyAISummer' — UGC-driven social campaign. Recommend launching all three, measuring week-1 engagement, then doubling down on the winner.", "sentiment": "decisive", "confidence": 0.90},
        ],
        "summary": "3 campaign concepts developed: 'AI Gives You Summer' (lifestyle), 'The 2-Hour Gift' (rational), '#MyAISummer' (UGC). All 3 launch simultaneously, best performer gets doubled budget after week 1.",
        "action_items": [
            {"owner": "creative-director", "task": "Produce mood boards for all 3 concepts", "deadline": "5 days", "priority": "high"},
            {"owner": "social-media", "task": "Identify 10 influencers for #MyAISummer seeding", "deadline": "7 days", "priority": "medium"},
            {"owner": "cmo-growth", "task": "Set up A/B test framework across channels", "deadline": "10 days", "priority": "high"},
        ],
    },
]

@app.route("/boardroom")
def boardroom():
    if AUTH_REQUIRED and not is_user_authenticated():
        return _auth_redirect(next_path="/boardroom")
    uid = get_current_user_id()
    if uid > 0 and _must_complete_onboarding(uid):
        return redirect(url_for("onboarding_page"))
    return render_template("boardroom.html")


@app.route("/api/boardroom/templates")
def boardroom_templates():
    return jsonify({"templates": MEETING_TEMPLATES})


@app.route("/api/boardroom/agents")
def boardroom_agents():
    return jsonify({"agents": BOARDROOM_AGENTS})


@app.route("/api/boardroom/meetings", methods=["GET"])
def boardroom_meetings_list():
    """List all meetings (mock + DB)"""
    uid = get_current_user_id()
    meetings_out = []

    # Add mock meetings
    for m in MOCK_MEETINGS:
        meetings_out.append({
            "id": m["id"],
            "template_id": m["template_id"],
            "title": m["title"],
            "status": m["status"],
            "created_at": m["created_at"],
            "duration_min": m["duration_min"],
            "agents": m["agents"],
            "rounds": m["rounds"],
            "topic": m["topic"][:120],
        })

    # Add from DB
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT id, template_id, title, status, created_at, duration_min, agents_json, rounds, topic FROM meetings WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
            (uid,)
        ).fetchall()
        conn.close()
        for r in rows:
            meetings_out.append({
                "id": f"db-{r['id']}",
                "template_id": r["template_id"],
                "title": r["title"],
                "status": r["status"],
                "created_at": r["created_at"],
                "duration_min": r["duration_min"],
                "agents": json.loads(r["agents_json"]) if r["agents_json"] else [],
                "rounds": r["rounds"],
                "topic": (r["topic"] or "")[:120],
            })
    except Exception:
        pass  # table may not exist yet

    return jsonify({"meetings": meetings_out})


@app.route("/api/boardroom/meetings/<meeting_id>", methods=["GET"])
def boardroom_meeting_detail(meeting_id):
    """Get full meeting details including transcript"""
    # Check mock meetings first
    for m in MOCK_MEETINGS:
        if m["id"] == meeting_id:
            return jsonify(m)

    # Check DB
    try:
        real_id = meeting_id.replace("db-", "")
        conn = get_db()
        row = conn.execute("SELECT * FROM meetings WHERE id = ?", (real_id,)).fetchone()
        conn.close()
        if row:
            return jsonify({
                "id": meeting_id,
                "template_id": row["template_id"],
                "title": row["title"],
                "status": row["status"],
                "created_at": row["created_at"],
                "duration_min": row["duration_min"],
                "agents": json.loads(row["agents_json"]) if row["agents_json"] else [],
                "rounds": row["rounds"],
                "topic": row["topic"],
                "transcript": json.loads(row["transcript_json"]) if row["transcript_json"] else [],
                "summary": row["summary"],
                "action_items": json.loads(row["action_items_json"]) if row["action_items_json"] else [],
            })
    except Exception:
        pass

    return jsonify({"error": "Meeting not found"}), 404


@app.route("/api/boardroom/meetings", methods=["POST"])
def boardroom_create_meeting():
    """Create a new meeting and run the simulation"""
    uid = get_current_user_id()
    data = request.get_json(force=True, silent=True) or {}

    template_id = data.get("template_id", "custom-sandbox")
    title = data.get("title", "Untitled Meeting")
    agents = data.get("agents", [])
    topic = data.get("topic", "General discussion")
    rounds = data.get("rounds", 2)
    config = data.get("config", {})

    if len(agents) < 2:
        return jsonify({"error": "At least 2 agents required for a meeting"}), 400

    # Find template
    tmpl = next((t for t in MEETING_TEMPLATES if t["id"] == template_id), MEETING_TEMPLATES[-1])

    # Simulate meeting transcript
    agent_map = {a["slug"]: a for a in BOARDROOM_AGENTS}
    transcript = []
    sentiments = ["analytical", "optimistic", "cautious", "decisive", "proactive", "creative", "pragmatic", "supportive", "focused", "strategic"]

    import random as _rand
    start_time = _time.time()

    for rnd in range(1, rounds + 1):
        for agent_slug in agents:
            agent_info = agent_map.get(agent_slug, {"name": agent_slug, "slug": agent_slug})
            # Generate contextual mock response
            prompt = tmpl["prompt_template"].replace("{topic}", topic)
            response_text = _generate_meeting_response(agent_info, rnd, rounds, topic, template_id, transcript)
            transcript.append({
                "round": rnd,
                "agent": agent_slug,
                "message": response_text,
                "sentiment": _rand.choice(sentiments),
                "confidence": round(_rand.uniform(0.75, 0.96), 2),
            })

    elapsed = round((_time.time() - start_time) * 1000 + _rand.randint(3000, 8000))
    duration_min = max(1, elapsed // 60000 + len(transcript) * 2)

    # Generate summary & action items
    summary = f"Meeting on '{topic}' completed with {len(agents)} participants over {rounds} rounds. Key themes discussed across {template_id.replace('-', ' ')} format."
    action_items = []
    for i, agent_slug in enumerate(agents[:4]):
        action_items.append({
            "owner": agent_slug,
            "task": f"Follow up on discussion point #{i+1} from the meeting",
            "deadline": f"{_rand.randint(3, 14)} days",
            "priority": ["critical", "high", "medium", "low"][min(i, 3)],
        })

    # Save to DB
    meeting_id = None
    try:
        conn = get_db()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER DEFAULT 1,
                template_id TEXT,
                title TEXT,
                status TEXT DEFAULT 'completed',
                created_at TEXT DEFAULT (datetime('now')),
                duration_min INTEGER,
                agents_json TEXT,
                rounds INTEGER,
                topic TEXT,
                transcript_json TEXT,
                summary TEXT,
                action_items_json TEXT,
                config_json TEXT
            )
        """)
        cursor = conn.execute("""
            INSERT INTO meetings (user_id, template_id, title, status, duration_min, agents_json, rounds, topic, transcript_json, summary, action_items_json, config_json)
            VALUES (?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, template_id, title, duration_min, json.dumps(agents), rounds, topic,
              json.dumps(transcript), summary, json.dumps(action_items), json.dumps(config)))
        meeting_id = cursor.lastrowid
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving meeting: {e}")

    return jsonify({
        "id": f"db-{meeting_id}" if meeting_id else f"tmp-{int(_time.time())}",
        "template_id": template_id,
        "title": title,
        "status": "completed",
        "created_at": datetime.now().isoformat(),
        "duration_min": duration_min,
        "agents": agents,
        "rounds": rounds,
        "topic": topic,
        "transcript": transcript,
        "summary": summary,
        "action_items": action_items,
    })


def _generate_meeting_response(agent_info, round_num, total_rounds, topic, template_id, history):
    """Generate contextual meeting responses based on agent role, round, and template"""
    import random as _rand
    name = agent_info.get("name", agent_info.get("slug", "Agent"))
    slug = agent_info.get("slug", "")
    ws = agent_info.get("ws", "")

    # Role-specific openers and perspectives
    perspectives = {
        "ceo-strategy":          ["From a strategic standpoint,", "Looking at the bigger picture,", "Our vision requires us to"],
        "cto-innovation":        ["Technically speaking,", "From an innovation perspective,", "The technology landscape suggests"],
        "cmo-growth":            ["From a growth lens,", "Marketing data shows", "Our audience research indicates"],
        "cfo-finance":           ["Looking at the numbers,", "Financially,", "The ROI analysis shows"],
        "coo-operations":        ["Operationally,", "From an execution standpoint,", "Our processes indicate"],
        "ppc-specialist":        ["The campaign data shows", "From a paid media perspective,", "Ad performance metrics indicate"],
        "seo-content":           ["Our organic data reveals", "Content-wise,", "SEO trends show"],
        "creative-director":     ["Creatively,", "From a design perspective,", "The visual direction should"],
        "social-media":          ["On social channels,", "Community sentiment shows", "Engagement data indicates"],
        "performance-analytics": ["The analytics dashboard shows", "Data-driven insight:", "Key metrics reveal"],
        "devops-infra":          ["Infrastructure-wise,", "From a deployment perspective,", "System metrics show"],
        "fullstack-dev":         ["From the codebase perspective,", "Implementation-wise,", "The tech stack allows us to"],
        "backend-architect":     ["Architecturally,", "The system design suggests", "Looking at scalability,"],
        "frontend-uiux":        ["From a UX perspective,", "User research shows", "The interface should"],
        "security-quality":      ["Security analysis shows", "From a compliance standpoint,", "Risk assessment indicates"],
        "life-coach":            ["For personal growth,", "I'd encourage you to consider", "A balanced approach would be"],
        "psychologist":          ["From a psychological perspective,", "Emotionally,", "The underlying pattern suggests"],
        "personal-mentor":       ["As your mentor, I'd say", "Learning-wise,", "Growth requires"],
        "fitness-wellness":      ["For overall wellness,", "Energy management suggests", "A healthy approach would be"],
        "creative-muse":         ["Imagine this:", "What if we", "The creative spirit suggests"],
    }

    opener = _rand.choice(perspectives.get(slug, ["In my assessment,"]))

    # Round-specific behavior
    if round_num == 1:
        phase = f"{opener} regarding '{topic}', my initial analysis suggests we need to focus on the key priorities within my domain. "
        detail = _rand.choice([
            "I see three main areas that need attention and I'll outline my recommendations.",
            "Based on current data and trends, here's my assessment of the situation.",
            "Let me share the critical factors from my perspective that should drive our decision.",
            "I've identified several opportunities and risks that the team should be aware of.",
        ])
    elif round_num == total_rounds:
        phase = f"{opener} to summarize my position: "
        detail = _rand.choice([
            "I'm aligned with the team's direction and committed to executing my action items within the agreed timeline.",
            "Based on our discussion, I'll prioritize the top deliverables and report back at our next check-in.",
            "The consensus is solid. I'll document my commitments and share the detailed plan by end of day.",
            "Good alignment achieved. My team will begin execution immediately with weekly progress updates.",
        ])
    else:
        phase = f"{opener} building on what's been discussed, "
        detail = _rand.choice([
            "I agree with the overall direction but want to flag a potential risk we should mitigate.",
            "I can support this approach if we add a safeguard for the scenario the team hasn't considered yet.",
            "Good progress. Let me add a data point that strengthens our confidence in this direction.",
            "I see a synergy between my domain and what was just proposed — let me elaborate on how we can amplify the impact.",
            "My analysis supports this direction. I'd recommend we also consider the second-order effects on our timeline.",
        ])

    # Add specificity based on template
    template_flavor = {
        "strategy-review": " This aligns with our quarterly OKRs and the broader company roadmap.",
        "creative-brainstorm": " I love where this is going — let me riff on that idea further.",
        "performance-standup": f" The numbers back this up — key metrics are trending {'positively' if _rand.random() > 0.3 else 'below target, requiring immediate attention'}.",
        "tech-architecture": " The architectural implications are significant but manageable with proper planning.",
        "crisis-war-room": " Urgency is clear. We need to act within the next 24 hours on this.",
        "budget-planning": f" Budget impact: approximately ${_rand.randint(5, 50)}K, with ROI expected in {_rand.randint(2, 6)} months.",
        "campaign-kickoff": " The target audience will respond well to this angle based on historical data.",
        "personal-growth": " Remember, sustainable growth comes from consistent small steps, not dramatic changes.",
        "retrospective": " This is a pattern we've seen before — let's document it as a team learning.",
    }

    return phase + detail + template_flavor.get(template_id, "")


# ═══════════════════════════════════════════════════════════════════════════════
# MATURITY INDEX — CMI / PMI / AMI / DMI
# ═══════════════════════════════════════════════════════════════════════════════

# Factor weights for maturity calculation
MATURITY_WEIGHTS = {
    "connectors_active":    {"weight": 0.12, "max_val": 15, "category": "infrastructure"},
    "connectors_configured":{"weight": 0.08, "max_val": 30, "category": "infrastructure"},
    "agents_configured":    {"weight": 0.10, "max_val": 20, "category": "agents"},
    "agents_with_rag":      {"weight": 0.08, "max_val": 15, "category": "agents"},
    "meetings_held":        {"weight": 0.06, "max_val": 20, "category": "collaboration"},
    "conversations_total":  {"weight": 0.05, "max_val": 100, "category": "engagement"},
    "flows_created":        {"weight": 0.07, "max_val": 10, "category": "automation"},
    "businesses_count":     {"weight": 0.08, "max_val": 5, "category": "scale"},
    "monthly_budget":       {"weight": 0.10, "max_val": 50000, "category": "investment"},
    "employees_count":      {"weight": 0.06, "max_val": 100, "category": "scale"},
    "digital_assets":       {"weight": 0.05, "max_val": 50, "category": "assets"},
    "premium_status":       {"weight": 0.05, "max_val": 1, "category": "commitment"},
    "active_days":          {"weight": 0.10, "max_val": 90, "category": "engagement"},
}

# Mock user profiles for maturity calculation
MOCK_USER_PROFILES = {
    1: {  # dev
        "businesses_count": 2,
        "monthly_budget": 8500,
        "employees_count": 12,
        "digital_assets": 18,
        "active_days": 42,
        "accounting": {
            "monthly_revenue": 28500,
            "monthly_expenses": 19200,
            "profit_margin": 32.6,
            "runway_months": 14,
            "burn_rate": 19200,
            "arr": 342000,
        },
    },
    2: {  # Alice
        "businesses_count": 1,
        "monthly_budget": 3200,
        "employees_count": 4,
        "digital_assets": 8,
        "active_days": 23,
        "accounting": {
            "monthly_revenue": 12800,
            "monthly_expenses": 9600,
            "profit_margin": 25.0,
            "runway_months": 8,
            "burn_rate": 9600,
            "arr": 153600,
        },
    },
    3: {  # Bob (premium)
        "businesses_count": 4,
        "monthly_budget": 34000,
        "employees_count": 45,
        "digital_assets": 37,
        "active_days": 67,
        "accounting": {
            "monthly_revenue": 89000,
            "monthly_expenses": 61000,
            "profit_margin": 31.5,
            "runway_months": 22,
            "burn_rate": 61000,
            "arr": 1068000,
        },
    },
}


@app.route("/api/maturity", methods=["GET"])
def maturity_index():
    """Calculate CMI = PMI + AMI + DMI for current user"""
    uid = get_current_user_id()
    profile = MOCK_USER_PROFILES.get(uid, MOCK_USER_PROFILES[1])

    # Gather real data from DB
    try:
        conn = get_db()
        connectors_active = conn.execute(
            "SELECT COUNT(*) FROM connectors_config WHERE user_id = ? AND status = 'Connected'", (uid,)
        ).fetchone()[0]
        connectors_configured = conn.execute(
            "SELECT COUNT(*) FROM connectors_config WHERE user_id = ?", (uid,)
        ).fetchone()[0]
        agents_configured = conn.execute(
            "SELECT COUNT(*) FROM agents_config WHERE user_id = ?", (uid,)
        ).fetchone()[0]
        agents_with_rag = conn.execute(
            "SELECT COUNT(*) FROM agents_config WHERE user_id = ? AND rag_enabled = 1", (uid,)
        ).fetchone()[0]
        conversations_total = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE user_id = ?", (uid,)
        ).fetchone()[0]
        flows_created = conn.execute(
            "SELECT COUNT(*) FROM flows WHERE user_id = ?", (uid,)
        ).fetchone()[0]
        meetings_held = 0
        try:
            meetings_held = conn.execute(
                "SELECT COUNT(*) FROM meetings WHERE user_id = ?", (uid,)
            ).fetchone()[0]
        except Exception:
            pass
        is_premium = is_user_premium(uid)
        conn.close()
    except Exception:
        connectors_active = 0
        connectors_configured = 0
        agents_configured = 0
        agents_with_rag = 0
        conversations_total = 0
        flows_created = 0
        meetings_held = 0
        is_premium = False

    # Add mock meetings count
    meetings_held += len(MOCK_MEETINGS)

    # Build factors dict
    factors = {
        "connectors_active": connectors_active,
        "connectors_configured": connectors_configured,
        "agents_configured": agents_configured,
        "agents_with_rag": agents_with_rag,
        "meetings_held": meetings_held,
        "conversations_total": conversations_total,
        "flows_created": flows_created,
        "businesses_count": profile["businesses_count"],
        "monthly_budget": profile["monthly_budget"],
        "employees_count": profile["employees_count"],
        "digital_assets": profile["digital_assets"],
        "premium_status": 1 if is_premium else 0,
        "active_days": profile["active_days"],
    }

    # Calculate scores per factor
    factor_scores = {}
    total_score = 0
    for key, meta in MATURITY_WEIGHTS.items():
        raw = factors.get(key, 0)
        normalized = min(raw / meta["max_val"], 1.0) if meta["max_val"] > 0 else 0
        weighted = normalized * meta["weight"] * 100
        factor_scores[key] = {
            "raw": raw,
            "max": meta["max_val"],
            "normalized": round(normalized, 3),
            "weighted_score": round(weighted, 2),
            "category": meta["category"],
        }
        total_score += weighted

    # Split into sub-indices: PMI, AMI, DMI
    pmi_categories = {"engagement", "commitment", "scale"}
    ami_categories = {"agents", "collaboration", "automation"}
    dmi_categories = {"infrastructure", "assets", "investment"}

    pmi_score = sum(v["weighted_score"] for v in factor_scores.values() if v["category"] in pmi_categories)
    ami_score = sum(v["weighted_score"] for v in factor_scores.values() if v["category"] in ami_categories)
    dmi_score = sum(v["weighted_score"] for v in factor_scores.values() if v["category"] in dmi_categories)
    cmi_score = pmi_score + ami_score + dmi_score

    # Maturity level labels
    def level(score, max_possible):
        pct = (score / max_possible * 100) if max_possible > 0 else 0
        if pct >= 80: return {"label": "Expert", "color": "success", "tier": 5}
        if pct >= 60: return {"label": "Advanced", "color": "info", "tier": 4}
        if pct >= 40: return {"label": "Intermediate", "color": "primary", "tier": 3}
        if pct >= 20: return {"label": "Growing", "color": "warning", "tier": 2}
        return {"label": "Starter", "color": "secondary", "tier": 1}

    pmi_max = sum(m["weight"] * 100 for k, m in MATURITY_WEIGHTS.items() if m["category"] in pmi_categories)
    ami_max = sum(m["weight"] * 100 for k, m in MATURITY_WEIGHTS.items() if m["category"] in ami_categories)
    dmi_max = sum(m["weight"] * 100 for k, m in MATURITY_WEIGHTS.items() if m["category"] in dmi_categories)

    return jsonify({
        "user_id": uid,
        "cmi": {
            "score": round(cmi_score, 1),
            "max": 100,
            "pct": round(cmi_score, 1),
            "level": level(cmi_score, 100),
        },
        "pmi": {
            "label": "Personal Maturity Index",
            "score": round(pmi_score, 1),
            "max": round(pmi_max, 1),
            "pct": round(pmi_score / pmi_max * 100, 1) if pmi_max else 0,
            "level": level(pmi_score, pmi_max),
        },
        "ami": {
            "label": "Agency Maturity Index",
            "score": round(ami_score, 1),
            "max": round(ami_max, 1),
            "pct": round(ami_score / ami_max * 100, 1) if ami_max else 0,
            "level": level(ami_score, ami_max),
        },
        "dmi": {
            "label": "Development Maturity Index",
            "score": round(dmi_score, 1),
            "max": round(dmi_max, 1),
            "pct": round(dmi_score / dmi_max * 100, 1) if dmi_max else 0,
            "level": level(dmi_score, dmi_max),
        },
        "factors": factor_scores,
        "accounting": profile.get("accounting", {}),
        "profile": {
            "businesses_count": profile["businesses_count"],
            "monthly_budget": profile["monthly_budget"],
            "employees_count": profile["employees_count"],
            "digital_assets": profile["digital_assets"],
            "active_days": profile["active_days"],
        },
        "recommendations": _maturity_recommendations(cmi_score, factor_scores),
    })


def _maturity_recommendations(cmi, factors):
    """Generate actionable recommendations based on maturity gaps"""
    recs = []
    for key, data in factors.items():
        if data["normalized"] < 0.3:
            labels = {
                "connectors_active": ("Connect more tools", "Activate connectors to unlock cross-platform insights.", "bi-plug"),
                "agents_configured": ("Configure your agents", "Customize agent personalities and LLM settings.", "bi-robot"),
                "meetings_held": ("Hold more boardroom meetings", "Multi-agent meetings accelerate strategic clarity.", "bi-people"),
                "flows_created": ("Build automation flows", "Orchestrator flows reduce manual coordination.", "bi-diagram-3"),
                "conversations_total": ("Chat more with your agents", "Deeper engagement unlocks personalized insights.", "bi-chat"),
                "monthly_budget": ("Scale your investment", "Higher budget unlocks premium analytics and reach.", "bi-cash-stack"),
                "agents_with_rag": ("Enable RAG for agents", "Knowledge-base retrieval makes agents smarter.", "bi-database"),
            }
            if key in labels:
                title, desc, icon = labels[key]
                recs.append({"title": title, "description": desc, "icon": icon, "priority": "high" if data["normalized"] < 0.1 else "medium"})

    if not recs:
        recs.append({"title": "Excellent maturity!", "description": "Your platform usage is well-optimized across all dimensions.", "icon": "bi-trophy", "priority": "info"})

    return recs[:5]


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVE CONTEXT — Mock Scaffold
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/active-context", methods=["GET"])
def active_context():
    """
    Active Context — a real-time snapshot of the user's operational state.
    Aggregates: maturity indices, recent activity, current meetings, connected tools,
    active agents, and contextual recommendations.
    Used by the system to enrich every agent interaction with awareness.
    """
    uid = get_current_user_id()
    cid = get_current_client_id()
    profile = MOCK_USER_PROFILES.get(uid, MOCK_USER_PROFILES[1])

    active_connectors = []
    active_agents = []
    recent_convs = []

    try:
        conn = get_db()
        _ensure_client_tables(conn)

        if cid is not None and not _client_owned(conn, uid, cid):
            conn.close()
            return jsonify({
                "user_id": uid,
                "active_client_id": cid,
                "timestamp": datetime.now().isoformat(),
                "session": {
                    "active_since": "2026-02-07T08:00:00",
                    "interactions_today": 0,
                    "current_workspace": "agency",
                },
                "maturity_snapshot": {
                    "cmi_tier": "Intermediate",
                    "cmi_score_approx": 0,
                },
                "active_connectors": [],
                "active_agents": [],
                "recent_conversations": [],
                "business_context": {
                    "businesses": 0,
                    "total_budget": 0,
                    "team_size": 0,
                    "accounting_summary": {
                        "mrr": 0,
                        "burn_rate": 0,
                        "runway": "0 months",
                        "health": "at-risk",
                    },
                },
                "contextual_signals": [],
                "next_actions": ["Select a valid client to load scoped context."],
            })

        connectors_sql = "SELECT connector_slug FROM connectors_config WHERE user_id = ? AND status = 'Connected'"
        connectors_params = [uid]
        if cid is not None:
            connectors_sql += " AND COALESCE(client_id, 0) = ?"
            connectors_params.append(cid)
        active_connectors = conn.execute(connectors_sql, tuple(connectors_params)).fetchall()

        agents_sql = "SELECT agent_slug, status FROM agents_config WHERE user_id = ? AND status = 'Active'"
        agents_params = [uid]
        if cid is not None:
            agents_sql += " AND COALESCE(client_id, 0) = ?"
            agents_params.append(cid)
        active_agents = conn.execute(agents_sql, tuple(agents_params)).fetchall()

        conv_sql = """
            SELECT c.agent_slug, c.title, MAX(m.timestamp) as last_msg
            FROM conversations c
            JOIN messages m ON c.id = m.conv_id
            WHERE c.user_id = ?
        """
        conv_params = [uid]
        if cid is not None:
            conv_sql += " AND COALESCE(c.client_id, 0) = ?"
            conv_params.append(cid)
        conv_sql += " GROUP BY c.id ORDER BY last_msg DESC LIMIT 5"
        recent_convs = conn.execute(conv_sql, tuple(conv_params)).fetchall()

        conn.close()
    except Exception:
        active_connectors = []
        active_agents = []
        recent_convs = []

    return jsonify({
        "user_id": uid,
        "active_client_id": cid,
        "timestamp": datetime.now().isoformat(),
        "session": {
            "active_since": "2026-02-07T08:00:00",
            "interactions_today": len(recent_convs),
            "current_workspace": "agency",
        },
        "maturity_snapshot": {
            "cmi_tier": "Growing" if uid == 2 else ("Advanced" if uid == 3 else "Intermediate"),
            "cmi_score_approx": 28.5 if uid == 2 else (61.2 if uid == 3 else 42.8),
        },
        "active_connectors": [r[0] for r in active_connectors],
        "active_agents": [{"slug": r[0], "status": r[1]} for r in active_agents],
        "recent_conversations": [
            {"agent": r[0], "title": r[1] or r[0], "last_activity": r[2]}
            for r in recent_convs
        ],
        "business_context": {
            "businesses": profile["businesses_count"],
            "total_budget": profile["monthly_budget"],
            "team_size": profile["employees_count"],
            "accounting_summary": {
                "mrr": profile["accounting"]["monthly_revenue"],
                "burn_rate": profile["accounting"]["burn_rate"],
                "runway": f"{profile['accounting']['runway_months']} months",
                "health": "healthy" if profile["accounting"]["profit_margin"] > 20 else "at-risk",
            },
        },
        "contextual_signals": [
            {"type": "insight", "message": "Your PPC campaigns are trending above target — consider scaling budget.", "source": "performance-analytics"},
            {"type": "alert", "message": "2 connectors haven't synced in 48+ hours.", "source": "system"},
            {"type": "opportunity", "message": "SEO content audit overdue by 14 days.", "source": "seo-content"},
        ],
        "next_actions": [
            "Review Q1 performance in a Strategy Review boardroom meeting",
            "Connect additional data sources to improve maturity index",
            "Schedule a campaign kickoff for the upcoming product launch",
        ],
    })

if __name__ == '__main__':
    app.run(debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)











