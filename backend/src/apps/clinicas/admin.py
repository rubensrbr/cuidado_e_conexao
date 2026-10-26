from django.contrib import admin

from .models import Clinica, Membro


class MembroInline(admin.TabularInline):
    model = Membro
    extra = 0
    fields = ("user", "grupo", "ativo")
    raw_id_fields = ("user",)


@admin.register(Clinica)
class ClinicaAdmin(admin.ModelAdmin):
    list_display = ("nome", "cnpj_formatado", "slug", "email", "ativa", "created_at")
    list_filter = ("ativa",)
    search_fields = ("nome", "razao_social", "cnpj", "slug")
    prepopulated_fields = {"slug": ("nome",)}
    readonly_fields = ("uuid", "created_at", "modified_at")
    inlines = [MembroInline]
    fieldsets = (
        ("Identificação", {"fields": ("nome", "razao_social", "cnpj", "slug")}),
        ("Contato", {"fields": ("email",)}),
        ("Situação", {"fields": ("ativa",)}),
        ("Registro", {"fields": ("uuid", "created_at", "modified_at")}),
    )

    @admin.display(description="CNPJ")
    def cnpj_formatado(self, obj):
        return obj.cnpj_formatado


@admin.register(Membro)
class MembroAdmin(admin.ModelAdmin):
    list_display = ("user", "clinica", "grupo", "ativo")
    list_filter = ("ativo", "clinica", "grupo")
    search_fields = ("user__email", "clinica__nome")
    raw_id_fields = ("user",)
    readonly_fields = ("uuid", "created_at", "modified_at")
