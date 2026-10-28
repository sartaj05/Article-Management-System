from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from users.models import MembershipInvoice, MembershipSubscription, PaymentTransaction


class Command(BaseCommand):
    help = 'Fail stale membership checkouts and void their unpaid invoices.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7)

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=max(1, options['days']))
        with transaction.atomic():
            transactions = list(PaymentTransaction.objects.filter(status='pending', created_at__lt=cutoff))
            transaction_ids = [item.id for item in transactions]
            PaymentTransaction.objects.filter(id__in=transaction_ids).update(status='failed', updated_at=timezone.now())
            MembershipInvoice.objects.filter(transaction_id__in=transaction_ids, status='issued').update(status='void')
            MembershipSubscription.objects.filter(status='pending', created_at__lt=cutoff).update(status='canceled', auto_renew=False, updated_at=timezone.now())
        self.stdout.write(self.style.SUCCESS(f'Expired {len(transactions)} pending membership checkout(s).'))
