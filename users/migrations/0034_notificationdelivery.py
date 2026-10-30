from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0033_publicapikey_expires_at'),
        ('articles', '0055_distributionjob_provider_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationDelivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('channel', models.CharField(choices=[('email', 'Email'), ('push', 'Web push')], max_length=12)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('sent', 'Sent'), ('failed', 'Failed'), ('skipped', 'Skipped')], default='queued', max_length=12)),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('provider_reference', models.CharField(blank=True, max_length=160)),
                ('last_error', models.CharField(blank=True, max_length=500)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('notification', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deliveries', to='articles.notification')),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notification_deliveries', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
