from decimal import Decimal

import requests
from urllib.parse import quote
from django.conf import settings
from config.resilience import call_with_circuit


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


def create_tip_checkout(tip, request):
    """Create a one-time hosted checkout for an author tip."""
    if tip.provider == 'stripe':
        return _create_stripe_tip_checkout(tip, request)
    if tip.provider == 'razorpay':
        return _create_razorpay_tip_order(tip)
    return {'configured': False, 'checkout_url': '', 'provider_reference': ''}


def cancel_remote_subscription(subscription):
    """Cancel a remote subscription when explicit remote lifecycle control is enabled."""
    if not settings.PAYMENT_REMOTE_CANCELLATION_ENABLED or not subscription.provider_reference:
        return {'configured': False, 'canceled': False}
    reference = quote(subscription.provider_reference, safe='')
    if subscription.provider == 'stripe':
        if not settings.STRIPE_SECRET_KEY:
            return {'configured': False, 'canceled': False}
        response = call_with_circuit('stripe', lambda: requests.delete(
            f'https://api.stripe.com/v1/subscriptions/{reference}',
            auth=(settings.STRIPE_SECRET_KEY, ''),
            timeout=settings.PAYMENT_HTTP_TIMEOUT,
        ))
    elif subscription.provider == 'razorpay':
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            return {'configured': False, 'canceled': False}
        response = call_with_circuit('razorpay', lambda: requests.post(
            f'https://api.razorpay.com/v1/subscriptions/{reference}/cancel',
            json={'cancel_at_cycle_end': 1},
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            timeout=settings.PAYMENT_HTTP_TIMEOUT,
        ))
    else:
        return {'configured': False, 'canceled': False}
    if not response.ok:
        raise ProviderRequestError(f'{subscription.provider.title()} subscription cancellation failed with HTTP {response.status_code}.')
    return {'configured': True, 'canceled': True, 'provider_response': response.json() if response.content else {}}


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


def _create_stripe_tip_checkout(tip, request):
    if not settings.STRIPE_SECRET_KEY:
        return {'configured': False, 'checkout_url': '', 'provider_reference': ''}
    payload = {
        'mode': 'payment',
        'success_url': settings.PAYMENT_SUCCESS_URL or request.build_absolute_uri('/tips/'),
        'cancel_url': settings.PAYMENT_CANCEL_URL or request.build_absolute_uri('/tips/'),
        'line_items[0][price_data][currency]': tip.currency.lower(),
        'line_items[0][price_data][product_data][name]': f'Tip for {tip.author.username}',
        'line_items[0][price_data][unit_amount]': _minor_units(tip.amount),
        'line_items[0][quantity]': 1,
        'metadata[tip_id]': tip.id,
        'metadata[checkout_token]': tip.checkout_token,
        'metadata[author_id]': tip.author_id,
        'metadata[sender_id]': tip.sender_id,
    }
    response = call_with_circuit('stripe', lambda: requests.post(
        'https://api.stripe.com/v1/checkout/sessions',
        data=payload,
        auth=(settings.STRIPE_SECRET_KEY, ''),
        timeout=settings.PAYMENT_HTTP_TIMEOUT,
    ))
    if not response.ok:
        raise ProviderRequestError(f'Stripe tip checkout failed with HTTP {response.status_code}.')
    data = response.json()
    return {'configured': True, 'checkout_url': data.get('url', ''), 'provider_reference': str(data.get('id', ''))}


def _create_razorpay_tip_order(tip):
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        return {'configured': False, 'checkout_url': '', 'provider_reference': ''}
    response = call_with_circuit('razorpay', lambda: requests.post(
        'https://api.razorpay.com/v1/orders',
        json={
            'amount': _minor_units(tip.amount),
            'currency': tip.currency,
            'receipt': tip.checkout_token,
            'notes': {'tip_id': tip.id, 'checkout_token': tip.checkout_token, 'author_id': tip.author_id, 'sender_id': tip.sender_id},
        },
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
        timeout=settings.PAYMENT_HTTP_TIMEOUT,
    ))
    if not response.ok:
        raise ProviderRequestError(f'Razorpay tip order creation failed with HTTP {response.status_code}.')
    data = response.json()
    return {'configured': True, 'checkout_url': '', 'provider_reference': str(data.get('id', ''))}
