from django.contrib import admin

from .forms import FaturamentoForm
from .models import Faturamento


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
    )
    list_filter = ("status_pagamento", "metodo_pagamento", "data_servico")
    search_fields = (
        "paciente__primeiro_nome",
        "paciente__sobrenome",
        "numero_nota",
    )
    date_hierarchy = "data_servico"
    ordering = ("-data_servico",)
    autocomplete_fields = ("paciente", "consulta")
    readonly_fields = ("uuid", "created_at", "modified_at")

    @admin.display(description="Valor Pendente")
    def valor_pendente(self, obj):
        return obj.valor_pendente
