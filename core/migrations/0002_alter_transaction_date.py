# Generated by Django 5.0.6 on 2024-06-22 21:33

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='date',
            field=models.DateTimeField(default=datetime.datetime(2024, 6, 22, 17, 33, 24, 803369)),
        ),
    ]
