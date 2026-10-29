from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from articles.models import Article, ArticleCorrection, ArticleMedia, ArticleTranslation, Notification
from users.models import NewsletterEdition


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
        reader_article, _ = Article.objects.get_or_create(
            author=user,
            title='E2E Public Reader Story',
            defaults={
                'content': 'A published fixture for reader features, corrections, and audio progress.',
                'author_name': user.username,
                'email': user.email,
                'agreed_to_terms': True,
                'category': 'news',
                'tags': 'e2e,reader',
                'summary': 'A deterministic public story used by reader feature tests.',
                'workflow_status': 'published',
                'status': 'published',
                'is_visible': True,
                'published_at': timezone.now(),
            },
        )
        ArticleMedia.objects.get_or_create(
            article=reader_article,
            title='E2E sample audio',
            defaults={
                'media_type': 'audio',
                'external_url': 'https://example.com/e2e-sample-audio.mp3',
                'duration_seconds': 90,
                'uploaded_by': user,
            },
        )
        ArticleCorrection.objects.get_or_create(
            article=reader_article,
            reason='E2E published correction fixture.',
            defaults={
                'reported_by': users['Editor'],
                'reviewed_by': users['Editor'],
                'original_text': 'The earlier figure was 12.',
                'corrected_text': 'The verified figure is 14.',
                'status': 'published',
                'published_at': timezone.now(),
            },
        )
        ArticleTranslation.objects.update_or_create(
            article=reader_article,
            language_code='hi',
            defaults={
                'title': 'E2E Hindi Reader Story',
                'subtitle': 'A localized E2E fixture',
                'content': 'यह एक स्थिर अनुवाद परीक्षण कहानी है।',
                'summary': 'A published Hindi translation used by the browser regression suite.',
                'status': 'published',
                'translated_by': user,
                'reviewed_by': users['Editor'],
                'reviewed_at': timezone.now(),
            },
        )
        Notification.objects.get_or_create(
            recipient=users['Editor'],
            article=reader_article,
            notification_type='reader_alert',
            message='E2E unread reader alert fixture.',
            defaults={'action_url': '/articles/read/e2e-public-reader-story/', 'priority': 'normal'},
        )
        NewsletterEdition.objects.get_or_create(
            subject='E2E Newsletter Campaign',
            defaults={
                'frequency': 'weekly',
                'body': 'A deterministic newsletter campaign for analytics tests.',
                'status': 'sent',
                'recipient_count': 3,
                'sent_at': timezone.now(),
            },
        )
        self.stdout.write(self.style.SUCCESS('Prepared deterministic E2E users, draft, and public reader story.'))
