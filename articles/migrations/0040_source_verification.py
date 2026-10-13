from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('articles', '0039_article_structured_content')]

    operations = [
        migrations.AddField(model_name='articlesource', name='verification_status', field=models.CharField(choices=[('pending', 'Pending'), ('verified', 'Verified'), ('unverified', 'Unverified')], default='pending', max_length=20)),
        migrations.AddField(model_name='articlesource', name='accessed_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='articlesource', name='citation_key', field=models.SlugField(blank=True, max_length=80)),
    ]
