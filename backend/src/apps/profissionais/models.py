from django.db import models
from core.models import BaseModel


class Profissional(BaseModel):
    """Profissionais da clínica (psicólogos, médicos, etc)"""

    primeiro_nome = models.CharField(
        max_length=100,
        verbose_name="Primeiro Nome",
    )
    sobrenome = models.CharField(
        max_length=100,
        verbose_name="Sobrenome",
    )
    email = models.EmailField(
        max_length=150,
        unique=True,
        verbose_name="E-mail",
    )

    # Relacionamentos
    telefones = models.ForeignKey(
        "telefones.Telefone",
        on_delete=models.CASCADE,
        related_name="profissionais",
        verbose_name="Telefones",
    )

    tipo_profissional = models.ForeignKey(
        "profissionais.TipoProfissional",
        on_delete=models.DO_NOTHING,
    )

    numero_registro = models.CharField(
        max_length=100,
        verbose_name="Número de Registro (CRP, CRM, etc)",
    )
    especializacao = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Especialização",
    )
    titulacao = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Titulação",
    )
    valor_hora = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Valor por Hora",
    )

    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
    )

    class Meta:
        verbose_name = "Profissional"
        verbose_name_plural = "Profissionais"
        ordering = ["sobrenome", "primeiro_nome"]

    def __str__(self):
        return f"{self.primeiro_nome} {self.sobrenome} - {self.tipo_profissional}"

    @property
    def nome_completo(self):
        return f"{self.primeiro_nome} {self.sobrenome}"


class Disponibilidade(BaseModel):
    """Horários disponíveis dos profissionais"""

    DIA_SEMANA_CHOICES = [
        ("segunda", "Segunda-feira"),
        ("terca", "Terça-feira"),
        ("quarta", "Quarta-feira"),
        ("quinta", "Quinta-feira"),
        ("sexta", "Sexta-feira"),
        ("sabado", "Sábado"),
        ("domingo", "Domingo"),
    ]

    profissional = models.ForeignKey(
        Profissional,
        on_delete=models.CASCADE,
        related_name="disponibilidades",
        verbose_name="Profissional",
    )
    dia_semana = models.CharField(
        max_length=10, choices=DIA_SEMANA_CHOICES, verbose_name="Dia da Semana"
    )
    hora_inicio = models.TimeField(verbose_name="Hora de Início")
    hora_fim = models.TimeField(verbose_name="Hora de Fim")
    recorrente = models.BooleanField(default=True, verbose_name="Recorrente")
    data_inicio = models.DateField(null=True, blank=True, verbose_name="Data de Início")
    data_fim = models.DateField(null=True, blank=True, verbose_name="Data de Fim")

    class Meta:
        verbose_name = "Disponibilidade"
        verbose_name_plural = "Disponibilidades"
        ordering = ["dia_semana", "hora_inicio"]

    def __str__(self):
        return f"{self.profissional.nome_completo} - {self.get_dia_semana_display()} {self.hora_inicio}-{self.hora_fim}"


class TipoProfissional(BaseModel):
    descricao = models.CharField(
        max_length=100,
    )

    class Meta:
        verbose_name = "Tipo Profissional"

    def __str__(self) -> str:
        return f"{self.descricao}"
