from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from .forms import FaturamentoForm
from .models import Faturamento
from clinicas.permissions import (
    PermissaoAdicionar,
    PermissaoAlterar,
    PermissaoExcluir,
    PermissaoVer,
)


class FaturamentoListView(PermissaoVer, ListView):
    model = Faturamento
    template_name = "faturamentos/faturamento_list.html"
    context_object_name = "faturamentos"
    paginate_by = 10


class FaturamentoDetailView(PermissaoVer, DetailView):
    model = Faturamento
    template_name = "faturamentos/faturamento_detail.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"


class FaturamentoCreateView(PermissaoAdicionar, CreateView):
    model = Faturamento
    template_name = "faturamentos/faturamento_form.html"
    form_class = FaturamentoForm
    success_url = reverse_lazy("faturamentos:faturamento_list")


class FaturamentoUpdateView(PermissaoAlterar, UpdateView):
    model = Faturamento
    template_name = "faturamentos/faturamento_form.html"
    form_class = FaturamentoForm
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("faturamentos:faturamento_list")


class FaturamentoDeleteView(PermissaoExcluir, DeleteView):
    model = Faturamento
    template_name = "faturamentos/faturamento_confirm_delete.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("faturamentos:faturamento_list")
