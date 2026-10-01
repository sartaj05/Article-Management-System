from django.core.management.base import BaseCommand
from django.core.mail import send_mass_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from articles.models import Article
from users.models import NewsletterSubscription


class Command(BaseCommand):
    help = 'Send a newsletter containing recently published articles.'

    def add_arguments(self, parser):
        parser.add_argument('--frequency', choices=['daily', 'weekly'], default='weekly')

    def handle(self, *args, **options):
        since = timezone.now() - timedelta(days=1 if options['frequency'] == 'daily' else 7)
        articles = Article.objects.filter(workflow_status='published', is_visible=True, published_at__gte=since).order_by('-published_at')[:10]
        if not articles:
            self.stdout.write('No recent published articles found.')
            return
        lines = ['Here are the latest stories from Article Studio:', '']
        lines.extend(f'- {article.title}: {article.summary or article.content[:160]}' for article in articles)
        message = '\n'.join(lines)
        recipients = NewsletterSubscription.objects.filter(frequency=options['frequency'], is_active=True).values_list('email', flat=True)
        send_mass_mail((('Article Studio newsletter', message, settings.NEWSLETTER_FROM_EMAIL, [email]) for email in recipients), fail_silently=True)
        self.stdout.write(self.style.SUCCESS(f'Newsletter sent to {len(recipients)} subscriber(s).'))
