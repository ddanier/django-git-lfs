import json
from django.core.urlresolvers import reverse
from django.http import JsonResponse, Http404, FileResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from django.views.generic.detail import BaseDetailView
from .models import *


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
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return FileResponse(self.object.file.open('rb'))
object_download = csrf_exempt(ObjectDownloadView.as_view())


class ObjectVerifyView(JsonUtilsMixin, BaseObjectDetailView):
    def get(self, request, *args, **kwargs):
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
                        "href": self.request.build_absolute_uri(reverse('lfs_object_upload')),
                        "header": self.lfs_auth_headers(),
                    },
                    "verify": {
                        "href": self.request.build_absolute_uri(reverse('lfs_object_verify', kwargs={"oid": request_json['oid']})),
                        "header": self.lfs_auth_headers(),
                    },
                }
            }, status=202)
object_upload_init = csrf_exempt(UploadInitView.as_view())


class ObjectUploadView(View):
    def http_method_not_allowed(self, request, *args, **kwargs):
        print request.method

    def put(self, request, *args, **kwargs):
        print request.body
object_upload = csrf_exempt(ObjectUploadView.as_view())
