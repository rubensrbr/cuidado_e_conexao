from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("/", include("core.urls")),
    path("admin/", admin.site.urls),
    path("consultas/", include("consultas.urls")),
    path("faturamentos/", include("faturamentos.urls")),
    path("pacientes/", include("pacientes.urls")),
    path("profissionais/", include("profissionais.urls")),
    path("salas/", include("salas.urls")),
    path("enderecos/", include("enderecos.urls")),
    path("telefones/", include("telefones.urls")),
]
