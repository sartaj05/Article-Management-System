"""Provider adapters for the editorial AI copilot.

The application keeps the deterministic provider available for local development
and tests, while the OpenAI-compatible adapter adds a production integration
without putting provider-specific code in the API view.
"""

from dataclasses import dataclass, field
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from .assistant import make_suggestions


class AIProviderError(RuntimeError):
    """Raised when an AI provider cannot return a valid editorial result."""


@dataclass
class AIResult:
    suggestions: dict
    provider: str
    model: str = ""
    latency_ms: int = 0
    metadata: dict = field(default_factory=dict)


class LocalRuleBasedProvider:
    name = "local-rule-based"

    def generate(self, article, action, context=None):
        started = time.perf_counter()
        context = context or {}
        if action == 'fact_check':
            from .fact_checking import make_fact_check_suggestions
            suggestions = make_fact_check_suggestions(article, context.get('sources', []))
        else:
            suggestions = make_suggestions(article, action)
        return AIResult(
            suggestions=suggestions,
            provider=self.name,
            model="rules-v1",
            latency_ms=round((time.perf_counter() - started) * 1000),
            metadata={"mode": "deterministic", "prompt_version": "editorial-v1"},
        )


class OpenAICompatibleProvider:
    name = "openai"

    def __init__(self, api_key=None, base_url=None, model=None, timeout=None):
        self.api_key = api_key or settings.AI_ASSISTANT_API_KEY
        self.base_url = base_url or settings.AI_ASSISTANT_BASE_URL
        self.model = model or settings.AI_ASSISTANT_MODEL
        self.timeout = timeout or settings.AI_ASSISTANT_TIMEOUT

    def generate(self, article, action, context=None):
        if not self.api_key:
            raise AIProviderError("AI_ASSISTANT_API_KEY is not configured.")

        payload = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an editorial copilot. Return only valid JSON. "
                        "Do not invent facts, sources, quotes, or statistics. "
                        "Every result requires human review before publication."
                    ),
                },
                {"role": "user", "content": self._prompt(article, action, context or {})},
            ],
        }
        request = Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "article-management-system/editorial-copilot",
            },
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise AIProviderError(f"OpenAI request failed: {exc}") from exc

        try:
            content = body["choices"][0]["message"]["content"]
            suggestions = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AIProviderError("OpenAI returned an invalid structured response.") from exc

        self._validate(action, suggestions)
        usage = body.get("usage") or {}
        return AIResult(
            suggestions=suggestions,
            provider=self.name,
            model=self.model,
            latency_ms=round((time.perf_counter() - started) * 1000),
            metadata={
                "mode": "remote",
                "prompt_version": "editorial-v1",
                "usage": {
                    key: usage[key]
                    for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                    if key in usage
                },
            },
        )

    @staticmethod
    def _prompt(article, action, context):
        schemas = {
            "summarize": '{"summary": "A concise 1-2 sentence summary under 420 characters."}',
            "headline": '{"headlines": ["Three accurate headline options, each under 80 characters."]}',
            "seo": '{"meta_title": "Under 60 characters", "meta_description": "Under 160 characters", "seo_keywords": "comma-separated keywords"}',
            "proofread": '{"content": "The corrected article content, preserving meaning and facts."}',
            "fact_check": '{"claims": [{"claim": "Exact claim from the article", "verdict": "verified|partly_verified|unverified|false", "confidence": 0.0, "explanation": "Evidence-based explanation", "source_ids": [1], "source_citations": [{"id": 1, "title": "Source title", "url": "https://..."}], "unresolved": true}]}',
        }
        source_text = '\n'.join(
            f"[{source.get('id')}] {source.get('title')} | {source.get('publisher')} | {source.get('source_type')} | {source.get('url')} | {source.get('notes')}"
            for source in context.get('sources', [])
        )
        return (
            f"Action: {action}\n"
            f"Return JSON matching this shape: {schemas.get(action, '{}')}\n\n"
            f"Title: {article.title}\n"
            f"Article:\n{article.content[:12000]}\n\n"
            f"Available sources (use only these IDs; do not invent citations):\n{source_text or '[none]'}"
        )

    @staticmethod
    def _validate(action, suggestions):
        if not isinstance(suggestions, dict):
            raise AIProviderError("AI output must be a JSON object.")
        required = {
            "summarize": {"summary"},
            "headline": {"headlines"},
            "seo": {"meta_title", "meta_description", "seo_keywords"},
            "proofread": {"content"},
            "fact_check": {"claims"},
        }.get(action)
        if required is None:
            raise AIProviderError("Unsupported editorial AI action.")
        if not required.issubset(suggestions):
            raise AIProviderError("AI output did not match the requested schema.")
        if action == "headline" and not isinstance(suggestions["headlines"], list):
            raise AIProviderError("AI headlines must be returned as a list.")
        if action == "fact_check" and not isinstance(suggestions["claims"], list):
            raise AIProviderError("AI claims must be returned as a list.")
        for key, value in suggestions.items():
            if key != "headlines" and not isinstance(value, str):
                raise AIProviderError("AI text fields must be strings.")


def get_editorial_provider():
    if settings.AI_ASSISTANT_PROVIDER == "openai":
        return OpenAICompatibleProvider()
    return LocalRuleBasedProvider()
