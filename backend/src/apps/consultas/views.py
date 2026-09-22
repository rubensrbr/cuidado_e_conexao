from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from .models import Consulta, Lembrete, ListaEspera


# --- Consulta Views ---
class ConsultaListView(ListView):
    model = Consulta
    template_name = "consultas/consulta_list.html"
    context_object_name = "consultas"
    paginate_by = 10


class ConsultaDetailView(DetailView):
    model = Consulta
    template_name = "consultas/consulta_detail.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"


class ConsultaCreateView(CreateView):
    model = Consulta
    template_name = "consultas/consulta_form.html"
    fields = [
        "paciente",
        "profissional",
        "data_consulta",
        "hora_inicio",
        "hora_fim",
        "tipo_consulta",
        "status",
        "notas_sessao",
        "motivo_cancelamento",
    ]
    success_url = reverse_lazy("consultas:consulta_list")


class ConsultaUpdateView(UpdateView):
    model = Consulta
    template_name = "consultas/consulta_form.html"
    fields = [
        "paciente",
        "profissional",
        "data_consulta",
        "hora_inicio",
        "hora_fim",
        "tipo_consulta",
        "status",
        "notas_sessao",
        "motivo_cancelamento",
    ]
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("consultas:consulta_list")


class ConsultaDeleteView(DeleteView):
    model = Consulta
    template_name = "consultas/consulta_confirm_delete.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("consultas:consulta_list")


# --- Lembrete Views ---
class LembreteListView(ListView):
    model = Lembrete
    template_name = "consultas/lembrete_list.html"
    context_object_name = "lembretes"


class LembreteCreateView(CreateView):
    model = Lembrete
    template_name = "consultas/lembrete_form.html"
    fields = ["consulta", "tipo_lembrete", "data_hora_envio", "enviado_em", "status"]
    success_url = reverse_lazy("consultas:lembrete_list")


# --- ListaEspera Views ---
class ListaEsperaListView(ListView):
    model = ListaEspera
    template_name = "consultas/lista_espera_list.html"
    context_object_name = "lista_espera"


class ListaEsperaCreateView(CreateView):
    model = ListaEspera
    template_name = "consultas/lista_espera_form.html"
    fields = [
        "paciente",
        "profissional_preferido",
        "dias_preferidos",
        "horario_preferido",
        "prioridade",
        "observacoes",
        "status",
    ]
    success_url = reverse_lazy("consultas:lista_espera_list")


class ListaEsperaUpdateView(UpdateView):
    model = ListaEspera
    template_name = "consultas/lista_espera_form.html"
    fields = [
        "paciente",
        "profissional_preferido",
        "dias_preferidos",
        "horario_preferido",
        "prioridade",
        "observacoes",
        "status",
    ]
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("consultas:lista_espera_list")
