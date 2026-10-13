from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('articles', '0047_distribution_jobs')]

    operations = [
        migrations.CreateModel(
            name='RecoveryDrill',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('passed', 'Passed'), ('failed', 'Failed'), ('unsupported', 'Unsupported')], max_length=20)),
                ('details', models.CharField(blank=True, max_length=500)),
                ('checked_at', models.DateTimeField(auto_now_add=True)),
                ('backup', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recovery_drills', to='articles.backuprecord')),
            ],
            options={'ordering': ['-checked_at']},
        ),
    ]
