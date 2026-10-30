"""Workspace policy, PII minimization, and usage accounting for AI calls."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import math
import re
from types import SimpleNamespace

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from .models import AIUsageEvent, AIWorkspacePolicy


class AIGovernanceError(RuntimeError):
    pass


@dataclass
class AIRequestContext:
    article: object
    policy: object
    redacted_pii: bool


def get_policy(article):
    if not article.workspace_id:
        return None
    return AIWorkspacePolicy.objects.filter(workspace_id=article.workspace_id).first()


def _redact(value):
    redacted = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", '[REDACTED_EMAIL]', value, flags=re.IGNORECASE)
    redacted = re.sub(r"\b(?:\+?\d[\d ()-]{8,}\d)\b", '[REDACTED_PHONE]', redacted)
    return redacted


def prepare_ai_request(article, action):
    policy = get_policy(article)
    if policy and not policy.enabled:
        raise AIGovernanceError('AI assistance is disabled for this workspace.')
    if policy and policy.allowed_actions and action not in policy.allowed_actions:
        raise AIGovernanceError(f'AI action not allowed by workspace policy: {action}.')
    if policy:
        current = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        tokens = AIUsageEvent.objects.filter(workspace_id=article.workspace_id, created_at__gte=current).aggregate(total=Sum('total_tokens'))['total'] or 0
        if policy.monthly_token_budget and tokens >= policy.monthly_token_budget:
            raise AIGovernanceError('The workspace monthly AI token budget has been reached.')
        if policy.monthly_spend_limit:
            spend = AIUsageEvent.objects.filter(workspace_id=article.workspace_id, created_at__gte=current).aggregate(total=Sum('estimated_cost'))['total'] or Decimal('0')
            if spend >= policy.monthly_spend_limit:
                raise AIGovernanceError('The workspace monthly AI spend limit has been reached.')
    content = (article.content or '')[:(policy.max_input_chars if policy else 12000)]
    redacted_content = _redact(content) if policy and policy.redact_pii else content
    return AIRequestContext(SimpleNamespace(title=article.title, content=redacted_content), policy, redacted_content != content)


def record_ai_usage(*, user, article, action, result, input_text, redacted_pii=False, job=None):
    usage = result.metadata.get('usage', {}) if isinstance(result.metadata, dict) else {}
    prompt_tokens = int(usage.get('prompt_tokens') or max(1, math.ceil(len(input_text or '') / 4)))
    completion_tokens = int(usage.get('completion_tokens') or max(1, math.ceil(len(str(result.suggestions)) / 4)))
    total_tokens = int(usage.get('total_tokens') or prompt_tokens + completion_tokens)
    cost = Decimal(str((total_tokens / 1000) * settings.AI_ASSISTANT_COST_PER_1K_TOKENS)).quantize(Decimal('0.0001'))
    return AIUsageEvent.objects.create(
        workspace_id=article.workspace_id, user=user, article=article, job=job,
        provider=result.provider, model=result.model, action=action,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens,
        estimated_cost=cost, redacted_pii=redacted_pii, metadata=result.metadata or {},
    )
