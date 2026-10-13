from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('users', '0025_workspace_branding')]

    operations = [
        migrations.CreateModel(
            name='FeatureFlag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.SlugField(max_length=100, unique=True)),
                ('description', models.CharField(blank=True, max_length=255)),
                ('is_enabled', models.BooleanField(default=False)),
                ('rollout_percent', models.PositiveSmallIntegerField(default=100)),
                ('allowed_roles', models.JSONField(blank=True, default=list)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('workspace', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='feature_flags', to='users.workspace')),
            ],
            options={'ordering': ['key']},
        ),
    ]
