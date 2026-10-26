# Passo 2 de 3 (login por e-mail): prepara os usuários já cadastrados.
#
# Migração separada das de esquema de propósito: no PostgreSQL, alterar uma
# tabela na mesma transação em que se atualizam linhas pendentes falha. Também
# roda ANTES de a coluna `username` ser removida, para poder citá-lo na mensagem.
#
# A partir daqui o e-mail é o login, então cada usuário precisa de um e-mail
# próprio. Não dá para inventar ou escolher e-mails sozinho; se algum usuário
# não tem e-mail, ou dois usuários têm o mesmo (sem diferenciar maiúsculas), a
# migração para listando quem são, sem alterar nada. Estando tudo certo, os
# e-mails são padronizados (sem espaços nas pontas, em minúsculas).

from collections import defaultdict

from django.db import migrations


def validar_e_normalizar_emails(apps, schema_editor):
    db = schema_editor.connection.alias
    User = apps.get_model("core", "User")

    sem_email = []
    por_email = defaultdict(list)
    for user in User.objects.using(db).order_by("pk"):
        email = (user.email or "").strip().lower()
        if email:
            por_email[email].append(user)
        else:
            sem_email.append(user.username)

    repetidos = {e: us for e, us in por_email.items() if len(us) > 1}

    problemas = []
    if sem_email:
        problemas.append("Usuários sem e-mail: " + ", ".join(sem_email) + ".")
    if repetidos:
        detalhes = "; ".join(
            f"{email} ({', '.join(u.username for u in us)})"
            for email, us in sorted(repetidos.items())
        )
        problemas.append("E-mails repetidos: " + detalhes + ".")
    if problemas:
        raise RuntimeError(
            "O e-mail passa a ser o login e precisa ser único por usuário. "
            "Corrija no admin ou no shell e rode `migrate` novamente. "
            + " ".join(problemas)
        )

    for email, (user,) in por_email.items():
        if user.email != email:
            User.objects.using(db).filter(pk=user.pk).update(email=email)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_user_change_password"),
    ]

    operations = [
        # Reverter não precisa desfazer a padronização.
        migrations.RunPython(validar_e_normalizar_emails, migrations.RunPython.noop),
    ]
