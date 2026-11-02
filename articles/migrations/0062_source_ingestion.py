from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('articles', '0061_ai_insights')]

    operations = [
        migrations.CreateModel(
            name='ArticleSourceDocument',
            fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('status', models.CharField(choices=[('queued', 'Queued'), ('fetching', 'Fetching'), ('ready', 'Ready'), ('failed', 'Failed')], default='queued', max_length=20)), ('content_type', models.CharField(blank=True, max_length=120)), ('text_content', models.TextField(blank=True)), ('content_hash', models.CharField(blank=True, max_length=64)), ('error', models.TextField(blank=True)), ('fetched_at', models.DateTimeField(blank=True, null=True)), ('created_at', models.DateTimeField(default=django.utils.timezone.now)), ('updated_at', models.DateTimeField(auto_now=True)), ('source', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='document', to='articles.articlesource'))],
            options={'ordering': ['-updated_at']},
        ),
        migrations.CreateModel(
            name='ArticleSourceChunk',
            fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('ordinal', models.PositiveIntegerField()), ('text', models.TextField()), ('token_count', models.PositiveIntegerField(default=0)), ('created_at', models.DateTimeField(default=django.utils.timezone.now)), ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chunks', to='articles.articlesourcedocument'))],
            options={'ordering': ['ordinal']},
        ),
        migrations.AddConstraint(model_name='articlesourcechunk', constraint=models.UniqueConstraint(fields=('document', 'ordinal'), name='unique_source_document_chunk')),
    ]
