from django.core.management.base import BaseCommand

from clinicas.papeis import sincronizar_papeis


class Command(BaseCommand):
    help = (
        "Cria os papéis (grupos) padrão e suas permissões. Papéis que já existem "
        "são mantidos, a menos que --atualizar seja usado. Pode rodar várias vezes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--atualizar",
            action="store_true",
            help="Redefine as permissões dos papéis que já existem para o padrão "
            "(descarta ajustes feitos no admin).",
        )

    def handle(self, *args, atualizar=False, **options):
        for nome, situacao, total in sincronizar_papeis(atualizar=atualizar):
            self.stdout.write(f"{nome}: {situacao} ({total} permissões)")
