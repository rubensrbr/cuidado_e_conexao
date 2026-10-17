from django.contrib import admin

from .models import Clinica


@admin.register(Clinica)
class ClinicaAdmin(admin.ModelAdmin):
    list_display = ("nome", "cnpj_formatado", "slug", "email", "ativa", "created_at")
    list_filter = ("ativa",)
    search_fields = ("nome", "razao_social", "cnpj", "slug")
    prepopulated_fields = {"slug": ("nome",)}
    readonly_fields = ("uuid", "created_at", "modified_at")
    fieldsets = (
        ("Identificação", {"fields": ("nome", "razao_social", "cnpj", "slug")}),
        ("Contato", {"fields": ("email",)}),
        ("Situação", {"fields": ("ativa",)}),
        ("Registro", {"fields": ("uuid", "created_at", "modified_at")}),
    )

    @admin.display(description="CNPJ")
    def cnpj_formatado(self, obj):
        return obj.cnpj_formatado
