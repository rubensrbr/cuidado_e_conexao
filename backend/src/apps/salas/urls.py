from django.urls import path
from . import views

app_name = "salas"

urlpatterns = [
    # Sala URLs
    path("", views.SalaListView.as_view(), name="sala_list"),
    path("nova/", views.SalaCreateView.as_view(), name="sala_create"),
    path("<uuid:uuid>/editar/", views.SalaUpdateView.as_view(), name="sala_update"),
    # AgendaSala URLs
    path("agenda/", views.AgendaSalaListView.as_view(), name="agendasala_list"),
    path(
        "agenda/nova/", views.AgendaSalaCreateView.as_view(), name="agendasala_create"
    ),
    path(
        "agenda/<uuid:uuid>/editar/",
        views.AgendaSalaUpdateView.as_view(),
        name="agendasala_update",
    ),
]
