from django import forms
from django.contrib.auth.forms import AdminUserCreationForm as BaseUserCreationForm
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm

from .models import User


class UserCreationForm(BaseUserCreationForm):
    """Form used by the admin to create new users, pointed at core.User.

    Subclasses AdminUserCreationForm (rather than the plain UserCreationForm)
    because that's the one that declares the "usable_password" field the
    stock UserAdmin.add_fieldsets expects.
    """

    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ("email", "first_name", "last_name")


class UserChangeForm(BaseUserChangeForm):
    """Form used to edit existing users."""

    class Meta(BaseUserChangeForm.Meta):
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "change_password",
            "groups",
            "user_permissions",
        )


class LoginForm(AuthenticationForm):
    """Login por e-mail (o campo continua se chamando `username` por dentro)."""

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "E-mail ou senha inválidos.",
    }


class TrocaDeSenhaForm(PasswordChangeForm):
    """Troca de senha com o visual dos demais formulários do sistema."""

    error_messages = {
        **PasswordChangeForm.error_messages,
        "password_incorrect": "Sua senha atual está incorreta. Digite-a novamente.",
        "password_mismatch": "As duas senhas digitadas não são iguais.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "form-control"
            campo.error_messages["required"] = "Este campo é obrigatório."
        self.fields["new_password2"].help_text = (
            "Digite a mesma senha novamente, para confirmação."
        )
