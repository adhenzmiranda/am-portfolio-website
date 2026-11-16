from django.urls import path

from . import editor, views

app_name = 'survey'

# Included last in projects/urls.py, so every existing page wins over a survey address.
urlpatterns = [
    path('<slug:slug>/', views.survey_page, name='page'),
    path('<slug:slug>/start/', views.start, name='start'),
    path('<slug:slug>/submit/', views.submit, name='submit'),

    # Editor (staff with 2FA only): the page, then its autosave API.
    path('<slug:slug>/edit/', editor.editor_page, name='editor'),
    path('<slug:slug>/edit/api/state/', editor.api_state, name='editor_state'),
    path('<slug:slug>/edit/api/reorder/', editor.api_reorder, name='editor_reorder'),
    path('<slug:slug>/edit/api/sign-video/', editor.api_sign_video, name='editor_sign_video'),
    path('<slug:slug>/edit/api/duplicate-survey/', editor.api_duplicate_survey, name='editor_duplicate_survey'),
    path('<slug:slug>/edit/api/question/<int:pk>/duplicate/', editor.api_duplicate_question, name='editor_duplicate_question'),
    path('<slug:slug>/edit/api/<str:model>/new/', editor.api_create, name='editor_create'),
    path('<slug:slug>/edit/api/<str:model>/<int:pk>/', editor.api_update, name='editor_update'),
    path('<slug:slug>/edit/api/<str:model>/<int:pk>/delete/', editor.api_delete, name='editor_delete'),
    path('<slug:slug>/edit/api/<str:model>/<int:pk>/upload/<str:field>/', editor.api_upload, name='editor_upload'),
]
