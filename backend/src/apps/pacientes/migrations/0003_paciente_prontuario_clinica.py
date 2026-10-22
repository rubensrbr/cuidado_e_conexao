# Passo 1 de 3 (multi-tenancy): cria a coluna `clinica` ainda NULA, para que as
# linhas já existentes continuem válidas até a 0004 preenchê-las.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clinicas", "0002_membro"),
        ("pacientes", "0002_alter_paciente_options_paciente_profissionais"),
    ]

    operations = [
        migrations.AddField(
            model_name="paciente",
            name="clinica",
            field=models.ForeignKey(
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="clinicas.clinica",
                verbose_name="Clínica",
            ),
        ),
        migrations.AddField(
            model_name="prontuario",
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
