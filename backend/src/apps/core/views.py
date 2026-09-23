from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class IndexView(LoginRequiredMixin, TemplateView):
    """Painel principal — ponto de entrada do sistema após o login."""

    template_name = "core/index.html"
    extra_context = {"page_title": "Painel"}
