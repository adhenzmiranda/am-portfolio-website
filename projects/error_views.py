from django.shortcuts import render

def custom_404(request, exception):
    return render(request, '404.html', status=404)

def custom_500(request):
    return render(request, '500.html', status=500)

def custom_403(request, exception):
    return render(request, '403.html', status=403)


def preview_error(request, code):
    """Development only: show an error page as visitors would see it.

    With DEBUG on, Django shows its own debug page instead of these templates, so
    this view (wired up in urls.py only when DEBUG is on) renders them directly,
    e.g. /preview-error/404/.
    """
    return render(request, f'{code}.html', status=code)
