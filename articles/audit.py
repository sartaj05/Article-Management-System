from .models import AuditLog


def record_audit_event(*, actor, action, article=None, target_model='Article', target_id='', details=None):
    return AuditLog.objects.create(
        actor=actor,
        article=article,
        action=action,
        target_model=target_model,
        target_id=str(target_id or (article.pk if article else '')),
        details=details or {},
    )
