"""
Resumo financeiro (os cards da aba "Resumo" e os totais do PDF).

Um só lugar calcula os números, para a tela e o PDF nunca divergirem:

    resumo = resumir(FaturamentoFilter(request.GET, queryset=...).qs)

Regras:
  - Cobranças canceladas aparecem no resumo por status, mas ficam fora dos
    totais (não são dinheiro a receber).
  - Pendente = cobrado − pago, sobre as cobranças não canceladas.
  - Atendimentos pro bono (sem valor) não entram nos status: viram uma contagem
    à parte, senão inflariam o "Pago".
"""

import calendar
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count, Sum
from django.http import QueryDict
from django.utils import timezone

from .models import Faturamento

ZERO = Decimal("0")
CAMPOS_DO_PERIODO = ("data_de", "data_ate")

# Cor do selo de cada status (mesmas classes `app-status-*` da lista).
SELO_DO_STATUS = {"pago": "active", "atrasado": "inactive", "cancelado": "neutral"}


@dataclass(frozen=True)
class ResumoPorStatus:
    status: str
    rotulo: str
    qtd: int
    cobrado: Decimal
    pago: Decimal

    @property
    def em_aberto(self):
        return self.cobrado - self.pago

    @property
    def valor(self):
        """O valor que interessa em cada status: recebido, cancelado ou em aberto."""
        if self.status == "pago":
            return self.pago
        if self.status == "cancelado":
            return self.cobrado
        return self.em_aberto

    @property
    def legenda(self):
        return {"pago": "recebido", "cancelado": "cancelado"}.get(
            self.status, "em aberto"
        )

    @property
    def selo(self):
        return SELO_DO_STATUS.get(self.status, "pending")


@dataclass(frozen=True)
class Resumo:
    por_status: list
    pro_bono: int  # atendimentos pro bono (não cancelados)

    @property
    def _validos(self):
        return [s for s in self.por_status if s.status != "cancelado"]

    @property
    def total_cobrado(self):
        return sum((s.cobrado for s in self._validos), ZERO)

    @property
    def total_pago(self):
        return sum((s.pago for s in self._validos), ZERO)

    @property
    def total_pendente(self):
        return self.total_cobrado - self.total_pago

    @property
    def taxa_recebimento(self):
        """Pago ÷ cobrado, em %, com uma casa; None quando não há nada cobrado."""
        cobrado = self.total_cobrado
        if not cobrado:
            return None
        return (self.total_pago / cobrado * 100).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )


def resumir(queryset):
    # order_by(): a ordenação padrão do model entraria no GROUP BY.
    base = queryset.order_by()
    grupos = {
        linha["status_pagamento"]: linha
        for linha in base.filter(pro_bono=False)
        .values("status_pagamento")
        .annotate(
            qtd=Count("pk"), cobrado=Sum("valor_cobrado"), pago=Sum("valor_pago")
        )
    }
    por_status = []
    for status, rotulo in Faturamento.STATUS_CHOICES:
        grupo = grupos.get(status, {})
        por_status.append(
            ResumoPorStatus(
                status=status,
                rotulo=rotulo,
                qtd=grupo.get("qtd", 0),
                cobrado=grupo.get("cobrado") or ZERO,
                pago=grupo.get("pago") or ZERO,
            )
        )
    pro_bono = (
        base.filter(pro_bono=True).exclude(status_pagamento="cancelado").count()
    )
    return Resumo(por_status=por_status, pro_bono=pro_bono)


def mes_atual(hoje=None):
    """Primeiro e último dia do mês de `hoje` (padrão: hoje)."""
    hoje = hoje or timezone.localdate()
    ultimo = calendar.monthrange(hoje.year, hoje.month)[1]
    return hoje.replace(day=1), hoje.replace(day=ultimo)


def periodo_da_query(get):
    """`data_de`/`data_ate` da query string, já codificados (sem o "?").

    As abas e os cards usam isso para levar o período de uma tela à outra.
    """
    periodo = QueryDict(mutable=True)
    for nome in CAMPOS_DO_PERIODO:
        if get.get(nome):
            periodo[nome] = get[nome]
    return periodo.urlencode()
