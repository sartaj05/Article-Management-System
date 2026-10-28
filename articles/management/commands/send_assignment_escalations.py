from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from articles.models import ArticleAssignment, Notification
from articles.notifications import notify
from users.models import CustomUser


class Command(BaseCommand):
    help = 'Escalate overdue editorial assignments to newsroom managers.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--cooldown-hours', type=int, default=24)

    def handle(self, *args, **options):
        now = timezone.now()
        cooldown = now - timedelta(hours=max(1, options['cooldown_hours']))
        managers = CustomUser.objects.filter(role__in={'Editor', 'Admin'}, is_active=True)
        escalated = 0
        assignments = ArticleAssignment.objects.filter(due_at__lt=now).exclude(status='done').select_related('article', 'editor')
        for assignment in assignments:
            message = f'Assignment for “{assignment.article.title}” is overdue and needs manager attention.'
            recipients = managers.exclude(pk=assignment.editor_id)
            for manager in recipients:
                already_sent = Notification.objects.filter(
                    recipient=manager, article=assignment.article, notification_type='sla_escalation',
                    message=message, created_at__gte=cooldown,
                ).exists()
                if already_sent:
                    continue
                if not options['dry_run']:
                    notify(recipient=manager, notification_type='sla_escalation', message=message, article=assignment.article)
                escalated += 1
        self.stdout.write(self.style.SUCCESS(f'Escalated {escalated} overdue assignment(s).'))
