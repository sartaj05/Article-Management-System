from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [('articles', '0063_ai_feedback')]

    operations = [
        migrations.RenameIndex(model_name='aifeedback', old_name='articles_aife_action_1d2b3a_idx', new_name='articles_ai_action_bfd9fe_idx'),
        migrations.CreateModel(
            name='AIReaderRecommendation',
            fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('score', models.DecimalField(decimal_places=3, default=0, max_digits=7)), ('reasons', models.JSONField(blank=True, default=list)), ('algorithm_version', models.CharField(default='reader-ranker-v1', max_length=40)), ('created_at', models.DateTimeField(default=django.utils.timezone.now)), ('expires_at', models.DateTimeField(blank=True, null=True))],
            options={'ordering': ['-score', '-created_at']},
        ),
        migrations.AddField(model_name='aireaderrecommendation', name='article', field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_reader_recommendations', to='articles.article')),
        migrations.AddField(model_name='aireaderrecommendation', name='user', field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_reader_recommendations', to=settings.AUTH_USER_MODEL)),
        migrations.AddIndex(model_name='aireaderrecommendation', index=models.Index(fields=['user', 'created_at'], name='articles_ai_user_id_446e1a_idx')),
    ]
