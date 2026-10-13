from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0022_security_foundation')]

    operations = [
        migrations.AddField(model_name='workspace', name='plan', field=models.CharField(choices=[('starter', 'Starter'), ('team', 'Team'), ('enterprise', 'Enterprise')], default='starter', max_length=20)),
        migrations.AddField(model_name='workspace', name='seat_limit', field=models.PositiveIntegerField(default=5)),
    ]
