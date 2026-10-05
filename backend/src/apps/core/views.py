from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.shortcuts import render, redirect, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from .decorators import unauthenticated_user
from django.contrib.auth.views import (
    LoginView as AuthLoginView,
    PasswordChangeView as AuthPasswordChangeView,
    LogoutView as AuthLogoutView,
)


# class IndexView(LoginRequiredMixin, TemplateView):
class IndexView(TemplateView):
    """Painel principal — ponto de entrada do sistema após o login."""

    template_name = "core/index.html"
    extra_context = {"page_title": "Painel"}


@method_decorator(unauthenticated_user, name="dispatch")
class LoginView(AuthLoginView):
    template_name = "core/registration/login.html"
    success_url = "/"

    def form_valid(self, form):
        self.request.session["just_logged_in"] = True

        http_respose = super().form_valid(form)
        if form.get_user().change_password:
            return redirect("alterar_senha")
        return http_respose


@method_decorator(login_required(login_url="login"), name="dispatch")
class LogoutView(AuthLogoutView):
    success_url = "/"
