from django.db import models
from core.models import BaseModel


class Consulta(BaseModel):
    """Consultas agendadas"""

    TIPO_CHOICES = [
        ("avaliacao_inicial", "Avaliação Inicial"),
        ("retorno", "Retorno"),
        ("sessao_grupo", "Sessão em Grupo"),
        ("emergencia", "Emergência"),
    ]

    STATUS_CHOICES = [
        ("agendada", "Agendada"),
        ("confirmada", "Confirmada"),
        ("realizada", "Realizada"),
        ("cancelada", "Cancelada"),
        ("falta", "Falta"),
    ]

    paciente = models.ForeignKey(
        "pacientes.Paciente",
        on_delete=models.CASCADE,
        related_name="consultas",
        verbose_name="Paciente",
    )
    profissional = models.ForeignKey(
        "profissionais.Profissional",
        on_delete=models.CASCADE,
        related_name="consultas",
        verbose_name="Profissional",
    )
    data_consulta = models.DateField(verbose_name="Data da Consulta")
    hora_inicio = models.TimeField(verbose_name="Hora de Início")
    hora_fim = models.TimeField(verbose_name="Hora de Fim")
    tipo_consulta = models.CharField(
        max_length=30,
        choices=TIPO_CHOICES,
        verbose_name="Tipo de Consulta",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="agendada", verbose_name="Status"
    )
    notas_sessao = models.TextField(blank=True, verbose_name="Notas da Sessão")
    motivo_cancelamento = models.TextField(
        blank=True, verbose_name="Motivo do Cancelamento"
    )

    class Meta:
        verbose_name = "Consulta"
        verbose_name_plural = "Consultas"
        ordering = ["-data_consulta", "-hora_inicio"]
        indexes = [
            models.Index(fields=["data_consulta"]),
            models.Index(fields=["paciente", "profissional"]),
        ]

    def __str__(self):
        return f"{self.paciente.nome_completo} - {self.profissional.nome_completo} - {self.data_consulta}"


class Lembrete(BaseModel):
    """Lembretes de consultas"""

    TIPO_CHOICES = [
        ("email", "E-mail"),
        ("sms", "SMS"),
        ("whatsapp", "WhatsApp"),
        ("telefone", "Telefone"),
    ]

    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("enviado", "Enviado"),
        ("falhou", "Falhou"),
    ]

    consulta = models.ForeignKey(
        "consultas.Consulta",
        on_delete=models.CASCADE,
        related_name="lembretes",
        verbose_name="Consulta",
    )
    tipo_lembrete = models.CharField(
        max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo de Lembrete"
    )
    data_hora_envio = models.DateTimeField(verbose_name="Data/Hora de Envio")
    enviado_em = models.DateTimeField(null=True, blank=True, verbose_name="Enviado em")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pendente", verbose_name="Status"
    )

    class Meta:
        verbose_name = "Lembrete"
        verbose_name_plural = "Lembretes"
        ordering = ["data_hora_envio"]

    def __str__(self):
        return f"Lembrete {self.get_tipo_lembrete_display()} - {self.consulta}"


class ListaEspera(BaseModel):
    """Lista de espera para consultas"""

    PRIORIDADE_CHOICES = [
        ("urgente", "Urgente"),
        ("alta", "Alta"),
        ("normal", "Normal"),
        ("baixa", "Baixa"),
    ]

    STATUS_CHOICES = [
        ("ativa", "Ativa"),
        ("agendada", "Agendada"),
        ("cancelada", "Cancelada"),
    ]

    paciente = models.ForeignKey(
        "pacientes.Paciente",
        on_delete=models.CASCADE,
        related_name="lista_espera",
        verbose_name="Paciente",
    )
    profissional_preferido = models.ForeignKey(
        "profissionais.Profissional",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lista_espera",
        verbose_name="Profissional Preferido",
    )
    dias_preferidos = models.CharField(
        max_length=100, blank=True, verbose_name="Dias Preferidos"
    )
    horario_preferido = models.CharField(
        max_length=50, blank=True, verbose_name="Horário Preferido"
    )
    prioridade = models.CharField(
        max_length=20,
        choices=PRIORIDADE_CHOICES,
        default="normal",
        verbose_name="Prioridade",
    )
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="ativa", verbose_name="Status"
    )
