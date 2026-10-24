# Passo 1 de 3 (multi-tenancy): cria a coluna `clinica` ainda NULA, para que as
# linhas já existentes continuem válidas até a 0005 preenchê-las.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clinicas", "0002_membro"),
        ("enderecos", "0003_remove_endereco_estado_alter_endereco_cidade"),
    ]

    operations = [
        migrations.AddField(
            model_name="endereco",
            name="clinica",
            field=models.ForeignKey(
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="clinicas.clinica",
                verbose_name="Clínica",
            ),
        ),
    ]
