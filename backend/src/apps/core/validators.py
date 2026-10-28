from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError


class _EmPortugues:
    """Troca as mensagens em inglês dos validadores do Django pelas em português.

    O projeto roda com LANGUAGE_CODE = "en-us", então os textos embutidos do
    Django (erros e dicas de senha) apareceriam em inglês. Em vez de mudar o
    idioma do sistema todo (o que também muda formato de data e de número), cada
    validador é só uma casca que chama o original e traduz a mensagem pelo
    `code` do erro. A regra de validação continua sendo a do Django.
    """

    mensagens = {}
    ajuda = ""

    def validate(self, password, user=None):
        try:
            super().validate(password, user)
        except ValidationError as erro:
            raise ValidationError(
                [self._traduzir(e) for e in erro.error_list]
            ) from None

    def _traduzir(self, erro):
        return ValidationError(
            self.mensagens.get(erro.code, erro.message),
            code=erro.code,
            params=erro.params,
        )

    def get_help_text(self):
        return self.ajuda


class TamanhoMinimoValidator(_EmPortugues, password_validation.MinimumLengthValidator):
    mensagens = {
        "password_too_short": (
            "Esta senha é muito curta. "
            "Ela precisa ter pelo menos %(min_length)d caracteres."
        )
    }

    def get_help_text(self):
        return f"Sua senha precisa ter pelo menos {self.min_length} caracteres."


class SenhaComumValidator(_EmPortugues, password_validation.CommonPasswordValidator):
    mensagens = {"password_too_common": "Esta senha é muito comum."}
    ajuda = "Sua senha não pode ser uma senha muito comum."


class SenhaNumericaValidator(_EmPortugues, password_validation.NumericPasswordValidator):
    mensagens = {"password_entirely_numeric": "Esta senha é totalmente numérica."}
    ajuda = "Sua senha não pode ser totalmente numérica."


class SimilaridadeComUsuarioValidator(
    _EmPortugues, password_validation.UserAttributeSimilarityValidator
):
    ajuda = "Sua senha não pode ser muito parecida com as suas outras informações pessoais."

    # `verbose_name` vem dos campos do usuário e muda com o idioma: em en-us é
    # "first name"/"last name"; em pt-br, "primeiro nome"/"último nome".
    CAMPOS = {
        "first name": "nome",
        "last name": "sobrenome",
        "primeiro nome": "nome",
        "último nome": "sobrenome",
        "e-mail": "e-mail",
    }

    def _traduzir(self, erro):
        campo = str((erro.params or {}).get("verbose_name", ""))
        return ValidationError(
            "Esta senha é muito parecida com o seu %(campo)s.",
            code=erro.code,
            params={"campo": self.CAMPOS.get(campo.lower(), campo.lower())},
        )


class ComplexityValidator:
    """Exige letra minúscula, maiúscula, número e símbolo.

    O tamanho mínimo fica com o MinimumLengthValidator do Django (veja
    AUTH_PASSWORD_VALIDATORS em settings.py). Usa os métodos de `str` em vez de
    [A-Z]/[a-z] para reconhecer também letras acentuadas.
    """

    def validate(self, password, user=None):
        faltando = []
        if not any(c.isupper() for c in password):
            faltando.append("uma letra maiúscula")
        if not any(c.islower() for c in password):
            faltando.append("uma letra minúscula")
        if not any(c.isdigit() for c in password):
            faltando.append("um número")
        if not any(not c.isalnum() and not c.isspace() for c in password):
            faltando.append("um símbolo (como ! @ # $ %)")
        if faltando:
            raise ValidationError(
                "A senha precisa ter também " + ", ".join(faltando) + ".",
                code="password_too_simple",
            )

    def get_help_text(self):
        return (
            "Sua senha precisa ter letras maiúsculas e minúsculas, "
            "números e símbolos."
        )
