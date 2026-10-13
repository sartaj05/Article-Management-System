from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('articles', '0044_workflow_rules')]

    operations = [
        migrations.AddField(model_name='mediaasset', name='processing_status', field=models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('ready', 'Ready'), ('failed', 'Failed')], default='pending', max_length=20)),
        migrations.AddField(model_name='mediaasset', name='processing_error', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='mediaasset', name='processed_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='mediaasset', name='cdn_url', field=models.URLField(blank=True)),
    ]
