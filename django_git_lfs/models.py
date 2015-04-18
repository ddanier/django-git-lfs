from datetime import timedelta
import os
from django.conf import settings
from django.db import models
from django.utils.timezone import now
import random


class LfsRepository(models.Model):
    created = models.DateTimeField(default=now)

    canonical = models.CharField(max_length=255)


def generate_unique_access_token():
    token = None
    while token is None or LfsAccess.objects.filter(token=token).exists():
        token = ''.join([random.choice(LfsAccess.TOKEN_CHOICES) for i in xrange(32)])
    return token


def default_expiration():
    return now() + timedelta(hours=8)


class LfsAccess(models.Model):
    TOKEN_CHOICES = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_:#%'

    created = models.DateTimeField(default=now)
    expires = models.DateTimeField(default=default_expiration)

    token = models.CharField(max_length=32, default=generate_unique_access_token)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True)
    repository = models.ForeignKey(LfsRepository)

    allow_read = models.BooleanField(default=False)
    allow_write = models.BooleanField(default=False)


class LfsObject(models.Model):
    created = models.DateTimeField(default=now)

    oid = models.CharField(max_length=71)  # normal OID length
    file = models.FileField(upload_to='lfs')
    size = models.PositiveIntegerField()

    uploader = models.ForeignKey(settings.AUTH_USER_MODEL, null=True)
    repositories = models.ManyToManyField(LfsRepository)
