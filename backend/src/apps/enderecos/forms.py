import re

from django import forms

from localidades.models import Cidade

from .models import Endereco

CEP_RE = re.compile(r"^\d{5}-?\d{3}$")


class EnderecoForm(forms.ModelForm):
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
            "cidade": forms.Select(attrs={"class": "form-select"}),
            "cep": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "00000-000"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # __str__ de Cidade usa estado.sigla; select_related evita 1 query por opção.
        self.fields["cidade"].queryset = Cidade.objects.select_related("estado")
        self.fields["cidade"].empty_label = "Selecione a cidade"

    def clean_cep(self):
        cep = self.cleaned_data["cep"].strip()
        if not CEP_RE.match(cep):
            raise forms.ValidationError("CEP inválido. Use o formato 00000-000.")
        digits = cep.replace("-", "")
        return f"{digits[:5]}-{digits[5:]}"
