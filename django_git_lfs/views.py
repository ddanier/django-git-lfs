from _ast import keyword
import hashlib
import json
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.core.files.uploadhandler import TemporaryFileUploadHandler
from django.core.urlresolvers import reverse
from django.http import JsonResponse, Http404, FileResponse, HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from django.views.generic.detail import BaseDetailView
from .models import *
from .forms import LfsObjectForm
from django.conf import settings


class JsonUtilsMixin(object):
    def json_response(self, json_data, **kwargs):
        kwargs.setdefault('content_type', 'application/vnd.git-lfs+json')
        return JsonResponse(json_data, **kwargs)

    def json_request_body(self):
        try:
            return self._json_request_body
        except AttributeError:
            try:
                self._json_request_body = json.loads(self.request.body)
            except:
                self._json_request_body = None
            return self._json_request_body


class LfsAccessMixin(object):
    def auth_headers(self):
        return {
          'X-Git-LFS-Access-Token': self.access.token,
          # Workaround for https://github.com/github/git-lfs/issues/243
          'Authorization': 'Basic bm9uZTpuZWVkZWQ=',
        }

    def ensure_read_allowed(self):
        if not self.access.allow_read:
            raise Http404()

    def ensure_write_allowed(self):
        if not self.access.allow_write:
            raise Http404()


class AuthMixin(LfsAccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.META.get('HTTP_X_GIT_LFS_ACCESS_TOKEN', ''):
            raise Http404()
        try:
            self.access = LfsAccess.objects.get(
                token=request.META['HTTP_X_GIT_LFS_ACCESS_TOKEN'],
                expires__gt=now(),
            )
        except LfsAccess.DoesNotExist:
            raise Http404()
        return super(AuthMixin, self).dispatch(request, *args, **kwargs)


class GetLfsObjectMixin(object):
    def get_lfs_object(self, oid):
        return LfsObject.objects.get(oid=oid)


class BaseObjectDetailView(GetLfsObjectMixin, BaseDetailView):
    def get_object(self, queryset=None):
        try:
            return self.get_lfs_object(self.kwargs['oid'])
        except KeyError:
            raise Http404()
        except LfsObject.DoesNotExist:
            raise Http404()


class ExistingObjectMixin(object):
    def lfs_object_json(self, object):
        return {
          "oid": object.oid,
          "size": object.size,
          "_links": {
            "self": {
              "href": self.request.build_absolute_uri(reverse('lfs_object_meta', kwargs={"oid": object.oid})),
            },
            "download": {
              "href": self.request.build_absolute_uri(reverse('lfs_object_download', kwargs={"oid": object.oid})),
              "header": self.auth_headers(),
            }
          }
        }


class ObjectMetaView(JsonUtilsMixin, ExistingObjectMixin, AuthMixin, BaseObjectDetailView):
    def get(self, request, *args, **kwargs):
        self.ensure_read_allowed()
        self.object = self.get_object()
        return self.json_response(self.lfs_object_json(self.object))
object_meta = csrf_exempt(ObjectMetaView.as_view())


class ObjectDownloadView(AuthMixin, BaseObjectDetailView):
    def get(self, request, *args, **kwargs):
        self.ensure_read_allowed()
        self.object = self.get_object()
        self.object.file.open('rb')
        return FileResponse(self.object.file)
object_download = csrf_exempt(ObjectDownloadView.as_view())


class ObjectVerifyView(JsonUtilsMixin, AuthMixin, BaseObjectDetailView):
    def post(self, request, *args, **kwargs):
        self.ensure_write_allowed()  # Verify is basically a read operation, but only necessary after a valid write
        self.object = self.get_object()
        request_json = self.json_request_body()
        if request_json is None:
            raise Http404()
        if request_json.get('oid', '') != self.object.oid:
            raise Http404()
        if request_json.get('size', -1) != self.object.size:
            raise Http404()
        return HttpResponse()  # Just send HTTP 200
object_verify = csrf_exempt(ObjectVerifyView.as_view())


class UploadInitView(JsonUtilsMixin, ExistingObjectMixin, GetLfsObjectMixin, AuthMixin, View):
    def post(self, request, *args, **kwargs):
        self.ensure_write_allowed()
        request_json = self.json_request_body()
        if request_json is None:
            raise Http404()
        if not request_json.get('oid'):
            raise Http404()
        try:
            object = self.get_lfs_object(request_json['oid'])
            if request_json.get('size', -1) != object.size:
                raise Http404()
            if not object.repositories.filter(pk=self.access.repository.pk).exists():
                # If the object is not yet bound to this repository, just add it
                object.repositories.add(self.access.repository)
            return self.json_response(self.lfs_object_json(object))
        except LfsObject.DoesNotExist:
            return self.json_response({
                "_links": {
                    "upload": {
                        "href": self.request.build_absolute_uri(reverse('lfs_object_upload', kwargs={"oid": request_json['oid']})),
                        "header": self.auth_headers(),
                    },
                    "verify": {
                        "href": self.request.build_absolute_uri(reverse('lfs_object_verify', kwargs={"oid": request_json['oid']})),
                        "header": self.auth_headers(),
                    },
                }
            }, status=202)
object_upload_init = csrf_exempt(UploadInitView.as_view())


class ObjectUploadView(JsonUtilsMixin, AuthMixin, View):
    CHUNK_SIZE = 1024 * 1024

    def put(self, request, *args, **kwargs):
        self.ensure_write_allowed()
        upload = TemporaryFileUploadHandler(self.request)
        upload.new_file('lfs_upload.bin', 'lfs_upload.bin', 'application/octet-stream', -1)
        hash = hashlib.sha256()

        chunk = True
        size = 0
        while chunk:
            chunk = request.read(self.CHUNK_SIZE)
            upload.receive_data_chunk(chunk, size)
            hash.update(chunk)
            size += len(chunk)
        upload.file_complete(size)

        oid = self.kwargs.get('oid', '')
        if hash.hexdigest() != oid:
            return self.json_response({
                'message': 'OID of request does not match file contents'
            }, status=400)

        upload.file.name = '%s.bin' % oid
        form = LfsObjectForm(data={
            'oid': oid,
            'size': size,
        }, files= {
            'file': upload.file,
        })
        if not form.is_valid():
            return self.json_response({
                'message': 'Field Errors for: %s' % ', '.join(form.errors)
            }, status=400)
        lfsobject = form.save(commit=False)
        lfsobject.uploader = self.access.user
        lfsobject.save()
        lfsobject.repositories.add(self.access.repository)
        return HttpResponse()  # Just return Status 200
object_upload = csrf_exempt(ObjectUploadView.as_view())


class PermsView(JsonUtilsMixin, LfsAccessMixin, View):
    def post(self, request, *args, **kwargs):
        if request.META.get('HTTP_X_GIT_LFS_PERMS_TOKEN', '') != getattr(settings, 'LFS_PERMS_TOKEN', ''):
            return HttpResponseForbidden('No valid perms token supplied')
        request_json = self.json_request_body()
        if request_json is None:
            raise Http404()
        if not request_json.get('repository', ''):
            raise Http404()
        if not request_json.get('user', ''):
            raise Http404()
        if not request_json.get('operation', '') in ('upload', 'download',):
            raise Http404()
        repository = LfsRepository.objects.get_or_create(
            canonical=LfsRepository.normalize_repo(request_json['repository']),
        )[0]
        try:
            self.access = LfsAccess.objects.get(
                user=request_json['user'],
                repository=repository,
                expires__gt=now(),
            )
            self.access.expires = default_expiration()
        except LfsAccess.DoesNotExist:
            self.access = LfsAccess(
                user=request_json['user'],
                repository=repository,
            )
        if request_json['operation'] == 'upload':
            self.access.allow_write = True
        if request_json['operation'] == 'download':
            self.access.allow_read = True
        self.access.save()
        return self.json_response({
            'header': self.auth_headers(),
            'href': request.build_absolute_uri(reverse('lfs_base')),
        })
perms = csrf_exempt(PermsView.as_view())
