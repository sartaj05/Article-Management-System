import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0029_membership_invoices'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='NewsletterCampaignAttribution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('visitor_key', models.CharField(max_length=64)),
                ('clicked_at', models.DateTimeField(auto_now_add=True)),
                ('checkout_started_at', models.DateTimeField(blank=True, null=True)),
                ('converted_at', models.DateTimeField(blank=True, null=True)),
                ('edition', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attributions', to='users.newsletteredition')),
                ('subscription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='newsletter_attributions', to='users.membershipsubscription')),
                ('transaction', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='newsletter_attributions', to='users.paymenttransaction')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='newsletter_attributions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-clicked_at'], 'constraints': [models.UniqueConstraint(fields=('edition', 'visitor_key'), name='unique_newsletter_campaign_visitor')]},
        ),
    ]
