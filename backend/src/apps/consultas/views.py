from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from .forms import ConsultaForm
from .models import Consulta, Lembrete, ListaEspera


# --- Consulta Views ---
class ConsultaListView(ListView):
    model = Consulta
    template_name = "consultas/consulta_list.html"
    context_object_name = "consultas"
    paginate_by = 10

    def get_queryset(self):
        # Paciente e profissional vêm no mesmo SELECT (evita N+1 na tabela).
        return super().get_queryset().select_related("paciente", "profissional")


class ConsultaDetailView(DetailView):
    model = Consulta
    template_name = "consultas/consulta_detail.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"


class ConsultaCreateView(CreateView):
    model = Consulta
    template_name = "consultas/consulta_form.html"
    form_class = ConsultaForm
    success_url = reverse_lazy("consultas:consulta_list")


class ConsultaUpdateView(UpdateView):
    model = Consulta
    template_name = "consultas/consulta_form.html"
    form_class = ConsultaForm
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
