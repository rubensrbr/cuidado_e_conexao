from django.db import models

from core.models import BaseModel

from .validators import (
    somente_digitos,
    validar_cnpj,
    validar_slug_nao_reservado,
)


class Clinica(BaseModel):
    """
    Tenant do sistema: cada clínica enxerga apenas os próprios dados.

    Os modelos de negócio (Paciente, Profissional, Consulta, ...) passarão a
    apontar para esta tabela por uma ForeignKey `clinica`.
    """

    nome = models.CharField(max_length=150, verbose_name="Nome fantasia")
    razao_social = models.CharField(
        max_length=200, blank=True, verbose_name="Razão social"
    )
    cnpj = models.CharField(
        max_length=18,
        unique=True,
        validators=[validar_cnpj],
        verbose_name="CNPJ",
        help_text="Somente números (a máscara é removida ao salvar).",
    )
    slug = models.SlugField(
        max_length=63,
        unique=True,
        validators=[validar_slug_nao_reservado],
        verbose_name="Identificador",
        help_text="Usado na URL/subdomínio da clínica. Não altere depois de em uso.",
    )
    email = models.EmailField(blank=True, verbose_name="E-mail de contato")
    ativa = models.BooleanField(
        default=True,
        verbose_name="Ativa",
        help_text="Desmarque para suspender o acesso da clínica sem apagar dados.",
    )

    class Meta:
        verbose_name = "Clínica"
        verbose_name_plural = "Clínicas"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def clean(self):
        # Roda antes de validate_unique: sem isso, "11.222.333/0001-81" não seria
        # reconhecido como duplicata de "11222333000181" nos formulários/admin.
        super().clean()
        self.cnpj = somente_digitos(self.cnpj)

    def save(self, *args, **kwargs):
        # Guarda só dígitos: "11.222.333/0001-81" e "11222333000181" são a mesma clínica.
        self.cnpj = somente_digitos(self.cnpj)
        super().save(*args, **kwargs)

    @property
    def cnpj_formatado(self):
        c = self.cnpj
        if len(c) != 14:
            return c
        return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
