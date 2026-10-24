# Passo 3 de 3 (multi-tenancy): `clinica` passa a ser obrigatória.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enderecos", "0005_preencher_clinica"),
    ]

    operations = [
        migrations.AlterField(
            model_name="endereco",
            name="clinica",
            field=models.ForeignKey(
                editable=False,
                on_delete=django.db.models.deletion.PROTECT,
                to="clinicas.clinica",
                verbose_name="Clínica",
            ),
        ),
    ]
