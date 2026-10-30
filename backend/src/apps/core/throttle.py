"""Limites do cadastro público: por IP (tentativas na janela) e geral (pendentes)."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import TentativaDeCadastro, User


def ip_do_cliente(request):
    if settings.CADASTRO_CONFIAR_X_FORWARDED_FOR:
        encaminhado = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if encaminhado:
            return encaminhado.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR") or "0.0.0.0"


def cadastros_fechados():
    """True quando já há contas demais esperando aprovação."""
    return (
        User.objects.filter(cadastro_pendente=True).count()
        >= settings.CADASTRO_MAX_PENDENTES
    )


def registrar_tentativa(request):
    """Conta este envio e diz se ele ainda cabe no limite do IP.

    Devolve (permitida, segundos_para_tentar_de_novo).
    """
    janela = timedelta(seconds=settings.CADASTRO_JANELA_EM_SEGUNDOS)
    agora = timezone.now()
    ip = ip_do_cliente(request)

    # Limpeza barata: o índice (ip, criada_em) e a janela curta mantêm a tabela pequena.
    TentativaDeCadastro.objects.filter(criada_em__lt=agora - janela).delete()

    recentes = TentativaDeCadastro.objects.filter(ip=ip).order_by("criada_em")
    if recentes.count() >= settings.CADASTRO_MAX_TENTATIVAS_POR_IP:
        mais_antiga = recentes.first().criada_em
        espera = int((mais_antiga + janela - agora).total_seconds()) + 1
        return False, max(espera, 1)

    TentativaDeCadastro.objects.create(ip=ip, criada_em=agora)
    return True, 0
