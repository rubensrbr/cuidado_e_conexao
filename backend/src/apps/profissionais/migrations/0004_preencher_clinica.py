# Passo 2 de 3 (multi-tenancy): preenche `clinica` nas linhas já existentes.
#
# Migração separada das de esquema de propósito: no PostgreSQL, alterar uma
# tabela na mesma transação em que se atualizam linhas com FK pendente falha.
#
# Regra: se há linhas sem clínica, é preciso existir EXATAMENTE UMA clínica
# cadastrada, e todas as linhas passam a pertencer a ela. Com zero ou várias
# clínicas não dá para adivinhar o dono dos dados, então a migração para com
# uma mensagem clara em vez de inventar um tenant.

from django.db import migrations


def preencher_clinica(apps, schema_editor):
    db = schema_editor.connection.alias
    Profissional = apps.get_model("profissionais", "Profissional")
    Disponibilidade = apps.get_model("profissionais", "Disponibilidade")
    Clinica = apps.get_model("clinicas", "Clinica")

    profissionais = Profissional.objects.using(db).filter(clinica__isnull=True)
    disponibilidades = Disponibilidade.objects.using(db).filter(clinica__isnull=True)
    if not (profissionais.exists() or disponibilidades.exists()):
        return  # banco novo ou já preenchido

    clinicas = list(Clinica.objects.using(db).all()[:2])
    if not clinicas:
        raise RuntimeError(
            "Existem profissionais/disponibilidades sem clínica, mas nenhuma "
            "clínica está cadastrada. Crie a clínica dona desses dados (admin "
            "ou shell) e rode `migrate` novamente."
        )
    if len(clinicas) > 1:
        raise RuntimeError(
            "Existem profissionais/disponibilidades sem clínica e mais de uma "
            "clínica cadastrada; não é possível saber a quem eles pertencem. "
            "Deixe só a clínica dona desses dados, rode `migrate` e depois "
            "cadastre as demais."
        )

    clinica = clinicas[0]
    profissionais.update(clinica=clinica)
    disponibilidades.update(clinica=clinica)


class Migration(migrations.Migration):

    dependencies = [
        ("profissionais", "0003_profissional_disponibilidade_clinica"),
    ]

    operations = [
        # Reverter não precisa desfazer o preenchimento.
        migrations.RunPython(preencher_clinica, migrations.RunPython.noop),
    ]
