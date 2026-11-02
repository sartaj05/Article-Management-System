import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0038_ssoprovider_auto_provision_ssoprovider_client_secret_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkspaceBillingContract",
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
                    "contract_type",
                    models.CharField(
                        choices=[
                            ("trial", "Trial"),
                            ("subscription", "Subscription"),
                            ("enterprise", "Enterprise contract"),
                            ("purchase_order", "Purchase order"),
                        ],
                        default="subscription",
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("active", "Active"),
                            ("past_due", "Past due"),
                            ("canceled", "Canceled"),
                            ("expired", "Expired"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("seat_commitment", models.PositiveIntegerField(default=0)),
                (
                    "monthly_commitment",
                    models.DecimalField(
                        decimal_places=2, default=Decimal("0.00"), max_digits=12
                    ),
                ),
                ("currency", models.CharField(default="INR", max_length=3)),
                ("tax_id", models.CharField(blank=True, max_length=80)),
                ("purchase_order", models.CharField(blank=True, max_length=120)),
                ("invoice_email", models.EmailField(blank=True, max_length=254)),
                ("payment_terms_days", models.PositiveIntegerField(default=30)),
                ("starts_at", models.DateField(blank=True, null=True)),
                ("ends_at", models.DateField(blank=True, null=True)),
                ("renewal_at", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "workspace",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="billing_contract",
                        to="users.workspace",
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
            },
        ),
    ]
