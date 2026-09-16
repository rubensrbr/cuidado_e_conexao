import uuid as uuid_lib
from django.db import models
from django.db.models import UUIDField
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    def save(self, *args, **kwargs):
        if self.password and not self.password.startswith(
            ("pbkdf2_", "bcrypt_", "argon2", "scrypt")
        ):
            raw_password = self.password
            self.set_password(raw_password)
        super().save(*args, **kwargs)


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
