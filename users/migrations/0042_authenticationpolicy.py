from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0041_supportticket_supportticketmessage"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuthenticationPolicy",
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
                    "name",
                    models.CharField(default="default", max_length=80, unique=True),
                ),
                ("require_mfa", models.BooleanField(default=False)),
                ("max_session_minutes", models.PositiveIntegerField(default=1440)),
                ("max_idle_minutes", models.PositiveIntegerField(default=60)),
                ("require_sso", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
