"""
Filtros da lista de consultas (django-filter).

Os filtros são opcionais e se combinam com "E": cada um só reduz o resultado.
O manager de `Consulta` (e o de `Profissional`, usado nas opções) já respeita a
clínica atual, então uma clínica nunca vê dados de outra.

    ConsultaFilter(request.GET, queryset=Consulta.objects.all(), request=request)
"""

import django_filters
from django import forms
from django.db.models import Q

from profissionais.models import Profissional

from .models import Consulta


def profissionais_da_clinica(request):
    # Chamado a cada requisição; o manager já filtra pela clínica atual.
    # `select_related` porque o __str__ do profissional mostra o tipo.
    return Profissional.objects.select_related("tipo_profissional")


def campo_de_data(label, lookup_expr):
    return django_filters.DateFilter(
        label=label,
        field_name="data_consulta",
        lookup_expr=lookup_expr,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )


class FiltroConsultaForm(forms.Form):
    """Formulário dos filtros, com a validação que envolve mais de um campo."""

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("data_de"), dados.get("data_ate")
        if inicio and fim and inicio > fim:
            self.add_error("data_ate", "A data final não pode ser anterior à inicial.")
        return dados


class ConsultaFilter(django_filters.FilterSet):
    busca = django_filters.CharFilter(
        label="Buscar",
        method="filtrar_busca",
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Paciente ou profissional"}),
    )
    status = django_filters.ChoiceFilter(
        label="Status",
        choices=Consulta.STATUS_CHOICES,
        empty_label="Todos",
    )
    tipo = django_filters.ChoiceFilter(
        label="Tipo",
        field_name="tipo_consulta",
        choices=Consulta.TIPO_CHOICES,
        empty_label="Todos",
    )
    profissional = django_filters.ModelChoiceFilter(
        label="Profissional",
        queryset=profissionais_da_clinica,
        empty_label="Todos",
    )
    data_de = campo_de_data("Data de", "gte")
    data_ate = campo_de_data("Data até", "lte")

    class Meta:
        model = Consulta
        fields = []  # todos os filtros estão declarados acima
        form = FiltroConsultaForm

    # --- Filtros com regra própria -------------------------------------------

    def filtrar_busca(self, queryset, name, value):
        # Cada palavra precisa aparecer no nome do paciente ou do profissional:
        # "ana silva" acha Ana Silva mesmo com nome e sobrenome em colunas diferentes.
        for termo in value.split():
            queryset = queryset.filter(
                Q(paciente__primeiro_nome__icontains=termo)
                | Q(paciente__sobrenome__icontains=termo)
                | Q(profissional__primeiro_nome__icontains=termo)
                | Q(profissional__sobrenome__icontains=termo)
            )
        return queryset
