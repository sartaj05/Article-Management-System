from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [('articles', '0058_ai_evaluation_framework')]

    operations = [
        migrations.CreateModel(
            name='AIJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('summarize', 'Summarize'), ('headline', 'Headline'), ('seo', 'SEO'), ('proofread', 'Proofread'), ('fact_check', 'Fact check')], max_length=20)),
                ('idempotency_key', models.CharField(blank=True, max_length=120)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed')], default='queued', max_length=20)),
                ('provider', models.CharField(blank=True, max_length=80)), ('model', models.CharField(blank=True, max_length=120)),
                ('result', models.JSONField(blank=True, default=dict)), ('error', models.TextField(blank=True)), ('attempts', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)), ('started_at', models.DateTimeField(blank=True, null=True)), ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_jobs', to='articles.article')),
                ('requested_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ai_jobs_requested', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at'], 'indexes': [models.Index(fields=['status', 'created_at'], name='articles_ai_status_41d9e6_idx')]},
        ),
    ]
