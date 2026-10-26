import uuid as uuid_lib
from django.db import models
from django.db.models import UUIDField
from django.contrib.auth.models import AbstractUser
from .managers import UserManager


class User(AbstractUser):
    username = None  # remove the username field
    email = models.EmailField("email address", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

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
