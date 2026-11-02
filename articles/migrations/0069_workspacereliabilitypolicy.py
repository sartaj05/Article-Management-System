import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0068_workspaceapprovalpolicy_workspacerolepermission"),
        ("users", "0039_workspacebillingcontract"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkspaceReliabilityPolicy",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("rto_minutes", models.PositiveIntegerField(default=240)),
                ("rpo_minutes", models.PositiveIntegerField(default=60)),
                ("backup_region", models.CharField(default="primary", max_length=80)),
                ("restore_verified_at", models.DateTimeField(blank=True, null=True)),
                ("status_page_enabled", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "workspace",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reliability_policy",
                        to="users.workspace",
                    ),
                ),
            ],
        ),
    ]
