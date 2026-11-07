"""
Direct browser-to-Cloudinary video uploads for the admin.

Why: Heroku ends every request after 30 seconds. Sending a video through the
dyno (browser -> Heroku -> Cloudinary inside one request) times out with a 500
for anything but small files. Instead the browser uploads straight to
Cloudinary, using a short-lived signature from `sign_video_upload`, and the form
only submits the resulting reference (public id, version, format and Cloudinary's
signature), which is verified here before it is saved.

Files over Cloudinary's 100 MB per-file limit (free plan) cannot be uploaded
directly. With DEBUG on (the local admin) they fall back to the normal upload,
which compresses them on the way (projects.fields.CompressedVideoField); on the
live site the widget asks for a smaller file instead.
"""
import time

import cloudinary
import cloudinary.utils
from cloudinary import CloudinaryResource
from cloudinary.forms import CloudinaryJsFileField
from django import forms
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpResponseNotAllowed, JsonResponse
from django.urls import reverse
from django.utils.html import format_html

VIDEO_FOLDER = 'project_videos'          # same folder ProjectVideo.video uploads to
MAX_DIRECT_UPLOAD_MB = 100               # Cloudinary free plan: max video file size


class DirectVideoUploadWidget(forms.Widget):
    """A file picker that uploads to Cloudinary from the browser.

    Renders a visible <input type=file> (without a name, so the file itself is not
    posted) and a hidden input that receives the Cloudinary reference once the
    upload finishes. static/admin/js/video_direct_upload.js does the uploading.
    """

    needs_multipart_form = True  # for the local >100 MB fallback

    class Media:
        js = ('admin/js/video_direct_upload.js',)
        css = {'all': ('admin/css/video_direct_upload.css',)}

    def value_from_datadict(self, data, files, name):
        # Local fallback: a large file posted the normal way (compressed on save).
        upload = files.get(name)
        if upload:
            return upload
        return data.get(name, '')

    def value_omitted_from_data(self, data, files, name):
        return name not in data and name not in files

    def render(self, name, value, attrs=None, renderer=None):
        attrs = self.build_attrs(self.attrs, attrs)
        input_id = attrs.get('id') or f'id_{name}'
        current = ''
        if isinstance(value, CloudinaryResource) and value.public_id:
            current = format_html(
                '<p class="direct-upload__current">Current: <a href="{}" target="_blank" rel="noopener">{}</a></p>',
                value.url, value.public_id.rsplit('/', 1)[-1],
            )
        return format_html(
            '<div class="direct-upload">'
            '{current}'
            '<input type="file" id="{id}" accept="video/*" data-direct-upload data-field-name="{name}"'
            ' data-sign-url="{sign_url}" data-max-mb="{max_mb}" data-allow-server-upload="{allow}">'
            '<input type="hidden" name="{name}" id="{id}_value" value="">'
            '<progress class="direct-upload__bar" max="100" value="0" hidden></progress>'
            '<p class="direct-upload__status" aria-live="polite"></p>'
            '</div>',
            current=current,
            id=input_id,
            name=name,
            sign_url=reverse('admin:projects_projectvideo_sign_upload'),
            max_mb=MAX_DIRECT_UPLOAD_MB,
            allow='true' if settings.DEBUG else 'false',
        )


class DirectUploadVideoField(CloudinaryJsFileField):
    """Accepts a signed reference from a direct upload (verified against the API
    secret, so a forged reference is rejected), a posted file (local fallback),
    or nothing (keep the current video)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', DirectVideoUploadWidget())
        kwargs.setdefault('required', False)  # "keep current" is decided in the form
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if not value:
            return None
        if isinstance(value, UploadedFile):
            return value
        return super().to_python(value)   # "video/upload/v123/folder/id.mp4#signature"

    def validate(self, value):
        if value is None or isinstance(value, UploadedFile):
            return forms.Field.validate(self, value)
        return super().validate(value)    # checks Cloudinary's signature

    def has_changed(self, initial, data):
        # Only a new upload changes the video; an empty value means "keep current".
        return bool(data)


def sign_video_upload(model_admin):
    """Build the view that signs one direct upload (admin-only, POST)."""

    def view(request):
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        if not (model_admin.has_add_permission(request) or model_admin.has_change_permission(request)):
            raise PermissionDenied
        config = cloudinary.config()
        params = {'timestamp': int(time.time()), 'folder': VIDEO_FOLDER}
        params['signature'] = cloudinary.utils.api_sign_request(params, config.api_secret)
        return JsonResponse({
            **params,
            'api_key': config.api_key,
            'upload_url': f'https://api.cloudinary.com/v1_1/{config.cloud_name}/video/upload',
        })

    return view
