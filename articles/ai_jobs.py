"""Execution service for retryable editorial AI jobs."""

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .ai_providers import AIProviderError, LocalRuleBasedProvider, get_editorial_provider
from .models import AIJob, Article, EditorialAssistantRun
from .audit import record_audit_event
from .ai_governance import AIGovernanceError, prepare_ai_request, record_ai_usage


def _context_for(article, action):
    if action != 'fact_check':
        return {}
    return {'sources': list(article.sources.values('id', 'title', 'publisher', 'source_type', 'url', 'notes', 'citation_key'))}


def execute_ai_job(job_id):
    with transaction.atomic():
        job = AIJob.objects.select_for_update().select_related('article', 'requested_by').get(pk=job_id)
        if job.status == 'completed':
            return job
        job.status = 'running'
        job.attempts += 1
        job.started_at = timezone.now()
        job.error = ''
        job.save(update_fields=['status', 'attempts', 'started_at', 'error'])

    try:
        context = _context_for(job.article, job.action)
        ai_request = prepare_ai_request(job.article, job.action)
        result = get_editorial_provider().generate(ai_request.article, job.action, context)
    except AIProviderError as exc:
        if not settings.AI_ASSISTANT_FALLBACK_ENABLED:
            _mark_failed(job_id, str(exc))
            raise
        result = LocalRuleBasedProvider().generate(ai_request.article, job.action, context)
        result.provider = 'local-rule-based-fallback'
        result.metadata.update({'fallback_reason': str(exc)})
    except Exception as exc:
        _mark_failed(job_id, str(exc))
        raise

    run = EditorialAssistantRun.objects.create(
        article=job.article, requested_by=job.requested_by, action=job.action,
        provider=result.provider, model=result.model, suggestions=result.suggestions,
        metadata=result.metadata, latency_ms=result.latency_ms,
    )
    usage = record_ai_usage(user=job.requested_by, article=job.article, action=job.action, result=result, input_text=ai_request.article.content, redacted_pii=ai_request.redacted_pii, job=job)
    result.metadata['usage_event_id'] = usage.id
    AIJob.objects.filter(pk=job_id).update(
        status='completed', provider=result.provider, model=result.model,
        result={'run_id': run.id, 'suggestions': result.suggestions, 'metadata': result.metadata},
        completed_at=timezone.now(),
    )
    record_audit_event(actor=job.requested_by, action='ai_job_completed', article=job.article, details={'job_id': job.id, 'run_id': run.id, 'action': job.action})
    return AIJob.objects.get(pk=job_id)


def _mark_failed(job_id, error):
    AIJob.objects.filter(pk=job_id).update(status='failed', error=str(error)[:2000], completed_at=timezone.now())
