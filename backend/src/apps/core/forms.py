from django import forms
from django.contrib.auth.forms import AdminUserCreationForm as BaseUserCreationForm
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm

from .models import User


class UserCreationForm(BaseUserCreationForm):
    """Form used by the admin to create new users, pointed at core.User.

    Subclasses AdminUserCreationForm (rather than the plain UserCreationForm)
    because that's the one that declares the "usable_password" field the
    stock UserAdmin.add_fieldsets expects.
    """

    email = forms.EmailField(required=False, label="E-mail")

    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name")


class UserChangeForm(BaseUserChangeForm):
    """Form used to edit existing users."""

    class Meta(BaseUserChangeForm.Meta):
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
        )
