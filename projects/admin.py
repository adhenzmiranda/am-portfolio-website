from django.contrib import admin
from django.utils.html import format_html
from .models import Projects, ProjectPhoto, ProjectVideo, ProjectEmbed
from django.urls import path
from django.shortcuts import render, redirect
from django import forms
from django.contrib import messages
from django.forms.models import BaseInlineFormSet

class ProjectPhotoFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial = [{'order': i} for i in range(len(self.forms))]

class ProjectPhotoInline(admin.TabularInline):
    model = ProjectPhoto
    formset = ProjectPhotoFormSet
    extra = 1
    fields = ('image', 'caption', 'order')
    readonly_fields = ('created_at',)
    min_num = 0
    validate_min = False
    can_delete = True
    show_change_link = True
    template = 'admin/edit_inline/tabular.html'

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.base_fields['order'].initial = 0
        return formset

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('order')

class ProjectVideoForm(forms.ModelForm):
    class Meta:
        model = ProjectVideo
        fields = '__all__'
        widgets = {
            'caption': forms.TextInput(attrs={
                'placeholder': 'Optional video description...'
            }),
            'order': forms.NumberInput(attrs={
                'placeholder': '0'
            }),
        }
        help_texts = {
            'video': '''
                <strong>Max file size: 100MB</strong><br>
                <strong>Recommended:</strong> MP4 format, 720p resolution, 1-2 Mbps bitrate<br>
                <strong>Supported formats:</strong> MP4, MOV, AVI, WMV, MKV, WebM<br>
                <em>If your file is too large, compress it first using tools like HandBrake or online compressors.</em><br>
                <a href="/static/docs/VIDEO_UPLOAD_GUIDE.md" target="_blank">📖 Full Video Upload Guide</a>
            ''',
        }

class ProjectVideoInline(admin.TabularInline):
    model = ProjectVideo
    form = ProjectVideoForm
    extra = 1
    fields = ('video', 'caption', 'order')
    readonly_fields = ('created_at',)
    min_num = 0
    validate_min = False
    can_delete = True
    show_change_link = True

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('order')

class ProjectPhotoForm(forms.ModelForm):
    class Meta:
        model = ProjectPhoto
        fields = '__all__'
        widgets = {
            'order': forms.HiddenInput(),
        }

class ProjectEmbedInline(admin.TabularInline):
    model = ProjectEmbed
    extra = 1

class ProjectsForm(forms.ModelForm):
    video_embed = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'class': 'vLargeTextField',
            'placeholder': 'Paste your YouTube/Vimeo embed code here. Example:\n<iframe width="560" height="315" src="https://www.youtube.com/embed/VIDEO_ID" frameborder="0" allowfullscreen></iframe>'
        }),
        required=False,
        help_text='Paste the full iframe code from YouTube or Vimeo. Make sure to include the full iframe tag with all attributes.'
    )

    class Meta:
        model = Projects
        fields = '__all__'

@admin.register(ProjectPhoto)
class ProjectPhotoAdmin(admin.ModelAdmin):
    list_display = ('project', 'display_image', 'caption', 'order', 'created_at')
    list_filter = ('project',)
    search_fields = ('caption', 'project__name')
    form = ProjectPhotoForm
    
    def display_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" height="100" />', obj.image.url)
        return "No image"
    display_image.short_description = 'Image'

@admin.register(ProjectVideo)
class ProjectVideoAdmin(admin.ModelAdmin):
    form = ProjectVideoForm
    list_display = ('project', 'display_video', 'caption', 'order', 'created_at')
    list_filter = ('project',)
    search_fields = ('caption', 'project__name')
    
    def display_video(self, obj):
        if obj.video:
            return format_html(
                '<video width="150" height="100" controls preload="metadata"><source src="{}" type="video/mp4">Your browser does not support video.</video>', 
                obj.video.url
            )
        return "No video"
    display_video.short_description = 'Video Preview'

@admin.register(ProjectEmbed)
class ProjectEmbedAdmin(admin.ModelAdmin):
    pass

@admin.register(Projects)
class ProjectsAdmin(admin.ModelAdmin):
    form = ProjectsForm
    list_display = ('name', 'category', 'year', 'created_at', 'featured')
    list_editable = ('featured',)
    list_filter = ('category', 'year')
    search_fields = ('name', 'description', 'tags')
    inlines = [ProjectPhotoInline, ProjectVideoInline, ProjectEmbedInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'category', 'year', 'tags', 'technologies', 'featured')
        }),
        ('Media', {
            'fields': ('thumbnail_image', 'video_embed')
        }),
    )
    
    class Media:
        css = {
            'all': ('admin/css/video_embed.css',)
        }
        js = ('admin/js/video_embed.js',)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('batch-upload/<int:project_id>/', self.batch_upload_view, name='projects-projects-batch-upload'),
        ]
        return custom_urls + urls

    def batch_upload_view(self, request, project_id):
        project = Projects.objects.get(id=project_id)
        
        if request.method == 'POST':
            files = request.FILES.getlist('photos')
            for file in files:
                ProjectPhoto.objects.create(
                    project=project,
                    image=file,
                    order=ProjectPhoto.objects.filter(project=project).count()
                )
            messages.success(request, f'Successfully uploaded {len(files)} photos.')
            return redirect('admin:projects_projects_change', project_id)
            
        return render(request, 'admin/projects/batch_upload.html', {
            'project': project,
            'title': 'Batch Upload Photos',
        })