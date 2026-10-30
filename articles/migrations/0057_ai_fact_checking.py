from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('articles', '0056_editorialassistantrun_ai_metadata')]

    operations = [
        migrations.AlterField(
            model_name='notification', name='notification_type',
            field=models.CharField(choices=[('submitted', 'Submitted'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('published', 'Published'), ('scheduled', 'Scheduled'), ('comment', 'Comment'), ('reader_alert', 'Reader alert'), ('assignment', 'Assignment reminder'), ('sla_escalation', 'SLA escalation')], max_length=20),
        ),
        migrations.AddField(model_name='articlefactcheck', name='confidence', field=models.DecimalField(decimal_places=2, default=0, max_digits=5)),
        migrations.AddField(model_name='articlefactcheck', name='is_ai_suggested', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='articlefactcheck', name='review_status', field=models.CharField(choices=[('pending', 'Pending editorial review'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='approved', max_length=20)),
        migrations.AddField(model_name='articlefactcheck', name='supporting_sources', field=models.ManyToManyField(blank=True, related_name='fact_checks', to='articles.articlesource')),
    ]
