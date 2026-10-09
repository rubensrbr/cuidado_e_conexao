from django.db import models
from core.models import BaseModel


class Endereco(BaseModel):
    """Endereços para pacientes e profissionais"""

    logradouro = models.CharField(max_length=255, verbose_name="Logradouro")
    numero = models.CharField(max_length=20, verbose_name="Número")
    complemento = models.CharField(
        max_length=100, blank=True, verbose_name="Complemento"
    )
    bairro = models.CharField(max_length=100, verbose_name="Bairro")
    cidade = models.CharField(max_length=100, verbose_name="Cidade")
    estado = models.CharField(max_length=2, verbose_name="Estado")
    cep = models.CharField(max_length=9, verbose_name="CEP")
    pacientes = models.ForeignKey(
        "pacientes.Paciente",
        on_delete=models.CASCADE,
        related_name="enderecos",
        verbose_name="pacientes",
        null=True,
        blank=True,
    )
    profissionais = models.ForeignKey(
        "profissionais.Profissional",
        on_delete=models.CASCADE,
        related_name="enderecos",
        verbose_name="profissionais",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Endereço"
        verbose_name_plural = "Endereços"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(pacientes__isnull=False, profissionais__isnull=True)
                    | models.Q(pacientes__isnull=True, profissionais__isnull=False)
                ),
                name="endereco_com_um_unico_dono",
            )
        ]

    def __str__(self):
        return f"{self.logradouro}, {self.numero} - {self.cidade}/{self.estado}"
