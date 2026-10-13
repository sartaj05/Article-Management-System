from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('articles', '0035_article_query_indexes')]

    operations = [
        migrations.AddIndex(
            model_name='article',
            index=models.Index(fields=['category', 'workflow_status', '-publish_date'], name='article_search_filters_idx'),
        ),
    ]
