from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from .models import Profissional, Disponibilidade
from .forms import (
    DisponibilidadeForm,
    EnderecoFormSet,
    ProfissionalForm,
    TelefoneFormSet,
)


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


class ProfissionalFormsetMixin:
    """Salva o profissional, seus telefones e endereços (inline formsets)
    na mesma transação."""

    model = Profissional
    form_class = ProfissionalForm
    template_name = "profissionais/profissional_form.html"
    success_url = reverse_lazy("profissionais:profissional_list")

    def get_formsets(self):
        data = self.request.POST if self.request.method == "POST" else None
        return {
            "telefone_formset": TelefoneFormSet(
                data,
                instance=self.object,  # None ao criar
                prefix="telefones",
            ),
            "endereco_formset": EnderecoFormSet(
                data,
                instance=self.object,
                prefix="enderecos",
            ),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for name, formset in self.get_formsets().items():
            context.setdefault(name, formset)
        return context

    def form_valid(self, form):
        formsets = self.get_formsets()
        # all([...]) valida todos (sem curto-circuito) para exibir todos os erros.
        if not all([formset.is_valid() for formset in formsets.values()]):
            return self.render_to_response(self.get_context_data(form=form, **formsets))
        with transaction.atomic():
            self.object = form.save()
            for formset in formsets.values():
                formset.instance = self.object
                formset.save()
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        # Mantém o que foi digitado nos formsets e mostra os erros deles também.
        formsets = self.get_formsets()
        for formset in formsets.values():
            formset.is_valid()
        return self.render_to_response(self.get_context_data(form=form, **formsets))


class ProfissionalCreateView(ProfissionalFormsetMixin, CreateView):
    pass


class ProfissionalUpdateView(ProfissionalFormsetMixin, UpdateView):
    slug_field = "uuid"
    slug_url_kwarg = "uuid"


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
