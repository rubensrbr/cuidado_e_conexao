from django.db import models
from core.models import BaseModel
from consultas.models import Consulta


class Sala(BaseModel):
    """Salas da clínica"""

    numero_sala = models.CharField(
        max_length=20, unique=True, verbose_name="Número da Sala"
    )
    nome = models.CharField(max_length=100, blank=True, verbose_name="Nome")
    capacidade = models.IntegerField(default=1, verbose_name="Capacidade")
    ativa = models.BooleanField(default=True, verbose_name="Ativa")

    class Meta:
        verbose_name = "Sala"
        verbose_name_plural = "Salas"
        ordering = ["numero_sala"]

    def __str__(self):
        return f"Sala {self.numero_sala}" + (f" - {self.nome}" if self.nome else "")


class AgendaSala(BaseModel):
    """Agendamento de salas"""

    sala = models.ForeignKey(
        Sala, on_delete=models.CASCADE, related_name="agendamentos", verbose_name="Sala"
    )
    consulta = models.ForeignKey(
        Consulta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sala_agendada",
        verbose_name="Consulta",
    )
    data = models.DateField(verbose_name="Data")
    hora_inicio = models.TimeField(verbose_name="Hora de Início")
    hora_fim = models.TimeField(verbose_name="Hora de Fim")

    class Meta:
        verbose_name = "Agenda de Sala"
        verbose_name_plural = "Agendas de Salas"
        ordering = ["data", "hora_inicio"]
        indexes = [
            models.Index(fields=["sala", "data"]),
        ]

    def __str__(self):
        return f"{self.sala} - {self.data} {self.hora_inicio}-{self.hora_fim}"
