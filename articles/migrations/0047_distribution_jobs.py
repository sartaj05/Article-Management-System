from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('articles', '0046_revision_versions')]

    operations = [
        migrations.CreateModel(
            name='DistributionJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('channel', models.CharField(choices=[('rss', 'RSS'), ('newsletter', 'Newsletter'), ('webhook', 'Webhook'), ('social', 'Social')], max_length=20)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('processing', 'Processing'), ('delivered', 'Delivered'), ('failed', 'Failed'), ('awaiting_provider', 'Awaiting provider')], default='queued', max_length=24)),
                ('attempts', models.PositiveIntegerField(default=0)),
                ('last_error', models.CharField(blank=True, max_length=500)),
                ('scheduled_for', models.DateTimeField(blank=True, null=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='distribution_jobs', to='articles.article')),
                ('requested_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='distribution_jobs_requested', to='users.customuser')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
