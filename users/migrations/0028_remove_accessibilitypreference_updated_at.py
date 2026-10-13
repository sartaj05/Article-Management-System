from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('users', '0027_personalization_preferences')]

    operations = [migrations.RemoveField(model_name='accessibilitypreference', name='updated_at')]
