from django.core.management import CommandError
from django.contrib.auth.management.commands.createsuperuser import Command as BaseCommand
from users.models import CustomUser
from django.core.mail import send_mail

class Command(BaseCommand):
    help = 'Create a superuser with role selection'

    def add_arguments(self, parser):
        # Add the custom --role argument
        super().add_arguments(parser)
        parser.add_argument(
            '--role',
            type=str,
            choices=['Journalist', 'Editor', 'Admin'],
            default='Journalist',  # Default role is Journalist
            help='Role of the superuser'
        )

    def handle(self, *args, **options):
        email = options.get('email')
        if not email:
            raise CommandError('Email is required.')

        if CustomUser.objects.filter(email=email).exists():
            raise CommandError(f"A user with the email {email} already exists.")

        # Call the original handle method to create the superuser
        super().handle(*args, **options)

        role = options.get('role')
        user = CustomUser.objects.get(email=email)
        user.role = role  # Set the role of the superuser
        user.save()

        # Send an email notification
        send_mail(
            subject='Superuser Account Created',
            message=f'Your superuser account has been created successfully.\n\n'
                    f'Username: {user.username}\n'
                    f'Email: {user.email}\n'
                    f'Role: {user.role}',
            from_email='admin@example.com',  # Replace with your admin email
            recipient_list=[user.email],
            fail_silently=False,
        )

        self.stdout.write(self.style.SUCCESS(f"Superuser created successfully with role: {role}"))
