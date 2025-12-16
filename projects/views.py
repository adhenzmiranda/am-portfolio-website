from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.core.mail import send_mail
from django.contrib import messages
from .models import Projects 
from .serializer import ProjectsSerializer
from .forms import ContactForm
from rest_framework.decorators import api_view, parser_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from cloudinary.uploader import upload
from django_ratelimit.decorators import ratelimit

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

def upload_image(request):
    if request.method == 'POST' and request.FILES.get('image'):
        try:
            image = request.FILES['image']
            upload_result = upload(image, folder="uploads")
            return JsonResponse({
                'success': True,
                'url': upload_result['secure_url'],
                'public_id': upload_result['public_id']
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    return JsonResponse({
        'success': False,
        'error': 'No image provided'
    }, status=400)

def home(request):
    # Get featured projects for the hero section
    featured_projects = Projects.objects.filter(featured=True)
    return render(request, 'index.html', {"featured_projects": featured_projects})

def about(request):
    return render(request, 'about.html')

@ratelimit(key='ip', rate='5/h', method='POST', block=True)
def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            # Send email
            email_message = f'From: {name}\nEmail: {email}\n\nMessage:\n{message}'
            from django.conf import settings
            recipient_email = getattr(settings, 'EMAIL_HOST_USER', None)
            try:
                send_mail(
                    subject,
                    email_message,
                    email,  # From email
                    [recipient_email],
                    fail_silently=False,
                )
                messages.success(request, 'Thank you for your message! I will get back to you soon.')
                return redirect('contact')
            except Exception as e:
                messages.error(request, 'An error occurred while sending your message. Please try again later.')
    else:
        form = ContactForm()
    return render(request, 'contact.html', {'form': form})

def projects_page(request):
    projects = Projects.objects.all().order_by('-created_at')
    # Group projects by year
    projects_by_year = {}
    for project in projects:
        if project.year not in projects_by_year:
            projects_by_year[project.year] = []
        projects_by_year[project.year].append(project)
    
    # Sort years in descending order
    sorted_years = sorted(projects_by_year.keys(), reverse=True)
    
    context = {
        'projects_by_year': projects_by_year,
        'sorted_years': sorted_years
    }
    return render(request, 'projects.html', context)

def project_detail_page(request, id):
    project = get_object_or_404(Projects, id=id)
    context = {
        'project': project
    }
    return render(request, 'project_detail.html', context)

@api_view(['GET', 'POST'])
@parser_classes([MultiPartParser, FormParser])
def projects_list(request, format=None):
    if request.method == 'GET':
        projects = Projects.objects.all()
        serializer = ProjectsSerializer(projects, many=True, context={'request': request})
        return JsonResponse({'projects': serializer.data})
    
    if request.method == 'POST':
        serializer = ProjectsSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PUT', 'DELETE'])
@parser_classes([MultiPartParser, FormParser])
def projects_detail(request, id, format=None):
    try:
        project = Projects.objects.get(pk=id)
    except Projects.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = ProjectsSerializer(project, context={'request': request})
        return Response(serializer.data)
    elif request.method == 'PUT':
        serializer = ProjectsSerializer(project, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    elif request.method == 'DELETE':
        project.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

def project_list(request):
    """
    View for displaying all projects
    """
    projects = Projects.objects.all().order_by('-year', '-created_at')
    context = {
        'projects': projects,
    }
    return render(request, 'projects/list.html', context)

def project_detail(request, project_id):
    """
    View for displaying a single project
    """
    project = get_object_or_404(Projects, id=project_id)
    photos = project.photos.all().order_by('order')
    
    # Get optimized image URLs
    if project.image:
        project.image_url = get_optimized_url(
            project.image.public_id,
            width=1200,
            height=800,
            crop='fill'
        )
    
    for photo in photos:
        if photo.image:
            photo.image_url = get_optimized_url(
                photo.image.public_id,
                width=1200,
                height=800,
                crop='fill'
            )
    
    context = {
        'project': project,
        'photos': photos,
    }
    return render(request, 'projects/detail.html', context)