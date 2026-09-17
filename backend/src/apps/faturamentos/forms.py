from decimal import Decimal

from django import forms

from .models import Faturamento


class FaturamentoForm(forms.ModelForm):
    class Meta:
        model = Faturamento
        fields = [
            "paciente",
            "consulta",
            "data_servico",
            "valor_cobrado",
            "valor_pago",
            "valor_convenio",
            "metodo_pagamento",
            "status_pagamento",
            "numero_nota",
            "observacoes",
        ]
        widgets = {
            "paciente": forms.Select(attrs={"class": "form-select"}),
            "consulta": forms.Select(attrs={"class": "form-select"}),
            "data_servico": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "valor_cobrado": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "valor_pago": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "valor_convenio": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "metodo_pagamento": forms.Select(attrs={"class": "form-select"}),
            "status_pagamento": forms.Select(attrs={"class": "form-select"}),
            "numero_nota": forms.TextInput(attrs={"class": "form-control"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        valor_cobrado = cleaned_data.get("valor_cobrado")
        valor_pago = cleaned_data.get("valor_pago")
        status_pagamento = cleaned_data.get("status_pagamento")

        if valor_cobrado is not None and valor_cobrado <= Decimal("0"):
            self.add_error("valor_cobrado", "O valor cobrado deve ser maior que zero.")

        if valor_cobrado is not None and valor_pago is not None:
            if valor_pago < Decimal("0"):
                self.add_error("valor_pago", "O valor pago não pode ser negativo.")
            elif valor_pago > valor_cobrado:
                self.add_error(
                    "valor_pago", "O valor pago não pode ser maior que o valor cobrado."
                )
            elif status_pagamento == "pago" and valor_pago < valor_cobrado:
                self.add_error(
                    "status_pagamento",
                    "Status 'Pago' exige que o valor pago seja igual ao valor cobrado.",
                )

        return cleaned_data
