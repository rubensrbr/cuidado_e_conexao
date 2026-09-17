from django.contrib import admin

from .forms import ConsultaForm, LembreteForm, ListaEsperaForm
from .models import Consulta, Lembrete, ListaEspera


class LembreteInline(admin.TabularInline):
    model = Lembrete
    form = LembreteForm
    extra = 0
    fields = ("tipo_lembrete", "data_hora_envio", "status")


@admin.register(Consulta)
class ConsultaAdmin(admin.ModelAdmin):
    form = ConsultaForm
    list_display = (
        "paciente",
        "profissional",
        "data_consulta",
        "hora_inicio",
        "hora_fim",
        "tipo_consulta",
        "status",
    )
    list_filter = ("status", "tipo_consulta", "data_consulta", "profissional")
    search_fields = (
        "paciente__primeiro_nome",
        "paciente__sobrenome",
        "profissional__primeiro_nome",
        "profissional__sobrenome",
    )
    date_hierarchy = "data_consulta"
    ordering = ("-data_consulta", "-hora_inicio")
    autocomplete_fields = ("paciente", "profissional")
    readonly_fields = ("uuid", "created_at", "modified_at")
    inlines = [LembreteInline]


@admin.register(Lembrete)
class LembreteAdmin(admin.ModelAdmin):
    form = LembreteForm
    list_display = ("consulta", "tipo_lembrete", "data_hora_envio", "status")
    list_filter = ("tipo_lembrete", "status")
    search_fields = (
        "consulta__paciente__primeiro_nome",
        "consulta__paciente__sobrenome",
    )
    autocomplete_fields = ("consulta",)
    readonly_fields = ("uuid", "created_at", "modified_at")


@admin.register(ListaEspera)
class ListaEsperaAdmin(admin.ModelAdmin):
    form = ListaEsperaForm
    list_display = (
        "paciente",
        "profissional_preferido",
        "prioridade",
        "status",
    )
    list_filter = ("prioridade", "status")
    search_fields = ("paciente__primeiro_nome", "paciente__sobrenome")
    autocomplete_fields = ("paciente", "profissional_preferido")
    readonly_fields = ("uuid", "created_at", "modified_at")
