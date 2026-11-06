import html
import json
import urllib.parse
import urllib.request
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.html import strip_tags
from django.utils.text import Truncator
from markdownify.templatetags.markdownify import markdownify
from django.core.mail import EmailMessage
from django.contrib import messages
from django.conf import settings
import logging
from django.db.models import Count
from .models import Category, Projects, Experience, Education
from .serializer import ProjectsSerializer
from .forms import ContactForm
from .seo import home_json_ld, project_json_ld
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django_ratelimit.decorators import ratelimit

logger = logging.getLogger(__name__)

def client_ip(group, request):
    """
    Real visitor IP behind Heroku's router and Cloudflare. CF-Connecting-IP
    is only trustworthy for traffic that actually passed through Cloudflare,
    which the herokuapp.com -> custom domain redirect enforces.
    """
    return (
        request.META.get('HTTP_CF_CONNECTING_IP')
        or request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR')
    )

TURNSTILE_VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'


def turnstile_passed(request):
    """Check the Cloudflare Turnstile token. Always passes when Turnstile isn't
    configured (no TURNSTILE_SECRET_KEY), so the form works without it."""
    if not settings.TURNSTILE_SECRET_KEY:
        return True
    token = request.POST.get('cf-turnstile-response', '')
    if not token:
        return False
    data = urllib.parse.urlencode({
        'secret': settings.TURNSTILE_SECRET_KEY,
        'response': token,
        'remoteip': client_ip(None, request) or '',
    }).encode()
    try:
        with urllib.request.urlopen(TURNSTILE_VERIFY_URL, data=data, timeout=5) as resp:
            return bool(json.load(resp).get('success'))
    except Exception:
        logger.exception('Turnstile verification request failed')
        return False

def home(request):
    # Featured projects for the home grid, newest first
    featured_projects = Projects.objects.filter(featured=True).select_related('category').order_by('-year', '-created_at')
    return render(request, 'index.html', {
        "featured_projects": featured_projects,
        "json_ld": home_json_ld(),
    })

def about(request):
    return render(request, 'about.html', {
        'experiences': Experience.objects.filter(visible=True),
        'education': Education.objects.filter(visible=True),
    })

@ratelimit(key=client_ip, rate='5/h', method='POST', block=True)
def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid() and form.is_expired():
            messages.error(request, 'This page was open too long. Please send your message again.')
            form = ContactForm(initial={k: form.cleaned_data[k] for k in ('name', 'email', 'subject', 'message')})
        elif form.is_valid() and form.spam_reason():
            # Pretend it worked so bots don't learn to adapt; nothing is emailed.
            logger.warning('Contact form spam blocked (%s) from %s', form.spam_reason(), client_ip(None, request))
            messages.success(request, 'Thank you for your message! I will get back to you soon.')
            return redirect('contact')
        elif form.is_valid() and not turnstile_passed(request):
            logger.warning('Contact form failed Turnstile from %s', client_ip(None, request))
            messages.error(request, 'Please complete the security check and try again.')
        elif form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            # Send email from our own address; the visitor's email goes in
            # Reply-To so replying still reaches them, without letting
            # visitors spoof the From header (which Gmail would reject anyway).
            email_message = f'From: {name}\nEmail: {email}\n\nMessage:\n{message}'
            try:
                EmailMessage(
                    subject=f'[Portfolio] {subject}',
                    body=email_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[settings.EMAIL_HOST_USER],
                    reply_to=[email],
                ).send(fail_silently=False)
                messages.success(request, 'Thank you for your message! I will get back to you soon.')
                return redirect('contact')
            except Exception:
                # Shows up in `heroku logs` so failures (e.g. a revoked Gmail
                # App Password) can be diagnosed; the visitor sees a generic message.
                logger.exception('Contact form email failed to send')
                messages.error(request, 'An error occurred while sending your message. Please try again later.')
    else:
        form = ContactForm()
    return render(request, 'contact.html', {'form': form, 'turnstile_site_key': settings.TURNSTILE_SITE_KEY})

def projects_page(request):
    """All projects, grouped by year (newest year first, newest project first within a year)."""
    projects = Projects.objects.select_related('category').order_by('-year', '-created_at')
    year_groups = []
    for project in projects:
        if not year_groups or year_groups[-1]['year'] != project.year:
            year_groups.append({'year': project.year, 'projects': []})
        year_groups[-1]['projects'].append(project)
    # Categories that have at least one project, for the filter row (count shown on each button).
    categories = Category.objects.annotate(project_total=Count('projects')).filter(project_total__gt=0).order_by('name')
    return render(request, 'projects.html', {
        'year_groups': year_groups,
        'project_count': len(projects),
        'categories': categories,
    })

def plain_text_summary(markdown_text, length=155):
    """Render markdown, strip the HTML and collapse whitespace for meta tags."""
    text = html.unescape(strip_tags(markdownify(markdown_text or '')))
    return Truncator(' '.join(text.split())).chars(length)

def project_detail_page(request, id):
    project = get_object_or_404(Projects, id=id)
    meta_description = plain_text_summary(project.description)
    context = {
        'project': project,
        'meta_description': meta_description,
        'json_ld': project_json_ld(project, meta_description),
    }
    return render(request, 'project_detail.html', context)

def indexnow_key(request, key):
    """Serves the IndexNow key at /<key>.txt so Bing can verify the site owns it."""
    if not settings.INDEXNOW_KEY or key != settings.INDEXNOW_KEY:
        raise Http404
    return HttpResponse(key, content_type='text/plain; charset=utf-8')

def llms_txt(request):
    """Plain-text summary of the site for AI tools (llmstxt.org), built from the featured projects."""
    featured = [
        (project, plain_text_summary(project.description, 150))
        for project in Projects.objects.filter(featured=True).order_by('-year', 'id')
    ]
    return render(request, 'llms.txt', {'featured': featured}, content_type='text/plain; charset=utf-8')

@api_view(['GET'])
def projects_list(request, format=None):
    projects = Projects.objects.all()
    serializer = ProjectsSerializer(projects, many=True, context={'request': request})
    return JsonResponse({'projects': serializer.data})

@api_view(['GET'])
def projects_detail(request, id, format=None):
    try:
        project = Projects.objects.get(pk=id)
    except Projects.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    serializer = ProjectsSerializer(project, context={'request': request})
    return Response(serializer.data)

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