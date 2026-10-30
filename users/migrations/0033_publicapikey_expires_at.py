from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0032_readerdigestdelivery')]

    operations = [
        migrations.AddField(
            model_name='publicapikey',
            name='expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
