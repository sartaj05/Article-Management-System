from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0034_notificationdelivery')]

    operations = [
        migrations.AddIndex(
            model_name='webhookdelivery',
            index=models.Index(fields=['status', 'attempts'], name='webhook_retry_idx'),
        ),
    ]
