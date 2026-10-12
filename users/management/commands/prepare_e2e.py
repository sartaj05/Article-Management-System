from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from articles.models import Article


class Command(BaseCommand):
    help = 'Create the deterministic local user used by Playwright E2E tests.'

    def handle(self, *args, **options):
        user_model = get_user_model()
        accounts = [
            ('e2e_journalist', 'e2e@example.com', 'Journalist'),
            ('e2e_editor', 'e2e-editor@example.com', 'Editor'),
            ('e2e_admin', 'e2e-admin@example.com', 'Admin'),
        ]
        users = {}
        for username, email, role in accounts:
            user, _ = user_model.objects.get_or_create(
                username=username,
                defaults={'email': email, 'role': role},
            )
            user.email = email
            user.role = role
            user.set_password('StrongPass123!')
            user.save(update_fields=['email', 'role', 'password'])
            users[role] = user

        user = users['Journalist']
        Article.objects.get_or_create(
            author=user,
            title='E2E Workflow Article',
            defaults={
                'content': 'A deterministic article used by the browser regression suite.',
                'author_name': user.username,
                'email': user.email,
                'agreed_to_terms': True,
                'category': 'news',
                'workflow_status': 'draft',
                'status': 'draft',
            },
        )
        self.stdout.write(self.style.SUCCESS('Prepared deterministic E2E users and article.'))
