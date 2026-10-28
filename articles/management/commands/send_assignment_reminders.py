from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from articles.models import ArticleAssignment, Notification
from articles.notifications import notify


class Command(BaseCommand):
    help = 'Notify assigned editors about overdue or upcoming assignment deadlines.'

    def handle(self, *args, **options):
        now = timezone.now()
        upcoming_limit = now + timedelta(hours=24)
        assignments = ArticleAssignment.objects.filter(due_at__isnull=False).exclude(status='done').select_related('article', 'editor')
        reminded = 0
        for assignment in assignments:
            if assignment.due_at > upcoming_limit:
                continue
            state = 'overdue' if assignment.due_at < now else 'due within 24 hours'
            message = f'Assignment for “{assignment.article.title}” is {state}.'
            if Notification.objects.filter(recipient=assignment.editor, article=assignment.article, notification_type='assignment', message=message, created_at__gte=now - timedelta(hours=24)).exists():
                continue
            notify(recipient=assignment.editor, notification_type='assignment', message=message, article=assignment.article)
            reminded += 1
        self.stdout.write(self.style.SUCCESS(f'Sent {reminded} assignment reminder(s).'))
