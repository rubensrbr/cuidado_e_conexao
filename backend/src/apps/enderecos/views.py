from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)

from .models import Endereco
from .forms import EnderecoForm


class EnderecoListView(ListView):
    model = Endereco
    template_name = "enderecos/endereco_list.html"
    context_object_name = "enderecos"


class EnderecoCreateView(CreateView):
    model = Endereco
    template_name = "enderecos/endereco_form.html"
    form_class = EnderecoForm
    success_url = reverse_lazy("enderecos:endereco_list")


class EnderecoUpdateView(UpdateView):
    model = Endereco
    template_name = "enderecos/endereco_form.html"
    form_class = EnderecoForm
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("enderecos:endereco_list")


class EnderecoDeleteView(DeleteView):
    model = Endereco
    template_name = "enderecos/endereco_confirm_delete.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("enderecos:endereco_list")
