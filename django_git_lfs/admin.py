from django.contrib import admin
from .models import *


class LfsRepositoryAdmin(admin.ModelAdmin):
    list_display = ('canonical', 'created')
admin.site.register(LfsRepository, LfsRepositoryAdmin)


class LfsAccessAdmin(admin.ModelAdmin):
    list_display = ('token', 'user', 'repository', 'allow_read', 'allow_write', 'created', 'expires')
admin.site.register(LfsAccess, LfsAccessAdmin)


class LfsObjectAdmin(admin.ModelAdmin):
    list_display = ('oid', 'file', 'size', 'uploader', 'created')
admin.site.register(LfsObject, LfsObjectAdmin)
