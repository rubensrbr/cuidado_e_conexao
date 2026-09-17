from django import forms
from django.utils import timezone

from .models import Paciente, Prontuario


class PacienteForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = [
            "primeiro_nome",
            "sobrenome",
            "data_nascimento",
            "genero",
            "email",
            "enderecos",
            "telefones",
            "contato_emergencia_nome",
            "contato_emergencia_telefone",
            "convenio",
            "numero_carteirinha",
            "ativo",
        ]
        widgets = {
            "primeiro_nome": forms.TextInput(attrs={"class": "form-control"}),
            "sobrenome": forms.TextInput(attrs={"class": "form-control"}),
            "data_nascimento": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "genero": forms.Select(attrs={"class": "form-select"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "enderecos": forms.Select(attrs={"class": "form-select"}),
            "telefones": forms.Select(attrs={"class": "form-select"}),
            "contato_emergencia_nome": forms.TextInput(attrs={"class": "form-control"}),
            "contato_emergencia_telefone": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "convenio": forms.TextInput(attrs={"class": "form-control"}),
            "numero_carteirinha": forms.TextInput(attrs={"class": "form-control"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {"enderecos": "Endereço", "telefones": "Telefone"}

    def clean_data_nascimento(self):
        data_nascimento = self.cleaned_data["data_nascimento"]
        if data_nascimento > timezone.localdate():
            raise forms.ValidationError("A data de nascimento não pode estar no futuro.")
        return data_nascimento


class ProntuarioForm(forms.ModelForm):
    class Meta:
        model = Prontuario
        fields = [
            "paciente",
            "profissional",
            "consulta",
            "data_registro",
            "codigo_cid",
            "queixa_principal",
            "plano_tratamento",
            "evolucao",
            "medicamentos",
            "avaliacao_risco",
        ]
        widgets = {
            "paciente": forms.Select(attrs={"class": "form-select"}),
            "profissional": forms.Select(attrs={"class": "form-select"}),
            "consulta": forms.Select(attrs={"class": "form-select"}),
            "data_registro": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "codigo_cid": forms.TextInput(attrs={"class": "form-control"}),
            "queixa_principal": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "plano_tratamento": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "evolucao": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "medicamentos": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "avaliacao_risco": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        consulta = cleaned_data.get("consulta")
        paciente = cleaned_data.get("paciente")
        if consulta and paciente and consulta.paciente_id != paciente.pk:
            self.add_error("consulta", "Esta consulta não pertence ao paciente selecionado.")
        return cleaned_data
