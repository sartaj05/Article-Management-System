from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('users', '0019_rolecapabilityoverride')]
    operations = [migrations.CreateModel(name='TwoFactorAuth', fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('secret', models.CharField(max_length=64)), ('backup_codes', models.JSONField(blank=True, default=list)), ('is_enabled', models.BooleanField(default=False)), ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)), ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='two_factor_auth', to=settings.AUTH_USER_MODEL))])]
