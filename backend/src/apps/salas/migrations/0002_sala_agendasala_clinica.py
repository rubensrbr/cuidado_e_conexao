# Passo 1 de 3 (multi-tenancy): cria a coluna `clinica` ainda NULA, para que as
# linhas já existentes continuem válidas até a 0003 preenchê-las.

import django.db.models.deletion
from django.db import migrations, models


def _campo_clinica():
    return models.ForeignKey(
        editable=False,
        null=True,
        on_delete=django.db.models.deletion.PROTECT,
        to="clinicas.clinica",
        verbose_name="Clínica",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("clinicas", "0002_membro"),
        ("salas", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="sala", name="clinica", field=_campo_clinica()
        ),
        migrations.AddField(
            model_name="agendasala", name="clinica", field=_campo_clinica()
        ),
    ]
