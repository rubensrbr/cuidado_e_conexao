from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)

from .forms import PacienteForm, TelefoneFormSet
from .models import Paciente, Prontuario


class PacienteListView(ListView):
    model = Paciente
    template_name = "pacientes/paciente_list.html"
    context_object_name = "pacientes"
    paginate_by = 10


class PacienteDetailView(DetailView):
    model = Paciente
    template_name = "pacientes/paciente_detail.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"


class PacienteCreateView(CreateView):
    model = Paciente
    template_name = "pacientes/paciente_form.html"
    form_class = PacienteForm
    success_url = reverse_lazy("pacientes:paciente_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context["telefone_formset"] = TelefoneFormSet(
                self.request.POST,
                instance=self.object,
            )
        else:
            context
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        telefone_formset = context["telefone_formset"]

        if telefone_formset.is_valid():
            self.object = form.save()
            telefone_formset.instance = self.object
            telefone_formset.save()

            return redirect(self.success_url)

        return self.form_invalid(form)


class PacienteUpdateView(UpdateView):
    model = Paciente
    template_name = "pacientes/paciente_form.html"
    fields = [
        "primeiro_nome",
        "sobrenome",
        "data_nascimento",
        "genero",
        "email",
        "convenio",
        "numero_carteirinha",
        "ativo",
    ]
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("pacientes:paciente_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context["telefone_formset"] = TelefoneFormSet(
                self.request.POST,
                instance=self.object,
            )
        else:
            context["telefone_formset"] = TelefoneFormSet(instance=self.object)

        return context

    def form_valid(self, form):
        context = self.get_context_data()
        telefone_formset = context["telefone_formset"]

        if telefone_formset.is_valid():
            self.object = form.save()
            telefone_formset.instance = self.object
            telefone_formset.save()

            return redirect(self.success_url)

        return self.form_invalid(form)


class PacienteDeleteView(DeleteView):
    model = Paciente
    template_name = "pacientes/paciente_confirm_delete.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("pacientes:paciente_list")


# --- Prontuario Views ---
class ProntuarioDetailView(DetailView):
    model = Prontuario
    template_name = "pacientes/prontuario_detail.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"


class ProntuarioCreateView(CreateView):
    model = Prontuario
    template_name = "pacientes/prontuario_form.html"
    fields = [
        "paciente",
        "profissional",
        "consulta",
        "data_registro",
        "codigo_cid",
        "queixa_principal",
        "plano_tratamento",
        "evolucao",
        "medicamentos",
        "avaliacao_risco",
    ]

    def get_success_url(self):
        return reverse_lazy(
            "pacientes:paciente_detail", kwargs={"uuid": self.object.paciente.uuid}
        )
