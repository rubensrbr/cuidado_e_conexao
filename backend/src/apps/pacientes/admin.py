from django.contrib import admin

from .forms import PacienteForm, ProntuarioForm
from .models import Paciente, Prontuario


class ProntuarioInline(admin.TabularInline):
    model = Prontuario
    form = ProntuarioForm
    extra = 0
    fields = ("data_registro", "profissional", "codigo_cid", "consulta")
    show_change_link = True


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    form = PacienteForm
    list_display = (
        "nome_completo",
        "data_nascimento",
        "genero",
        "email",
        "convenio",
        "ativo",
    )
    list_filter = ("ativo", "genero", "convenio")
    search_fields = (
        "primeiro_nome",
        "sobrenome",
        "email",
        "numero_carteirinha",
    )
    ordering = ("sobrenome", "primeiro_nome")
    autocomplete_fields = ("enderecos", "telefones")
    readonly_fields = ("uuid", "created_at", "modified_at")
    inlines = [ProntuarioInline]
    fieldsets = (
        (
            "Dados pessoais",
            {
                "fields": (
                    "primeiro_nome",
                    "sobrenome",
                    "data_nascimento",
                    "genero",
                    "email",
                    "ativo",
                )
            },
        ),
        ("Contato", {"fields": ("enderecos", "telefones")}),
        (
            "Contato de emergência",
            {"fields": ("contato_emergencia_nome", "contato_emergencia_telefone")},
        ),
        ("Convênio", {"fields": ("convenio", "numero_carteirinha")}),
        (
            "Metadados",
            {"fields": ("uuid", "created_at", "modified_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Prontuario)
class ProntuarioAdmin(admin.ModelAdmin):
    form = ProntuarioForm
    list_display = ("paciente", "profissional", "data_registro", "codigo_cid")
    list_filter = ("data_registro", "profissional")
    search_fields = (
        "paciente__primeiro_nome",
        "paciente__sobrenome",
        "codigo_cid",
    )
    ordering = ("-data_registro",)
    autocomplete_fields = ("paciente", "profissional", "consulta")
    readonly_fields = ("uuid", "created_at", "modified_at")
