# Models as dicts/helpers for now

import json
import os
import random
import sqlite3
from pathlib import Path

SYNTHETIC_DATA_DIR = Path(__file__).parent / "synthetic_datasets"
AGENT_EXAMPLES = {}  # Cache for loaded examples

DB_PATH = Path(__file__).parent / "knowledge_base" / "knowledge.db"
API_DOCS_DB = Path(__file__).parent / "connectors_api_docs.db"


def get_api_docs_context(query: str, connectors: list, top_k: int = 3) -> str:
    """Search API docs prioritizing specific connectors, return formatted context with citations"""
    if not API_DOCS_DB.exists():
        return ""

    # Extract meaningful keywords
    stop_words = {'what', 'is', 'the', 'how', 'to', 'for', 'and', 'or', 'but', 'in',
                  'on', 'at', 'by', 'with', 'a', 'an', 'of', 'are', 'was', 'do', 'does',
                  'can', 'could', 'should', 'would', 'will', 'my', 'me', 'i', 'show',
                  'tell', 'about', 'from', 'get', 'give', 'this', 'that', 'these', 'those'}
    words = [w.lower() for w in query.split() if len(w) > 2 and w.lower() not in stop_words]
    if not words:
        words = [query.lower()]

    conn = sqlite3.connect(API_DOCS_DB)
    cursor = conn.cursor()

    results = []

    # Phase 1: Search within prioritized connectors first
    if connectors:
        word_conditions = " OR ".join(
            ["(LOWER(title) LIKE ? OR LOWER(content) LIKE ?)" for _ in words]
        )
        connector_placeholders = ",".join(["?" for _ in connectors])
        params = []
        for w in words:
            params.extend([f"%{w}%", f"%{w}%"])
        params.extend(connectors)
        params.append(top_k)

        sql = f"""
            SELECT connector, title, url, content, section_type
            FROM api_docs
            WHERE ({word_conditions})
              AND connector IN ({connector_placeholders})
            ORDER BY LENGTH(content) DESC
            LIMIT ?
        """
        results = cursor.execute(sql, params).fetchall()

    # Phase 2: If not enough results, also search all connectors
    if len(results) < top_k:
        remaining = top_k - len(results)
        word_conditions = " OR ".join(
            ["(LOWER(title) LIKE ? OR LOWER(content) LIKE ?)" for _ in words]
        )
        params = []
        for w in words:
            params.extend([f"%{w}%", f"%{w}%"])

        # Exclude already-found URLs
        exclude = ""
        found_urls = [r[2] for r in results]
        if found_urls:
            exclude = " AND url NOT IN (" + ",".join(["?" for _ in found_urls]) + ")"
            params.extend(found_urls)

        params.append(remaining)
        sql = f"""
            SELECT connector, title, url, content, section_type
            FROM api_docs
            WHERE ({word_conditions}) {exclude}
            ORDER BY LENGTH(content) DESC
            LIMIT ?
        """
        results.extend(cursor.execute(sql, params).fetchall())

    conn.close()

    if not results:
        return ""

    context = ""
    for connector, title, url, content, section_type in results:
        # Clean title (remove non-breaking spaces)
        clean_title = title.replace('\xa0', ' ').strip()[:80] if title else connector
        # Truncate content smartly
        preview = content[:400].rsplit(' ', 1)[0] + "..." if len(content) > 400 else content
        # Format with citation link
        context += f"📖 **[{clean_title}]({url})** ({connector} – {section_type})\n"
        context += f"{preview}\n\n"

    return context.strip()

def get_rag_context(query: str, top_k: int = 3) -> str:
    """Caută simple keyword în chunks și returnează context relevant"""
    if not DB_PATH.exists():
        return ""
    
    # Extract key terms: words longer than 3 chars, remove common stop words
    stop_words = {'what', 'is', 'the', 'how', 'to', 'for', 'and', 'or', 'but', 'in', 'on', 'at', 'by', 'with', 'a', 'an', 'of', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'can', 'may', 'might', 'must'}
    words = [w.lower() for w in query.split() if len(w) > 3 and w.lower() not in stop_words]
    if not words:
        words = [query.lower()]  # fallback
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Build LIKE conditions for each key word
    conditions = " OR ".join(["content LIKE ?" for _ in words])
    params = [f"%{word}%" for word in words]
    
    sql = f"""
    SELECT title, summary, content, source
    FROM chunks
    WHERE {conditions}
    ORDER BY LENGTH(content) DESC
    LIMIT ?
    """
    params.append(top_k)
    
    rows = cursor.execute(sql, params).fetchall()
    conn.close()
    
    print(f"DEBUG: Found {len(rows)} chunks for query: {query}")
    
    if not rows:
        return ""
    
    context = "Relevant knowledge from reports:\n\n"
    for title, summary, content, source in rows:
        context += f"**{title}**\n{summary}\n\n{content[:600]}...\n\n---\n"
    
    return context.strip()

def load_agent_examples(agent_slug, num_examples=5):
    if agent_slug in AGENT_EXAMPLES:
        return AGENT_EXAMPLES[agent_slug]
    
    file_path = SYNTHETIC_DATA_DIR / f"{agent_slug}_synthetic.jsonl"
    if not file_path.exists():
        return []
    
    examples = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    examples.append(json.loads(line))
    except Exception as e:
        print(f"Error loading examples for {agent_slug}: {e}")
        return []
    
    # Cache and return random sample
    AGENT_EXAMPLES[agent_slug] = random.sample(examples, min(num_examples, len(examples)))
    return AGENT_EXAMPLES[agent_slug]

workspaces = {
    'personal': {
        'name': 'Personal',
        'agents': {
            'life-coach': 'Personal Assistant',
            'psychologist': 'Psychologist',
            'personal-mentor': 'Personal Teacher / Mentor',
            'fitness-wellness': 'Fitness & Wellness Coach',
            'creative-muse': 'Creative Muse'
        }
    },
    'business': {
        'name': 'Business',
        'agents': {
            'ceo-strategy': 'CEO / Vision & Strategy',
            'cto-innovation': 'CTO / Tech & Innovation',
            'cmo-growth': 'CMO / Marketing & Growth',
            'cfo-finance': 'CFO / Finance & Numbers',
            'coo-operations': 'COO / Operations & Execution'
        }
    },
    'agency': {
        'name': 'Agency',
        'agents': {
            'ppc-specialist': 'PPC Specialist',
            'seo-content': 'SEO & Content Strategist',
            'creative-director': 'Creative Director / Designer',
            'social-media': 'Social Media Manager',
            'performance-analytics': 'Performance & Analytics Expert'
        }
    },
    'development': {
        'name': 'Development',
        'agents': {
            'devops-infra': 'DevOps & Infrastructure Engineer',
            'fullstack-dev': 'Full-Stack Developer',
            'backend-architect': 'Backend Architect',
            'frontend-uiux': 'Frontend / UI-UX Specialist',
            'security-quality': 'Security & Code Quality Engineer'
        }
    }
}

routing_keywords = {
    'life-coach': ['goal', 'habit', 'motivation'],
    'psychologist': ['anxiety', 'depression', 'therapy'],
    'personal-mentor': ['learn', 'skill', 'education'],
    'fitness-wellness': ['exercise', 'nutrition', 'health'],
    'creative-muse': ['art', 'writing', 'inspiration'],
    'ceo-strategy': ['strategy', 'vision', 'scaling'],
    'cto-innovation': ['tech', 'innovation', 'stack'],
    'cmo-growth': ['marketing', 'brand', 'growth'],
    'cfo-finance': ['budget', 'finance', 'investment'],
    'coo-operations': ['operations', 'efficiency', 'process'],
    'ppc-specialist': ['ads', 'ppc', 'campaign'],
    'seo-content': ['seo', 'content', 'ranking'],
    'creative-director': ['design', 'creative', 'visual'],
    'social-media': ['social', 'instagram', 'facebook'],
    'performance-analytics': ['analytics', 'kpi', 'data'],
    'devops-infra': ['deploy', 'ci/cd', 'infrastructure'],
    'fullstack-dev': ['code', 'bug', 'debug'],
    'backend-architect': ['backend', 'database', 'api'],
    'frontend-uiux': ['frontend', 'ui', 'ux'],
    'security-quality': ['security', 'vulnerability', 'testing']
}

ROUTING_KEYWORDS = {
    "PPC Specialist": ["ads", "ppc", "campaign", "google ads", "paid", "cpc"],
    "SEO & Content Strategist": ["seo", "organic", "keyword", "ranking", "content"],
    "Performance & Analytics Expert": ["analytics", "ga4", "traffic", "sessions", "conversion", "performance"],
    "CFO / Finance & Numbers": ["revenue", "finance", "cost", "budget", "stripe", "mrr", "profit"],
    "COO / Operations & Execution": ["operations", "process", "efficiency", "team", "execution", "workflow"],
    "CTO / Tech & Innovation": ["tech", "innovation", "architecture", "scalability", "tech stack"],
    # Add more as needed
}

def detect_best_agent(message: str, current_agent: str) -> tuple[str | None, float]:
    """Returnează (suggested_agent, confidence) sau (None, 0)"""
    msg_lower = message.lower()
    best_match = None
    best_score = 0.0
    
    for agent, keywords in ROUTING_KEYWORDS.items():
        if agent == current_agent:
            continue
        matches = sum(1 for kw in keywords if kw in msg_lower)
        score = matches / max(1, len(keywords)) if matches > 0 else 0
        if score > best_score:
            best_score = score
            best_match = agent
    
    if best_score >= 0.4:  # prag rezonabil pentru MVP
        return best_match, best_score
    return None, 0.0

def detect_handover(message: str) -> str | None:
    msg_lower = message.lower().strip()
    if any(word in msg_lower for word in ["yes", "transfer", "handover", "switch to"]):
        # Extract agent name if possible, e.g., "switch to PPC Specialist"
        for agent in ROUTING_KEYWORDS.keys():
            if agent.lower() in msg_lower:
                return agent
        # If no specific, return the suggested one from context (but for now, assume from previous)
        return None
    return None

def enhance_context(base_response: str, context: str, agent_slug: str = "") -> str:
    prompt = base_response
    if context:
        prompt = f"Context from previous messages:\n{context}\n\n{prompt}"
    
    # Add few-shot examples if available
    if agent_slug:
        examples = load_agent_examples(agent_slug, 3)  # 3 examples for brevity
        if examples:
            few_shot = "\n\n".join([
                f"User: {ex['messages'][1]['content']}\nAssistant: {ex['messages'][2]['content']}"
                for ex in examples
            ])
            prompt = f"Examples of similar conversations:\n{few_shot}\n\nNow respond to:\n{prompt}"
    
    return prompt

def get_llm_response(prompt: str) -> str:
    import requests
    from config import Config

    if not Config.GROK_API_KEY:
        return f"Simulated LLM response to: {prompt[:100]}... (No API key set)"

    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",  # Assuming this is the endpoint
            headers={
                "Authorization": f"Bearer {Config.GROK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "grok-1",  # Or whatever the model is
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000
            }
        )
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            return f"Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Exception: {str(e)}"

from mocks.connectors import MOCK_CONNECTORS

def get_agent_name(ws_slug, agent_slug):
    return workspaces.get(ws_slug, {}).get('agents', {}).get(agent_slug, 'Unknown Agent')

def simulate_response(agent_slug: str, user_message: str) -> str:
    msg_lower = user_message.lower().strip()
    agent_name = get_agent_name('', agent_slug)

    # ── Google Ads (existent)
    if agent_slug == "ppc-specialist" and any(kw in msg_lower for kw in ["campaign", "campaigns", "ads", "ppc", "show campaigns"]):
        campaigns = MOCK_CONNECTORS["google_ads"].list_campaigns()
        lines = [f"• {c['name']} ({c['status']}) – Budget ${c['budget']:.1f}, {c['clicks']} clicks, ${c['cost']:.2f} spent" for c in campaigns]
        return "Current Google Ads campaigns:\n\n" + "\n".join(lines) + "\n\nWant performance for a specific campaign?"

    # ── GA4 (existent)
    if agent_slug in ["performance-analytics", "cmo-growth"] and any(kw in msg_lower for kw in ["analytics", "performance", "sessions", "traffic", "users"]):
        data = MOCK_CONNECTORS["ga4"].get_sessions_last_7d()
        return (f"GA4 last 7 days overview:\n"
                f"• Sessions: {data['sessions']:,}\n"
                f"• Users: {data['users']:,}\n"
                f"• Avg. engagement: {data['avg_engagement_time']}\n"
                f"• Bounce rate: {data['bounce_rate']}%")

    # ── GitHub (nou)
    if agent_slug in ["fullstack-dev", "devops-infra", "backend-architect"] and any(kw in msg_lower for kw in ["commit", "commits", "recent", "github", "repo", "changes"]):
        commits = MOCK_CONNECTORS["github"].list_recent_commits(6)
        lines = [f"{c['date']}  {c['author']:<12}  {c['message'][:68]}" for c in commits]
        stats = MOCK_CONNECTORS["github"].get_repo_stats()
        return (f"Recent commits:\n\n" + "\n".join(lines) + "\n\n" +
                f"Repository stats: {stats['stars']:,} ★  |  {stats['forks']} forks  |  {stats['open_issues']} open issues")

    # ── Stripe (nou)
    if agent_slug in ["cfo-finance", "coo-operations"] and any(kw in msg_lower for kw in ["revenue", "charges", "subscription", "stripe", "payment", "mrr"]):
        charges = MOCK_CONNECTORS["stripe"].get_recent_charges(5)
        lines = [f"{c['created']}  ${c['amount']:.2f}  {c['description']}  ({c['status']})" for c in charges]
        summary = MOCK_CONNECTORS["stripe"].get_subscription_summary()
        return (f"Recent Stripe charges:\n\n" + "\n".join(lines) + "\n\n" +
                f"Summary: ${summary['monthly_recurring_revenue']:,.2f} MRR  |  "
                f"{summary['active_subscriptions']} active subs  |  "
                f"Churn {summary['churn_rate_last_30d']}% last 30d")

    # ── RAG pentru CMO, Analytics, CEO, COO (rapoarte McKinsey/BCG)
    if agent_slug in ["cmo-growth", "performance-analytics", "ceo-strategy", "coo-operations"] and \
       any(kw in msg_lower for kw in ["ai", "generative ai", "gen ai", "marketing", "sales", "personalization", "uplift", "roi", "operating model", "transformation", "organizational redesign", "resilience", "strategy", "operations"]):
        
        # Extragem context RAG
        rag_context = get_rag_context(user_message, top_k=2)
        print(f"DEBUG: RAG context for '{user_message}': {rag_context[:200]}...")  # Debug
        if rag_context:
            agent_insight = {
                "cmo-growth": "marketing and growth strategies",
                "performance-analytics": "data-driven insights and analytics",
                "ceo-strategy": "strategic vision and operating models",
                "coo-operations": "operational excellence and execution"
            }.get(agent_slug, "strategic insights")
            
            return (
                f"[{agent_name}] Here's {agent_insight} powered by expert knowledge:\n\n"
                f"{rag_context}\n\n"
                f"Applying to your query '{user_message}':\n"
                f"- Key takeaway: Focus on scalable, data-backed approaches.\n"
                f"- Recommendation: Start with pilot programs and measure impact.\n"
                f"Need more details? Ask about specific frameworks."
            )

    # Fallback + routing suggestion
    suggestion = None
    for target_slug, keywords in routing_keywords.items():
        if target_slug != agent_slug and any(kw in msg_lower for kw in keywords):
            suggestion = target_slug
            break

    base = f"[{agent_name}] Understood: '{user_message}' → working on it..."
    if suggestion:
        base += f"\n\n(This might be better suited for {get_agent_name('', suggestion)} – want me to transfer you?)"

    return base
