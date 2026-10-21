import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('articles', '0048_recovery_drills'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ReadingCollection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80)),
                ('description', models.CharField(blank=True, max_length=240)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reading_collections', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-updated_at', 'name'], 'constraints': [models.UniqueConstraint(fields=('user', 'name'), name='unique_reading_collection_name')]},
        ),
        migrations.CreateModel(
            name='ReadingCollectionArticle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.PositiveIntegerField(default=0)),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reader_collections', to='articles.article')),
                ('collection', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='articles.readingcollection')),
            ],
            options={'ordering': ['position', '-added_at'], 'constraints': [models.UniqueConstraint(fields=('collection', 'article'), name='unique_collection_article')]},
        ),
    ]
