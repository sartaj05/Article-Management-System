from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [('articles', '0059_ai_jobs')]

    operations = [
        migrations.CreateModel(
            name='AIWorkspacePolicy',
            fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('enabled', models.BooleanField(default=True)), ('allowed_actions', models.JSONField(blank=True, default=list)), ('monthly_token_budget', models.PositiveIntegerField(default=100000)), ('monthly_spend_limit', models.DecimalField(decimal_places=4, default=0, max_digits=10)), ('redact_pii', models.BooleanField(default=True)), ('require_human_review', models.BooleanField(default=True)), ('max_input_chars', models.PositiveIntegerField(default=12000)), ('created_at', models.DateTimeField(default=django.utils.timezone.now)), ('updated_at', models.DateTimeField(auto_now=True)), ('workspace', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='ai_policy', to='users.workspace'))],
        ),
        migrations.CreateModel(
            name='AIUsageEvent',
            fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('provider', models.CharField(max_length=80)), ('model', models.CharField(blank=True, max_length=120)), ('action', models.CharField(max_length=30)), ('prompt_tokens', models.PositiveIntegerField(default=0)), ('completion_tokens', models.PositiveIntegerField(default=0)), ('total_tokens', models.PositiveIntegerField(default=0)), ('estimated_cost', models.DecimalField(decimal_places=4, default=0, max_digits=10)), ('redacted_pii', models.BooleanField(default=False)), ('metadata', models.JSONField(blank=True, default=dict)), ('created_at', models.DateTimeField(default=django.utils.timezone.now)), ('article', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ai_usage_events', to='articles.article')), ('job', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='usage_events', to='articles.aijob')), ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ai_usage_events', to=settings.AUTH_USER_MODEL)), ('workspace', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ai_usage_events', to='users.workspace'))],
            options={'ordering': ['-created_at'], 'indexes': [models.Index(fields=['workspace', 'created_at'], name='articles_ai_workspa_4dd0ac_idx')]},
        ),
    ]
