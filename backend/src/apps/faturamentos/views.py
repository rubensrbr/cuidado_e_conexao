from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, F, Q, RestrictedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.functional import cached_property
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    TemplateView,
    View,
)
from consultas.models import Consulta
from core.mixins import FiltrosPersistentesMixin

from .filters import FaturamentoFilter, FaturamentoResumoFilter
from .forms import FaturamentoForm, PacoteForm, SessaoPacoteForm
from .models import Faturamento, Pacote, SessaoPacote
from .resumo import mes_atual, periodo_da_query, resumir
from clinicas.permissions import (
    PermissaoAdicionar,
    PermissaoAlterar,
    PermissaoExcluir,
    PermissaoVer,
)


class FaturamentoListView(PermissaoVer, FiltrosPersistentesMixin, ListView):
    model = Faturamento
    filterset_class = FaturamentoFilter
    template_name = "faturamentos/faturamento_list.html"
    context_object_name = "faturamentos"
    paginate_by = 10

    def get_queryset(self):
        # O paciente vem no mesmo SELECT (evita N+1 na tabela).
        queryset = super().get_queryset().select_related("paciente")
        self.filtro = self.filterset_class(
            self.request.GET, queryset=queryset, request=self.request
        )
        if not self.filtro.is_valid():
            # Valor de filtro inválido (data final antes da inicial...) não pode
            # virar "mostrar tudo": a lista fica vazia e o formulário mostra o erro.
            return queryset.none()
        return self.filtro.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filtro"] = self.filtro
        context["filtros_ativos"] = sum(
            1 for nome in self.filtro.filters if self.request.GET.get(nome, "").strip()
        )
        _contexto_do_periodo(context, self.request)
        return context


def _contexto_do_periodo(context, request):
    """Período atual da tela, para as abas (Lista/Resumo) o levarem de uma à outra."""
    periodo = periodo_da_query(request.GET)
    context["periodo_qs"] = periodo
    context["periodo_query"] = f"?{periodo}" if periodo else ""


class FaturamentoResumoView(PermissaoVer, TemplateView):
    """Aba "Resumo": cards com o panorama financeiro do período.

    Sem período na URL, abre no mês atual. Período em branco (campos enviados
    vazios) significa "todo o período". Usa o manager padrão de `Faturamento`,
    então só soma a clínica atual.
    """

    model = Faturamento  # usado só para montar a permissão (view_faturamento)
    template_name = "faturamentos/faturamento_resumo.html"

    def get(self, request, *args, **kwargs):
        if not any(nome in request.GET for nome in ("data_de", "data_ate")):
            inicio, fim = mes_atual()
            parametros = urlencode({"data_de": inicio, "data_ate": fim})
            return redirect(f"{request.path}?{parametros}")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = Faturamento.objects.all()
        filtro = FaturamentoResumoFilter(
            self.request.GET, queryset=queryset, request=self.request
        )
        # Período inválido não pode virar "todos os faturamentos" (igual à lista).
        valido = filtro.is_valid()
        context["filtro"] = filtro
        context["resumo"] = resumir(filtro.qs if valido else queryset.none())
        _contexto_do_periodo(context, self.request)
        return context


class FaturamentoPdfReportView(PermissaoVer, View):
    """Relatório em PDF (WeasyPrint) dos faturamentos da clínica atual.

    Usa o manager padrão de `Faturamento`, que já filtra pela clínica da
    requisição; sem clínica atual o relatório sai vazio (falha fechada).
    Respeita os mesmos filtros da lista (a tela repassa a query string no botão),
    mas não é paginado: o PDF traz todos os resultados, não só a página da tela.
    """

    model = Faturamento  # usado só para montar a permissão (view_faturamento)
    filterset_class = FaturamentoFilter
    template_name = "faturamentos/faturamento_report_pdf.html"

    def get_queryset(self):
        return Faturamento.objects.select_related("paciente")

    def get(self, request, *args, **kwargs):
        # Import tardio: o WeasyPrint carrega bibliotecas nativas (Pango). Assim,
        # um ambiente sem elas só afeta esta tela, não a inicialização do Django.
        from weasyprint import HTML, URLFetcher

        queryset = self.get_queryset()
        filtro = self.filterset_class(request.GET, queryset=queryset, request=request)
        # Filtro inválido não pode virar "todos os faturamentos" (igual à lista).
        valido = filtro.is_valid()
        faturamentos = list(filtro.qs if valido else queryset.none())
        dados = filtro.form.cleaned_data if valido else {}
        filtros_ativos = sum(
            1 for nome in filtro.filters if request.GET.get(nome, "").strip()
        )

        # Cobranças canceladas aparecem na tabela, mas não entram nos valores
        # totais (não são dinheiro a receber). Mesmo cálculo da aba Resumo.
        resumo = resumir(filtro.qs if valido else queryset.none())
        total_cobrado = resumo.total_cobrado
        total_pago = resumo.total_pago

        agora = timezone.localtime()
        contexto = {
            "faturamentos": faturamentos,
            "total": len(faturamentos),
            "total_cobrado": total_cobrado,
            "total_pago": total_pago,
            "total_pendente": resumo.total_pendente,
            "filtros_ativos": filtros_ativos,
            "periodo_de": dados.get("data_de"),
            "periodo_ate": dados.get("data_ate"),
            "clinica": request.clinica,
            "gerado_em": agora,
            "gerado_por": request.user.get_full_name() or request.user.get_username(),
        }
        html = render_to_string(self.template_name, contexto, request=request)

        # O documento é autocontido (CSS e logo embutidos): só `data:` é permitido,
        # então o WeasyPrint nunca faz requisições de rede ao renderizar.
        pdf = HTML(
            string=html,
            base_url=str(settings.BASE_DIR),
            url_fetcher=URLFetcher(allowed_protocols={"data"}),
        ).write_pdf()

        resposta = HttpResponse(pdf, content_type="application/pdf")
        nome_arquivo = f"faturamentos_{agora:%Y%m%d}.pdf"
        resposta["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'
        return resposta


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
