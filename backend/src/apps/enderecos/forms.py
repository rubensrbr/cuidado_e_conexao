import re

from django import forms

from localidades.models import Cidade, Estado

from .models import Endereco

CEP_RE = re.compile(r"^\d{5}-?\d{3}$")


class EnderecoForm(forms.ModelForm):
    # Campo auxiliar (não é do model): serve só para filtrar as cidades.
    estado = forms.ModelChoiceField(
        queryset=Estado.objects.all(),
        label="UF",
        empty_label="UF",
        widget=forms.Select(attrs={"class": "form-select endereco-estado"}),
    )

    class Meta:
        model = Endereco
        fields = [
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "cep",
        ]
        widgets = {
            "logradouro": forms.TextInput(attrs={"class": "form-control"}),
            "numero": forms.TextInput(attrs={"class": "form-control"}),
            "complemento": forms.TextInput(attrs={"class": "form-control"}),
            "bairro": forms.TextInput(attrs={"class": "form-control"}),
            "cidade": forms.Select(attrs={"class": "form-select endereco-cidade"}),
            "cep": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "00000-000"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].label_from_instance = lambda e: f"{e.sigla} - {e.nome}"
        self.fields["cidade"].label_from_instance = lambda c: c.nome
        self.fields["cidade"].empty_label = "Selecione a cidade"

        # Só as cidades da UF escolhida: a postada (formulário preenchido),
        # ou a do endereço salvo (edição); sem UF, a lista fica vazia.
        estado_id = None
        if self.is_bound:
            estado_id = self.data.get(self.add_prefix("estado")) or None
        elif self.instance.pk:
            estado_id = self.instance.cidade.estado_id
            self.initial["estado"] = estado_id

        try:
            self.fields["cidade"].queryset = Cidade.objects.filter(
                estado_id=int(estado_id)
            ).order_by("nome")
        except (TypeError, ValueError):
            self.fields["cidade"].queryset = Cidade.objects.none()

    def clean_cep(self):
        cep = self.cleaned_data["cep"].strip()
        if not CEP_RE.match(cep):
            raise forms.ValidationError("CEP inválido. Use o formato 00000-000.")
        digits = cep.replace("-", "")
        return f"{digits[:5]}-{digits[5:]}"
