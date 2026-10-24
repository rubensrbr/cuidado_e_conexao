# Passo 2 de 3 (multi-tenancy): preenche `clinica` nas linhas já existentes.
#
# Migração separada das de esquema de propósito: no PostgreSQL, alterar uma
# tabela na mesma transação em que se atualizam linhas com FK pendente falha.
#
# Não é preciso adivinhar nada: cada faturamento herda a clínica do paciente a
# que pertence (`paciente` é obrigatório). Por isso funciona mesmo com várias
# clínicas cadastradas.

from django.db import migrations
from django.db.models import OuterRef, Subquery


def preencher_clinica(apps, schema_editor):
    db = schema_editor.connection.alias
    Paciente = apps.get_model("pacientes", "Paciente")
    Faturamento = apps.get_model("faturamentos", "Faturamento")

    clinica_do_paciente = Subquery(
        Paciente.objects.using(db)
        .filter(pk=OuterRef("paciente_id"))
        .values("clinica_id")[:1]
    )
    Faturamento.objects.using(db).filter(clinica__isnull=True).update(
        clinica=clinica_do_paciente
    )


class Migration(migrations.Migration):

    dependencies = [
        ("faturamentos", "0002_faturamento_clinica"),
        # Garante que `Paciente.clinica` já existe e está preenchida.
        ("pacientes", "0005_clinica_obrigatoria"),
    ]

    operations = [
        # Reverter não precisa desfazer o preenchimento.
        migrations.RunPython(preencher_clinica, migrations.RunPython.noop),
    ]
