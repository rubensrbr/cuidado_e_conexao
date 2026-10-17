import re

from django.core.exceptions import ValidationError

# Subdomínios/rotas que não podem virar o identificador de uma clínica
# (ex.: clinica.seudominio.com.br ou /c/<slug>/).
SLUGS_RESERVADOS = {
    "admin",
    "api",
    "app",
    "www",
    "static",
    "media",
    "accounts",
    "login",
    "logout",
    "suporte",
    "painel",
}


def somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _digito_cnpj(base: str) -> str:
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos = pesos[len(pesos) - len(base):]
    soma = sum(int(d) * p for d, p in zip(base, pesos))
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def validar_cnpj(valor: str) -> None:
    cnpj = somente_digitos(valor)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        raise ValidationError("Informe um CNPJ válido (14 dígitos).")
    d1 = _digito_cnpj(cnpj[:12])
    d2 = _digito_cnpj(cnpj[:12] + d1)
    if cnpj[12:] != d1 + d2:
        raise ValidationError("CNPJ inválido: dígitos verificadores não conferem.")


def validar_slug_nao_reservado(valor: str) -> None:
    if valor in SLUGS_RESERVADOS:
        raise ValidationError("Este identificador é reservado. Escolha outro.")
