"""
Filtros da lista de profissionais (django-filter).

Os filtros são opcionais e se combinam com "E": cada um só reduz o resultado.
O manager de `Profissional` já respeita a clínica atual, então uma clínica nunca
vê profissionais de outra. As especialidades (`TipoProfissional`) são globais.

    ProfissionalFilter(request.GET, queryset=Profissional.objects.all(), request=request)
"""

import django_filters
from django import forms
from django.db.models import Q

from .models import Profissional, TipoProfissional


class ProfissionalFilter(django_filters.FilterSet):
    busca = django_filters.CharFilter(
        label="Buscar",
        method="filtrar_busca",
        max_length=100,
        widget=forms.TextInput(
            attrs={"placeholder": "Nome, sobrenome, e-mail ou registro"}
        ),
    )
    tipo = django_filters.ModelChoiceFilter(
        label="Especialidade",
        field_name="tipo_profissional",
        queryset=TipoProfissional.objects.order_by("descricao"),
        empty_label="Todas",
    )
    status = django_filters.ChoiceFilter(
        label="Situação",
        method="filtrar_status",
        choices=[("ativo", "Ativos"), ("inativo", "Inativos")],
        empty_label="Todos",
    )

    class Meta:
        model = Profissional
        fields = []  # todos os filtros estão declarados acima

    # --- Filtros com regra própria -------------------------------------------

    def filtrar_busca(self, queryset, name, value):
        # Cada palavra precisa aparecer em algum campo: "ana lima" acha Ana Lima
        # mesmo que nome e sobrenome estejam em colunas diferentes.
        for termo in value.split():
            queryset = queryset.filter(
                Q(primeiro_nome__icontains=termo)
                | Q(sobrenome__icontains=termo)
                | Q(email__icontains=termo)
                | Q(numero_registro__icontains=termo)
            )
        return queryset

    def filtrar_status(self, queryset, name, value):
        return queryset.filter(ativo=(value == "ativo"))
