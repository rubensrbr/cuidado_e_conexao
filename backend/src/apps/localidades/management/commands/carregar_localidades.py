import gzip
import json
from urllib.request import urlopen, Request

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from localidades.models import Cidade, Estado

BASE_URL = "https://servicodados.ibge.gov.br/api/v1/localidades"


def get_json(url):
    req = Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",  # pede resposta sem compressão
            "User-Agent": "cuidado-e-conexao/1.0",
        },
    )
    with urlopen(req, timeout=30) as resp:
        raw = resp.read()

    # Se o servidor comprimir mesmo assim, descomprime
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)

    return json.loads(raw.decode("utf-8"))


class Command(BaseCommand):
    help = "Carrega/atualiza estados e cidades a partir da API de localidades do IBGE."

    def handle(self, *args, **options):
        try:
            estados_api = get_json(f"{BASE_URL}/estados?orderBy=nome")
            dados = {
                e["id"]: get_json(f"{BASE_URL}/estados/{e['id']}/municipios")
                for e in estados_api
            }
        except OSError as exc:
            raise CommandError(f"Falha ao consultar a API do IBGE: {exc}")

        # Só escreve no banco depois de ter baixado tudo com sucesso
        with transaction.atomic():
            for e in estados_api:
                estado, _ = Estado.objects.update_or_create(
                    codigo_ibge=e["id"],
                    defaults={"sigla": e["sigla"], "nome": e["nome"]},
                )
                Cidade.objects.bulk_create(
                    [
                        Cidade(codigo_ibge=m["id"], nome=m["nome"], estado=estado)
                        for m in dados[e["id"]]
                    ],
                    update_conflicts=True,
                    unique_fields=["codigo_ibge"],
                    update_fields=["nome", "estado"],
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"{Estado.objects.count()} estados, {Cidade.objects.count()} cidades."
            )
        )
