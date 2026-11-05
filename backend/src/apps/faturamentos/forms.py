from decimal import Decimal

from django import forms
from django.db.models import Q

from clinicas.forms import TenantFormMixin

from .models import Faturamento, Pacote, SessaoPacote, status_do_pagamento


class OpcoesPorPaciente(forms.Select):
    """Select que marca cada opção com o paciente dono dela (`data-paciente`).

    O formulário usa essa marca para esconder, no navegador, as opções de
    outros pacientes assim que o paciente é trocado.
    """

    paciente_por_opcao = None

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        chave = getattr(value, "value", value)  # ModelChoiceIteratorValue -> pk
        paciente_id = (self.paciente_por_opcao or {}).get(chave)
        if paciente_id is not None:
            option["attrs"]["data-paciente"] = paciente_id
        return option


class FaturamentoForm(TenantFormMixin, forms.ModelForm):
    # Pendente, parcialmente pago e pago não são escolhidos: saem do valor pago
    # (ver `status_do_pagamento`). Só "atrasado" e "cancelado" são marcados à mão.
    status_pagamento = forms.ChoiceField(
        label="Status do pagamento",
        required=False,
        choices=[
            ("", "Automático (conforme o valor pago)"),
            ("atrasado", "Atrasado"),
            ("cancelado", "Cancelado"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=(
            "Pendente, parcialmente pago e pago são definidos pelo valor pago. "
            "Marque só se estiver atrasado ou cancelado."
        ),
    )

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
            "consulta": OpcoesPorPaciente(attrs={"class": "form-select"}),
            "pacote": OpcoesPorPaciente(attrs={"class": "form-select"}),
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
            "numero_nota": forms.TextInput(attrs={"class": "form-control"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pro bono não tem valores: os campos só são obrigatórios nos demais casos
        # (a regra está em `clean`).
        self.fields["valor_cobrado"].required = False
        self.fields["valor_pago"].required = False
        # Na edição, só uma marcação manual aparece escolhida; um status derivado
        # (pago, pendente...) volta a "Automático".
        if self.instance.status_pagamento not in Faturamento.STATUS_MANUAIS:
            self.initial["status_pagamento"] = ""
        # Só pacotes ativos aparecem para novas cobranças; na edição, mantém o
        # pacote já vinculado mesmo que tenha sido concluído ou cancelado.
        filtro = Q(status="ativo")
        if self.instance.pacote_id:
            filtro |= Q(pk=self.instance.pacote_id)
        self.fields["pacote"].queryset = self.fields["pacote"].queryset.filter(filtro)

        # Consulta e pacote são sempre do próprio paciente da cobrança: com o
        # paciente conhecido, só as opções dele são oferecidas; sem ele (formulário
        # novo), todas vão marcadas com `data-paciente` e o navegador filtra ao
        # escolher o paciente.
        paciente_id = self._paciente_selecionado()
        for nome in ("consulta", "pacote"):
            campo = self.fields[nome]
            if paciente_id:
                campo.queryset = campo.queryset.filter(paciente_id=paciente_id)
            campo.widget.paciente_por_opcao = dict(
                campo.queryset.values_list("pk", "paciente_id")
            )
        self.fields["consulta"].help_text = "Só aparecem consultas do paciente escolhido."
        self.fields["pacote"].help_text = (
            "Só aparecem pacotes ativos do paciente escolhido."
        )

    def _paciente_selecionado(self):
        if self.is_bound:
            valor = self.data.get(self.add_prefix("paciente"))
        else:
            valor = self.initial.get("paciente") or self.instance.paciente_id
        try:
            return int(valor) if valor else None
        except (TypeError, ValueError):
            return None

    def _get_validation_exclusions(self):
        # O status é calculado em `clean`; o valor "" do campo (automático) não
        # pode ser validado como se fosse o status do modelo.
        exclude = super()._get_validation_exclusions()
        exclude.add("status_pagamento")
        return exclude

    def _definir_status(self, cleaned_data, cobrado, pago, pro_bono):
        marcacao = cleaned_data.get("status_pagamento") or ""
        status = status_do_pagamento(cobrado, pago, pro_bono, marcacao)
        if marcacao == "atrasado" and status == "pago":
            self.add_error(
                "status_pagamento",
                "Um faturamento quitado não pode estar atrasado.",
            )
            return
        cleaned_data["status_pagamento"] = status

    def clean(self):
        cleaned_data = super().clean()
        paciente = cleaned_data.get("paciente")
        pacote = cleaned_data.get("pacote")
        valor_cobrado = cleaned_data.get("valor_cobrado")
        valor_pago = cleaned_data.get("valor_pago")
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
                cleaned_data["valor_cobrado"] = valor_cobrado = Decimal("0")
            if valor_pago is None and not self.has_error("valor_pago"):
                cleaned_data["valor_pago"] = valor_pago = Decimal("0")
            self._definir_status(cleaned_data, valor_cobrado, valor_pago, True)
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

        if not (self.has_error("valor_cobrado") or self.has_error("valor_pago")):
            self._definir_status(cleaned_data, valor_cobrado, valor_pago, False)

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
