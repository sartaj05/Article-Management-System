from decimal import Decimal

import requests
from django.conf import settings


class ProviderRequestError(Exception):
    pass


def _minor_units(amount):
    return int(Decimal(amount) * 100)


def create_checkout(transaction, request):
    """Create a hosted checkout when the selected provider is configured."""
    if transaction.provider == 'stripe':
        return _create_stripe_checkout(transaction, request)
    if transaction.provider == 'razorpay':
        return _create_razorpay_order(transaction)
    return {'configured': False, 'checkout_url': '', 'provider_reference': ''}


def _create_stripe_checkout(transaction, request):
    if not settings.STRIPE_SECRET_KEY:
        return {'configured': False, 'checkout_url': '', 'provider_reference': ''}
    payload = {
        'mode': 'subscription',
        'success_url': settings.PAYMENT_SUCCESS_URL or request.build_absolute_uri('/membership/'),
        'cancel_url': settings.PAYMENT_CANCEL_URL or request.build_absolute_uri('/membership/'),
        'line_items[0][price_data][currency]': transaction.currency.lower(),
        'line_items[0][price_data][product_data][name]': transaction.plan.name,
        'line_items[0][price_data][unit_amount]': _minor_units(transaction.amount),
        'line_items[0][price_data][recurring][interval]': transaction.plan.interval,
        'line_items[0][quantity]': 1,
        'metadata[user_id]': transaction.user_id,
        'metadata[plan_id]': transaction.plan_id,
        'metadata[transaction_id]': transaction.id,
        'metadata[checkout_token]': transaction.checkout_token,
    }
    response = requests.post('https://api.stripe.com/v1/checkout/sessions', data=payload, auth=(settings.STRIPE_SECRET_KEY, ''), timeout=settings.PAYMENT_HTTP_TIMEOUT)
    if not response.ok:
        raise ProviderRequestError(f'Stripe checkout failed with HTTP {response.status_code}.')
    data = response.json()
    return {'configured': True, 'checkout_url': data.get('url', ''), 'provider_reference': str(data.get('id', ''))}


def _create_razorpay_order(transaction):
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        return {'configured': False, 'checkout_url': '', 'provider_reference': ''}
    response = requests.post(
        'https://api.razorpay.com/v1/orders',
        json={'amount': _minor_units(transaction.amount), 'currency': transaction.currency, 'receipt': transaction.checkout_token, 'notes': {'user_id': transaction.user_id, 'plan_id': transaction.plan_id, 'transaction_id': transaction.id}},
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
        timeout=settings.PAYMENT_HTTP_TIMEOUT,
    )
    if not response.ok:
        raise ProviderRequestError(f'Razorpay order creation failed with HTTP {response.status_code}.')
    data = response.json()
    return {'configured': True, 'checkout_url': '', 'provider_reference': str(data.get('id', ''))}
