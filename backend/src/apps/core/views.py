from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView
from django.shortcuts import render, redirect, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from .decorators import unauthenticated_user
from .forms import CadastroForm, LoginForm, TrocaDeSenhaForm
from .models import User
from .throttle import (
    cadastros_fechados,
    limpar_falhas_de_login,
    login_bloqueado,
    registrar_falha_de_login,
    registrar_tentativa,
)
from django.contrib.auth.views import (
    LoginView as AuthLoginView,
    PasswordChangeView as AuthPasswordChangeView,
    LogoutView as AuthLogoutView,
)


class IndexView(LoginRequiredMixin, TemplateView):
    """Painel principal — ponto de entrada do sistema após o login."""

    template_name = "core/index.html"
    extra_context = {"page_title": "Painel"}


@method_decorator(unauthenticated_user, name="dispatch")
class LoginView(AuthLoginView):
    authentication_form = LoginForm
    template_name = "core/registration/login.html"
    success_url = "/"

    def post(self, request, *args, **kwargs):
        bloqueado, espera = login_bloqueado(request)
        if bloqueado:
            self.object = None
            contexto = self.get_context_data(
                form=self.get_form_class()(request),
                aviso="Muitas tentativas de login. Tente novamente mais tarde.",
            )
            resposta = self.render_to_response(contexto)
            resposta.status_code = 429
            resposta["Retry-After"] = str(espera)
            return resposta
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        registrar_falha_de_login(self.request)
        return super().form_invalid(form)

    def form_valid(self, form):
        limpar_falhas_de_login(self.request)
        self.request.session["just_logged_in"] = True

        http_respose = super().form_valid(form)
        if form.get_user().change_password:
            return redirect("alterar_senha")
        return http_respose


@method_decorator(unauthenticated_user, name="dispatch")
class CadastroView(CreateView):
    """Cadastro público: cria a conta (inativa, aguardando aprovação) e volta ao login.

    Limites: cada IP só pode enviar o formulário um número de vezes por janela, e
    o cadastro fecha enquanto houver contas demais esperando aprovação (veja
    `core/throttle.py` e as CADASTRO_* em settings).
    """

    form_class = CadastroForm
    template_name = "core/registration/cadastro.html"
    success_url = reverse_lazy("login")

    def post(self, request, *args, **kwargs):
        if cadastros_fechados():
            return self._recusar(
                "Os cadastros estão temporariamente fechados. "
                "Fale com o administrador da sua clínica.",
                status=503,
            )
        permitida, espera = registrar_tentativa(request)
        if not permitida:
            return self._recusar(
                "Muitas tentativas de cadastro. Tente novamente mais tarde.",
                status=429,
                espera=espera,
            )
        return super().post(request, *args, **kwargs)

    def _recusar(self, aviso, status, espera=None):
        # Formulário em branco (sem validar nada) e a mensagem do motivo.
        self.object = None
        contexto = self.get_context_data(form=self.form_class(), aviso=aviso)
        resposta = self.render_to_response(contexto)
        resposta.status_code = status
        if espera:
            resposta["Retry-After"] = str(espera)
        return resposta

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            "Conta criada! Ela será liberada depois que um administrador "
            "aprovar o seu cadastro.",
        )
        return response


@method_decorator(login_required(login_url="login"), name="dispatch")
class LogoutView(AuthLogoutView):
    success_url = "/"


@method_decorator(login_required(login_url="login"), name="dispatch")
class PasswordChangeView(AuthPasswordChangeView):
    """Troca de senha; também é para onde vai quem tem `change_password`."""

    form_class = TrocaDeSenhaForm
    template_name = "core/registration/password_change.html"
    success_url = reverse_lazy("home")
    extra_context = {"page_title": "Alterar senha"}

    def form_valid(self, form):
        response = super().form_valid(form)
        # Só a marca muda aqui; update direto evita regravar a senha.
        User.objects.filter(pk=form.user.pk).update(change_password=False)
        messages.success(self.request, "Senha alterada com sucesso.")
        return response
