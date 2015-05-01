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


class LfsAuthMixin(object):  # TODO!
    def lfs_auth_headers(self):
        return {}


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


class ExistingObjectMixin(LfsAuthMixin):
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
              "header": self.lfs_auth_headers(),
            }
          }
        }


class ObjectMetaView(JsonUtilsMixin, ExistingObjectMixin, BaseObjectDetailView):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.json_response(self.lfs_object_json(self.object))
object_meta = csrf_exempt(ObjectMetaView.as_view())


class ObjectDownloadView(BaseObjectDetailView):

    def dispatch(self, request, *args, **kwargs):
        try:
            return super(ObjectDownloadView, self).dispatch(request, *args, **kwargs)
        except Exception as e:
            import traceback

            print e
            traceback.print_exc()
            raise

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.file.open('rb')
        return FileResponse(self.object.file)
object_download = csrf_exempt(ObjectDownloadView.as_view())


class ObjectVerifyView(JsonUtilsMixin, BaseObjectDetailView):
    def post(self, request, *args, **kwargs):
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


class UploadInitView(JsonUtilsMixin, ExistingObjectMixin, GetLfsObjectMixin, View):
    def post(self, request, *args, **kwargs):
        request_json = self.json_request_body()
        if request_json is None:
            raise Http404()
        if not request_json.get('oid'):
            raise Http404()
        try:
            object = self.get_lfs_object(request_json['oid'])
            if request_json.get('size', -1) != object.size:
                raise Http404()
            return self.json_response(self.lfs_object_json(object))
        except LfsObject.DoesNotExist:
            return self.json_response({
                "_links": {
                    "upload": {
                        "href": self.request.build_absolute_uri(reverse('lfs_object_upload', kwargs={"oid": request_json['oid']})),
                        "header": self.lfs_auth_headers(),
                    },
                    "verify": {
                        "href": self.request.build_absolute_uri(reverse('lfs_object_verify', kwargs={"oid": request_json['oid']})),
                        "header": self.lfs_auth_headers(),
                    },
                }
            }, status=202)
object_upload_init = csrf_exempt(UploadInitView.as_view())


class ObjectUploadView(JsonUtilsMixin, View):
    CHUNK_SIZE = 1024 * 1024

    def put(self, request, *args, **kwargs):
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
        # TODO: Add user and repository
        lfsobject.save()
        return HttpResponse()  # Just return Status 200
object_upload = csrf_exempt(ObjectUploadView.as_view())


class PermsView(JsonUtilsMixin, View):
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
        repository = LfsRepository.objects.get_or_create(canonical=request_json['repository'])[0]
        try:
            access = LfsAccess.objects.get(
                user=request_json['user'],
                repository=repository,
                expires__gt=now(),
            )
            access.expires = default_expiration()
        except LfsAccess.DoesNotExist:
            access = LfsAccess(
                user=request_json['user'],
                repository=repository,
            )
        if request_json['operation'] == 'upload':
            access.allow_write = True
        if request_json['operation'] == 'download':
            access.allow_read = True
        access.save()
        return self.json_response({
            'header': {
              'X-Git-LFS-Access-Token': access.token,
            },
            'href': request.build_absolute_uri(reverse('lfs_object_upload_init')),
        })
perms = csrf_exempt(PermsView.as_view())
