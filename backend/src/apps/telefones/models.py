from django.db import models
from django.core.validators import RegexValidator
from core.models import BaseModel


class Telefone(BaseModel):
    """Telefones para pacientes e profissionais"""

    TIPO_CHOICES = [
        ("residencial", "Residencial"),
        ("celular", "Celular"),
        ("comercial", "Comercial"),
        ("recado", "Recado"),
    ]

    numero = models.CharField(
        max_length=20,
        verbose_name="Número",
        validators=[
            RegexValidator(
                regex=r"^\+?1?\d{9,15}$", message="Número de telefone inválido"
            )
        ],
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo")
    principal = models.BooleanField(default=False, verbose_name="Principal")
    pacientes = models.ForeignKey(
        "pacientes.Paciente",
        on_delete=models.CASCADE,
        related_name="telefones",
        verbose_name="pacientes",
    )
    profissionais = models.ForeignKey(
        "profissionais.Profissional",
        on_delete=models.CASCADE,
        related_name="profissionais",
        verbose_name="profissionais",
    )

    class Meta:
        verbose_name = "Telefone"
        verbose_name_plural = "Telefones"

    def __str__(self):
        return f"{self.numero} ({self.get_tipo_display()})"
