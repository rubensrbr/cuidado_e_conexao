from django import forms

from .models import AgendaSala, Sala


class SalaForm(forms.ModelForm):
    class Meta:
        model = Sala
        fields = ["numero_sala", "nome", "capacidade", "ativa"]
        widgets = {
            "numero_sala": forms.TextInput(attrs={"class": "form-control"}),
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "capacidade": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "ativa": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_capacidade(self):
        capacidade = self.cleaned_data["capacidade"]
        if capacidade < 1:
            raise forms.ValidationError("A capacidade deve ser de pelo menos 1 pessoa.")
        return capacidade


class AgendaSalaForm(forms.ModelForm):
    class Meta:
        model = AgendaSala
        fields = ["sala", "consulta", "data", "hora_inicio", "hora_fim"]
        widgets = {
            "sala": forms.Select(attrs={"class": "form-select"}),
            "consulta": forms.Select(attrs={"class": "form-select"}),
            "data": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "hora_inicio": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "hora_fim": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        sala = cleaned_data.get("sala")
        data = cleaned_data.get("data")
        hora_inicio = cleaned_data.get("hora_inicio")
        hora_fim = cleaned_data.get("hora_fim")

        if hora_inicio and hora_fim and hora_fim <= hora_inicio:
            self.add_error("hora_fim", "A hora de fim deve ser depois da hora de início.")

        if sala and data and hora_inicio and hora_fim:
            conflitos = AgendaSala.objects.filter(
                sala=sala,
                data=data,
                hora_inicio__lt=hora_fim,
                hora_fim__gt=hora_inicio,
            )
            if self.instance.pk:
                conflitos = conflitos.exclude(pk=self.instance.pk)
            if conflitos.exists():
                raise forms.ValidationError(
                    "Já existe um agendamento para esta sala neste horário."
                )

        return cleaned_data
