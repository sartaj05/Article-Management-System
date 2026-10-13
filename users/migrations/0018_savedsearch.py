from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('users', '0017_alertrule')]

    operations = [
        migrations.CreateModel(
            name='SavedSearch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('query', models.CharField(max_length=150)),
                ('frequency', models.CharField(choices=[('instant', 'Instant'), ('daily', 'Daily'), ('weekly', 'Weekly')], default='daily', max_length=10)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='saved_searches', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-updated_at'], 'constraints': [models.UniqueConstraint(fields=('user', 'query'), name='unique_user_saved_search')]},
        ),
    ]
