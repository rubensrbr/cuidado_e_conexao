from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from .models import Sala, AgendaSala
from .forms import SalaForm, AgendaSalaForm


# --- Sala Views ---
class SalaListView(ListView):
    model = Sala
    template_name = "salas/sala_list.html"
    context_object_name = "salas"


class SalaCreateView(CreateView):
    model = Sala
    template_name = "salas/sala_form.html"
    form_class = SalaForm
    success_url = reverse_lazy("salas:sala_list")


class SalaUpdateView(UpdateView):
    model = Sala
    template_name = "salas/sala_form.html"
    form_class = SalaForm
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("salas:sala_list")


# --- AgendaSala Views ---
class AgendaSalaListView(ListView):
    model = AgendaSala
    template_name = "salas/agendasala_list.html"
    context_object_name = "agendamentos"


class AgendaSalaCreateView(CreateView):
    model = AgendaSala
    form_class = AgendaSalaForm
    template_name = "salas/agendasala_form.html"
    success_url = reverse_lazy("salas:agendasala_list")


class AgendaSalaUpdateView(UpdateView):
    model = AgendaSala
    template_name = "salas/agendasala_form.html"
    form_class = AgendaSalaForm
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("salas:agendasala_list")
