# Passo 3 de 3 (multi-tenancy): `clinica` passa a ser obrigatória e o número da
# sala deixa de ser único no sistema todo: passa a ser único por clínica.

import django.db.models.deletion
from django.db import migrations, models


def _campo_clinica():
    return models.ForeignKey(
        editable=False,
        on_delete=django.db.models.deletion.PROTECT,
        to="clinicas.clinica",
        verbose_name="Clínica",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("salas", "0003_preencher_clinica"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sala", name="clinica", field=_campo_clinica()
        ),
        migrations.AlterField(
            model_name="agendasala", name="clinica", field=_campo_clinica()
        ),
        migrations.AlterField(
            model_name="sala",
            name="numero_sala",
            field=models.CharField(max_length=20, verbose_name="Número da Sala"),
        ),
        migrations.AddConstraint(
            model_name="sala",
            constraint=models.UniqueConstraint(
                fields=("clinica", "numero_sala"),
                name="sala_numero_unico_por_clinica",
                violation_error_message="Já existe uma sala com este número nesta clínica.",
            ),
        ),
    ]
