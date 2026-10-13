from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('users', '0021_publicapikey_scopes')]

    operations = [
        migrations.CreateModel(
            name='TrustedDevice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(default='Trusted device', max_length=120)),
                ('token_hash', models.CharField(max_length=64, unique=True)),
                ('user_agent', models.CharField(blank=True, max_length=500)),
                ('expires_at', models.DateTimeField()),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='trusted_devices', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='PasskeyCredential',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('credential_id', models.CharField(max_length=512, unique=True)),
                ('public_key', models.TextField()),
                ('sign_count', models.PositiveIntegerField(default=0)),
                ('label', models.CharField(default='Passkey', max_length=120)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='passkey_credentials', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='SSOProvider',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(choices=[('oidc', 'OpenID Connect'), ('google', 'Google'), ('microsoft', 'Microsoft')], max_length=20, unique=True)),
                ('client_id', models.CharField(blank=True, max_length=255)),
                ('discovery_url', models.URLField(blank=True)),
                ('is_enabled', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
