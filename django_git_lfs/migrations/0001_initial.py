# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_git_lfs.models
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LfsAccess',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('expires', models.DateTimeField(default=django_git_lfs.models.default_expiration)),
                ('token', models.CharField(default=django_git_lfs.models.generate_unique_access_token, unique=True, max_length=32)),
                ('allow_read', models.BooleanField(default=False)),
                ('allow_write', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='LfsObject',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('oid', models.CharField(unique=True, max_length=64)),
                ('file', models.FileField(upload_to=b'lfs')),
                ('size', models.PositiveIntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='LfsRepository',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('canonical', models.CharField(unique=True, max_length=255)),
            ],
        ),
        migrations.AddField(
            model_name='lfsobject',
            name='repositories',
            field=models.ManyToManyField(to='django_git_lfs.LfsRepository'),
        ),
        migrations.AddField(
            model_name='lfsobject',
            name='uploader',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True),
        ),
        migrations.AddField(
            model_name='lfsaccess',
            name='repository',
            field=models.ForeignKey(to='django_git_lfs.LfsRepository'),
        ),
        migrations.AddField(
            model_name='lfsaccess',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True),
        ),
    ]
