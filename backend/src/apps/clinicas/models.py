from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models

from core.models import BaseModel

from .tenancy import TenantModel  # noqa: F401  (reexportado: `from clinicas.models import TenantModel`)
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


class Membro(BaseModel):
    """
    Vínculo de um usuário com uma clínica, com o papel que ele exerce nela.

    Um usuário pode ter vários vínculos (um por clínica); o papel é um
    `Group` do Django, cujas permissões valem apenas dentro daquela clínica.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membros",
        verbose_name="Usuário",
    )
    clinica = models.ForeignKey(
        Clinica,
        on_delete=models.CASCADE,
        related_name="membros",
        verbose_name="Clínica",
    )
    grupo = models.ForeignKey(
        Group,
        on_delete=models.PROTECT,
        related_name="membros",
        verbose_name="Papel",
        help_text="Grupo de permissões que o usuário tem nesta clínica.",
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Desmarque para remover o acesso sem apagar o vínculo.",
    )

    class Meta:
        verbose_name = "Membro"
        verbose_name_plural = "Membros"
        ordering = ["clinica__nome", "user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "clinica"], name="membro_unico_por_clinica"
            )
        ]

    def __str__(self):
        return f"{self.user} @ {self.clinica} ({self.grupo})"
