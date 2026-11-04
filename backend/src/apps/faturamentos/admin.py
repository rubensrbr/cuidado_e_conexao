from django.contrib import admin

from .forms import FaturamentoForm, PacoteForm, SessaoPacoteForm
from .models import Faturamento, Pacote, SessaoPacote


@admin.register(Faturamento)
class FaturamentoAdmin(admin.ModelAdmin):
    form = FaturamentoForm
    list_display = (
        "paciente",
        "data_servico",
        "valor_cobrado",
        "valor_pago",
        "valor_pendente",
        "status_pagamento",
        "metodo_pagamento",
        "pro_bono",
        "pacote",
    )
    list_filter = ("status_pagamento", "metodo_pagamento", "pro_bono", "data_servico")
    search_fields = (
        "paciente__primeiro_nome",
        "paciente__sobrenome",
        "numero_nota",
    )
    date_hierarchy = "data_servico"
    ordering = ("-data_servico",)
    autocomplete_fields = ("paciente", "consulta", "pacote")
    readonly_fields = ("uuid", "created_at", "modified_at")

    @admin.display(description="Valor Pendente")
    def valor_pendente(self, obj):
        return obj.valor_pendente


class SessaoPacoteInline(admin.TabularInline):
    model = SessaoPacote
    form = SessaoPacoteForm
    extra = 0
    fields = ("consulta",)
    autocomplete_fields = ("consulta",)


@admin.register(Pacote)
class PacoteAdmin(admin.ModelAdmin):
    form = PacoteForm
    list_display = (
        "paciente",
        "quantidade_sessoes",
        "sessoes_usadas",
        "saldo",
        "valor_total",
        "data_compra",
        "validade",
        "status",
    )
    list_filter = ("status", "data_compra")
    search_fields = ("paciente__primeiro_nome", "paciente__sobrenome")
    date_hierarchy = "data_compra"
    autocomplete_fields = ("paciente", "profissional")
    readonly_fields = ("uuid", "created_at", "modified_at")
    inlines = [SessaoPacoteInline]
