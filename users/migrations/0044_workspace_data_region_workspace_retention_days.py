from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0043_workspaceintegration_encrypted_secret"),
    ]

    operations = [
        migrations.AddField(
            model_name="workspace",
            name="data_region",
            field=models.CharField(
                choices=[
                    ("global", "Global"),
                    ("us", "United States"),
                    ("eu", "European Union"),
                    ("in", "India"),
                ],
                default="global",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="workspace",
            name="retention_days",
            field=models.PositiveIntegerField(default=365),
        ),
    ]
