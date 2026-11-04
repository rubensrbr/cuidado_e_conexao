from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, F, Q, RestrictedError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.functional import cached_property
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from consultas.models import Consulta

from .forms import FaturamentoForm, PacoteForm, SessaoPacoteForm
from .models import Faturamento, Pacote, SessaoPacote
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


class FaturamentoCreateView(PermissaoAdicionar, SuccessMessageMixin, CreateView):
    model = Faturamento
    template_name = "faturamentos/faturamento_form.html"
    form_class = FaturamentoForm
    success_url = reverse_lazy("faturamentos:faturamento_list")
    success_message = "Faturamento salvo com sucesso!"


class FaturamentoUpdateView(PermissaoAlterar, SuccessMessageMixin, UpdateView):
    model = Faturamento
    template_name = "faturamentos/faturamento_form.html"
    form_class = FaturamentoForm
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("faturamentos:faturamento_list")
    success_message = "Faturamento atualizado com sucesso!"


class FaturamentoDeleteView(PermissaoExcluir, DeleteView):
    model = Faturamento
    template_name = "faturamentos/faturamento_confirm_delete.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("faturamentos:faturamento_list")


class PacoteListView(PermissaoVer, ListView):
    """Lista de pacotes da clínica atual.

    `qtd_sessoes_usadas` e `qtd_saldo` vêm anotados na própria query para a
    lista não fazer uma consulta por linha (as propriedades `sessoes_usadas` e
    `saldo` do model fazem uma query cada). Usam a mesma regra de
    `Pacote.STATUS_QUE_CONSOMEM_SESSAO`.
    """

    model = Pacote
    template_name = "faturamentos/pacote_list.html"
    context_object_name = "pacotes"
    paginate_by = 10

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("paciente", "profissional")
            .annotate(
                qtd_sessoes_usadas=Count(
                    "sessoes",
                    filter=Q(
                        sessoes__consulta__status__in=Pacote.STATUS_QUE_CONSOMEM_SESSAO
                    ),
                )
            )
            .annotate(qtd_saldo=F("quantidade_sessoes") - F("qtd_sessoes_usadas"))
            .order_by("-data_compra", "-created_at")
        )


class PacoteDetailView(PermissaoVer, DetailView):
    model = Pacote
    template_name = "faturamentos/pacote_detail.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_queryset(self):
        return super().get_queryset().select_related("paciente", "profissional")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sessoes"] = self.object.sessoes.select_related(
            "consulta", "consulta__profissional"
        )
        context["faturamentos"] = self.object.faturamentos.all()
        return context


class PacoteCreateView(PermissaoAdicionar, SuccessMessageMixin, CreateView):
    model = Pacote
    template_name = "faturamentos/pacote_form.html"
    form_class = PacoteForm
    success_url = reverse_lazy("faturamentos:pacote_list")
    success_message = "Pacote salvo com sucesso!"


class PacoteUpdateView(PermissaoAlterar, SuccessMessageMixin, UpdateView):
    model = Pacote
    template_name = "faturamentos/pacote_form.html"
    form_class = PacoteForm
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("faturamentos:pacote_list")
    success_message = "Pacote atualizado com sucesso!"


class PacoteDeleteView(PermissaoExcluir, DeleteView):
    model = Pacote
    template_name = "faturamentos/pacote_confirm_delete.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("faturamentos:pacote_list")

    def form_valid(self, form):
        # `Faturamento.pacote` é RESTRICT: pacote com cobrança não pode ser
        # apagado. Sem este tratamento o usuário veria um erro 500.
        try:
            return super().form_valid(form)
        except RestrictedError:
            messages.error(
                self.request,
                "Este pacote tem cobranças registradas e não pode ser excluído. "
                "Altere o status para Cancelado.",
            )
            return redirect(
                reverse("faturamentos:pacote_detail", kwargs={"uuid": self.object.uuid})
            )


class SessaoPacoteCreateView(PermissaoAdicionar, SuccessMessageMixin, CreateView):
    """Vincula uma consulta a um pacote (a consulta passa a gastar uma sessão).

    O pacote vem da URL (`<uuid:uuid>` do pacote) e não pode ser trocado no
    formulário. As consultas oferecidas são só as do mesmo paciente (e do mesmo
    profissional, se o pacote for de um só), ainda sem pacote e não canceladas.
    As demais regras (pacote ativo, sessões disponíveis) ficam em
    `SessaoPacote.clean`.
    """

    model = SessaoPacote
    template_name = "faturamentos/sessaopacote_form.html"
    form_class = SessaoPacoteForm
    success_message = "Consulta vinculada ao pacote com sucesso!"

    @cached_property
    def pacote(self):
        return get_object_or_404(Pacote, uuid=self.kwargs["uuid"])

    def get_initial(self):
        initial = super().get_initial()
        initial["pacote"] = self.pacote.pk
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        pacote = self.pacote

        campo_pacote = form.fields["pacote"]
        campo_pacote.queryset = Pacote.objects.filter(pk=pacote.pk)
        campo_pacote.disabled = True

        consultas = Consulta.objects.filter(
            paciente_id=pacote.paciente_id,
            sessao_pacote__isnull=True,
        ).exclude(status="cancelada")
        if pacote.profissional_id:
            consultas = consultas.filter(profissional_id=pacote.profissional_id)
        form.fields["consulta"].queryset = consultas.select_related("profissional")
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pacote"] = self.pacote
        return context

    def get_success_url(self):
        return reverse("faturamentos:pacote_detail", kwargs={"uuid": self.pacote.uuid})


class SessaoPacoteDeleteView(PermissaoExcluir, DeleteView):
    """Desvincula a consulta do pacote (a consulta em si não é apagada)."""

    model = SessaoPacote
    template_name = "faturamentos/sessaopacote_confirm_delete.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_success_url(self):
        return reverse(
            "faturamentos:pacote_detail", kwargs={"uuid": self.object.pacote.uuid}
        )
