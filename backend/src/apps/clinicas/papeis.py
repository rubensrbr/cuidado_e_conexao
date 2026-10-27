"""
Papéis (grupos) padrão do sistema e as permissões de cada um.

Um papel é um `django.contrib.auth.models.Group`; a pessoa ganha um papel numa
clínica por meio do `Membro.grupo`. As definições abaixo são um PONTO DE PARTIDA:
ajuste à vontade e rode `python manage.py sincronizar_papeis`. Papéis também
podem ser criados e editados pelo admin, e nenhum papel é obrigatório.

Formato: papel -> {"app.model": ações}. As ações são as quatro permissões padrão
do Django para cada model: view, add, change, delete.

Apps opcionais que não estão em INSTALLED_APPS (salas, faturamentos no release 1)
são ignorados: as permissões deles só existem depois que o app é instalado.
"""

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.core.management.base import CommandError
from django.db import transaction

VER = ("view",)
VER_E_EDITAR = ("view", "add", "change")
TUDO = ("view", "add", "change", "delete")

# Dados de cadastro e agenda do dia a dia.
_NEGOCIO = (
    "pacientes.paciente",
    "profissionais.profissional",
    "profissionais.disponibilidade",
    "profissionais.tipoprofissional",
    "consultas.consulta",
    "consultas.lembrete",
    "consultas.listaespera",
    "telefones.telefone",
    "enderecos.endereco",
    "salas.sala",
    "salas.agendasala",
)

PAPEIS = {
    # Tudo, inclusive prontuário e faturamento.
    "Administração": {
        **{modelo: TUDO for modelo in _NEGOCIO},
        "pacientes.prontuario": TUDO,
        "faturamentos.faturamento": TUDO,
        "localidades.estado": VER,
        "localidades.cidade": VER,
    },
    # Atendimento no balcão: cadastra e agenda, mas não exclui cadastros e não
    # acessa prontuário (dado clínico sensível) nem faturamento.
    "Recepção": {
        "pacientes.paciente": VER_E_EDITAR,
        "profissionais.profissional": VER,
        "profissionais.disponibilidade": VER,
        "profissionais.tipoprofissional": VER,
        "consultas.consulta": VER_E_EDITAR,
        "consultas.lembrete": VER_E_EDITAR,
        "consultas.listaespera": TUDO,  # a fila é gerida pela recepção
        "telefones.telefone": VER_E_EDITAR,
        "enderecos.endereco": VER_E_EDITAR,
        "salas.sala": VER,
        "salas.agendasala": VER,
        "localidades.estado": VER,
        "localidades.cidade": VER,
    },
    # Consulta sem alterar nada; sem prontuário nem faturamento.
    "Somente leitura": {
        **{modelo: VER for modelo in _NEGOCIO},
        "localidades.estado": VER,
        "localidades.cidade": VER,
    },
}


def _codenames(modelo, acoes):
    app_label, nome_modelo = modelo.split(".")
    return app_label, [f"{acao}_{nome_modelo}" for acao in acoes]


def permissoes_do_papel(definicao):
    """Resolve {"app.model": ações} em objetos `Permission`.

    Models de apps não instalados são pulados. Uma permissão que deveria existir
    (app instalado) e não existe é um erro de digitação na definição acima, e
    falha alto em vez de gerar um papel incompleto sem aviso.
    """
    resultado = []
    for modelo, acoes in definicao.items():
        app_label, codenames = _codenames(modelo, acoes)
        if not apps.is_installed(app_label):
            continue
        encontradas = Permission.objects.filter(
            content_type__app_label=app_label, codename__in=codenames
        )
        faltando = set(codenames) - {p.codename for p in encontradas}
        if faltando:
            raise CommandError(
                f"Permissões inexistentes em {app_label}: {sorted(faltando)}. "
                "Confira PAPEIS em clinicas/papeis.py (e se o `migrate` já rodou)."
            )
        resultado.extend(encontradas)
    return resultado


@transaction.atomic
def sincronizar_papeis(atualizar=False, papeis=None):
    """Cria os papéis que não existem. Devolve [(nome, situação, qtd. permissões)].

    Papel que já existe é MANTIDO como está (alguém pode tê-lo ajustado no admin),
    a menos que `atualizar=True`, que redefine suas permissões para o padrão.
    """
    papeis = PAPEIS if papeis is None else papeis
    relatorio = []
    for nome, definicao in papeis.items():
        grupo, criado = Group.objects.get_or_create(name=nome)
        if criado or atualizar:
            permissoes = permissoes_do_papel(definicao)
            grupo.permissions.set(permissoes)
            relatorio.append((nome, "criado" if criado else "atualizado", len(permissoes)))
        else:
            relatorio.append((nome, "mantido", grupo.permissions.count()))
    return relatorio
