from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class TrocaDeSenhaObrigatoriaMiddleware:
    """Leva ao formulário de troca de senha quem tem `change_password` ligado.

    Sem isso a marca só valeria no momento do login: bastaria digitar outra
    URL para continuar usando o sistema com a senha antiga.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and user.change_password
            and not self._liberada(request.path)
        ):
            return redirect("alterar_senha")
        return self.get_response(request)

    @staticmethod
    def _liberada(path):
        # A própria troca, o logout (para poder sair) e os arquivos estáticos.
        return path in (reverse("alterar_senha"), reverse("logout")) or path.startswith(
            settings.STATIC_URL
        )
