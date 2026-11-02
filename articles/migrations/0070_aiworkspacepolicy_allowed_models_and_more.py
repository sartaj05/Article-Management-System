from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0069_workspacereliabilitypolicy"),
    ]

    operations = [
        migrations.AddField(
            model_name="aiworkspacepolicy",
            name="allowed_models",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="aiworkspacepolicy",
            name="allowed_providers",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="aiworkspacepolicy",
            name="approved_prompt_version",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="aiworkspacepolicy",
            name="data_retention_days",
            field=models.PositiveIntegerField(default=30),
        ),
        migrations.AddField(
            model_name="aiworkspacepolicy",
            name="require_publish_approval",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="aiworkspacepolicy",
            name="training_data_opt_out",
            field=models.BooleanField(default=True),
        ),
    ]
