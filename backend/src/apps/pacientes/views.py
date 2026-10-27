from django.contrib import messages
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

from .forms import PacienteForm, ProntuarioForm, TelefoneFormSet
from telefones.models import Telefone

from .models import Paciente, Prontuario
from clinicas.permissions import (
    PermissaoAdicionar,
    PermissaoAlterar,
    PermissaoExcluir,
    PermissaoVer,
)


class PacienteListView(PermissaoVer, ListView):
    model = Paciente
    template_name = "pacientes/paciente_list.html"
    context_object_name = "pacientes"
    paginate_by = 10

    def get_queryset(self):
        # Uma query extra para todos os telefones da página (evita N+1),
        # com o telefone principal primeiro.
        return (
            super()
            .get_queryset()
            .prefetch_related(
                Prefetch(
                    "telefones", queryset=Telefone.objects.order_by("-principal", "id")
                )
            )
        )


class PacienteDetailView(PermissaoVer, DetailView):
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
    success_message = "Paciente salvo com sucesso!"

    def get_telefone_formset(self):
        return TelefoneFormSet(
            self.request.POST or None,
            instance=self.object,
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

        messages.success(self.request, self.success_message)

        return redirect(self.get_success_url())

    def form_invalid(self, form):
        # Mantém o que foi digitado nos telefones e mostra os erros deles também.
        telefone_formset = self.get_telefone_formset()
        telefone_formset.is_valid()
        return self.render_to_response(
            self.get_context_data(form=form, telefone_formset=telefone_formset)
        )


class PacienteCreateView(PermissaoAdicionar, PacienteFormsetMixin, CreateView):
    pass


class PacienteUpdateView(PermissaoAlterar, PacienteFormsetMixin, UpdateView):
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_message = "Paciente atualizado com sucesso!"


class PacienteDeleteView(PermissaoExcluir, DeleteView):
    model = Paciente
    template_name = "pacientes/paciente_confirm_delete.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("pacientes:paciente_list")


# --- Prontuario Views ---
class ProntuarioDetailView(PermissaoVer, DetailView):
    model = Prontuario
    template_name = "pacientes/prontuario_detail.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"


class ProntuarioCreateView(PermissaoAdicionar, CreateView):
    model = Prontuario
    template_name = "pacientes/prontuario_form.html"
    # form_class (e não `fields`) para usar o TenantFormMixin: só pacientes da
    # clínica atual aparecem e são aceitos.
    form_class = ProntuarioForm

    def get_success_url(self):
        return reverse_lazy(
            "pacientes:paciente_detail", kwargs={"uuid": self.object.paciente.uuid}
        )
