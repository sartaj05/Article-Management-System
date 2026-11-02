from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0036_publicapikeyusage"),
    ]

    operations = [
        migrations.AddField(
            model_name="authortip",
            name="checkout_token",
            field=models.CharField(blank=True, max_length=80, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="authortip",
            name="checkout_url",
            field=models.URLField(blank=True),
        ),
    ]
