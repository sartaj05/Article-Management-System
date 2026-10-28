from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('articles', '0053_distributionjob_idempotency_key_and_more')]

    operations = [migrations.AddField(model_name='workflowrule', name='auto_assign_role', field=models.CharField(blank=True, max_length=20))]
