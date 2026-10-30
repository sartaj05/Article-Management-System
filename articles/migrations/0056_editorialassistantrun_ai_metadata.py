from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('articles', '0055_distributionjob_provider_fields')]

    operations = [
        migrations.AddField(
            model_name='editorialassistantrun',
            name='model',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='editorialassistantrun',
            name='metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='editorialassistantrun',
            name='latency_ms',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
