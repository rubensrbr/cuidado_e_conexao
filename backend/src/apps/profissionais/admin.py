from django.contrib import admin

from .forms import DisponibilidadeForm, ProfissionalForm, TipoProfissionalForm
from .models import Disponibilidade, Profissional, TipoProfissional


class DisponibilidadeInline(admin.TabularInline):
    model = Disponibilidade
    form = DisponibilidadeForm
    extra = 0
    fields = ("dia_semana", "hora_inicio", "hora_fim", "recorrente")


@admin.register(TipoProfissional)
class TipoProfissionalAdmin(admin.ModelAdmin):
    form = TipoProfissionalForm
    list_display = ("descricao",)
    search_fields = ("descricao",)


@admin.register(Profissional)
class ProfissionalAdmin(admin.ModelAdmin):
    form = ProfissionalForm
    list_display = (
        "nome_completo",
        "tipo_profissional",
        "numero_registro",
        "email",
        "valor_hora",
        "ativo",
    )
    list_filter = ("ativo", "tipo_profissional")
    search_fields = ("primeiro_nome", "sobrenome", "email", "numero_registro")
    ordering = ("sobrenome", "primeiro_nome")
    autocomplete_fields = ("telefones",)
    readonly_fields = ("uuid", "created_at", "modified_at")
    inlines = [DisponibilidadeInline]
    fieldsets = (
        (
            "Dados pessoais",
            {"fields": ("primeiro_nome", "sobrenome", "email", "telefones", "ativo")},
        ),
        (
            "Dados profissionais",
            {
                "fields": (
                    "tipo_profissional",
                    "numero_registro",
                    "especializacao",
                    "titulacao",
                    "valor_hora",
                )
            },
        ),
        (
            "Metadados",
            {"fields": ("uuid", "created_at", "modified_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Disponibilidade)
class DisponibilidadeAdmin(admin.ModelAdmin):
    form = DisponibilidadeForm
    list_display = (
        "profissional",
        "dia_semana",
        "hora_inicio",
        "hora_fim",
        "recorrente",
    )
    list_filter = ("dia_semana", "recorrente")
    search_fields = ("profissional__primeiro_nome", "profissional__sobrenome")
    autocomplete_fields = ("profissional",)
    readonly_fields = ("uuid", "created_at", "modified_at")
