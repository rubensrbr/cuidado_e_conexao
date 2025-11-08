from django.db import models
from consultas.models import Consulta
from pacientes.models import Paciente
from core.models import BaseModel


class Faturamento(BaseModel):
    """Controle de faturamento e pagamentos"""

    METODO_PAGAMENTO_CHOICES = [
        ("dinheiro", "Dinheiro"),
        ("cartao_credito", "Cartão de Crédito"),
        ("cartao_debito", "Cartão de Débito"),
        ("pix", "PIX"),
        ("convenio", "Convênio"),
        ("cheque", "Cheque"),
    ]

    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("pago", "Pago"),
        ("parcialmente_pago", "Parcialmente Pago"),
        ("atrasado", "Atrasado"),
        ("cancelado", "Cancelado"),
    ]

    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.CASCADE,
        related_name="faturamentos",
        verbose_name="Paciente",
    )
    consulta = models.ForeignKey(
        Consulta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="faturamentos",
        verbose_name="Consulta",
    )
    data_servico = models.DateField(verbose_name="Data do Serviço")
    valor_cobrado = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Valor Cobrado"
    )
    valor_pago = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Valor Pago"
    )
    valor_convenio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Valor do Convênio",
    )
    metodo_pagamento = models.CharField(
        max_length=30,
        choices=METODO_PAGAMENTO_CHOICES,
        blank=True,
        verbose_name="Método de Pagamento",
    )
    status_pagamento = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="pendente",
        verbose_name="Status do Pagamento",
    )
    numero_nota = models.CharField(
        max_length=100, blank=True, verbose_name="Número da Nota"
    )
    observacoes = models.TextField(blank=True, verbose_name="Observações")

    class Meta:
        verbose_name = "Faturamento"
        verbose_name_plural = "Faturamentos"
        ordering = ["-data_servico"]

    def __str__(self):
        return f"Faturamento {self.paciente.nome_completo} - {self.data_servico} - R$ {self.valor_cobrado}"

    @property
    def valor_pendente(self):
        return self.valor_cobrado - self.valor_pago
