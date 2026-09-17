from django import forms

from .models import Consulta, Lembrete, ListaEspera


class ConsultaForm(forms.ModelForm):
    class Meta:
        model = Consulta
        fields = [
            "paciente",
            "profissional",
            "data_consulta",
            "hora_inicio",
            "hora_fim",
            "tipo_consulta",
            "status",
            "notas_sessao",
            "motivo_cancelamento",
        ]
        widgets = {
            "paciente": forms.Select(attrs={"class": "form-select"}),
            "profissional": forms.Select(attrs={"class": "form-select"}),
            "data_consulta": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "hora_inicio": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "hora_fim": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "tipo_consulta": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "notas_sessao": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "motivo_cancelamento": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        hora_inicio = cleaned_data.get("hora_inicio")
        hora_fim = cleaned_data.get("hora_fim")
        status = cleaned_data.get("status")
        motivo_cancelamento = cleaned_data.get("motivo_cancelamento")
        profissional = cleaned_data.get("profissional")
        data_consulta = cleaned_data.get("data_consulta")

        if hora_inicio and hora_fim and hora_fim <= hora_inicio:
            self.add_error("hora_fim", "A hora de fim deve ser depois da hora de início.")

        if status == "cancelada" and not motivo_cancelamento:
            self.add_error(
                "motivo_cancelamento", "Informe o motivo do cancelamento."
            )

        if profissional and data_consulta and hora_inicio and hora_fim:
            conflitos = Consulta.objects.filter(
                profissional=profissional,
                data_consulta=data_consulta,
                hora_inicio__lt=hora_fim,
                hora_fim__gt=hora_inicio,
            ).exclude(status="cancelada")
            if self.instance.pk:
                conflitos = conflitos.exclude(pk=self.instance.pk)
            if conflitos.exists():
                raise forms.ValidationError(
                    "Este profissional já possui uma consulta agendada neste horário."
                )

        return cleaned_data


class LembreteForm(forms.ModelForm):
    class Meta:
        model = Lembrete
        fields = [
            "consulta",
            "tipo_lembrete",
            "data_hora_envio",
            "enviado_em",
            "status",
        ]
        widgets = {
            "consulta": forms.Select(attrs={"class": "form-select"}),
            "tipo_lembrete": forms.Select(attrs={"class": "form-select"}),
            "data_hora_envio": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "enviado_em": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        enviado_em = cleaned_data.get("enviado_em")
        if status == "enviado" and not enviado_em:
            self.add_error("enviado_em", "Informe a data/hora em que o lembrete foi enviado.")
        return cleaned_data


class ListaEsperaForm(forms.ModelForm):
    class Meta:
        model = ListaEspera
        fields = [
            "paciente",
            "profissional_preferido",
            "dias_preferidos",
            "horario_preferido",
            "prioridade",
            "observacoes",
            "status",
        ]
        widgets = {
            "paciente": forms.Select(attrs={"class": "form-select"}),
            "profissional_preferido": forms.Select(attrs={"class": "form-select"}),
            "dias_preferidos": forms.TextInput(attrs={"class": "form-control"}),
            "horario_preferido": forms.TextInput(attrs={"class": "form-control"}),
            "prioridade": forms.Select(attrs={"class": "form-select"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }
