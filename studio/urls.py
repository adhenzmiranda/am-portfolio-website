from django.urls import path

from . import api, views

app_name = 'studio'

urlpatterns = [
    # Pages (shells; each loads its data from the API)
    path('', views.dashboard, name='dashboard'),
    path('projects/', views.projects, name='projects'),
    path('projects/<int:pk>/', views.project, name='project'),

    # API
    path('api/dashboard/', api.dashboard, name='api_dashboard'),
    path('api/preview/', api.preview, name='api_preview'),
    path('api/categories/new/', api.category_create, name='api_category_create'),
    path('api/projects/', api.projects, name='api_projects'),
    path('api/projects/new/', api.project_create, name='api_project_create'),
    path('api/projects/<int:pk>/', api.project, name='api_project'),
    path('api/projects/<int:pk>/delete/', api.project_delete, name='api_project_delete'),
    path('api/projects/<int:pk>/upload/<str:field>/', api.project_upload, name='api_project_upload'),
    path('api/projects/<int:pk>/cards/new/', api.card_create, name='api_card_create'),
    path('api/projects/<int:pk>/cards/reorder/', api.cards_reorder, name='api_cards_reorder'),
    path('api/projects/<int:pk>/cards/import/', api.cards_import, name='api_cards_import'),
    path('api/projects/<int:pk>/cards/export/', api.cards_export, name='api_cards_export'),
    path('api/projects/<int:pk>/cards/<int:cid>/', api.card_update, name='api_card_update'),
    path('api/projects/<int:pk>/cards/<int:cid>/delete/', api.card_delete, name='api_card_delete'),
    path('api/projects/<int:pk>/cards/<int:cid>/upload/<str:field>/', api.card_upload, name='api_card_upload'),
]
