"""Small pysaml2 adapter used by the SSO callback."""


class SAMLConfigurationError(RuntimeError):
    pass


def validate_saml_response(provider, request):
    response = request.query_params.get('SAMLResponse')
    if not response:
        raise SAMLConfigurationError('The identity provider did not return a SAML response.')
    if not provider.metadata_url or not provider.client_id:
        raise SAMLConfigurationError('SAML metadata_url and client_id are required.')
    try:
        from saml2 import BINDING_HTTP_POST
        from saml2.client import Saml2Client
        from saml2.config import SPConfig
    except ImportError as exc:
        raise SAMLConfigurationError('pysaml2 is not installed on this deployment.') from exc
    callback = request.build_absolute_uri(f'/api/sso/{provider.provider}/callback/')
    config = {
        'entityid': provider.client_id,
        'metadata': {'remote': [{'url': provider.metadata_url}]},
        'service': {'sp': {'allow_unsolicited': True, 'want_response_signed': True, 'endpoints': {'assertion_consumer_service': [(callback, BINDING_HTTP_POST)]}}},
    }
    try:
        client = Saml2Client(config=SPConfig().load(config))
        assertion = client.parse_authn_request_response(response, BINDING_HTTP_POST)
        identity = assertion.get_identity() or {}
    except Exception as exc:
        raise SAMLConfigurationError('The SAML assertion could not be validated.') from exc
    email_values = identity.get('mail') or identity.get('email') or identity.get('uid') or []
    email = email_values[0] if isinstance(email_values, (list, tuple)) else email_values
    if not email:
        raise SAMLConfigurationError('The SAML assertion did not contain an email claim.')
    return {'email': str(email).strip().lower(), 'given_name': '', 'family_name': ''}
