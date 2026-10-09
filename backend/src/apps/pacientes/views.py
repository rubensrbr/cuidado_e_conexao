from django.db import transaction
from django.db.models import Prefetch
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
from telefones.models import Telefone

from .models import Paciente, Prontuario


class PacienteListView(ListView):
    model = Paciente
    template_name = "pacientes/paciente_list.html"
    context_object_name = "pacientes"
    paginate_by = 10

    def get_queryset(self):
        # Uma query extra para todos os telefones da página (evita N+1),
        # com o telefone principal primeiro.
        return super().get_queryset().prefetch_related(
            Prefetch("telefones", queryset=Telefone.objects.order_by("-principal", "id"))
        )


class PacienteDetailView(DetailView):
    model = Paciente
    template_name = "pacientes/paciente_detail.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"


class PacienteFormsetMixin:
    """Salva o paciente e seus telefones (inline formset) na mesma transação."""

    model = Paciente
    form_class = PacienteForm
    template_name = "pacientes/paciente_form.html"
    success_url = reverse_lazy("pacientes:paciente_list")

    def get_telefone_formset(self):
        return TelefoneFormSet(
            self.request.POST or None,
            instance=self.object,  # None ao criar
            prefix="telefones",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if "telefone_formset" not in context:
            context["telefone_formset"] = self.get_telefone_formset()
        return context

    def form_valid(self, form):
        telefone_formset = self.get_telefone_formset()
        if not telefone_formset.is_valid():
            return self.render_to_response(
                self.get_context_data(form=form, telefone_formset=telefone_formset)
            )
        with transaction.atomic():
            self.object = form.save()
            telefone_formset.instance = self.object
            telefone_formset.save()
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        # Mantém o que foi digitado nos telefones e mostra os erros deles também.
        telefone_formset = self.get_telefone_formset()
        telefone_formset.is_valid()
        return self.render_to_response(
            self.get_context_data(form=form, telefone_formset=telefone_formset)
        )


class PacienteCreateView(PacienteFormsetMixin, CreateView):
    pass


class PacienteUpdateView(PacienteFormsetMixin, UpdateView):
    slug_field = "uuid"
    slug_url_kwarg = "uuid"


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
