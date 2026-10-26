from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import UserChangeForm, UserCreationForm
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Admin for the custom core.User model (login por e-mail, sem username)."""

    add_form = UserCreationForm
    form = UserChangeForm
    model = User

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Dados pessoais", {"fields": ("first_name", "last_name")}),
        (
            "Permissões",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Segurança", {"fields": ("change_password",)}),
        ("Datas importantes", {"fields": ("last_login", "date_joined")}),
    )

    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "change_password",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "change_password", "groups")
    search_fields = ("first_name", "last_name", "email")
    ordering = ("email",)
    actions = ["exigir_troca_de_senha"]

    @admin.action(description="Exigir troca de senha no próximo acesso")
    def exigir_troca_de_senha(self, request, queryset):
        total = queryset.update(change_password=True)
        self.message_user(
            request,
            f"{total} usuário(s) precisarão definir uma nova senha no próximo acesso.",
            messages.SUCCESS,
        )
