from django.contrib import admin

from .forms import EnderecoForm
from .models import Endereco


@admin.register(Endereco)
class EnderecoAdmin(admin.ModelAdmin):
    form = EnderecoForm
    list_display = ("logradouro", "numero", "bairro", "cidade", "estado", "cep")
    list_filter = ("estado", "cidade")
    search_fields = ("logradouro", "bairro", "cidade", "cep")
    ordering = ("cidade", "logradouro")
    readonly_fields = ("uuid", "created_at", "modified_at")
    fieldsets = (
        (
            "Endereço",
            {
                "fields": (
                    "logradouro",
                    "numero",
                    "complemento",
                    "bairro",
                    "cidade",
                    "estado",
                    "cep",
                )
            },
        ),
        ("Metadados", {"fields": ("uuid", "created_at", "modified_at"), "classes": ("collapse",)}),
    )
