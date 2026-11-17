"""Studio pages. Each one is only a shell: its script loads the data from studio/api.py."""
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from projects.models import Projects

from .access import studio_page


def _context(page, **extra):
    return {'page': page, 'script': f'studio/{page}.js', 'admin_url': reverse('admin:index'), **extra}


@studio_page
@require_GET
def dashboard(request):
    return render(request, 'studio/page.html', _context('dashboard', title='Dashboard'))


@studio_page
@require_GET
def projects(request):
    return render(request, 'studio/page.html', _context('projects', title='Projects'))


@studio_page
@require_GET
def about(request):
    return render(request, 'studio/page.html', _context('about', title='About page'))


@studio_page
@require_GET
def project(request, pk):
    item = get_object_or_404(Projects, pk=pk)
    return render(request, 'studio/page.html', _context('project', title=item.name, project_id=item.pk))
