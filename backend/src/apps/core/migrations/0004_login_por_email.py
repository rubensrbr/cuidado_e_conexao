# Passo 3 de 3 (login por e-mail): remove o `username` e torna o e-mail o
# identificador de login, único sem diferenciar maiúsculas de minúsculas.

import core.managers
import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("core", "0003_validar_emails"),
    ]

    operations = [
        migrations.AlterModelManagers(
            name="user",
            managers=[
                ("objects", core.managers.UserManager()),
            ],
        ),
        migrations.RemoveField(
            model_name="user",
            name="username",
        ),
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(
                error_messages={"unique": "Já existe um usuário com este e-mail."},
                max_length=254,
                unique=True,
                verbose_name="E-mail",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower("email"),
                name="user_email_unico_ci",
                violation_error_message="Já existe um usuário com este e-mail.",
            ),
        ),
    ]
