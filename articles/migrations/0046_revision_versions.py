from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('articles', '0045_media_processing_status')]

    operations = [
        migrations.AddField(model_name='articlerevision', name='version_number', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='articlerevision', name='snapshot_hash', field=models.CharField(blank=True, max_length=64)),
    ]
