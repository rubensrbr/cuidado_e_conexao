from django.urls import path
from . import views

app_name = "profissionais"

urlpatterns = [
    # Profissional URLs
    path("", views.ProfissionalListView.as_view(), name="profissional_list"),
    path("novo/", views.ProfissionalCreateView.as_view(), name="profissional_create"),
    path(
        "<uuid:uuid>/",
        views.ProfissionalDetailView.as_view(),
        name="profissional_detail",
    ),
    path(
        "<uuid:uuid>/editar/",
        views.ProfissionalUpdateView.as_view(),
        name="profissional_update",
    ),
    path(
        "<uuid:uuid>/deletar/",
        views.ProfissionalDeleteView.as_view(),
        name="profissional_delete",
    ),
    # Disponibilidade URLs
    path(
        "disponibilidade/nova/",
        views.DisponibilidadeCreateView.as_view(),
        name="disponibilidade_create",
    ),
]
