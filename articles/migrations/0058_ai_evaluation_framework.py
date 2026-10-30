from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('articles', '0057_ai_fact_checking')]

    operations = [
        migrations.CreateModel(
            name='AIPromptVersion',
            fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('name', models.CharField(default='editorial-copilot', max_length=80)), ('version', models.CharField(max_length=40)), ('system_prompt', models.TextField()), ('is_active', models.BooleanField(default=True)), ('created_at', models.DateTimeField(default=django.utils.timezone.now)), ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ai_prompt_versions_created', to=settings.AUTH_USER_MODEL))],
            options={'ordering': ['name', '-created_at']},
        ),
        migrations.CreateModel(
            name='AIEvaluationCase',
            fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('name', models.CharField(max_length=120, unique=True)), ('action', models.CharField(choices=[('summarize', 'Summarize'), ('headline', 'Headline'), ('seo', 'SEO'), ('proofread', 'Proofread')], max_length=20)), ('title', models.CharField(max_length=255)), ('content', models.TextField()), ('criteria', models.JSONField(blank=True, default=dict)), ('is_active', models.BooleanField(default=True)), ('created_at', models.DateTimeField(default=django.utils.timezone.now))],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='AIEvaluationRun',
            fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('prompt_version', models.CharField(default='editorial-v1', max_length=80)), ('provider', models.CharField(max_length=80)), ('total_cases', models.PositiveIntegerField(default=0)), ('passed_cases', models.PositiveIntegerField(default=0)), ('score', models.DecimalField(decimal_places=2, default=0, max_digits=5)), ('results', models.JSONField(blank=True, default=list)), ('created_at', models.DateTimeField(default=django.utils.timezone.now)), ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ai_evaluation_runs_created', to=settings.AUTH_USER_MODEL))],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(model_name='aipromptversion', constraint=models.UniqueConstraint(fields=('name', 'version'), name='unique_ai_prompt_version')),
    ]
