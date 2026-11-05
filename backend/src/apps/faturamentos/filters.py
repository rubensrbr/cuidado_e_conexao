"""
Filtros da lista de faturamentos (django-filter).

Os filtros são opcionais e se combinam com "E": cada um só reduz o resultado.
O manager de `Faturamento` já respeita a clínica atual, então uma clínica nunca
vê dados de outra.

    FaturamentoFilter(request.GET, queryset=Faturamento.objects.all(), request=request)
"""

import django_filters
from django import forms
from django.db.models import Q

from .models import Faturamento


def campo_de_data(label, lookup_expr):
    return django_filters.DateFilter(
        label=label,
        field_name="data_servico",
        lookup_expr=lookup_expr,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )


class FiltroFaturamentoForm(forms.Form):
    """Formulário dos filtros, com a validação que envolve mais de um campo."""

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("data_de"), dados.get("data_ate")
        if inicio and fim and inicio > fim:
            self.add_error("data_ate", "A data final não pode ser anterior à inicial.")
        return dados


class FaturamentoFilter(django_filters.FilterSet):
    busca = django_filters.CharFilter(
        label="Paciente",
        method="filtrar_busca",
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Nome do paciente"}),
    )
    status = django_filters.ChoiceFilter(
        label="Status",
        field_name="status_pagamento",
        choices=Faturamento.STATUS_CHOICES,
        empty_label="Todos",
    )
    data_de = campo_de_data("Data do serviço de", "gte")
    data_ate = campo_de_data("Data do serviço até", "lte")

    class Meta:
        model = Faturamento
        fields = []  # todos os filtros estão declarados acima
        form = FiltroFaturamentoForm

    # --- Filtros com regra própria -------------------------------------------

    def filtrar_busca(self, queryset, name, value):
        # Cada palavra precisa aparecer no nome ou no sobrenome do paciente:
        # "ana silva" acha Ana Silva mesmo com nome e sobrenome em colunas diferentes.
        for termo in value.split():
            queryset = queryset.filter(
                Q(paciente__primeiro_nome__icontains=termo)
                | Q(paciente__sobrenome__icontains=termo)
            )
        return queryset


class FaturamentoResumoFilter(django_filters.FilterSet):
    """Filtro da aba Resumo: só o período (o status é justamente o que se resume)."""

    data_de = campo_de_data("Data do serviço de", "gte")
    data_ate = campo_de_data("Data do serviço até", "lte")

    class Meta:
        model = Faturamento
        fields = []
        form = FiltroFaturamentoForm
