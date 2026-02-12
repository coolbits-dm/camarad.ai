# mocks/connectors.py
from datetime import datetime, timedelta
from typing import Dict, List, Any
import random

class MockGoogleAds:
    @staticmethod
    def list_campaigns() -> List[Dict[str, Any]]:
        return [
            {"id": "1234567890", "name": "Summer Sale RO", "status": "ENABLED", "budget": 150.0, "clicks": 2841, "impressions": 87420, "cost": 412.67},
            {"id": "0987654321", "name": "Brand Awareness", "status": "PAUSED", "budget": 80.0, "clicks": 0, "impressions": 0, "cost": 0.0},
        ]

    @staticmethod
    def get_performance_last_30d() -> Dict[str, Any]:
        return {
            "period": "last 30 days",
            "clicks": 3124,
            "impressions": 96210,
            "cost": 458.19,
            "conversions": 47,
            "conv_value": 3840.50
        }

class MockGA4:
    @staticmethod
    def get_sessions_last_7d() -> Dict[str, Any]:
        return {
            "date_range": "last 7 days",
            "sessions": 1842,
            "users": 1376,
            "avg_engagement_time": "1m 48s",
            "bounce_rate": 41.3
        }

    @staticmethod
    def top_pages() -> List[Dict[str, Any]]:
        return [
            {"page": "/home", "views": 1245, "avg_time": "2m 15s"},
            {"page": "/products", "views": 892, "avg_time": "1m 42s"},
            {"page": "/about", "views": 567, "avg_time": "58s"},
        ]

class MockGitHub:
    @staticmethod
    def list_recent_commits(limit: int = 5) -> List[Dict[str, Any]]:
        today = datetime.now()
        return [
            {
                "sha": f"abc{random.randint(1000,9999)}def",
                "message": random.choice([
                    "Fix login validation edge case",
                    "Refactor user service layer",
                    "Add caching for dashboard queries",
                    "Update dependencies + security patch",
                    "Implement dark mode toggle"
                ]),
                "author": random.choice(["dev-alex", "mihai-dev", "ana-frontend"]),
                "date": (today - timedelta(days=random.randint(0, 14))).strftime("%Y-%m-%d %H:%M"),
                "additions": random.randint(10, 320),
                "deletions": random.randint(0, 180)
            } for _ in range(limit)
        ]

    @staticmethod
    def get_repo_stats() -> Dict[str, Any]:
        return {
            "stars": random.randint(120, 3400),
            "forks": random.randint(15, 820),
            "open_issues": random.randint(3, 42),
            "last_commit": (datetime.now() - timedelta(hours=random.randint(2, 96))).strftime("%Y-%m-%d %H:%M"),
            "main_branch_status": "All checks passed"
        }

class MockStripe:
    @staticmethod
    def get_recent_charges(limit: int = 5) -> List[Dict[str, Any]]:
        amounts = [19.99, 49.00, 99.00, 149.50, 9.99, 299.00]
        return [
            {
                "id": f"ch_{random.randint(100000,999999)}",
                "amount": random.choice(amounts),
                "currency": "USD",
                "status": random.choice(["succeeded", "succeeded", "succeeded", "pending"]),
                "created": (datetime.now() - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))).strftime("%Y-%m-%d %H:%M"),
                "description": random.choice(["Pro Plan Monthly", "Team Plan Yearly", "One-time Consulting", "Custom Add-on"])
            } for _ in range(limit)
        ]

    @staticmethod
    def get_subscription_summary() -> Dict[str, Any]:
        return {
            "active_subscriptions": random.randint(18, 87),
            "monthly_recurring_revenue": round(random.uniform(1200, 9800), 2),
            "churn_rate_last_30d": round(random.uniform(1.8, 7.4), 1),
            "trial_ending_soon": random.randint(2, 11)
        }

MOCK_CONNECTORS = {
    "google_ads": MockGoogleAds,
    "ga4": MockGA4,
    "github": MockGitHub,
    "stripe": MockStripe,
}