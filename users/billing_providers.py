from decimal import Decimal
import hashlib
import hmac
import time

import requests
from urllib.parse import quote
from django.conf import settings
from django.utils import timezone
from config.resilience import call_with_circuit


class ProviderRequestError(Exception):
    pass


def verify_payment_webhook_signature(provider, body, headers):
    """Verify native provider signatures, with the internal HMAC fallback."""
    provider = str(provider or '').lower()
    if provider == 'stripe' and headers.get('Stripe-Signature'):
        secret = settings.STRIPE_WEBHOOK_SECRET or settings.PAYMENT_WEBHOOK_SECRET
        if not secret:
            return False
        values = {}
        for item in headers['Stripe-Signature'].split(','):
            key, _, value = item.partition('=')
            values.setdefault(key, []).append(value)
        timestamp = (values.get('t') or [''])[0]
        try:
            timestamp_value = int(timestamp)
        except (TypeError, ValueError):
            return False
        if abs(time.time() - timestamp_value) > settings.PAYMENT_WEBHOOK_TOLERANCE_SECONDS:
            return False
        signed = f'{timestamp}.{body.decode("utf-8")}'.encode('utf-8')
        expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        return any(hmac.compare_digest(expected, signature) for signature in values.get('v1', []))
    if provider == 'razorpay' and headers.get('X-Razorpay-Signature'):
        secret = settings.RAZORPAY_WEBHOOK_SECRET or settings.PAYMENT_WEBHOOK_SECRET
        if not secret:
            return False
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(headers['X-Razorpay-Signature'], expected)
    secret = settings.PAYMENT_WEBHOOK_SECRET
    signature = headers.get('X-Payment-Signature', '')
    expected = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest() if secret else ''
    return bool(secret and hmac.compare_digest(signature, expected))


def _minor_units(amount):
    return int(Decimal(amount) * 100)


def create_checkout(transaction, request):
    """Create a hosted checkout when the selected provider is configured."""
    if not settings.PAYMENTS_ENABLED:
        return {'configured': False, 'checkout_url': '', 'provider_reference': '', 'reason': 'payments_disabled'}
    if transaction.provider == 'stripe':
        return _create_stripe_checkout(transaction, request)
    if transaction.provider == 'razorpay':
        return _create_razorpay_order(transaction)
    return {'configured': False, 'checkout_url': '', 'provider_reference': ''}


def create_tip_checkout(tip, request):
    """Create a one-time hosted checkout for an author tip."""
    if not settings.PAYMENTS_ENABLED:
        return {'configured': False, 'checkout_url': '', 'provider_reference': '', 'reason': 'payments_disabled'}
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


def _remote_payment_status(provider, reference):
    if provider == 'stripe' and settings.STRIPE_SECRET_KEY:
        response = call_with_circuit('stripe', lambda: requests.get(
            f'https://api.stripe.com/v1/checkout/sessions/{quote(reference, safe="")}',
            auth=(settings.STRIPE_SECRET_KEY, ''),
            timeout=settings.PAYMENT_HTTP_TIMEOUT,
        ))
        if not response.ok:
            raise ProviderRequestError(f'Stripe reconciliation failed with HTTP {response.status_code}.')
        data = response.json()
        if data.get('payment_status') == 'paid':
            return 'succeeded', data
        if data.get('status') == 'expired':
            return 'failed', data
        return 'pending', data
    if provider == 'razorpay' and settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
        response = call_with_circuit('razorpay', lambda: requests.get(
            f'https://api.razorpay.com/v1/orders/{quote(reference, safe="")}',
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            timeout=settings.PAYMENT_HTTP_TIMEOUT,
        ))
        if not response.ok:
            raise ProviderRequestError(f'Razorpay reconciliation failed with HTTP {response.status_code}.')
        data = response.json()
        return {'paid': 'succeeded', 'attempted': 'pending', 'created': 'pending'}.get(data.get('status'), 'failed'), data
    return None, {}


def reconcile_pending_payments(limit=50):
    """Repair local payment state when a provider webhook was delayed or missed."""
    from .models import AuthorTip, MembershipInvoice, MembershipSubscription, PaymentTransaction

    summary = {'checked': 0, 'succeeded': 0, 'failed': 0, 'pending': 0, 'skipped': 0}
    transactions = PaymentTransaction.objects.filter(
        status='pending',
        provider__in={'stripe', 'razorpay'},
    ).exclude(provider_reference='').order_by('created_at')[:limit]
    for transaction in transactions:
        summary['checked'] += 1
        try:
            state, payload = _remote_payment_status(transaction.provider, transaction.provider_reference)
        except ProviderRequestError:
            summary['skipped'] += 1
            continue
        if not state:
            summary['skipped'] += 1
            continue
        transaction.status = state
        transaction.save(update_fields=['status', 'updated_at'])
        if state == 'succeeded':
            summary['succeeded'] += 1
            MembershipInvoice.objects.filter(transaction=transaction).update(status='paid', paid_at=timezone.now())
            MembershipSubscription.objects.filter(user=transaction.user, plan=transaction.plan).update(status='active', auto_renew=True, updated_at=timezone.now())
        elif state == 'failed':
            summary['failed'] += 1
            MembershipInvoice.objects.filter(transaction=transaction, status='issued').update(status='void')
        else:
            summary['pending'] += 1

    tips = AuthorTip.objects.filter(
        status='pending',
        provider__in={'stripe', 'razorpay'},
    ).exclude(provider_reference='').order_by('created_at')[:limit]
    for tip in tips:
        summary['checked'] += 1
        try:
            state, _ = _remote_payment_status(tip.provider, tip.provider_reference)
        except ProviderRequestError:
            summary['skipped'] += 1
            continue
        if state == 'succeeded':
            tip.status = 'succeeded'
            tip.save(update_fields=['status', 'updated_at'])
            summary['succeeded'] += 1
        elif state == 'failed':
            tip.status = 'failed'
            tip.save(update_fields=['status', 'updated_at'])
            summary['failed'] += 1
        else:
            summary['pending'] += 1
    return summary


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
