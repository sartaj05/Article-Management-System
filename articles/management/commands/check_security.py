from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from config.security import production_security_issues


class Command(BaseCommand):
    help = 'Validate production security settings when ENFORCE_PRODUCTION_SECURITY is enabled.'

    def handle(self, *args, **options):
        if not settings.ENFORCE_PRODUCTION_SECURITY:
            self.stdout.write('Production security enforcement is disabled for this environment.')
            return
        issues = production_security_issues()
        if issues:
            raise CommandError('Production security validation failed:\n- ' + '\n- '.join(issues))
        self.stdout.write(self.style.SUCCESS('Production security validation passed.'))
