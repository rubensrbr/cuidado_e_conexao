"""
Middleware de multi-tenancy: define a "clínica atual" de cada requisição.

Resolução (nesta ordem), sempre a partir dos vínculos `Membro` do usuário
autenticado, só considerando vínculos ativos de clínicas ativas:

1. Clínica escolhida e guardada na sessão (`SESSION_KEY`), se o usuário ainda
   tiver vínculo ativo com ela.
2. Se o usuário tem exatamente um vínculo ativo, essa clínica (e ela é
   guardada na sessão).
3. Caso contrário (anônimo, sem vínculo, ou vários vínculos sem escolha),
   não há clínica atual. O manager dos modelos devolve vazio (falha fechada).

Deve ficar DEPOIS de `AuthenticationMiddleware` em `settings.MIDDLEWARE`.
"""

import uuid

from .models import Membro
from .tenancy import clinica_atual

SESSION_KEY = "clinica_uuid"


def _uuid_valido(valor):
    try:
        return uuid.UUID(str(valor))
    except (ValueError, AttributeError, TypeError):
        return None


def resolver_membro(request):
    """Devolve o `Membro` (com clínica e grupo) ativo na requisição, ou None."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return None

    membros = Membro.objects.filter(
        user=user, ativo=True, clinica__ativa=True
    ).select_related("clinica", "grupo")

    escolhida = request.session.get(SESSION_KEY)
    if escolhida:
        uuid_escolhido = _uuid_valido(escolhida)
        membro = (
            membros.filter(clinica__uuid=uuid_escolhido).first()
            if uuid_escolhido
            else None
        )
        if membro:
            return membro
        # Vínculo removido/desativado, clínica suspensa ou valor inválido.
        request.session.pop(SESSION_KEY, None)

    candidatos = list(membros[:2])
    if len(candidatos) == 1:
        request.session[SESSION_KEY] = str(candidatos[0].clinica.uuid)
        return candidatos[0]
    return None


class ClinicaAtualMiddleware:
    """
    Define `request.membro`, `request.clinica` e a ContextVar da clínica atual
    durante toda a requisição, restaurando-a ao final (inclusive com erro).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        membro = resolver_membro(request)
        request.membro = membro
        request.clinica = membro.clinica if membro else None
        with clinica_atual(request.clinica):
            return self.get_response(request)
