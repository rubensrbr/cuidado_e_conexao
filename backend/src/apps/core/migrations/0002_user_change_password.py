# Passo 1 de 3 (login por e-mail): campo que obriga o usuário a trocar a senha
# no próximo acesso (usado pelo `LoginView` e pelo middleware de troca).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="change_password",
            field=models.BooleanField(
                default=False,
                help_text="Se marcado, o usuário só usa o sistema depois de definir uma nova senha.",
                verbose_name="Trocar a senha no próximo acesso",
            ),
        ),
    ]
