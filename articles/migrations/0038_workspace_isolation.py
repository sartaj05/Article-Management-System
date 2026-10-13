from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('articles', '0037_backuprecord'),
        ('users', '0024_payment_transactions'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='workspace',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='articles', to='users.workspace'),
        ),
        migrations.AddField(
            model_name='mediaasset',
            name='workspace',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='media_assets', to='users.workspace'),
        ),
    ]
