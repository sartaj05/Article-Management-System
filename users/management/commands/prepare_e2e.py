from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from articles.models import Article


class Command(BaseCommand):
    help = 'Create the deterministic local user used by Playwright E2E tests.'

    def handle(self, *args, **options):
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            username='e2e_journalist',
            defaults={'email': 'e2e@example.com', 'role': 'Journalist'},
        )
        user.email = 'e2e@example.com'
        user.role = 'Journalist'
        user.set_password('StrongPass123!')
        user.save(update_fields=['email', 'role', 'password'])
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
        state = 'created' if created else 'reset'
        self.stdout.write(self.style.SUCCESS(f'E2E user {state}: e2e_journalist'))
