from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('articles', '0040_source_verification')]

    operations = [
        migrations.AddField(model_name='notification', name='action_url', field=models.CharField(blank=True, max_length=500)),
        migrations.AddField(model_name='notification', name='priority', field=models.CharField(choices=[('normal', 'Normal'), ('high', 'High')], default='normal', max_length=10)),
        migrations.AddField(model_name='notification', name='read_at', field=models.DateTimeField(blank=True, null=True)),
    ]
