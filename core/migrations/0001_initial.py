# Generated by Django 5.0.6 on 2024-06-22 21:32

import core.mixins
import datetime
import django.contrib.auth.models
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Currency',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(error_messages={'unique': 'A user with that username already exists.'}, help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.', max_length=150, unique=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()], verbose_name='username')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='email address')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
                ('main_currency', models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='core.currency')),
            ],
            options={
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
                'abstract': False,
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='Account',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=50)),
                ('description', models.CharField(max_length=100)),
                ('opening_time', models.DateTimeField(auto_now=True)),
                ('current_balance', models.DecimalField(decimal_places=2, default=0.0, max_digits=15)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('currency', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.currency')),
            ],
            bases=(core.mixins.StrAsNameMixin, models.Model),
        ),
        migrations.CreateModel(
            name='ExchangeRate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('exchange_rate', models.DecimalField(decimal_places=2, max_digits=15)),
                ('active', models.BooleanField(default=True)),
                ('currency1', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='currency1_exchange_rate', to='core.currency')),
                ('currency2', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='currency2_exchange_rate', to='core.currency')),
            ],
            bases=(core.mixins.StrAsNameMixin, models.Model),
        ),
        migrations.CreateModel(
            name='HistoricBalance',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('balance', models.DecimalField(decimal_places=2, max_digits=15)),
                ('date', models.DateField(auto_now=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.account')),
            ],
            bases=(core.mixins.StrAsNameMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=50, unique=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Tags',
            },
            bases=(core.mixins.StrAsNameMixin, models.Model),
        ),
        migrations.CreateModel(
            name='MoneyTag',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('active', models.BooleanField(default=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.account')),
                ('tag', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.tag')),
            ],
            bases=(core.mixins.StrAsNameMixin, models.Model),
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('reference', models.CharField(blank=True, max_length=15, null=True)),
                ('transaction_type', models.CharField(choices=[('+', 'Income'), ('-', 'Expense')], max_length=1)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('description', models.CharField(blank=True, max_length=100, null=True)),
                ('hold', models.BooleanField(default=False)),
                ('date', models.DateTimeField(default=datetime.datetime(2024, 6, 22, 17, 32, 42, 567566))),
                ('from_account', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transaction_from_account', to='core.account')),
                ('to_account', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transaction_to_account', to='core.account')),
            ],
        ),
        migrations.CreateModel(
            name='Fee',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('transaction_type', models.CharField(choices=[('P', 'Income'), ('A', 'Absolute')], max_length=1)),
                ('fee_percent', models.DecimalField(decimal_places=2, max_digits=5)),
                ('fee_maximum', models.DecimalField(decimal_places=2, max_digits=15)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.account')),
                ('currency', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.currency')),
                ('exchange_rate_used', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.exchangerate')),
                ('transaction', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.transaction')),
            ],
            bases=(core.mixins.StrAsNameMixin, models.Model),
        ),
    ]
