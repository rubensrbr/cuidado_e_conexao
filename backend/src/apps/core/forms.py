from django import forms
from django.contrib.auth.forms import AdminUserCreationForm as BaseUserCreationForm
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.forms import BaseUserCreationForm as ContaUserCreationForm
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


class CadastroForm(ContaUserCreationForm):
    """Cadastro público de conta.

    Cria só a conta (nunca staff nem superusuário). Ela não dá acesso a nenhuma
    clínica: isso só acontece quando um administrador cria o vínculo (`Membro`).
    """

    error_messages = {
        **ContaUserCreationForm.error_messages,
        "password_mismatch": "As duas senhas digitadas não são iguais.",
    }

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].label = "Nome"
        self.fields["last_name"].label = "Sobrenome"
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["password1"].label = "Senha"
        self.fields["password2"].label = "Confirmar senha"
        self.fields["password2"].help_text = (
            "Digite a mesma senha novamente, para confirmação."
        )
        placeholders = {
            "first_name": "Digite seu nome",
            "last_name": "Digite seu sobrenome",
            "email": "Digite seu e-mail",
            "password1": "Crie uma senha",
            "password2": "Repita a senha",
        }
        for nome, campo in self.fields.items():
            campo.widget.attrs["class"] = "form-control"
            campo.widget.attrs["placeholder"] = placeholders[nome]
            campo.error_messages["required"] = "Este campo é obrigatório."
        self.fields["first_name"].widget.attrs["autofocus"] = True
        self.fields["first_name"].widget.attrs["autocomplete"] = "given-name"
        self.fields["last_name"].widget.attrs["autocomplete"] = "family-name"
