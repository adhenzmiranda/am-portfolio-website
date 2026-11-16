from django.urls import path

from . import views

app_name = 'survey'

# Included last in projects/urls.py, so every existing page wins over a survey address.
urlpatterns = [
    path('<slug:slug>/', views.survey_page, name='page'),
    path('<slug:slug>/start/', views.start, name='start'),
    path('<slug:slug>/submit/', views.submit, name='submit'),
]
