from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('articles', '0054_workflowrule_auto_assign_role')]

    operations = [
        migrations.AddField(model_name='distributionjob', name='provider_reference', field=models.CharField(blank=True, max_length=160)),
        migrations.AddField(model_name='distributionjob', name='provider_response', field=models.JSONField(blank=True, default=dict)),
    ]
