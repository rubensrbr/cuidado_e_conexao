"""
Filtros da lista de pacientes (django-filter).

Os filtros são opcionais e se combinam com "E": cada um só reduz o resultado.
Os dados que aparecem como opção (convênios, profissionais) vêm dos managers
que já respeitam a clínica atual, então uma clínica nunca vê opções de outra.

    PacienteFilter(request.GET, queryset=Paciente.objects.all(), request=request)
"""

import django_filters
from django import forms
from django.db.models import Q
from django.utils import timezone

from profissionais.models import Profissional

from .models import Paciente


class InteiroFilter(django_filters.Filter):
    """Filtro de número inteiro (o NumberFilter do django-filter aceita decimais)."""

    field_class = forms.IntegerField


def profissionais_da_clinica(request):
    # Chamado a cada requisição; o manager já filtra pela clínica atual.
    return Profissional.objects.all()


class FiltroPacienteForm(forms.Form):
    """Formulário dos filtros, com a validação que envolve mais de um campo."""

    def clean(self):
        dados = super().clean()
        minima, maxima = dados.get("idade_min"), dados.get("idade_max")
        if minima is not None and maxima is not None and minima > maxima:
            self.add_error(
                "idade_max", "A idade máxima não pode ser menor que a mínima."
            )
        return dados


class PacienteFilter(django_filters.FilterSet):
    busca = django_filters.CharFilter(
        label="Buscar",
        method="filtrar_busca",
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Nome, sobrenome ou e-mail"}),
    )
    genero = django_filters.ChoiceFilter(
        label="Gênero",
        choices=Paciente.GENERO_CHOICES,
        empty_label="Todos",
    )
    status = django_filters.ChoiceFilter(
        label="Situação",
        method="filtrar_status",
        choices=[("ativo", "Ativos"), ("inativo", "Inativos")],
        empty_label="Todos",
    )
    profissional = django_filters.ModelChoiceFilter(
        label="Profissional",
        field_name="profissionais",
        queryset=profissionais_da_clinica,
        empty_label="Todos",
    )

    class Meta:
        model = Paciente
        fields = []  # todos os filtros estão declarados acima
        form = FiltroPacienteForm

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # --- Filtros com regra própria -------------------------------------------

    def filtrar_busca(self, queryset, name, value):
        # Cada palavra precisa aparecer em algum campo: "ana silva" acha Ana Silva
        # mesmo que nome e sobrenome estejam em colunas diferentes.
        for termo in value.split():
            queryset = queryset.filter(
                Q(primeiro_nome__icontains=termo)
                | Q(sobrenome__icontains=termo)
                | Q(email__icontains=termo)
            )
        return queryset

    def filtrar_status(self, queryset, name, value):
        return queryset.filter(ativo=(value == "ativo"))
