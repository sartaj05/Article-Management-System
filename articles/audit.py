from .models import AuditLog


def record_audit_event(*, actor, action, article=None, workspace=None, target_model='Article', target_id='', details=None):
    return AuditLog.objects.create(
        actor=actor,
        article=article,
        workspace=workspace or getattr(article, 'workspace', None),
        action=action,
        target_model=target_model,
        target_id=str(target_id or (article.pk if article else '')),
        details=details or {},
    )
