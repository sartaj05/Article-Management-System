from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('users', '0028_remove_accessibilitypreference_updated_at')]

    operations = [
        migrations.CreateModel(
            name='MembershipInvoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('invoice_number', models.CharField(max_length=40, unique=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=8)),
                ('currency', models.CharField(default='INR', max_length=3)),
                ('status', models.CharField(choices=[('issued', 'Issued'), ('paid', 'Paid'), ('void', 'Void'), ('refunded', 'Refunded')], default='issued', max_length=20)),
                ('due_at', models.DateTimeField(blank=True, null=True)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='invoices', to='users.membershipplan')),
                ('transaction', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='invoice', to='users.paymenttransaction')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='membership_invoices', to='users.customuser')),
            ],
        ),
    ]
