from django.urls import path

from . import views

app_name = "localidades"

urlpatterns = [
    path("cidades/", views.cidades_por_estado, name="cidades"),
]
