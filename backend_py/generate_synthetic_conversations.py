"""
Generare overnight de conversații sintetice pentru cei 20 de agenți Camarad.ai
Rulează 6-8 ore pe CPU, salvează progresiv în JSONL
"""

import json
import time
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

# ── CONFIG (modifică după nevoie) ──────────────────────────────────────────────
OUTPUT_DIR = Path("synthetic_datasets")
OUTPUT_DIR.mkdir(exist_ok=True)

TOTAL_EXAMPLES = 50400          # țintă ~50k pentru ~7 ore (cu sleep 100s)
EXAMPLES_PER_AGENT = TOTAL_EXAMPLES // 20  # ~2520 per agent
BATCH_SIZE = 200               # salvează la fiecare 200 ca să nu pierzi progres
SLEEP_BETWEEN = 100            # 100s delay pentru ~7 ore total

# ── Agenții și stiluri lor (exact din proiectul tău) ───────────────────────────
AGENTS = {
    # Personal
    "life-coach": {"name": "Life Coach", "style": "empathetic, motivational, goal-oriented, actionable steps"},
    "psychologist": {"name": "Psychologist", "style": "empathetic, non-judgmental, reflective questions, emotional insight"},
    "personal-mentor": {"name": "Personal Teacher / Mentor", "style": "patient teacher, explanations, learning plans"},
    "fitness-wellness": {"name": "Fitness & Wellness Coach", "style": "practical routines, nutrition tips, mind-body balance"},
    "creative-muse": {"name": "Creative Muse", "style": "inspirational, idea brainstorming, artistic prompts"},

    # Business
    "ceo-strategy": {"name": "CEO / Vision & Strategy", "style": "strategic, long-term vision, leverage, moats, decisive frameworks"},
    "cto-innovation": {"name": "CTO / Tech & Innovation", "style": "technical depth, scalability, architecture choices"},
    "cmo-growth": {"name": "CMO / Marketing & Growth", "style": "growth hacking, channels, funnels, metrics-driven"},
    "cfo-finance": {"name": "CFO / Finance & Numbers", "style": "numbers-focused, cash flow, burn rate, valuation"},
    "coo-operations": {"name": "COO / Operations & Execution", "style": "processes, efficiency, team execution, SOPs"},

    # Agency
    "ppc-specialist": {"name": "PPC Specialist", "style": "paid ads tactics, bidding, ROAS, campaign optimization"},
    "seo-content": {"name": "SEO & Content Strategist", "style": "keyword research, content pillars, backlinks, SERP"},
    "creative-director": {"name": "Creative Director / Designer", "style": "visual identity, branding, design principles"},
    "social-media": {"name": "Social Media Manager", "style": "content calendar, engagement, virality, community"},
    "performance-analytics": {"name": "Performance & Analytics Expert", "style": "data-driven, dashboards, attribution, A/B"},

    # Development
    "devops-infra": {"name": "DevOps & Infrastructure Engineer", "style": "CI/CD, cloud infra, monitoring, reliability"},
    "fullstack-dev": {"name": "Full-Stack Developer", "style": "code examples, frontend+backend, debugging tips"},
    "backend-architect": {"name": "Backend Architect", "style": "system design, APIs, databases, scalability"},
    "frontend-uiux": {"name": "Frontend / UI-UX Specialist", "style": "UI patterns, accessibility, user flows"},
    "security-quality": {"name": "Security & Code Quality Engineer", "style": "security best practices, testing, clean code"},
}

# ── Template-uri user prompt generice (variație random) ────────────────────────
USER_PROMPT_TEMPLATES = [
    "How do I {action} in my current situation?",
    "What should be my next step for {goal}?",
    "I'm struggling with {problem} – advice?",
    "Analyze this: {scenario}",
    "Best way to optimize {metric} right now?",
    "Should I {decision} or wait?",
    "Help me plan {activity} for the next {timeframe}",
    "Explain {concept} like I'm a beginner",
    "Generate ideas for {topic}",
    "Review my approach to {issue}",
]

# ── Funcție simplă de generare răspuns mock (CPU-friendly, variat) ─────────────
def generate_mock_response(agent_style: str, user_msg: str) -> str:
    prefixes = [
        f"**{agent_style.capitalize()} perspective**",
        "Thinking step-by-step:",
        "Key insight:",
        "Recommended action:",
        "Framework to use:",
    ]
    content = random.choice([
        f"First, understand the root: {user_msg[:30]}... Then prioritize leverage.",
        f"Break it down: 1. Assess current state. 2. Define goal. 3. Execute small wins.",
        f"Potential risks: burnout / misalignment. Mitigation: delegate + measure.",
        f"Idea generation: {random.randint(3,7)} options – pick the one with highest leverage.",
        f"Metrics to watch: {random.choice(['ROI', 'CAC', 'LTV', 'velocity', 'engagement'])}.",
    ])
    return f"{random.choice(prefixes)}\n\n{content}\n\nAlways iterate based on feedback."

# ── Main loop ──────────────────────────────────────────────────────────────────
def main():
    total_generated = 0
    start_time = time.time()

    for agent_slug, info in AGENTS.items():
        print(f"\nStarting agent: {info['name']} ({agent_slug})")
        agent_file = OUTPUT_DIR / f"{agent_slug}_synthetic.jsonl"

        batch = []
        for i in range(EXAMPLES_PER_AGENT):
            # Generează user prompt variat
            template = random.choice(USER_PROMPT_TEMPLATES)
            action = random.choice(["scale faster", "reduce costs", "improve team morale", "launch new feature", "fix retention"])
            goal = random.choice(["hit $10k MRR", "build strong culture", "optimize ad spend", "ship v2"])
            problem = random.choice(["decision fatigue", "slow growth", "tech debt", "creative block"])
            user_msg = template.format(
                action=action, goal=goal, problem=problem,
                scenario=f"a startup at {random.choice(['seed', 'Series A', 'bootstrapped'])} stage",
                metric=random.choice(["conversion rate", "velocity", "burn rate"]),
                decision=random.choice(["hire now", "pivot", "raise funds"]),
                timeframe=random.choice(["week", "month", "quarter"]),
                concept=random.choice(["leverage", "moat", "OKRs", "unit economics"]),
                topic=random.choice(["content strategy", "branding", "infrastructure"]),
                issue=random.choice(["scaling ops", "security audit", "UI redesign"]),
                activity=random.choice(["a product launch", "team expansion", "budget allocation"]),
            )

            assistant_msg = generate_mock_response(info['style'], user_msg)

            entry = {
                "messages": [
                    {"role": "system", "content": f"You are {info['name']}. {info['style'].capitalize()} responses."},
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": assistant_msg}
                ],
                "agent": agent_slug,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source": "synthetic-overnight-2026"
            }
            batch.append(entry)
            total_generated += 1

            if len(batch) >= BATCH_SIZE:
                with open(agent_file, "a", encoding="utf-8") as f:
                    for ex in batch:
                        f.write(json.dumps(ex, ensure_ascii=False) + "\n")
                batch = []
                elapsed = (time.time() - start_time) / 3600
                print(f"  {total_generated:5d} total | {elapsed:.2f}h | saved batch for {info['name']}")
                time.sleep(SLEEP_BETWEEN)

        # Ultima batch per agent
        if batch:
            with open(agent_file, "a", encoding="utf-8") as f:
                for ex in batch:
                    f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    total_hours = (time.time() - start_time) / 3600
    print(f"\nFINISHED OVERNIGHT RUN")
    print(f"Total examples: {total_generated}")
    print(f"Time: {total_hours:.2f} hours")
    print(f"Files saved in: {OUTPUT_DIR.resolve()}")
    for slug in AGENTS:
        file = OUTPUT_DIR / f"{slug}_synthetic.jsonl"
        if file.exists():
            size_mb = file.stat().st_size / (1024 * 1024)
            print(f"  - {slug}: {file.stat().st_size:,} bytes (~{size_mb:.1f} MB)")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user – partial files are saved.")