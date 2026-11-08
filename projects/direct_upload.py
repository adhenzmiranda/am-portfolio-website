"""
Direct browser-to-Cloudinary uploads for the admin (project videos and photos).

Why: Heroku ends every request after 30 seconds. Sending files through the dyno
(browser -> Heroku -> Cloudinary inside the save request) times out with a 500
for videos, and for batches of photos. Instead the browser uploads straight to
Cloudinary using a short-lived signature from `sign_upload`, and the form only
submits the resulting reference (public id, version, format and Cloudinary's
signature), which is verified here before it is saved.

The signed upload parameters (folder and upload-time transformation) are read
from the model field itself, so a direct upload is stored exactly as the field
would store it, and the browser cannot change them.

Files over Cloudinary's free-plan per-file limits (videos 100 MB, images 10 MB)
cannot be uploaded directly. A video that is too big can still go through the
local admin (DEBUG on), which compresses it on Save
(projects.fields.CompressedVideoField); otherwise the widget asks for a smaller file.
"""
import cloudinary
import cloudinary.utils
from cloudinary import CloudinaryResource
from cloudinary.forms import CloudinaryJsFileField
from django import forms
from django.apps import apps
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpResponseNotAllowed, JsonResponse
from django.urls import reverse
from django.utils.html import format_html

# What can be uploaded directly, and Cloudinary free-plan size limits per file.
UPLOAD_KINDS = {
    'video': {
        'model': 'projects.ProjectVideo', 'field': 'video', 'max_mb': 100,
        'accept': 'video/*', 'noun': 'video',
        'local_fallback': 'it will be compressed and uploaded when you click Save',
        'sign_url': 'admin:projects_projectvideo_sign_upload',
    },
    'photo': {
        'model': 'projects.ProjectPhoto', 'field': 'image', 'max_mb': 10,
        'accept': 'image/*', 'noun': 'photo',
        # No fallback: Cloudinary's 10 MB image limit applies to every upload, not just direct ones.
        'local_fallback': '',
        'sign_url': 'admin:projects_projectphoto_sign_upload',
    },
}
MAX_DIRECT_UPLOAD_MB = UPLOAD_KINDS['video']['max_mb']  # kept for the video help text


def _model_field(kind):
    spec = UPLOAD_KINDS[kind]
    return apps.get_model(spec['model'])._meta.get_field(spec['field'])


class DirectUploadWidget(forms.Widget):
    """A file picker that uploads to Cloudinary from the browser.

    Renders a visible <input type=file> (without a name, so the file itself is not
    posted) and a hidden input that receives the Cloudinary reference once the
    upload finishes. static/admin/js/direct_upload.js does the uploading.
    """

    needs_multipart_form = True  # for the local fallback

    class Media:
        js = ('admin/js/direct_upload.js',)
        css = {'all': ('admin/css/direct_upload.css',)}

    def __init__(self, kind, attrs=None):
        self.kind = kind
        super().__init__(attrs)

    def value_from_datadict(self, data, files, name):
        # Local fallback: a large file posted the normal way.
        upload = files.get(name)
        if upload:
            return upload
        return data.get(name, '')

    def value_omitted_from_data(self, data, files, name):
        return name not in data and name not in files

    def render(self, name, value, attrs=None, renderer=None):
        spec = UPLOAD_KINDS[self.kind]
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
            '<input type="file" id="{id}" accept="{accept}" data-direct-upload data-field-name="{name}"'
            ' data-sign-url="{sign_url}" data-max-mb="{max_mb}" data-noun="{noun}"'
            ' data-local-fallback="{fallback}" data-allow-server-upload="{allow}">'
            '<input type="hidden" name="{name}" id="{id}_value" value="">'
            '<progress class="direct-upload__bar" max="100" value="0" hidden></progress>'
            '<p class="direct-upload__status" aria-live="polite"></p>'
            '</div>',
            current=current,
            id=input_id,
            name=name,
            accept=spec['accept'],
            sign_url=reverse(spec['sign_url']),
            max_mb=spec['max_mb'],
            noun=spec['noun'],
            fallback=spec['local_fallback'],
            # Local admin only, and only where the server can do better (videos: compress first).
            allow='true' if settings.DEBUG and spec['local_fallback'] else 'false',
        )


class DirectUploadField(CloudinaryJsFileField):
    """Accepts a signed reference from a direct upload (verified against the API
    secret, so a forged reference is rejected), a posted file (local fallback),
    or nothing (keep the current file; see DirectUploadFormMixin)."""

    def __init__(self, kind, *args, **kwargs):
        kwargs.setdefault('widget', DirectUploadWidget(kind))
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
        # Only a new upload changes the file; an empty value means "keep current".
        return bool(data)


class DirectUploadFormMixin:
    """For ModelForms with DirectUploadFields: an empty value keeps the current file,
    and a new row without a file gets a clear message."""

    def keep_current_or_require(self, name, message):
        value = self.cleaned_data.get(name)
        if value is None:
            current = getattr(self.instance, name, None) if self.instance.pk else None
            if current:
                return current
            raise forms.ValidationError(message)
        return value


def sign_upload(model_admin, kind):
    """Build the view that signs one direct upload of `kind` (admin-only, POST)."""
    field = _model_field(kind)

    def view(request):
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        if not (model_admin.has_add_permission(request) or model_admin.has_change_permission(request)):
            raise PermissionDenied
        # Exactly the parameters the model field would upload with (folder, transformation).
        params = cloudinary.utils.build_upload_params(**field.options)
        signed = cloudinary.utils.sign_request(params, {})  # adds api_key + signature, drops empty values
        api_key = signed.pop('api_key')
        return JsonResponse({
            'params': signed,
            'api_key': api_key,
            'upload_url': cloudinary.utils.cloudinary_api_url('upload', resource_type=field.resource_type),
        })

    return view
