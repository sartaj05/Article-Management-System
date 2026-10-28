from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from users.models import CustomUser
from ..models import Article, ArticleAssignment, Notification


class AssignmentEscalationTests(TestCase):
    def test_overdue_assignment_escalates_once_to_manager(self):
        author = CustomUser.objects.create_user(username='sla-author', email='sla-author@example.com', password='StrongPass123!', role='Journalist')
        editor = CustomUser.objects.create_user(username='sla-editor', email='sla-editor@example.com', password='StrongPass123!', role='Editor')
        manager = CustomUser.objects.create_user(username='sla-manager', email='sla-manager@example.com', password='StrongPass123!', role='Admin')
        article = Article.objects.create(title='Overdue assignment', content='Content', author=author, agreed_to_terms=True)
        ArticleAssignment.objects.create(article=article, editor=editor, due_at=timezone.now() - timedelta(hours=2))
        call_command('send_assignment_escalations')
        self.assertEqual(Notification.objects.filter(recipient=manager, notification_type='sla_escalation').count(), 1)
        self.assertFalse(Notification.objects.filter(recipient=editor, notification_type='sla_escalation').exists())
        call_command('send_assignment_escalations')
        self.assertEqual(Notification.objects.filter(recipient=manager, notification_type='sla_escalation').count(), 1)
