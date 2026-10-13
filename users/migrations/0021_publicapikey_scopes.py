from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0020_twofactorauth')]

    operations = [
        migrations.AddField(
            model_name='publicapikey',
            name='scopes',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
