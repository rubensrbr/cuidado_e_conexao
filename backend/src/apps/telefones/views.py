from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DeleteView,
)

from .models import Telefone
from .forms import TelefoneForm


class TelefoneListView(ListView):
    model = Telefone
    template_name = "telefones/telefone_list.html"
    context_object_name = "telefones"


class TelefoneCreateView(CreateView):
    model = Telefone
    template_name = "telefones/telefone_form.html"
    form_class = TelefoneForm
    success_url = reverse_lazy("telefones:telefone_list")


class TelefoneUpdateView(UpdateView):
    model = Telefone
    template_name = "telefones/endereco_form.html"
    form_class = TelefoneForm
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("telefones:telefone_list")


class TelefoneDeleteView(DeleteView):
    model = Telefone
    template_name = "telefones/telefone_confirm_delete.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("telefones:telefone_list")
