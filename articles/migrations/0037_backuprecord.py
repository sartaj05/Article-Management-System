from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('articles', '0036_article_search_filters_index')]

    operations = [migrations.CreateModel(
        name='BackupRecord',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('kind', models.CharField(choices=[('database', 'Database'), ('media_manifest', 'Media manifest')], default='database', max_length=30)),
            ('status', models.CharField(choices=[('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed')], default='running', max_length=20)),
            ('path', models.CharField(blank=True, max_length=500)),
            ('checksum', models.CharField(blank=True, max_length=64)),
            ('size_bytes', models.PositiveBigIntegerField(default=0)),
            ('error', models.CharField(blank=True, max_length=500)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('completed_at', models.DateTimeField(blank=True, null=True)),
            ('initiated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='backups_initiated', to=settings.AUTH_USER_MODEL)),
        ],
        options={'ordering': ['-created_at']},
    )]
