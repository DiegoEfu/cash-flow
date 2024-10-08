# Generated by Django 5.0.6 on 2024-07-04 21:04

import datetime
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_alter_transaction_date_alter_user_email'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='account',
            options={'ordering': ('name',)},
        ),
        migrations.AddField(
            model_name='account',
            name='visible',
            field=models.BooleanField(blank=True, default=False),
        ),
        migrations.AlterField(
            model_name='account',
            name='current_balance',
            field=models.DecimalField(blank=True, decimal_places=2, default=0.0, max_digits=15, validators=[django.core.validators.MinValueValidator(0.0)]),
        ),
        migrations.AlterField(
            model_name='account',
            name='owner',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='date',
            field=models.DateTimeField(default=datetime.datetime(2024, 7, 4, 17, 4, 26, 522169)),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='to_account',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transaction_to_account', to='core.account'),
        ),
    ]
