from core.models import BaseModel
from django.db import models


class Estado(BaseModel):
    codigo_ibge = models.PositiveSmallIntegerField(unique=True)
    sigla = models.CharField(max_length=2, unique=True)
    nome = models.CharField(max_length=50)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.sigla


class Cidade(BaseModel):
    codigo_ibge = models.PositiveIntegerField(unique=True)
    nome = models.CharField(max_length=100)
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT, related_name="cidades")

    class Meta:
        ordering = ["nome"]
        indexes = [models.Index(fields=["estado", "nome"])]

    def __str__(self):
        return f"{self.nome}/{self.estado.sigla}"
