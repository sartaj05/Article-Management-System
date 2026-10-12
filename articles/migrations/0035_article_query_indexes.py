from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('articles', '0034_articlemedia_captions_file_articlemedia_file_size_and_more')]

    operations = [
        migrations.AddIndex(
            model_name='article',
            index=models.Index(fields=['workflow_status', '-updated_at'], name='article_workflow_updated_idx'),
        ),
        migrations.AddIndex(
            model_name='article',
            index=models.Index(fields=['is_visible', '-publish_date'], name='article_visible_publish_idx'),
        ),
        migrations.AddIndex(
            model_name='article',
            index=models.Index(fields=['author', 'workflow_status'], name='article_author_workflow_idx'),
        ),
        migrations.AddIndex(
            model_name='mediaasset',
            index=models.Index(fields=['is_archived', '-updated_at'], name='media_archived_updated_idx'),
        ),
        migrations.AddIndex(
            model_name='mediaasset',
            index=models.Index(fields=['media_type', 'is_archived'], name='media_type_archived_idx'),
        ),
    ]
