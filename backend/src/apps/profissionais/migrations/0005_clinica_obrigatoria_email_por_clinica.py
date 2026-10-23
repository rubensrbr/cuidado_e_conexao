# Passo 3 de 3 (multi-tenancy): `clinica` passa a ser obrigatória e o e-mail do
# profissional deixa de ser único no sistema todo: passa a ser único por clínica.

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
        ("profissionais", "0004_preencher_clinica"),
    ]

    operations = [
        migrations.AlterField(
            model_name="profissional", name="clinica", field=_campo_clinica()
        ),
        migrations.AlterField(
            model_name="disponibilidade", name="clinica", field=_campo_clinica()
        ),
        migrations.AlterField(
            model_name="profissional",
            name="email",
            field=models.EmailField(max_length=150, verbose_name="E-mail"),
        ),
        migrations.AddConstraint(
            model_name="profissional",
            constraint=models.UniqueConstraint(
                fields=("clinica", "email"),
                name="profissional_email_unico_por_clinica",
                violation_error_message="Já existe um profissional com este e-mail nesta clínica.",
            ),
        ),
    ]
