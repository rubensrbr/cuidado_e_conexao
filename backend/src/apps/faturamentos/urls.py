from django.urls import path
from . import views

app_name = "faturamentos"

urlpatterns = [
    path(
        "",
        views.FaturamentoListView.as_view(),
        name="faturamento_list",
    ),
    path(
        "novo/",
        views.FaturamentoCreateView.as_view(),
        name="faturamento_create",
    ),
    path(
        "<uuid:uuid>/",
        views.FaturamentoDetailView.as_view(),
        name="faturamento_detail",
    ),
    path(
        "<uuid:uuid>/editar/",
        views.FaturamentoUpdateView.as_view(),
        name="faturamento_update",
    ),
    path(
        "<uuid:uuid>/deletar/",
        views.FaturamentoDeleteView.as_view(),
        name="faturamento_delete",
    ),
    # Pacotes de sessões
    path(
        "pacotes/",
        views.PacoteListView.as_view(),
        name="pacote_list",
    ),
    path(
        "pacotes/novo/",
        views.PacoteCreateView.as_view(),
        name="pacote_create",
    ),
    path(
        "pacotes/<uuid:uuid>/",
        views.PacoteDetailView.as_view(),
        name="pacote_detail",
    ),
    path(
        "pacotes/<uuid:uuid>/editar/",
        views.PacoteUpdateView.as_view(),
        name="pacote_update",
    ),
    path(
        "pacotes/<uuid:uuid>/deletar/",
        views.PacoteDeleteView.as_view(),
        name="pacote_delete",
    ),
    # Consultas vinculadas a um pacote (o uuid de "nova" é o do PACOTE; o de
    # "deletar" é o da própria sessão).
    path(
        "pacotes/<uuid:uuid>/sessoes/nova/",
        views.SessaoPacoteCreateView.as_view(),
        name="sessaopacote_create",
    ),
    path(
        "sessoes/<uuid:uuid>/deletar/",
        views.SessaoPacoteDeleteView.as_view(),
        name="sessaopacote_delete",
    ),
]
