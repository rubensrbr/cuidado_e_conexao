from django.urls import path
from . import views

app_name = "pacientes"

urlpatterns = [
    # Paciente URLs
    path(
        "",
        views.PacienteListView.as_view(),
        name="paciente_list",
    ),
    path(
        "novo/",
        views.PacienteCreateView.as_view(),
        name="paciente_create",
    ),
    path(
        "<uuid:uuid>/",
        views.PacienteDetailView.as_view(),
        name="paciente_detail",
    ),
    path(
        "<uuid:uuid>/editar/",
        views.PacienteUpdateView.as_view(),
        name="paciente_update",
    ),
    path(
        "<uuid:uuid>/deletar/",
        views.PacienteDeleteView.as_view(),
        name="paciente_delete",
    ),
    # Prontuario URLs
    path(
        "prontuarios/novo/",
        views.ProntuarioCreateView.as_view(),
        name="prontuario_create",
    ),
    path(
        "prontuarios/<uuid:uuid>/",
        views.ProntuarioDetailView.as_view(),
        name="prontuario_detail",
    ),
]
