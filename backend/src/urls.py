from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("consultas/", include("consultas.urls")),
    path("faturamentos/", include("faturamentos.urls")),
    path("pacientes/", include("pacientes.urls")),
    path("profissionais/", include("profissionais.urls")),
    path("salas/", include("salas.urls")),
    path("enderecos/", include("salas.urls")),
    path("telefones/", include("salas.urls")),
]
