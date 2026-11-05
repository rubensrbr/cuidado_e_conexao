from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from clinicas.tenancy import TenantModel

ZERO = Decimal("0")


def status_do_pagamento(valor_cobrado, valor_pago, pro_bono=False, marcacao=""):
    """Status de um faturamento, derivado dos valores.

    Só duas situações são marcadas à mão (`marcacao`): "cancelado" e "atrasado".
    Todo o resto vem do valor pago:

      pago >= cobrado (cobrado > 0)  -> pago
      0 < pago < cobrado             -> parcialmente_pago
      pago == 0                      -> pendente (pro bono: pago, não há o que cobrar)

    "cancelado" vale sempre. "atrasado" só vale enquanto falta pagar: quitado,
    o status volta a ser "pago". Qualquer outro valor em `marcacao` (inclusive um
    status antigo como "pendente") é ignorado.
    """
    if marcacao == "cancelado":
        return "cancelado"
    cobrado = Decimal(str(valor_cobrado or 0))
    pago = Decimal(str(valor_pago or 0))
    if cobrado > ZERO and pago >= cobrado:
        calculado = "pago"
    elif pago > ZERO:
        calculado = "parcialmente_pago"
    elif pro_bono:
        calculado = "pago"
    else:
        calculado = "pendente"
    if marcacao == "atrasado" and calculado != "pago":
        return "atrasado"
    return calculado


class Faturamento(TenantModel):
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
    # Únicos status escolhidos por uma pessoa; os demais saem dos valores
    # (ver `status_do_pagamento`).
    STATUS_MANUAIS = ("atrasado", "cancelado")

    paciente = models.ForeignKey(
        "pacientes.Paciente",
        # PROTECT: o histórico financeiro não some junto com o cadastro. Para
        # deixar de atender o paciente, inative-o (Paciente.ativo).
        on_delete=models.PROTECT,
        related_name="faturamentos",
        verbose_name="Paciente",
    )

    consulta = models.ForeignKey(
        "consultas.Consulta",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="faturamentos",
        verbose_name="Consulta",
    )
    data_servico = models.DateField(
        verbose_name="Data do Serviço",
    )
    valor_cobrado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Valor Cobrado",
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
    pacote = models.ForeignKey(
        "faturamentos.Pacote",
        # RESTRICT: não dá para apagar um pacote que já tem cobrança. Apagar o
        # paciente também é barrado (Faturamento.paciente e Pacote.paciente são
        # PROTECT), então não há mais caminho em cascata que leve a cobrança.
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="faturamentos",
        verbose_name="Pacote",
    )
    pro_bono = models.BooleanField(
        default=False,
        verbose_name="Pro bono",
        help_text="Atendimento gratuito: não há valor cobrado nem pago.",
    )

    class Meta:
        verbose_name = "Faturamento"
        verbose_name_plural = "Faturamentos"
        ordering = ["-data_servico"]

    def __str__(self):
        return f"Faturamento {self.paciente.nome_completo} - {self.data_servico} - R$ {self.valor_cobrado}"

    def clean(self):
        super().clean()
        # O formulário já limita as opções à clínica atual; estas checagens
        # protegem também quem grava fora de formulários (shell, comandos).
        erros = {}

        if self.paciente_id and self.consulta_id:
            if self.paciente.clinica_id != self.consulta.clinica_id:
                erros["consulta"] = "A consulta pertence a outra clínica."

        if self.paciente_id and self.pacote_id:
            if self.pacote.clinica_id != self.paciente.clinica_id:
                erros["pacote"] = "O pacote pertence a outra clínica."
            elif self.pacote.paciente_id != self.paciente_id:
                erros["pacote"] = "O pacote pertence a outro paciente."

        if self.pro_bono:
            if self.pacote_id:
                erros["pacote"] = "Atendimento pro bono não pode estar em um pacote."
            if self.valor_cobrado:
                erros["valor_cobrado"] = "Atendimento pro bono não tem valor cobrado."
            if self.valor_pago:
                erros["valor_pago"] = "Atendimento pro bono não tem valor pago."
            if self.valor_convenio:
                erros["valor_convenio"] = (
                    "Atendimento pro bono não tem valor de convênio."
                )

        if erros:
            raise ValidationError(erros)

    def atualizar_status(self):
        """Recalcula `status_pagamento` a partir dos valores (ver `status_do_pagamento`)."""
        self.status_pagamento = status_do_pagamento(
            self.valor_cobrado, self.valor_pago, self.pro_bono, self.status_pagamento
        )

    def save(self, *args, **kwargs):
        # O status nunca contradiz os valores, venha o faturamento de formulário,
        # shell ou comando. (`QuerySet.update()` e `bulk_create()` não passam por
        # aqui: quem os usa precisa chamar `status_do_pagamento` por conta própria.)
        self.atualizar_status()
        campos = kwargs.get("update_fields")
        if campos is not None and {
            "valor_cobrado", "valor_pago", "pro_bono", "status_pagamento"
        } & set(campos):
            kwargs["update_fields"] = {*campos, "status_pagamento"}
        super().save(*args, **kwargs)

    @property
    def valor_pendente(self):
        return self.valor_cobrado - self.valor_pago


class Pacote(TenantModel):
    """Pacote de sessões pago de uma vez (ex.: 4 sessões).

    O pagamento fica em um `Faturamento` com `pacote=<este pacote>` (sem
    consulta). As sessões consumidas vêm das consultas vinculadas por
    `SessaoPacote`; o saldo é sempre calculado, nunca guardado.
    """

    STATUS_CHOICES = [
        ("ativo", "Ativo"),
        ("concluido", "Concluído"),
        ("expirado", "Expirado"),
        ("cancelado", "Cancelado"),
    ]

    STATUS_QUE_CONSOMEM_SESSAO = ("realizada",)

    paciente = models.ForeignKey(
        "pacientes.Paciente",
        # PROTECT: pacote é registro financeiro (valor pago, sessões a
        # consumir); não é apagado junto com o paciente.
        on_delete=models.PROTECT,
        related_name="pacotes",
        verbose_name="Paciente",
    )
    profissional = models.ForeignKey(
        "profissionais.Profissional",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pacotes",
        verbose_name="Profissional",
        help_text="Deixe em branco se o pacote vale com qualquer profissional.",
    )
    quantidade_sessoes = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Quantidade de sessões",
    )
    valor_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Valor Total",
    )
    data_compra = models.DateField(
        default=timezone.localdate,
        verbose_name="Data da Compra",
    )
    validade = models.DateField(null=True, blank=True, verbose_name="Validade")
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="ativo",
        verbose_name="Status",
    )

    class Meta:
        verbose_name = "Pacote"
        verbose_name_plural = "Pacotes"
        ordering = ["-data_compra", "-created_at"]

    def __str__(self):
        return (
            f"Pacote {self.quantidade_sessoes} sessões - "
            f"{self.paciente.nome_completo} - {self.data_compra}"
        )

    def clean(self):
        super().clean()
        erros = {}

        if self.validade and self.data_compra and self.validade < self.data_compra:
            erros["validade"] = "A validade não pode ser anterior à data da compra."

        if self.paciente_id and self.profissional_id:
            if self.paciente.clinica_id != self.profissional.clinica_id:
                erros["profissional"] = "O profissional pertence a outra clínica."

        if erros:
            raise ValidationError(erros)

    @property
    def sessoes_usadas(self):
        return self.sessoes.filter(
            consulta__status__in=self.STATUS_QUE_CONSOMEM_SESSAO
        ).count()

    @property
    def saldo(self):
        return self.quantidade_sessoes - self.sessoes_usadas

    @property
    def esta_vencido(self):
        return bool(self.validade and self.validade < timezone.localdate())


class SessaoPacote(TenantModel):
    """Liga uma consulta a um pacote (a consulta gasta uma sessão dele).

    Fica aqui, e não como campo em `Consulta`, porque `faturamentos` é um app
    opcional: `consultas` não pode depender dele.
    """

    pacote = models.ForeignKey(
        "faturamentos.Pacote",
        on_delete=models.CASCADE,
        related_name="sessoes",
        verbose_name="Pacote",
    )
    consulta = models.OneToOneField(
        "consultas.Consulta",
        on_delete=models.CASCADE,
        related_name="sessao_pacote",
        verbose_name="Consulta",
    )

    class Meta:
        verbose_name = "Sessão do pacote"
        verbose_name_plural = "Sessões do pacote"
        ordering = ["consulta__data_consulta", "consulta__hora_inicio"]

    def __str__(self):
        return f"{self.pacote} - {self.consulta}"

    def clean(self):
        super().clean()
        if not (self.pacote_id and self.consulta_id):
            return
        pacote, consulta = self.pacote, self.consulta
        erros = {}

        if consulta.clinica_id != pacote.clinica_id:
            erros["consulta"] = "A consulta pertence a outra clínica."
        elif consulta.paciente_id != pacote.paciente_id:
            erros["consulta"] = "A consulta é de outro paciente."
        elif (
            pacote.profissional_id
            and consulta.profissional_id != pacote.profissional_id
        ):
            erros["consulta"] = "A consulta é de outro profissional."
        elif self._state.adding:
            if pacote.status != "ativo":
                erros["pacote"] = "O pacote não está ativo."
            else:
                # Sessões já reservadas (canceladas liberam a vaga).
                reservadas = pacote.sessoes.exclude(
                    consulta__status="cancelada"
                ).count()
                if reservadas >= pacote.quantidade_sessoes:
                    erros["pacote"] = (
                        "Todas as sessões deste pacote já foram agendadas."
                    )

        if erros:
            raise ValidationError(erros)
