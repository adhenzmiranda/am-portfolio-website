"""
URL configuration for projects project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from projects import views
from projects import compression_views
from rest_framework.urlpatterns import format_suffix_patterns

urlpatterns = [
    path('admin/', admin.site.urls),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    
    # Compression progress endpoints
    path('admin/compression-progress/<str:task_id>/', compression_views.compression_progress, name='compression_progress'),
    path('admin/cancel-compression/<str:task_id>/', compression_views.cancel_compression, name='cancel_compression'),
    path('admin/get-latest-task/', compression_views.get_latest_task, name='get_latest_task'),
    
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('projects/', views.projects_page, name='projects_page'),
    path('projects/<int:id>/', views.project_detail_page, name='project_detail'),
    # API endpoints
    path('api/projects/', views.projects_list),
    path('api/projects/<int:id>', views.projects_detail),
]

# Serve static files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

urlpatterns = format_suffix_patterns(urlpatterns)
