from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('articles', '0042_threaded_comments'), ('users', '0026_feature_flags')]

    operations = [
        migrations.CreateModel(
            name='WorkflowRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('from_status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted for review'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('published', 'Published')], max_length=20)),
                ('to_status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted for review'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('published', 'Published')], max_length=20)),
                ('required_role', models.CharField(blank=True, max_length=20)),
                ('require_sources', models.BooleanField(default=False)),
                ('require_fact_check', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='workflow_rules', to='users.workspace')),
            ],
            options={'ordering': ['from_status', 'to_status', 'name']},
        ),
    ]
