"""Studio pages. Each one is only a shell: its script loads the data from studio/api.py
(the survey editor's from survey/editor.py)."""
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from projects.models import Projects
from survey.models import Survey

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
def survey(request):
    """Studio's Survey tab: the editor of the survey that's open, else the newest draft
    (e.g. a new version being prepared), else the newest one."""
    surveys = Survey.objects.order_by('-created_at')
    current = (surveys.filter(status=Survey.OPEN).first() or surveys.filter(status=Survey.DRAFT).first()
               or surveys.first())
    if not current:
        return redirect('admin:survey_survey_changelist')
    return redirect(reverse('survey:editor', args=[current.slug]))


@studio_page
@require_GET
def project(request, pk):
    item = get_object_or_404(Projects, pk=pk)
    return render(request, 'studio/page.html', _context('project', title=item.name, project_id=item.pk))
