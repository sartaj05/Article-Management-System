from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('users', '0023_workspace_multitenancy')]

    operations = [migrations.CreateModel(
        name='PaymentTransaction',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('provider', models.CharField(choices=[('manual', 'Manual'), ('stripe', 'Stripe'), ('razorpay', 'Razorpay')], default='manual', max_length=20)),
            ('checkout_token', models.CharField(max_length=80, unique=True)),
            ('provider_reference', models.CharField(blank=True, max_length=160)),
            ('amount', models.DecimalField(decimal_places=2, max_digits=8)),
            ('currency', models.CharField(default='INR', max_length=3)),
            ('status', models.CharField(choices=[('pending', 'Pending'), ('succeeded', 'Succeeded'), ('failed', 'Failed'), ('refunded', 'Refunded')], default='pending', max_length=20)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payment_transactions', to='users.membershipplan')),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_transactions', to=settings.AUTH_USER_MODEL)),
        ],
        options={'ordering': ['-created_at']},
    )]
