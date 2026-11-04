from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0045_impersonationsession')]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='role',
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
