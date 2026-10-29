from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import redirect
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
from telefones.models import Telefone
from .filters import ProfissionalFilter
from .models import Profissional, Disponibilidade
from .forms import (
    DisponibilidadeForm,
    EnderecoFormSet,
    ProfissionalForm,
    TelefoneFormSet,
)
from clinicas.permissions import (
    PermissaoAdicionar,
    PermissaoAlterar,
    PermissaoExcluir,
    PermissaoVer,
)


# --- Profissional Views ---
class ProfissionalListView(PermissaoVer, FiltrosPersistentesMixin, ListView):
    model = Profissional
    filterset_class = ProfissionalFilter
    template_name = "profissionais/profissional_list.html"
    context_object_name = "profissionais"
    paginate_by = 10

    def get_queryset(self):
        # Uma query extra para todos os telefones da página (evita N+1),
        # com o telefone principal primeiro.
        queryset = (
            super()
            .get_queryset()
            .select_related("tipo_profissional")
            .prefetch_related(
                Prefetch(
                    "telefones", queryset=Telefone.objects.order_by("-principal", "id")
                )
            )
        )
        self.filtro = self.filterset_class(
            self.request.GET, queryset=queryset, request=self.request
        )
        if not self.filtro.is_valid():
            # Valor de filtro inválido (especialidade inexistente...) não pode
            # virar "mostrar tudo": a lista fica vazia e o formulário mostra o erro.
            return queryset.none()
        return self.filtro.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filtro"] = self.filtro
        context["filtros_ativos"] = sum(
            1 for nome in self.filtro.filters if self.request.GET.get(nome, "").strip()
        )
        return context


class ProfissionalDetailView(PermissaoVer, DetailView):
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
    success_message = "Profissional salvo com sucesso!"

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


class ProfissionalCreateView(PermissaoAdicionar, ProfissionalFormsetMixin, CreateView):
    pass


class ProfissionalUpdateView(PermissaoAlterar, ProfissionalFormsetMixin, UpdateView):
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_message = "Profissional atualizado com sucesso!"


class ProfissionalDeleteView(PermissaoExcluir, DeleteView):
    model = Profissional
    template_name = "profissionais/profissional_confirm_delete.html"
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_url = reverse_lazy("profissionais:profissional_list")


class ProfissionalPdfReportView(PermissaoVer, View):
    """Relatório em PDF (WeasyPrint) com todos os profissionais da clínica atual.

    Usa o manager padrão de `Profissional`, que já filtra pela clínica da
    requisição; sem clínica atual o relatório sai vazio (falha fechada).
    Não é paginado: o PDF traz a lista completa, não só a página da tela.
    """

    model = Profissional  # usado só para montar a permissão (view_profissional)
    template_name = "profissionais/profissional_report_pdf.html"

    def get_queryset(self):
        return Profissional.objects.select_related("tipo_profissional").prefetch_related(
            Prefetch(
                "telefones",
                queryset=Telefone.objects.order_by("-principal", "pk"),
            )
        )

    def get(self, request, *args, **kwargs):
        # Import tardio: o WeasyPrint carrega bibliotecas nativas (Pango). Assim,
        # um ambiente sem elas só afeta esta tela, não a inicialização do Django.
        from weasyprint import HTML, URLFetcher

        profissionais = list(self.get_queryset())
        agora = timezone.localtime()
        ativos = sum(1 for profissional in profissionais if profissional.ativo)
        contexto = {
            "profissionais": profissionais,
            "total": len(profissionais),
            "total_ativos": ativos,
            "total_inativos": len(profissionais) - ativos,
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
        nome_arquivo = f"profissionais_{agora:%Y%m%d}.pdf"
        resposta["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'
        return resposta


# --- Disponibilidade Views ---
class DisponibilidadeCreateView(PermissaoAdicionar, CreateView):
    model = Disponibilidade
    template_name = "profissionais/disponibilidade_form.html"
    form_class = DisponibilidadeForm
    success_url = reverse_lazy("profissionais:profissional_list")
