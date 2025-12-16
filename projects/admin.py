from django.contrib import admin
from django.utils.html import format_html
from .models import Projects, ProjectPhoto, ProjectVideo, ProjectEmbed, Category
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
    extra = 0  # No empty forms - use batch upload button instead
    fields = ('thumbnail_preview', 'image', 'caption', 'order')
    readonly_fields = ('created_at', 'thumbnail_preview')
    min_num = 0
    validate_min = False
    can_delete = True
    show_change_link = True
    template = 'admin/edit_inline/tabular.html'

    def thumbnail_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width: 100px; max-height: 100px; border-radius: 4px;" />', obj.image.url)
        return "No image"
    thumbnail_preview.short_description = 'Preview'

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
                <strong>📹 Auto-Compression Enabled!</strong><br>
                <strong>Max file size:</strong> 100MB (system will auto-compress larger files)<br>
                <strong>Supported formats:</strong> MP4, MOV, AVI, WMV, MKV, WebM<br>
                <strong>Auto-compression:</strong> Videos over 100MB will be automatically compressed to 720p before upload.<br>
                <em>Upload any size video - the system will handle compression automatically!</em><br>
                <a href="/static/docs/VIDEO_UPLOAD_GUIDE.md" target="_blank">📖 Full Video Upload Guide</a>
            ''',
        }
    
    def __init__(self, *args, **kwargs):
        """Override init to process video BEFORE field validation."""
        super().__init__(*args, **kwargs)
        
        # Get the uploaded file from request data if available
        if 'video' in self.files:
            from .video_utils import process_video_upload, needs_compression
            import logging
            
            logger = logging.getLogger(__name__)
            video_file = self.files['video']
            
            if video_file:
                file_size = getattr(video_file, 'size', 0)
                logger.info(f"[INIT] Video upload detected: {video_file.name}, size: {file_size / (1024*1024):.2f}MB")
                
                # Check if compression is needed
                if needs_compression(file_size):
                    try:
                        logger.info("[INIT] Starting automatic compression BEFORE validation...")
                        compressed_file, was_compressed, orig_mb, final_mb = process_video_upload(video_file)
                        
                        if was_compressed:
                            logger.info(f"[INIT] Compression successful: {orig_mb:.2f}MB → {final_mb:.2f}MB")
                            
                            # Replace the file in the form data
                            self.files['video'] = compressed_file
                            
                            # Store compression info for later
                            self._compression_info = {
                                'was_compressed': True,
                                'original_size_mb': orig_mb,
                                'compressed_size_mb': final_mb
                            }
                    except Exception as e:
                        logger.error(f"[INIT] Compression failed: {e}", exc_info=True)
                        # Don't raise here - let validation handle it
                        self._compression_error = str(e)
    
    def clean_video(self):
        """Apply compression info to instance if compression happened in init."""
        video = self.cleaned_data.get('video')
        
        # Check if we had a compression error
        if hasattr(self, '_compression_error'):
            raise forms.ValidationError(
                f"Video compression failed: {self._compression_error}. "
                "Please compress your video manually to under 100MB and try again."
            )
        
        # Apply compression metadata if it exists
        if hasattr(self, '_compression_info'):
            self.instance.was_compressed = self._compression_info['was_compressed']
            self.instance.original_size_mb = self._compression_info['original_size_mb']
            self.instance.compressed_size_mb = self._compression_info['compressed_size_mb']
        
        return video

class ProjectVideoInline(admin.TabularInline):
    model = ProjectVideo
    form = ProjectVideoForm
    extra = 0  # No empty forms - use batch upload button instead
    fields = ('video_preview', 'video', 'compression_quality', 'caption', 'order')
    readonly_fields = ('created_at', 'video_preview')
    min_num = 0
    validate_min = False
    can_delete = True
    show_change_link = True

    def video_preview(self, obj):
        if obj.video:
            return format_html(
                '<video src="{}" style="max-width: 150px; max-height: 100px; border-radius: 4px;" controls></video>',
                obj.video.url
            )
        return "No video"
    video_preview.short_description = 'Preview'

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
    list_display = ('project', 'display_video', 'caption', 'order', 'compression_info', 'created_at')
    list_filter = ('project', 'was_compressed', 'compression_quality')
    search_fields = ('caption', 'project__name')
    readonly_fields = ('was_compressed', 'original_size_mb', 'compressed_size_mb', 'created_at')
    
    # Show compression_quality field in the form
    fields = ('project', 'video', 'compression_quality', 'caption', 'order', 'created_at', 'was_compressed', 'original_size_mb', 'compressed_size_mb')
    
    def display_video(self, obj):
        if obj.video:
            return format_html(
                '<video width="150" height="100" controls preload="metadata"><source src="{}" type="video/mp4">Your browser does not support video.</video>', 
                obj.video.url
            )
        return "No video"
    display_video.short_description = 'Video Preview'
    
    def compression_info(self, obj):
        if obj.was_compressed:
            # Format the numbers first as strings, then use format_html
            original = float(obj.original_size_mb) if obj.original_size_mb else 0.0
            compressed = float(obj.compressed_size_mb) if obj.compressed_size_mb else 0.0
            size_text = f"{original:.1f}MB → {compressed:.1f}MB"
            return format_html(
                '<span style="color: green;">✓ Compressed</span><br>'
                '<small>{}</small>',
                size_text
            )
        return format_html('<span style="color: gray;">No compression needed</span>')
    compression_info.short_description = 'Compression'

@admin.register(ProjectEmbed)
class ProjectEmbedAdmin(admin.ModelAdmin):
    pass

@admin.register(Projects)
class ProjectsAdmin(admin.ModelAdmin):
    form = ProjectsForm
    list_display = ('name', 'category', 'year', 'created_at', 'featured')
    list_editable = ('featured',)
    list_filter = ('category', 'year')
    search_fields = ('name', 'description')
    inlines = [ProjectPhotoInline, ProjectVideoInline, ProjectEmbedInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'category', 'year', 'technologies', 'featured')
        }),
        ('Thumbnail', {
            'fields': ('thumbnail_image',)
        }),
    )
    
    class Media:
        css = {
            'all': ('admin/css/video_embed.css',)
        }
        js = ('admin/js/video_embed.js',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
