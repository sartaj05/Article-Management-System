from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0018_savedsearch')]
    operations = [migrations.CreateModel(name='RoleCapabilityOverride', fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('role', models.CharField(choices=[('Journalist', 'Journalist'), ('Editor', 'Editor'), ('Admin', 'Admin')], max_length=20)), ('capability', models.CharField(max_length=100)), ('is_enabled', models.BooleanField(default=True)), ('updated_at', models.DateTimeField(auto_now=True))], options={'ordering': ['role', 'capability'], 'constraints': [models.UniqueConstraint(fields=('role', 'capability'), name='unique_role_capability_override')]}),]
