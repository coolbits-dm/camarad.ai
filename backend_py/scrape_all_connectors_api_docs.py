# scrape_all_connectors_api_docs.py
import requests
from bs4 import BeautifulSoup
import sqlite3
from pathlib import Path
import time
import random
from tqdm import tqdm
import re
from urllib.parse import urljoin, urlparse

DB_PATH = Path("connectors_api_docs.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        connector TEXT,
        url TEXT UNIQUE,
        title TEXT,
        content TEXT,
        section_type TEXT,
        fetched_at TEXT,
        depth INTEGER DEFAULT 0
    )
""")
conn.commit()

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Lista completă de conectori + URL-uri de start oficiale
CONNECTORS = {
    "Google Ads": "https://developers.google.com/google-ads/api/docs/start",
    "Google Analytics 4": "https://developers.google.com/analytics/devguides/reporting/data/v1",
    "Google Search Console": "https://developers.google.com/webmaster-tools/v1/api-ref",
    "Google Tag Manager": "https://developers.google.com/tag-platform/tag-manager/api/v2",
    "Google Business Profile": "https://developers.google.com/my-business/content/prereqs",
    "Google Merchant Center": "https://developers.google.com/shopping-content/guides/quickstart",
    "Google Calendar": "https://developers.google.com/calendar/api/v3/reference",
    "Google Drive": "https://developers.google.com/drive/api/v3/reference",
    "Gmail": "https://developers.google.com/gmail/api/reference/rest",
    "Google Cloud Platform": "https://cloud.google.com/apis/docs/overview",
    "Google Gemini": "https://ai.google.dev/gemini-api/docs",
    "Meta Ads": "https://developers.facebook.com/docs/marketing-api",
    "TikTok Ads": "https://ads.tiktok.com/marketing_api/docs",
    "LinkedIn Ads": "https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads-reporting",
    "Twitter/X Ads": "https://developer.twitter.com/en/docs/twitter-ads-api",
    "Pinterest Ads": "https://developers.pinterest.com/docs/api/v5/",
    "Snapchat Ads": "https://businesshelp.snapchat.com/s/article/ads-api?language=en_US",
    "xAI Grok API": "https://docs.x.ai/docs/getting-started",
    "OpenAI": "https://platform.openai.com/docs/api-reference",
    "Anthropic": "https://docs.anthropic.com/en/api/getting-started",
    "Google Gemini": "https://ai.google.dev/gemini-api/docs",
    "Meta Llama": "https://llama.meta.com/docs/model-cards-and-prompt-formats/llama3_1",
    "Mistral": "https://docs.mistral.ai/api/",
    "Cohere": "https://docs.cohere.com/reference/about-the-api",
    "Perplexity API": "https://docs.perplexity.ai/docs/getting-started",
    "Hugging Face Inference": "https://huggingface.co/docs/api-inference/index",
    "Groq": "https://console.groq.com/docs/quickstart",
    "GitHub": "https://docs.github.com/en/rest",
    "GitLab": "https://docs.gitlab.com/ee/api/",
    "Bitbucket": "https://developer.atlassian.com/bitbucket/api/2/reference/",
    "Docker Hub": "https://docs.docker.com/reference/api/hub/latest/",
    "AWS": "https://docs.aws.amazon.com/general/latest/gr/welcome.html",
    "Microsoft Azure": "https://learn.microsoft.com/en-us/rest/api/azure/",
    "Vercel": "https://vercel.com/docs/rest-api",
    "Netlify": "https://docs.netlify.com/api/get-started/",
    "Render": "https://render.com/docs/api",
    "Sentry": "https://docs.sentry.io/api/",
    "Datadog": "https://docs.datadoghq.com/api/latest/",
    "SonarQube": "https://sonarcloud.io/web_api",
    "Snyk": "https://docs.snyk.io/snyk-api",
    "GitHub Actions": "https://docs.github.com/en/rest/actions",
    "Jenkins": "https://www.jenkins.io/doc/book/managing/remote-access-api/",
    "Stripe": "https://docs.stripe.com/api",
    "PayPal": "https://developer.paypal.com/api/rest/",
    "QuickBooks": "https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/account",
    "Xero": "https://developer.xero.com/documentation/api/api-overview",
    "Shopify": "https://shopify.dev/docs/api/admin-rest",
    "HubSpot": "https://developers.hubspot.com/docs/api/overview",
    "Salesforce": "https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/intro_what_is_rest_api.htm",
    "Pipedrive": "https://developers.pipedrive.com/docs/api/v1",
    "Mailchimp": "https://mailchimp.com/developer/marketing/api/",
    "Klaviyo": "https://developers.klaviyo.com/en/reference/api-overview",
    "Zapier": "https://developer.zapier.com/docs/platform/quickstart/introduction",
    "Notion": "https://developers.notion.com/reference/intro",
    "Todoist": "https://developer.todoist.com/rest/v2",
    "TickTick": "https://developer.ticktick.com/api",
    "Strava": "https://developers.strava.com/docs/reference/",
    "MyFitnessPal": "https://www.myfitnesspal.com/api",
    "Telegram": "https://core.telegram.org/bots/api",
}

def clean_text(text):
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def scrape_page(url, connector, depth=0, max_depth=4):
    if depth > max_depth:
        return

    if cursor.execute("SELECT 1 FROM api_docs WHERE url = ?", (url,)).fetchone():
        return

    print(f"[{depth}] Scraping {connector}: {url}")

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  Skip - {r.status_code}")
            return

        soup = BeautifulSoup(r.text, 'html.parser')

        title = soup.title.string if soup.title else url.split('/')[-1]
        content_parts = []

        for tag in soup.find_all(['h1', 'h2', 'h3', 'p', 'pre', 'code', 'li', 'table']):
            if tag.name == 'table':
                content_parts.append(tag.get_text(separator=' ', strip=True))
            else:
                content_parts.append(tag.get_text(strip=True))

        content = clean_text(' '.join(content_parts))
        if len(content) < 400:
            print("  Skip - too short")
            return

        section_type = "unknown"
        url_lower = url.lower()
        if any(x in url_lower for x in ['endpoint', 'api', 'reference', 'method']):
            section_type = "endpoint"
        elif any(x in url_lower for x in ['changelog', 'release', 'version', 'update']):
            section_type = "changelog"
        elif 'guide' in url_lower or 'tutorial' in url_lower:
            section_type = "guide"
        elif len(content_parts) > 30:
            section_type = "reference"

        cursor.execute("""
            INSERT OR IGNORE INTO api_docs
            (connector, url, title, content, section_type, fetched_at, depth)
            VALUES (?, ?, ?, ?, ?, datetime('now'), ?)
        """, (connector, url, title, content, section_type, depth))
        conn.commit()

        print(f"  Saved: {title[:100]}... ({len(content):,} chars)")

        # Urmărește link-uri interne
        base_domain = urlparse(url).netloc
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(url, href)
            if full_url.startswith('http') and base_domain in urlparse(full_url).netloc:
                if full_url not in links:
                    links.append(full_url)
                    if len(links) >= 10:  # max 10 per pagină
                        break

        for link in links:
            time.sleep(random.uniform(10, 20))  # 10–20 sec între request-uri
            scrape_page(link, connector, depth + 1, max_depth)

    except Exception as e:
        print(f"  Error: {e}")

def main():
    print("Starting overnight API docs scraping...")
    for connector, start_url in tqdm(CONNECTORS.items()):
        print(f"\n=== {connector} ===")
        scrape_page(start_url, connector)
        time.sleep(30)  # pauză mare între conectori

    conn.close()
    print("\nFinished scraping!")
    print("Database saved:", DB_PATH.resolve())
    print("Query example: SELECT * FROM api_docs WHERE connector = 'Google Ads' AND section_type = 'endpoint'")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped early – data saved up to now.")
        conn.close()