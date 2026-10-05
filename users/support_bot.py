"""Deterministic, project-documentation-based support answers.

This module intentionally does not call an external AI provider. It gives users
helpful answers for the workflows implemented in this project while keeping
unknown questions safe and predictable.
"""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SupportTopic:
    key: str
    keywords: tuple[str, ...]
    answer: str
    links: tuple[tuple[str, str], ...] = ()


TOPICS = (
    SupportTopic(
        "getting-started",
        ("start", "begin", "register", "sign up", "login", "log in", "account"),
        "Create an account, log in, and choose the workspace that matches your role. Authors can draft articles, while reviewers and administrators manage the publishing workflow.",
        (("Create an account", "/register-template/"), ("Log in", "/login-template/")),
    ),
    SupportTopic(
        "article-workflow",
        ("draft", "submit", "review", "approve", "publish", "workflow", "article status", "article"),
        "Write an article as a draft, submit it for editorial review, and publish it after approval. The article list shows your current status and available actions.",
        (("Browse articles", "/#articles"),),
    ),
    SupportTopic(
        "seo",
        ("seo", "search engine", "meta title", "meta description", "canonical", "sitemap"),
        "Use the article SEO fields for a search title, description, canonical URL, and structured metadata. The project also exposes sitemap, RSS, and robots endpoints for discovery.",
        (("Sitemap", "/sitemap.xml"), ("RSS feed", "/rss.xml")),
    ),
    SupportTopic(
        "media",
        ("media", "image", "photo", "video", "audio", "upload"),
        "Use the media workflow to upload and reuse assets. Add alt text, captions, credits, and license details; archive unused assets and avoid duplicate uploads when the same file is already available.",
        (("Developer API guide", "/api/developer.json"),),
    ),
    SupportTopic(
        "security",
        ("security", "session", "password", "token", "logout", "privacy", "delete account"),
        "The Security Center helps you review security events and revoke active sessions. Password reset, privacy preferences, export, and deletion requests are available from the account area.",
        (("Security events", "/api/security/events/"), ("Privacy preferences", "/api/privacy/preferences/")),
    ),
    SupportTopic(
        "analytics",
        ("analytics", "views", "read time", "engagement", "report"),
        "Article analytics can summarize views, reading time, and engagement. Reader consent and privacy settings control how analytics data is collected and used.",
        (("Developer API guide", "/api/developer.json"),),
    ),
    SupportTopic(
        "newsletter",
        ("newsletter", "email", "subscribe", "unsubscribe", "digest"),
        "Readers can subscribe to newsletter editions and unsubscribe later. Editorial users can prepare previews before an edition is sent to subscribers.",
        (("Newsletter API", "/api/newsletter/subscribe/"),),
    ),
    SupportTopic(
        "membership",
        ("membership", "premium", "subscription", "paywall", "paid"),
        "Premium articles require an active membership. Membership plans and signed membership webhooks support subscription state changes and access checks.",
        (("Membership plans", "/api/membership/plans/"),),
    ),
    SupportTopic(
        "accessibility",
        ("accessibility", "alt text", "contrast", "screen reader", "large text"),
        "Use the accessibility preferences to improve reading comfort and enable larger text or contrast support. Published media should include meaningful alternative text.",
        (("Accessibility preferences", "/api/accessibility/preferences/"),),
    ),
    SupportTopic(
        "developer",
        ("api", "developer", "webhook", "integration", "api key"),
        "The developer API exposes documented integration endpoints. API keys, webhook endpoints, delivery records, and signed webhook requests are available for approved integrations.",
        (("Developer API guide", "/api/developer.json"),),
    ),
)

WELCOME = "Hi! I can help with this project’s account, article, SEO, media, security, analytics, newsletter, membership, accessibility, and API workflows."
FALLBACK = "I could not match that question to the current project guide. Try asking about submitting an article, article SEO, media uploads, security sessions, newsletters, accessibility, or the developer API."
PRIVATE_QUERY = re.compile(r"\b(my|our)\s+(password|api key|token|secret|private data|account data)\b")


def _topic_score(message: str, topic: SupportTopic) -> int:
    return sum(1 for keyword in topic.keywords if keyword in message)


def get_support_response(message: str) -> dict:
    """Return a stable support response without exposing private project data."""

    normalized = re.sub(r"\s+", " ", str(message or "").strip().lower())[:500]
    if not normalized:
        return {
            "topic": "welcome",
            "answer": WELCOME,
            "links": [],
            "suggestions": ["How do I submit an article?", "How do I improve article SEO?", "How do I revoke a session?"],
            "source": "project-documentation",
        }

    if PRIVATE_QUERY.search(normalized):
        return {
            "topic": "fallback",
            "answer": FALLBACK,
            "links": [],
            "suggestions": ["How do I submit an article?", "How do I improve article SEO?", "How do I revoke a session?"],
            "source": "project-documentation",
        }

    matches = sorted(
        ((-_topic_score(normalized, topic), index, topic) for index, topic in enumerate(TOPICS)),
        key=lambda item: (item[0], item[1]),
    )
    score, _, topic = matches[0]
    if score == 0:
        return {
            "topic": "fallback",
            "answer": FALLBACK,
            "links": [],
            "suggestions": ["How do I submit an article?", "How do I improve article SEO?", "How do I revoke a session?"],
            "source": "project-documentation",
        }

    return {
        "topic": topic.key,
        "answer": topic.answer,
        "links": [{"label": label, "url": url} for label, url in topic.links],
        "suggestions": ["How do I submit an article?", "How do I improve article SEO?", "How do I revoke a session?"],
        "source": "project-documentation",
    }
