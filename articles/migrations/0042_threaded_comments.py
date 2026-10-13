from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('articles', '0041_notification_actions')]

    operations = [
        migrations.AddField(
            model_name='comment', name='parent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='replies', to='articles.comment'),
        ),
    ]
