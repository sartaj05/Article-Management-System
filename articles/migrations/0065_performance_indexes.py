from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('articles', '0064_ai_reader_recommendations')]

    operations = [
        migrations.AddIndex(
            model_name='article',
            index=models.Index(fields=['workflow_status', 'is_visible', '-published_at'], name='article_public_feed_idx'),
        ),
        migrations.AddIndex(
            model_name='distributionjob',
            index=models.Index(fields=['status', 'scheduled_for'], name='distribution_retry_idx'),
        ),
    ]
