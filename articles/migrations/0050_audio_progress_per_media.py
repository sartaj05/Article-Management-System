from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('articles', '0049_reading_collections')]

    operations = [
        migrations.RemoveConstraint(
            model_name='readingprogress',
            name='unique_article_reading_progress',
        ),
        migrations.AddField(
            model_name='readingprogress',
            name='media_key',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddConstraint(
            model_name='readingprogress',
            constraint=models.UniqueConstraint(fields=('article', 'user', 'media_key'), name='unique_article_media_reading_progress'),
        ),
    ]
