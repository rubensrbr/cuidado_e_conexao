# Passo 3 de 3 (multi-tenancy): `clinica` passa a ser obrigatória.

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
        ("consultas", "0005_preencher_clinica"),
    ]

    operations = [
        migrations.AlterField(
            model_name="consulta", name="clinica", field=_campo_clinica()
        ),
        migrations.AlterField(
            model_name="lembrete", name="clinica", field=_campo_clinica()
        ),
        migrations.AlterField(
            model_name="listaespera", name="clinica", field=_campo_clinica()
        ),
    ]
