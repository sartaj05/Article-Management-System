from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [('articles', '0062_source_ingestion')]

    operations = [
        migrations.CreateModel(
            name='AIFeedback',
            fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('action', models.CharField(max_length=30)), ('feedback_type', models.CharField(choices=[('accepted', 'Accepted'), ('rejected', 'Rejected'), ('corrected', 'Corrected'), ('comment', 'Comment')], max_length=20)), ('field', models.CharField(blank=True, max_length=60)), ('original_value', models.TextField(blank=True)), ('corrected_value', models.TextField(blank=True)), ('note', models.TextField(blank=True)), ('created_at', models.DateTimeField(default=django.utils.timezone.now)), ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_feedback', to='articles.article')), ('run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='feedback', to='articles.editorialassistantrun')), ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ai_feedback_given', to=settings.AUTH_USER_MODEL))],
            options={'ordering': ['-created_at'], 'indexes': [models.Index(fields=['action', 'feedback_type', 'created_at'], name='articles_aife_action_1d2b3a_idx')]},
        ),
    ]
