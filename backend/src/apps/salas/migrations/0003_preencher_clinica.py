# Passo 2 de 3 (multi-tenancy): preenche `clinica` nas linhas já existentes.
#
# Migração separada das de esquema de propósito: no PostgreSQL, alterar uma
# tabela na mesma transação em que se atualizam linhas com FK pendente falha.
#
# Salas: se há salas sem clínica, é preciso existir EXATAMENTE UMA clínica
# cadastrada, e todas passam a pertencer a ela. Com zero ou várias clínicas não
# dá para adivinhar o dono das salas (uma sala não aponta para nenhum registro
# que diga a quem ela pertence), então a migração para com uma mensagem clara
# em vez de inventar um tenant.
#
# Agendamentos: não há o que adivinhar, cada um herda a clínica da sua sala.

from django.db import migrations
from django.db.models import OuterRef, Subquery


def preencher_clinica(apps, schema_editor):
    db = schema_editor.connection.alias
    Sala = apps.get_model("salas", "Sala")
    AgendaSala = apps.get_model("salas", "AgendaSala")
    Clinica = apps.get_model("clinicas", "Clinica")

    salas = Sala.objects.using(db).filter(clinica__isnull=True)
    if salas.exists():
        clinicas = list(Clinica.objects.using(db).all()[:2])
        if not clinicas:
            raise RuntimeError(
                "Existem salas sem clínica, mas nenhuma clínica está "
                "cadastrada. Crie a clínica dona dessas salas (admin ou "
                "shell) e rode `migrate` novamente."
            )
        if len(clinicas) > 1:
            raise RuntimeError(
                "Existem salas sem clínica e mais de uma clínica cadastrada; "
                "não é possível saber a quem elas pertencem. Deixe só a "
                "clínica dona dessas salas, rode `migrate` e depois cadastre "
                "as demais."
            )
        salas.update(clinica=clinicas[0])

    # Depois das salas, pois o agendamento herda a clínica da sala.
    clinica_da_sala = Subquery(
        Sala.objects.using(db)
        .filter(pk=OuterRef("sala_id"))
        .values("clinica_id")[:1]
    )
    AgendaSala.objects.using(db).filter(clinica__isnull=True).update(
        clinica=clinica_da_sala
    )


class Migration(migrations.Migration):

    dependencies = [
        ("salas", "0002_sala_agendasala_clinica"),
    ]

    operations = [
        # Reverter não precisa desfazer o preenchimento.
        migrations.RunPython(preencher_clinica, migrations.RunPython.noop),
    ]
