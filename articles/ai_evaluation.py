"""Small, reproducible evaluation harness for editorial AI providers."""

from types import SimpleNamespace

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .ai_providers import AIProviderError, get_editorial_provider
from .models import AIEvaluationCase, AIEvaluationRun, AIPromptVersion


def active_prompt_version():
    prompt = AIPromptVersion.objects.filter(name='editorial-copilot', is_active=True).order_by('-created_at').first()
    return prompt.version if prompt else settings.AI_ASSISTANT_PROMPT_VERSION


def _passes_criteria(suggestions, criteria):
    required_keys = set(criteria.get('required_keys', []))
    if not required_keys.issubset(suggestions):
        return False, f"missing keys: {sorted(required_keys - set(suggestions))}"
    for field in criteria.get('non_empty', []):
        value = suggestions.get(field)
        if not value:
            return False, f"empty field: {field}"
    for field, minimum in criteria.get('min_items', {}).items():
        if len(suggestions.get(field, [])) < int(minimum):
            return False, f"not enough items: {field}"
    forbidden = {str(value).lower() for value in criteria.get('forbidden_terms', [])}
    output_text = str(suggestions).lower()
    if forbidden.intersection(output_text):
        return False, f"forbidden terms: {sorted(forbidden.intersection(output_text))}"
    return True, 'criteria passed'


@transaction.atomic
def run_evaluation(*, actor=None):
    provider = get_editorial_provider()
    cases = list(AIEvaluationCase.objects.filter(is_active=True))
    results = []
    for case in cases:
        article = SimpleNamespace(title=case.title, content=case.content)
        try:
            generated = provider.generate(article, case.action)
            passed, reason = _passes_criteria(generated.suggestions, case.criteria)
            provider_name = generated.provider
        except (AIProviderError, ValueError) as exc:
            passed, reason, provider_name = False, str(exc), getattr(provider, 'name', settings.AI_ASSISTANT_PROVIDER)
        results.append({'case': case.name, 'action': case.action, 'passed': passed, 'reason': reason})
    passed_count = sum(1 for result in results if result['passed'])
    total = len(results)
    run = AIEvaluationRun.objects.create(
        prompt_version=active_prompt_version(), provider=provider_name if cases else settings.AI_ASSISTANT_PROVIDER,
        total_cases=total, passed_cases=passed_count, score=round((passed_count / total) * 100, 2) if total else 0,
        results=results, created_by=actor,
    )
    return run
