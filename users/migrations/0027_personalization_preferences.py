from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('users', '0026_feature_flags')]

    operations = [
        migrations.CreateModel(
            name='PersonalizationPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(default=True)),
                ('use_reading_history', models.BooleanField(default=True)),
                ('use_topic_interests', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='personalization_preferences', to='users.customuser')),
            ],
        ),
    ]
