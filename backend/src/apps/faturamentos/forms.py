from decimal import Decimal

from django import forms
from django.db.models import Q

from clinicas.forms import TenantFormMixin

from .models import Faturamento, Pacote, SessaoPacote


class FaturamentoForm(TenantFormMixin, forms.ModelForm):
    class Meta:
        model = Faturamento
        fields = [
            "paciente",
            "consulta",
            "pacote",
            "pro_bono",
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
            "pacote": forms.Select(attrs={"class": "form-select"}),
            "pro_bono": forms.CheckboxInput(attrs={"class": "form-check-input"}),
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pro bono não tem valores: os campos só são obrigatórios nos demais casos
        # (a regra está em `clean`).
        self.fields["valor_cobrado"].required = False
        self.fields["valor_pago"].required = False
        # Só pacotes ativos aparecem para novas cobranças; na edição, mantém o
        # pacote já vinculado mesmo que tenha sido concluído ou cancelado.
        filtro = Q(status="ativo")
        if self.instance.pacote_id:
            filtro |= Q(pk=self.instance.pacote_id)
        self.fields["pacote"].queryset = self.fields["pacote"].queryset.filter(filtro)

    def clean(self):
        cleaned_data = super().clean()
        paciente = cleaned_data.get("paciente")
        pacote = cleaned_data.get("pacote")
        valor_cobrado = cleaned_data.get("valor_cobrado")
        valor_pago = cleaned_data.get("valor_pago")
        status_pagamento = cleaned_data.get("status_pagamento")
        pro_bono = cleaned_data.get("pro_bono")

        # Paciente pro bono + valor em branco = atendimento pro bono.
        if (
            not pro_bono
            and valor_cobrado is None
            and not self.has_error("valor_cobrado")
            and paciente is not None
            and paciente.pro_bono
            and pacote is None
        ):
            pro_bono = cleaned_data["pro_bono"] = True

        if pro_bono:
            # Valores em branco viram zero; valores preenchidos são recusados
            # pela validação do modelo (Faturamento.clean).
            if valor_cobrado is None and not self.has_error("valor_cobrado"):
                cleaned_data["valor_cobrado"] = Decimal("0")
            if valor_pago is None and not self.has_error("valor_pago"):
                cleaned_data["valor_pago"] = Decimal("0")
            if status_pagamento == "pendente":
                cleaned_data["status_pagamento"] = "pago"
            return cleaned_data

        for campo in ("valor_cobrado", "valor_pago"):
            if cleaned_data.get(campo) is None and not self.has_error(campo):
                self.add_error(campo, self.fields[campo].error_messages["required"])

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


class PacoteForm(TenantFormMixin, forms.ModelForm):
    class Meta:
        model = Pacote
        fields = [
            "paciente",
            "profissional",
            "quantidade_sessoes",
            "valor_total",
            "data_compra",
            "validade",
            "status",
        ]
        widgets = {
            "paciente": forms.Select(attrs={"class": "form-select"}),
            "profissional": forms.Select(attrs={"class": "form-select"}),
            "quantidade_sessoes": forms.NumberInput(
                attrs={"class": "form-control", "min": "1"}
            ),
            "valor_total": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "data_compra": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "validade": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }


class SessaoPacoteForm(TenantFormMixin, forms.ModelForm):
    class Meta:
        model = SessaoPacote
        fields = ["pacote", "consulta"]
        widgets = {
            "pacote": forms.Select(attrs={"class": "form-select"}),
            "consulta": forms.Select(attrs={"class": "form-select"}),
        }
