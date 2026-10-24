# Passo 2 de 3 (multi-tenancy): preenche `clinica` nas linhas já existentes.
#
# Migração separada das de esquema de propósito: no PostgreSQL, alterar uma
# tabela na mesma transação em que se atualizam linhas com FK pendente falha.
#
# Diferente de pacientes/profissionais, aqui não é preciso adivinhar nada: cada
# registro herda a clínica do paciente a que pertence (e o lembrete, a da sua
# consulta). Por isso funciona mesmo com várias clínicas cadastradas.

from django.db import migrations
from django.db.models import OuterRef, Subquery


def preencher_clinica(apps, schema_editor):
    db = schema_editor.connection.alias
    Paciente = apps.get_model("pacientes", "Paciente")
    Consulta = apps.get_model("consultas", "Consulta")
    Lembrete = apps.get_model("consultas", "Lembrete")
    ListaEspera = apps.get_model("consultas", "ListaEspera")

    clinica_do_paciente = Subquery(
        Paciente.objects.using(db)
        .filter(pk=OuterRef("paciente_id"))
        .values("clinica_id")[:1]
    )
    Consulta.objects.using(db).filter(clinica__isnull=True).update(
        clinica=clinica_do_paciente
    )
    ListaEspera.objects.using(db).filter(clinica__isnull=True).update(
        clinica=clinica_do_paciente
    )

    # Depois das consultas, pois o lembrete herda a clínica da consulta.
    clinica_da_consulta = Subquery(
        Consulta.objects.using(db)
        .filter(pk=OuterRef("consulta_id"))
        .values("clinica_id")[:1]
    )
    Lembrete.objects.using(db).filter(clinica__isnull=True).update(
        clinica=clinica_da_consulta
    )


class Migration(migrations.Migration):

    dependencies = [
        ("consultas", "0004_consulta_lembrete_listaespera_clinica"),
        # Garante que `Paciente.clinica` já existe e está preenchida.
        ("pacientes", "0005_clinica_obrigatoria"),
    ]

    operations = [
        # Reverter não precisa desfazer o preenchimento.
        migrations.RunPython(preencher_clinica, migrations.RunPython.noop),
    ]
