from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from .models import Faturamento


class FaturamentoListView(ListView):
    model = Faturamento
    template_name = "faturamentos/faturamento_list.html"
    context_object_name = "faturamentos"
    paginate_by = 10


class FaturamentoDetailView(DetailView):
    model = Faturamento
    template_name = "faturamentos/faturamento_detail.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"


class FaturamentoCreateView(CreateView):
    model = Faturamento
    template_name = "faturamentos/faturamento_form.html"
    fields = [
        "paciente",
        "consulta",
        "data_servico",
        "valor_cobrado",
        "valor_pago",
        "valor_convenio",
        "metodo_pagamento",
        "status_pagamento",
        "numero_nota",
        "observacoes",
    ]
    success_url = reverse_lazy("faturamentos:faturamento_list")


class FaturamentoUpdateView(UpdateView):
    model = Faturamento
    template_name = "faturamentos/faturamento_form.html"
    fields = [
        "paciente",
        "consulta",
        "data_servico",
        "valor_cobrado",
        "valor_pago",
        "valor_convenio",
        "metodo_pagamento",
        "status_pagamento",
        "numero_nota",
        "observacoes",
    ]
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("faturamentos:faturamento_list")


class FaturamentoDeleteView(DeleteView):
    model = Faturamento
    template_name = "faturamentos/faturamento_confirm_delete.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("faturamentos:faturamento_list")
