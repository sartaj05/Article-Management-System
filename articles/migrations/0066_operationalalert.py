import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0065_performance_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="OperationalAlert",
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
                ("fingerprint", models.CharField(max_length=160, unique=True)),
                ("area", models.CharField(max_length=80)),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("low", "Low"),
                            ("medium", "Medium"),
                            ("high", "High"),
                            ("critical", "Critical"),
                        ],
                        default="medium",
                        max_length=20,
                    ),
                ),
                ("message", models.CharField(max_length=500)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("acknowledged", "Acknowledged"),
                            ("resolved", "Resolved"),
                        ],
                        default="open",
                        max_length=20,
                    ),
                ),
                ("occurrences", models.PositiveIntegerField(default=1)),
                ("details", models.JSONField(blank=True, default=dict)),
                (
                    "first_seen_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                (
                    "last_seen_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-last_seen_at"],
                "indexes": [
                    models.Index(
                        fields=["status", "-last_seen_at"],
                        name="ops_alert_status_seen_idx",
                    )
                ],
            },
        ),
    ]
