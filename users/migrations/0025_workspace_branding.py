from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0024_payment_transactions')]

    operations = [
        migrations.AddField(model_name='workspace', name='logo_url', field=models.URLField(blank=True)),
        migrations.AddField(model_name='workspace', name='primary_color', field=models.CharField(default='#2f5d62', max_length=7)),
        migrations.AddField(model_name='workspace', name='accent_color', field=models.CharField(default='#f28f6b', max_length=7)),
        migrations.AddField(model_name='workspace', name='custom_domain', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='workspace', name='email_from_name', field=models.CharField(blank=True, max_length=120)),
    ]
