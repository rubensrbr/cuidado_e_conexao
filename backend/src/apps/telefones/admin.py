from django.contrib import admin

from .forms import TelefoneForm
from .models import Telefone


@admin.register(Telefone)
class TelefoneAdmin(admin.ModelAdmin):
    form = TelefoneForm
    list_display = ("numero", "tipo", "principal")
    list_filter = ("tipo", "principal")
    search_fields = ("numero",)
    readonly_fields = ("uuid", "created_at", "modified_at")
