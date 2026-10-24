from django.apps import apps
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("", include("core.urls")),
    path("admin/", admin.site.urls),
    path("consultas/", include("consultas.urls")),
    path("pacientes/", include("pacientes.urls")),
    path("profissionais/", include("profissionais.urls")),
    path("localidades/", include("localidades.urls")),
]

# Apps opcionais: só registram URLs quando estão em INSTALLED_APPS.
if apps.is_installed("faturamentos"):
    urlpatterns.append(path("faturamentos/", include("faturamentos.urls")))
if apps.is_installed("salas"):
    urlpatterns.append(path("salas/", include("salas.urls")))
