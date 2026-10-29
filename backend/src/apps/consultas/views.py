from django.conf import settings
from django.db.models import Case, IntegerField, When
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    View,
)
from core.mixins import FiltrosPersistentesMixin
from .filters import ConsultaFilter
from .forms import ConsultaForm, LembreteForm, ListaEsperaForm
from .models import Consulta, Lembrete, ListaEspera
from clinicas.permissions import (
    PermissaoAdicionar,
    PermissaoAlterar,
    PermissaoExcluir,
    PermissaoVer,
)


# --- Consulta Views ---
class ConsultaListView(PermissaoVer, FiltrosPersistentesMixin, ListView):
    model = Consulta
    filterset_class = ConsultaFilter
    template_name = "consultas/consulta_list.html"
    context_object_name = "consultas"
    paginate_by = 10

    def get_queryset(self):
        # Paciente e profissional vêm no mesmo SELECT (evita N+1 na tabela).
        queryset = super().get_queryset().select_related("paciente", "profissional")
        self.filtro = self.filterset_class(
            self.request.GET, queryset=queryset, request=self.request
        )
        if not self.filtro.is_valid():
            # Valor de filtro inválido (data final antes da inicial, profissional de
            # outra clínica...) não pode virar "mostrar tudo": a lista fica vazia e
            # o formulário mostra o erro.
            return queryset.none()
        return self.filtro.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filtro"] = self.filtro
        context["filtros_ativos"] = sum(
            1 for nome in self.filtro.filters if self.request.GET.get(nome, "").strip()
        )
        return context


class ConsultaPdfReportView(PermissaoVer, View):
    """Relatório em PDF (WeasyPrint) das consultas da clínica atual.

    Usa o manager padrão de `Consulta`, que já filtra pela clínica da requisição;
    sem clínica atual o relatório sai vazio (falha fechada).
    Respeita os mesmos filtros da lista (a tela repassa a query string no botão),
    mas não é paginado: o PDF traz todos os resultados, não só a página da tela.
    """

    model = Consulta  # usado só para montar a permissão (view_consulta)
    filterset_class = ConsultaFilter
    template_name = "consultas/consulta_report_pdf.html"

    # Agrupamento dos status no resumo do relatório.
    STATUS_EM_ABERTO = {"agendada", "reagendada", "confirmada"}
    STATUS_NAO_COMPARECEU = {"cancelada", "falta"}

    def get_queryset(self):
        return Consulta.objects.select_related("paciente", "profissional")

    def get(self, request, *args, **kwargs):
        # Import tardio: o WeasyPrint carrega bibliotecas nativas (Pango). Assim,
        # um ambiente sem elas só afeta esta tela, não a inicialização do Django.
        from weasyprint import HTML, URLFetcher

        queryset = self.get_queryset()
        filtro = self.filterset_class(request.GET, queryset=queryset, request=request)
        # Filtro inválido não pode virar "todas as consultas" (igual à lista).
        valido = filtro.is_valid()
        consultas = list(filtro.qs if valido else queryset.none())
        dados = filtro.form.cleaned_data if valido else {}
        filtros_ativos = sum(
            1 for nome in filtro.filters if request.GET.get(nome, "").strip()
        )

        agora = timezone.localtime()
        status = [consulta.status for consulta in consultas]
        contexto = {
            "consultas": consultas,
            "total": len(consultas),
            "total_em_aberto": sum(1 for s in status if s in self.STATUS_EM_ABERTO),
            "total_realizadas": status.count("realizada"),
            "total_nao_compareceu": sum(
                1 for s in status if s in self.STATUS_NAO_COMPARECEU
            ),
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
        nome_arquivo = f"consultas_{agora:%Y%m%d}.pdf"
        resposta["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'
        return resposta


class ConsultaDetailView(PermissaoVer, DetailView):
    model = Consulta
    template_name = "consultas/consulta_detail.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"


class ConsultaCreateView(PermissaoAdicionar, CreateView):
    model = Consulta
    template_name = "consultas/consulta_form.html"
    form_class = ConsultaForm
    success_url = reverse_lazy("consultas:consulta_list")


class ConsultaUpdateView(PermissaoAlterar, UpdateView):
    model = Consulta
    template_name = "consultas/consulta_form.html"
    form_class = ConsultaForm
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("consultas:consulta_list")


class ConsultaDeleteView(PermissaoExcluir, DeleteView):
    model = Consulta
    template_name = "consultas/consulta_confirm_delete.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("consultas:consulta_list")


# --- Lembrete Views ---
class LembreteListView(PermissaoVer, ListView):
    model = Lembrete
    template_name = "consultas/lembrete_list.html"
    context_object_name = "lembretes"


class LembreteCreateView(PermissaoAdicionar, CreateView):
    model = Lembrete
    template_name = "consultas/lembrete_form.html"
    # form_class (e não `fields`) para usar o TenantFormMixin: só consultas da
    # clínica atual aparecem e são aceitas.
    form_class = LembreteForm
    success_url = reverse_lazy("consultas:lembrete_list")


# --- ListaEspera Views ---
class ListaEsperaListView(PermissaoVer, ListView):
    model = ListaEspera
    template_name = "consultas/lista_espera_list.html"
    context_object_name = "lista_espera"

    def get_queryset(self):
        # Fila de atendimento: mais urgente primeiro e, na mesma prioridade, quem espera há mais tempo.
        ordem_prioridade = Case(
            When(prioridade="urgente", then=0),
            When(prioridade="alta", then=1),
            When(prioridade="normal", then=2),
            default=3,
            output_field=IntegerField(),
        )
        return (
            super()
            .get_queryset()
            .select_related("paciente", "profissional_preferido")
            .order_by(ordem_prioridade, "created_at")
        )


class ListaEsperaCreateView(PermissaoAdicionar, CreateView):
    model = ListaEspera
    template_name = "consultas/lista_espera_form.html"
    form_class = ListaEsperaForm
    success_url = reverse_lazy("consultas:lista_espera_list")


class ListaEsperaUpdateView(PermissaoAlterar, UpdateView):
    model = ListaEspera
    template_name = "consultas/lista_espera_form.html"
    form_class = ListaEsperaForm
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("consultas:lista_espera_list")


class ListaEsperaDeleteView(PermissaoExcluir, DeleteView):
    model = ListaEspera
    template_name = "consultas/lista_espera_confirm_delete.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("consultas:lista_espera_list")
