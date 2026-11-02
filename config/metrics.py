from django.conf import settings
from django.http import HttpResponse, JsonResponse

from .observability import metrics_payload


def metrics_view(request):
    """Expose Prometheus metrics only to callers with the configured token."""
    configured_token = getattr(settings, 'METRICS_TOKEN', '')
    supplied_token = request.headers.get('X-Metrics-Token', '')
    if not configured_token or supplied_token != configured_token:
        return JsonResponse({'detail': 'Metrics access is not configured.'}, status=404)
    return HttpResponse(metrics_payload(), content_type='text/plain; version=0.0.4')
