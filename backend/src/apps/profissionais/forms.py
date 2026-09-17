from decimal import Decimal

from django import forms

from .models import Disponibilidade, Profissional, TipoProfissional


class TipoProfissionalForm(forms.ModelForm):
    class Meta:
        model = TipoProfissional
        fields = ["descricao"]
        widgets = {
            "descricao": forms.TextInput(attrs={"class": "form-control"}),
        }


class ProfissionalForm(forms.ModelForm):
    class Meta:
        model = Profissional
        fields = [
            "primeiro_nome",
            "sobrenome",
            "email",
            "telefones",
            "tipo_profissional",
            "numero_registro",
            "especializacao",
            "titulacao",
            "valor_hora",
            "ativo",
        ]
        widgets = {
            "primeiro_nome": forms.TextInput(attrs={"class": "form-control"}),
            "sobrenome": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "telefones": forms.Select(attrs={"class": "form-select"}),
            "tipo_profissional": forms.Select(attrs={"class": "form-select"}),
            "numero_registro": forms.TextInput(attrs={"class": "form-control"}),
            "especializacao": forms.TextInput(attrs={"class": "form-control"}),
            "titulacao": forms.TextInput(attrs={"class": "form-control"}),
            "valor_hora": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {"telefones": "Telefone"}

    def clean_valor_hora(self):
        valor_hora = self.cleaned_data["valor_hora"]
        if valor_hora <= Decimal("0"):
            raise forms.ValidationError("O valor por hora deve ser maior que zero.")
        return valor_hora


class DisponibilidadeForm(forms.ModelForm):
    class Meta:
        model = Disponibilidade
        fields = [
            "profissional",
            "dia_semana",
            "hora_inicio",
            "hora_fim",
            "recorrente",
            "data_inicio",
            "data_fim",
        ]
        widgets = {
            "profissional": forms.Select(attrs={"class": "form-select"}),
            "dia_semana": forms.Select(attrs={"class": "form-select"}),
            "hora_inicio": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "hora_fim": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "recorrente": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "data_inicio": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "data_fim": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        hora_inicio = cleaned_data.get("hora_inicio")
        hora_fim = cleaned_data.get("hora_fim")
        recorrente = cleaned_data.get("recorrente")
        data_inicio = cleaned_data.get("data_inicio")
        data_fim = cleaned_data.get("data_fim")

        if hora_inicio and hora_fim and hora_fim <= hora_inicio:
            self.add_error("hora_fim", "A hora de fim deve ser depois da hora de início.")

        if not recorrente and not (data_inicio and data_fim):
            raise forms.ValidationError(
                "Para disponibilidades não recorrentes, informe a data de início e fim."
            )

        if data_inicio and data_fim and data_fim < data_inicio:
            self.add_error("data_fim", "A data de fim não pode ser anterior à data de início.")

        return cleaned_data
