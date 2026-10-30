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
                    "cadastro_pendente",
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
        "cadastro_pendente",
        "change_password",
    )
    list_filter = (
        "cadastro_pendente",
        "is_staff",
        "is_superuser",
        "is_active",
        "change_password",
        "groups",
    )
    search_fields = ("first_name", "last_name", "email")
    ordering = ("email",)
    actions = ["aprovar_cadastros", "exigir_troca_de_senha"]

    def save_model(self, request, obj, form, change):
        # Marcar "Ativo" à mão também aprova o cadastro.
        if obj.is_active and obj.cadastro_pendente:
            obj.cadastro_pendente = False
        super().save_model(request, obj, form, change)

    @admin.action(description="Aprovar cadastros selecionados")
    def aprovar_cadastros(self, request, queryset):
        total = queryset.filter(cadastro_pendente=True).update(
            is_active=True, cadastro_pendente=False
        )
        self.message_user(
            request,
            f"{total} cadastro(s) aprovado(s). Para dar acesso a uma clínica, "
            "crie o vínculo (Membro) da pessoa com ela.",
            messages.SUCCESS,
        )

    @admin.action(description="Exigir troca de senha no próximo acesso")
    def exigir_troca_de_senha(self, request, queryset):
        total = queryset.update(change_password=True)
        self.message_user(
            request,
            f"{total} usuário(s) precisarão definir uma nova senha no próximo acesso.",
            messages.SUCCESS,
        )
