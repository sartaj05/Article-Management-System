from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0046_reader_demo_role')]

    operations = [
        migrations.AlterField(
            model_name='ssoprovider',
            name='default_role',
            field=models.CharField(
                choices=[
                    ('Journalist', 'Journalist'),
                    ('Editor', 'Editor'),
                    ('Admin', 'Admin'),
                    ('Reader', 'Reader'),
                ],
                default='Journalist',
                max_length=20,
            ),
        ),
    ]
