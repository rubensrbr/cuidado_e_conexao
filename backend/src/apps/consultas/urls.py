from django.urls import path
from . import views

app_name = "consultas"

urlpatterns = [
    # Consulta URLs
    path(
        "",
        views.ConsultaListView.as_view(),
        name="consulta_list",
    ),
    path(
        "nova/",
        views.ConsultaCreateView.as_view(),
        name="consulta_create",
    ),
    path(
        "<uuid:uuid>/",
        views.ConsultaDetailView.as_view(),
        name="consulta_detail",
    ),
    path(
        "<uuid:uuid>/editar/",
        views.ConsultaUpdateView.as_view(),
        name="consulta_update",
    ),
    path(
        "<uuid:uuid>/deletar/",
        views.ConsultaDeleteView.as_view(),
        name="consulta_delete",
    ),
    # Lembrete URLs
    path(
        "lembretes/",
        views.LembreteListView.as_view(),
        name="lembrete_list",
    ),
    path(
        "lembretes/novo/",
        views.LembreteCreateView.as_view(),
        name="lembrete_create",
    ),
    # ListaEspera URLs
    path(
        "lista-espera/",
        views.ListaEsperaListView.as_view(),
        name="lista_espera_list",
    ),
    path(
        "lista-espera/nova/",
        views.ListaEsperaCreateView.as_view(),
        name="lista_espera_create",
    ),
    path(
        "lista-espera/<uuid:uuid>/editar/",
        views.ListaEsperaUpdateView.as_view(),
        name="lista_espera_update",
    ),
]

from django.urls import path
from . import views

app_name = "pacientes"

urlpatterns = [
    # Paciente URLs
    path("", views.PacienteListView.as_view(), name="paciente_list"),
    path("novo/", views.PacienteCreateView.as_view(), name="paciente_create"),
    path("<uuid:uuid>/", views.PacienteDetailView.as_view(), name="paciente_detail"),
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
