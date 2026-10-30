from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [('articles', '0060_ai_governance')]

    operations = [
        migrations.CreateModel(
            name='AIInsight',
            fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('kind', models.CharField(default='newsroom-intelligence', max_length=40)), ('payload', models.JSONField(blank=True, default=dict)), ('score', models.DecimalField(decimal_places=2, default=0, max_digits=5)), ('created_at', models.DateTimeField(default=django.utils.timezone.now)), ('article', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ai_insights', to='articles.article')), ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ai_insights_created', to=settings.AUTH_USER_MODEL)), ('workspace', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ai_insights', to='users.workspace'))],
            options={'ordering': ['-created_at']},
        ),
    ]
