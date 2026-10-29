from django.conf import settings
from django.contrib import messages
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

from .filters import PacienteFilter
from .forms import PacienteForm, ProntuarioForm, TelefoneFormSet
from telefones.models import Telefone

from .models import Paciente, Prontuario
from clinicas.permissions import (
    PermissaoAdicionar,
    PermissaoAlterar,
    PermissaoExcluir,
    PermissaoVer,
)


class PacienteListView(PermissaoVer, FiltrosPersistentesMixin, ListView):
    model = Paciente
    filterset_class = PacienteFilter
    template_name = "pacientes/paciente_list.html"
    context_object_name = "pacientes"
    paginate_by = 10

    def get_queryset(self):
        # Uma query extra para todos os telefones da página (evita N+1),
        # com o telefone principal primeiro.
        queryset = (
            super()
            .get_queryset()
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
            # Valor de filtro inválido (idade fora da faixa, profissional de outra
            # clínica...) não pode virar "mostrar tudo": a lista fica vazia e o
            # formulário mostra o erro.
            return queryset.none()
        return self.filtro.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filtro"] = self.filtro
        context["filtros_ativos"] = sum(
            1 for nome in self.filtro.filters if self.request.GET.get(nome, "").strip()
        )
        return context


class PacientePdfReportView(PermissaoVer, View):
    """Relatório em PDF (WeasyPrint) dos pacientes da clínica atual.

    Usa o manager padrão de `Paciente`, que já filtra pela clínica da requisição;
    sem clínica atual o relatório sai vazio (falha fechada).
    Respeita os mesmos filtros da lista (a tela repassa a query string no botão),
    mas não é paginado: o PDF traz todos os resultados, não só a página da tela.
    """

    model = Paciente  # usado só para montar a permissão (view_paciente)
    filterset_class = PacienteFilter
    template_name = "pacientes/paciente_report_pdf.html"

    def get_queryset(self):
        return Paciente.objects.prefetch_related(
            "profissionais",
            Prefetch(
                "telefones",
                queryset=Telefone.objects.order_by("-principal", "pk"),
            ),
        )

    def get(self, request, *args, **kwargs):
        # Import tardio: o WeasyPrint carrega bibliotecas nativas (Pango). Assim,
        # um ambiente sem elas só afeta esta tela, não a inicialização do Django.
        from weasyprint import HTML, URLFetcher

        queryset = self.get_queryset()
        filtro = self.filterset_class(request.GET, queryset=queryset, request=request)
        # Filtro inválido não pode virar "todos os pacientes" (igual à lista).
        pacientes = list(filtro.qs if filtro.is_valid() else queryset.none())
        filtros_ativos = sum(
            1 for nome in filtro.filters if request.GET.get(nome, "").strip()
        )

        agora = timezone.localtime()
        ativos = sum(1 for paciente in pacientes if paciente.ativo)
        contexto = {
            "pacientes": pacientes,
            "total": len(pacientes),
            "total_ativos": ativos,
            "total_inativos": len(pacientes) - ativos,
            "filtros_ativos": filtros_ativos,
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
        nome_arquivo = f"pacientes_{agora:%Y%m%d}.pdf"
        resposta["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'
        return resposta


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
