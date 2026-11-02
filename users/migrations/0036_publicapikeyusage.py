from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('users', '0035_performance_indexes')]

    operations = [
        migrations.CreateModel(
            name='PublicAPIKeyUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.CharField(blank=True, max_length=160)),
                ('method', models.CharField(default='GET', max_length=10)),
                ('status_code', models.PositiveSmallIntegerField(default=200)),
                ('response_ms', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('api_key', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usage_events', to='users.publicapikey')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='publicapikeyusage',
            index=models.Index(fields=['api_key', '-created_at'], name='api_key_usage_recent_idx'),
        ),
    ]
