from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0042_authenticationpolicy"),
    ]

    operations = [
        migrations.AddField(
            model_name="workspaceintegration",
            name="encrypted_secret",
            field=models.TextField(blank=True),
        ),
    ]
