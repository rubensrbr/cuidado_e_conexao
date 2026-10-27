"""Apoio aos testes: papéis com permissões, sem repetir a montagem em cada arquivo."""

from django.apps import apps
from django.contrib.auth.models import Group, Permission

# Apps com telas protegidas por permissão (os opcionais só contam se instalados).
APPS_COM_TELAS = (
    "pacientes",
    "profissionais",
    "consultas",
    "telefones",
    "enderecos",
    "salas",
    "faturamentos",
)


def grupo_com_todas_as_permissoes(nome="Administração"):
    """Cria (ou reaproveita) um grupo com todas as permissões das telas do sistema.

    Para testes que verificam isolamento entre clínicas e precisam que o usuário
    consiga abrir as telas, sem se importar com a granularidade dos papéis.
    """
    grupo, _ = Group.objects.get_or_create(name=nome)
    apps_instalados = [a for a in APPS_COM_TELAS if apps.is_installed(a)]
    grupo.permissions.set(
        Permission.objects.filter(content_type__app_label__in=apps_instalados)
    )
    return grupo


def grupo_com_permissoes(nome, *permissoes):
    """Grupo com exatamente as permissões dadas, no formato "app.codename"."""
    grupo, _ = Group.objects.get_or_create(name=nome)
    objetos = []
    for permissao in permissoes:
        app_label, codename = permissao.split(".", 1)
        objetos.append(
            Permission.objects.get(
                content_type__app_label=app_label, codename=codename
            )
        )
    grupo.permissions.set(objetos)
    return grupo
