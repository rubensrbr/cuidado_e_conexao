import uuid as uuid_lib
from django.db import models
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
