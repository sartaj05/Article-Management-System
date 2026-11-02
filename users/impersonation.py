import hashlib

from django.utils import timezone

from .models import ImpersonationSession


SESSION_ID_KEY = 'admin_impersonation_session_id'
SESSION_TOKEN_KEY = 'admin_impersonation_token'


def hash_impersonation_token(token):
    return hashlib.sha256(str(token).encode()).hexdigest()


def activate_impersonation(request):
    """Swap the browser request user only while a valid admin session is active."""
    token = request.session.get(SESSION_TOKEN_KEY)
    session_id = request.session.get(SESSION_ID_KEY)
    if not token or not session_id or not getattr(request.user, 'is_authenticated', False):
        return
    session = ImpersonationSession.objects.select_related('admin', 'target').filter(
        pk=session_id, token_hash=hash_impersonation_token(token), ended_at__isnull=True,
    ).first()
    if session is None:
        request.session.pop(SESSION_ID_KEY, None)
        request.session.pop(SESSION_TOKEN_KEY, None)
        return
    if session.expires_at <= timezone.now() or request.user.pk != session.admin_id:
        session.ended_at = timezone.now()
        session.save(update_fields=['ended_at'])
        request.session.pop(SESSION_ID_KEY, None)
        request.session.pop(SESSION_TOKEN_KEY, None)
        return
    request.user = session.target
    request.impersonating = True
    request.impersonator = session.admin
    request.impersonation_session = session
