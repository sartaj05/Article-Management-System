import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0067_auditlog_event_hash_auditlog_previous_hash_and_more"),
        ("users", "0038_ssoprovider_auto_provision_ssoprovider_client_secret_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkspaceApprovalPolicy",
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
                ("require_dual_publish", models.BooleanField(default=False)),
                ("require_dual_billing", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "workspace",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approval_policy",
                        to="users.workspace",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="WorkspaceRolePermission",
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
                    "role",
                    models.CharField(
                        choices=[
                            ("Journalist", "Journalist"),
                            ("Editor", "Editor"),
                            ("Admin", "Admin"),
                        ],
                        max_length=20,
                    ),
                ),
                ("capability", models.CharField(max_length=100)),
                ("is_enabled", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="role_permissions",
                        to="users.workspace",
                    ),
                ),
            ],
            options={
                "ordering": ["role", "capability"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("workspace", "role", "capability"),
                        name="unique_workspace_role_permission",
                    )
                ],
            },
        ),
    ]
