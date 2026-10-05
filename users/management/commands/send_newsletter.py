from django.core.management.base import BaseCommand
from django.core.mail import send_mass_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from articles.models import Article
from users.models import NewsletterEdition, NewsletterSubscription


class Command(BaseCommand):
    help = 'Send a newsletter containing recently published articles.'

    def add_arguments(self, parser):
        parser.add_argument('--frequency', choices=['daily', 'weekly'], default='weekly')
        parser.add_argument('--dry-run', action='store_true', help='Build an edition without sending email.')
        parser.add_argument('--subject', default='Article Studio newsletter')

    def handle(self, *args, **options):
        since = timezone.now() - timedelta(days=1 if options['frequency'] == 'daily' else 7)
        articles = Article.objects.filter(workflow_status='published', is_visible=True, published_at__gte=since).order_by('-published_at')[:10]
        if not articles:
            self.stdout.write('No recent published articles found.')
            return
        lines = ['Here are the latest stories from Article Studio:', '']
        lines.extend(f'- {article.title}: {article.summary or article.content[:160]}' for article in articles)
        message = '\n'.join(lines)
        subscriptions = NewsletterSubscription.objects.filter(frequency=options['frequency'], is_active=True)
        recipients = list(subscriptions.values_list('email', flat=True))
        edition = NewsletterEdition.objects.create(
            frequency=options['frequency'], subject=options['subject'], body=message,
            article_ids=[article.id for article in articles],
            status='draft' if options['dry_run'] else 'sent',
            recipient_count=len(recipients),
            sent_at=None if options['dry_run'] else timezone.now(),
        )
        if not options['dry_run']:
            send_mass_mail(((edition.subject, edition.body, settings.NEWSLETTER_FROM_EMAIL, [email]) for email in recipients), fail_silently=True)
        state = 'prepared' if options['dry_run'] else 'sent'
        self.stdout.write(self.style.SUCCESS(f'Newsletter {state} for {len(recipients)} subscriber(s). Edition {edition.id}.'))
