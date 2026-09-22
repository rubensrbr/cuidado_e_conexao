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
]
