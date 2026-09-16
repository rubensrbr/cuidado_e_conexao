from django.contrib import admin

from .forms import AgendaSalaForm, SalaForm
from .models import AgendaSala, Sala


class AgendaSalaInline(admin.TabularInline):
    model = AgendaSala
    form = AgendaSalaForm
    extra = 0
    fields = ("data", "hora_inicio", "hora_fim", "consulta")


@admin.register(Sala)
class SalaAdmin(admin.ModelAdmin):
    form = SalaForm
    list_display = ("numero_sala", "nome", "capacidade", "ativa")
    list_filter = ("ativa",)
    search_fields = ("numero_sala", "nome")
    ordering = ("numero_sala",)
    readonly_fields = ("uuid", "created_at", "modified_at")
    inlines = [AgendaSalaInline]


@admin.register(AgendaSala)
class AgendaSalaAdmin(admin.ModelAdmin):
    form = AgendaSalaForm
    list_display = ("sala", "data", "hora_inicio", "hora_fim", "consulta")
    list_filter = ("sala", "data")
    search_fields = ("sala__numero_sala", "sala__nome")
    ordering = ("-data", "hora_inicio")
    autocomplete_fields = ("consulta",)
    readonly_fields = ("uuid", "created_at", "modified_at")
