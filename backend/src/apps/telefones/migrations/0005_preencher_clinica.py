# Passo 2 de 3 (multi-tenancy): preenche `clinica` nas linhas já existentes.
#
# Migração separada das de esquema de propósito: no PostgreSQL, alterar uma
# tabela na mesma transação em que se atualizam linhas com FK pendente falha.
#
# Regra: todo telefone pertence a um paciente OU a um profissional (garantido
# pela constraint `telefone_com_um_unico_dono`), e ambos já têm clínica. O
# telefone herda a clínica do dono, então funciona com qualquer número de
# clínicas cadastradas.

from django.db import migrations
from django.db.models import OuterRef, Subquery


def preencher_clinica(apps, schema_editor):
    db = schema_editor.connection.alias
    Telefone = apps.get_model("telefones", "Telefone")
    Paciente = apps.get_model("pacientes", "Paciente")
    Profissional = apps.get_model("profissionais", "Profissional")

    sem_clinica = Telefone.objects.using(db).filter(clinica__isnull=True)

    sem_clinica.filter(pacientes__isnull=False).update(
        clinica=Subquery(
            Paciente.objects.using(db)
            .filter(pk=OuterRef("pacientes_id"))
            .values("clinica_id")[:1]
        )
    )
    sem_clinica.filter(profissionais__isnull=False).update(
        clinica=Subquery(
            Profissional.objects.using(db)
            .filter(pk=OuterRef("profissionais_id"))
            .values("clinica_id")[:1]
        )
    )

    restantes = sem_clinica.count()
    if restantes:
        raise RuntimeError(
            f"{restantes} telefone(s) continuam sem clínica porque o dono "
            "(paciente/profissional) também não tem clínica. Corrija os "
            "donos e rode `migrate` novamente."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("telefones", "0004_telefone_clinica"),
        ("pacientes", "0005_clinica_obrigatoria"),
        ("profissionais", "0005_clinica_obrigatoria_email_por_clinica"),
    ]

    operations = [
        # Reverter não precisa desfazer o preenchimento.
        migrations.RunPython(preencher_clinica, migrations.RunPython.noop),
    ]
