"""Low-dependency observability primitives used by web and worker deployments."""

import contextvars
import json
import logging
import time

request_id_context = contextvars.ContextVar('request_id', default='-')
logger = logging.getLogger(__name__)
_otel_initialized = False

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

    REQUEST_COUNT = Counter('article_studio_http_requests_total', 'HTTP requests handled', ['method', 'status'])
    REQUEST_LATENCY = Histogram('article_studio_http_request_duration_seconds', 'HTTP request duration', ['method'])
except ImportError:  # Local development does not need the production metrics package.
    CONTENT_TYPE_LATEST = 'text/plain; version=0.0.4'
    REQUEST_COUNT = None
    REQUEST_LATENCY = None

    def generate_latest():
        return b''


class JsonFormatter(logging.Formatter):
    """Emit one searchable JSON object per log line."""

    def format(self, record):
        payload = {
            'timestamp': self.formatTime(record, '%Y-%m-%dT%H:%M:%S%z'),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'request_id': request_id_context.get(),
        }
        if hasattr(record, 'request_method'):
            payload['method'] = record.request_method
        if hasattr(record, 'request_path'):
            payload['path'] = record.request_path
        if hasattr(record, 'status_code'):
            payload['status_code'] = record.status_code
        if hasattr(record, 'duration_ms'):
            payload['duration_ms'] = record.duration_ms
        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def record_request(method, path, status_code, duration_seconds):
    from django.core.cache import cache
    bucket = int(time.time() // 60)
    total_key = f'ops:http-total:{bucket}'
    error_key = f'ops:http-errors:{bucket}'
    try:
        cache.add(total_key, 0, timeout=600)
        cache.incr(total_key)
        if int(status_code) >= 500:
            cache.add(error_key, 0, timeout=600)
            cache.incr(error_key)
    except Exception:
        pass
    if REQUEST_COUNT is not None:
        REQUEST_COUNT.labels(method=method, status=str(status_code)).inc()
    if REQUEST_LATENCY is not None:
        REQUEST_LATENCY.labels(method=method).observe(duration_seconds)


def request_error_rate(window_minutes=5):
    from django.core.cache import cache
    now_bucket = int(time.time() // 60)
    total = errors = 0
    for bucket in range(now_bucket - max(1, window_minutes) + 1, now_bucket + 1):
        total += int(cache.get(f'ops:http-total:{bucket}', 0) or 0)
        errors += int(cache.get(f'ops:http-errors:{bucket}', 0) or 0)
    return {'total': total, 'errors': errors, 'rate': errors / total if total else 0.0}


def metrics_payload():
    return generate_latest()


def init_sentry():
    """Initialize Sentry only when a DSN is explicitly configured."""
    try:
        import sentry_sdk
    except ImportError:
        return False
    from django.conf import settings

    dsn = getattr(settings, 'SENTRY_DSN', '')
    if not dsn:
        return False
    sentry_sdk.init(
        dsn=dsn,
        environment=getattr(settings, 'SENTRY_ENVIRONMENT', 'production' if not settings.DEBUG else 'development'),
        traces_sample_rate=getattr(settings, 'SENTRY_TRACES_SAMPLE_RATE', 0.0),
        send_default_pii=False,
    )
    return True


def init_otel():
    """Install optional Django/requests OpenTelemetry instrumentation."""
    global _otel_initialized
    if _otel_initialized:
        return True
    from django.conf import settings
    if not getattr(settings, 'OTEL_ENABLED', False):
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning('OTEL_ENABLED is true but OpenTelemetry dependencies are not installed')
        return False
    provider = TracerProvider(resource=Resource.create({'service.name': settings.OTEL_SERVICE_NAME}))
    exporter_kwargs = {}
    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        exporter_kwargs['endpoint'] = settings.OTEL_EXPORTER_OTLP_ENDPOINT
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(**exporter_kwargs)))
    trace.set_tracer_provider(provider)
    DjangoInstrumentor().instrument()
    RequestsInstrumentor().instrument()
    _otel_initialized = True
    return True


class ObservabilityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('article_studio.request')

    def __call__(self, request):
        started = time.perf_counter()
        response = self.get_response(request)
        duration = time.perf_counter() - started
        record_request(request.method, request.path, response.status_code, duration)
        self.logger.info(
            'request completed',
            extra={
                'request_method': request.method,
                'request_path': request.path,
                'status_code': response.status_code,
                'duration_ms': round(duration * 1000, 2),
            },
        )
        return response
