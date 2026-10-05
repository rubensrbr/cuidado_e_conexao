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
