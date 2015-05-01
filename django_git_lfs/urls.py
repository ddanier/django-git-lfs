from django.conf.urls import url
from . import views


urlpatterns = [
    # Base URL
    url(r'^$', views.object_upload_init, name='lfs_base'),  # Does allow upload init, too

    # manage permissions
    url(r'^perms$', views.perms, name='lfs_perms'),

    # write access
    url(r'^objects$', views.object_upload_init, name='lfs_object_upload_init'),
    url(r'^objects/(?P<oid>[^/]+)/upload$', views.object_upload, name='lfs_object_upload'),

    # read access
    url(r'^objects/(?P<oid>[^/]+)$', views.object_meta, name='lfs_object_meta'),
    url(r'^objects/(?P<oid>[^/]+)/download$', views.object_download, name='lfs_object_download'),
    url(r'^objects/(?P<oid>[^/]+)/verify', views.object_verify, name='lfs_object_verify'),
]
