from django.urls import path
from . import views

app_name = "telefones"

urlpatterns = [
    # Telefone URLs
    path("", views.TelefoneListView.as_view(), name="telefone_list"),
    path("nova/", views.TelefoneCreateView.as_view(), name="telefone_create"),
    path(
        "<uuid:uuid>/editar/",
        views.TelefoneUpdateView.as_view(),
        name="endereco_update",
    ),
]
