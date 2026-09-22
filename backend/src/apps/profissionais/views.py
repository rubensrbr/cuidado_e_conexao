from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from .models import Profissional, Disponibilidade
from .forms import ProfissionalForm, DisponibilidadeForm


# --- Profissional Views ---
class ProfissionalListView(ListView):
    model = Profissional
    template_name = "profissionais/profissional_list.html"
    context_object_name = "profissionais"
    paginate_by = 10


class ProfissionalDetailView(DetailView):
    model = Profissional
    template_name = "profissionais/profissional_detail.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"


class ProfissionalCreateView(CreateView):
    model = Profissional
    template_name = "profissionais/profissional_form.html"
    form_class = ProfissionalForm
    success_url = reverse_lazy("profissionais:profissional_list")


class ProfissionalUpdateView(UpdateView):
    model = Profissional
    template_name = "profissionais/profissional_form.html"
    form_class = ProfissionalForm
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("profissionais:profissional_list")


class ProfissionalDeleteView(DeleteView):
    model = Profissional
    template_name = "profissionais/profissional_confirm_delete.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("profissionais:profissional_list")


# --- Disponibilidade Views ---
class DisponibilidadeCreateView(CreateView):
    model = Disponibilidade
    template_name = "profissionais/disponibilidade_form.html"
    form_class = DisponibilidadeForm
    success_url = reverse_lazy("profissionais:profissional_list")
