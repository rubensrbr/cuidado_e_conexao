import uuid as uuid_lib
from django.db import models
from django.utils import timezone
from django.db.models import UUIDField
from django.db.models.functions import Lower
from django.contrib.auth.models import AbstractUser
from .managers import UserManager


class User(AbstractUser):
    username = None  # remove the username field
    email = models.EmailField(
        "E-mail",
        unique=True,
        error_messages={"unique": "Já existe um usuário com este e-mail."},
    )
    change_password = models.BooleanField(
        default=False,
        verbose_name="Trocar a senha no próximo acesso",
        help_text="Se marcado, o usuário só usa o sistema depois de definir uma nova senha.",
    )

    cadastro_pendente = models.BooleanField(
        default=False,
        verbose_name="Cadastro aguardando aprovação",
        help_text=(
            "Conta criada pelo cadastro público. Fica inativa até um administrador "
            "aprovar (ação \"Aprovar cadastros\" ou marcando \"Ativo\")."
        ),
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta(AbstractUser.Meta):
        constraints = [
            # `unique=True` diferencia maiúsculas de minúsculas; esta garante,
            # no banco, que "Ana@x.com" e "ana@x.com" não sejam duas pessoas.
            models.UniqueConstraint(
                Lower("email"),
                name="user_email_unico_ci",
                violation_error_message="Já existe um usuário com este e-mail.",
            ),
        ]

    def save(self, *args, **kwargs):
        # O manager já padroniza, mas o admin e os formulários não passam por
        # ele: sem isto o login (que não diferencia maiúsculas) ficaria
        # ambíguo para e-mails gravados com letras maiúsculas.
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class TimeStamped(models.Model):
    created_at = models.DateTimeField(
        null=True,
        blank=True,
        auto_now_add=True,
    )
    modified_at = models.DateTimeField(
        null=True,
        blank=True,
        auto_now=True,
    )

    class Meta:
        abstract = True


class BaseModel(TimeStamped):
    uuid = models.UUIDField(
        unique=True,
        editable=False,
        default=uuid_lib.uuid4,
    )

    class Meta:
        abstract = True


class TentativaDeCadastro(models.Model):
    """Um envio do formulário de cadastro, guardado para limitar abusos por IP.

    Fica no banco (e não no cache) porque o servidor roda com vários processos,
    e o cache em memória de cada um contaria separado.
    """

    ip = models.GenericIPAddressField()
    criada_em = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["ip", "criada_em"])]

    def __str__(self):
        return f"{self.ip} em {self.criada_em:%d/%m/%Y %H:%M}"


class TentativaDeLogin(models.Model):
    """Um login que falhou, guardado para limitar tentativas por IP.

    Só falhas entram na conta (quem acerta a senha não é punido) e, como no
    cadastro, ficam no banco porque o servidor roda com vários processos.
    """

    ip = models.GenericIPAddressField()
    criada_em = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["ip", "criada_em"])]

    def __str__(self):
        return f"{self.ip} em {self.criada_em:%d/%m/%Y %H:%M}"
