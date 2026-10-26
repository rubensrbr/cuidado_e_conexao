from django.core.exceptions import ValidationError


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
