"""Consistent error envelopes for the public DRF API."""

from rest_framework.views import exception_handler


def structured_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response
    payload = response.data
    if isinstance(payload, dict) and 'detail' in payload:
        message = str(payload['detail'])
        fields = None
    elif isinstance(payload, dict):
        message = 'Validation failed.'
        fields = payload
    else:
        message = str(payload)
        fields = None
    request = context.get('request')
    response.data = {
        'error': {
            'code': getattr(exc, 'default_code', 'api_error'),
            'message': message,
            'status': response.status_code,
            'fields': fields,
            'request_id': getattr(request, 'request_id', None),
        },
        'detail': payload.get('detail') if isinstance(payload, dict) and 'detail' in payload else message,
    }
    if fields is not None:
        response.data['errors'] = fields
    return response
