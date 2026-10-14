import re

from django import forms

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
            "cidade": forms.TextInput(attrs={"class": "form-control"}),
            "cep": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "00000-000"}
            ),
        }

    def clean_cep(self):
        cep = self.cleaned_data["cep"].strip()
        if not CEP_RE.match(cep):
            raise forms.ValidationError("CEP inválido. Use o formato 00000-000.")
        digits = cep.replace("-", "")
        return f"{digits[:5]}-{digits[5:]}"
