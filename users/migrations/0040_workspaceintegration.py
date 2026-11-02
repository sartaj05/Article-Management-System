import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0039_workspacebillingcontract"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkspaceIntegration",
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
                (
                    "provider",
                    models.CharField(
                        choices=[
                            ("slack", "Slack"),
                            ("teams", "Microsoft Teams"),
                            ("salesforce", "Salesforce"),
                            ("cms", "Content management system"),
                            ("sharepoint", "SharePoint"),
                            ("google_drive", "Google Drive"),
                        ],
                        max_length=20,
                    ),
                ),
                ("name", models.CharField(max_length=120)),
                ("endpoint_url", models.URLField(blank=True)),
                ("secret", models.CharField(blank=True, max_length=512)),
                ("config", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("configured", "Configured"),
                            ("healthy", "Healthy"),
                            ("degraded", "Degraded"),
                            ("disabled", "Disabled"),
                        ],
                        default="configured",
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("last_checked_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="workspace_integrations_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="integrations",
                        to="users.workspace",
                    ),
                ),
            ],
            options={
                "ordering": ["provider", "name"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("workspace", "name"),
                        name="unique_workspace_integration_name",
                    )
                ],
            },
        ),
    ]
