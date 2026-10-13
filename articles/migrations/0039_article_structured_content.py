from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('articles', '0038_workspace_isolation')]

    operations = [
        migrations.AddField(
            model_name='article',
            name='structured_content',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
