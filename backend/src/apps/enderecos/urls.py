from django.urls import path
from . import views

app_name = "enderecos"

urlpatterns = [
    # Endereco URLs
    path("", views.EnderecoListView.as_view(), name="endereco_list"),
    path("nova/", views.EnderecoCreateView.as_view(), name="endereco_create"),
    path(
        "<uuid:uuid>/editar/",
        views.EnderecoUpdateView.as_view(),
        name="endereco_update",
    ),
]
