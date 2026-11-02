import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0037_authortip_checkout_token_authortip_checkout_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="ssoprovider",
            name="auto_provision",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="ssoprovider",
            name="client_secret",
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AddField(
            model_name="ssoprovider",
            name="default_role",
            field=models.CharField(
                choices=[
                    ("Journalist", "Journalist"),
                    ("Editor", "Editor"),
                    ("Admin", "Admin"),
                ],
                default="Journalist",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="ssoprovider",
            name="metadata_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="ssoprovider",
            name="token_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="ssoprovider",
            name="userinfo_url",
            field=models.URLField(blank=True),
        ),
        migrations.AlterField(
            model_name="ssoprovider",
            name="provider",
            field=models.CharField(
                choices=[
                    ("oidc", "OpenID Connect"),
                    ("google", "Google"),
                    ("microsoft", "Microsoft"),
                    ("saml", "SAML 2.0"),
                ],
                max_length=20,
                unique=True,
            ),
        ),
        migrations.CreateModel(
            name="SCIMToken",
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
                ("prefix", models.CharField(db_index=True, max_length=12)),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scim_tokens",
                        to="users.workspace",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
