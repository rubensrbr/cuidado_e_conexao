import re

from django.core.exceptions import ValidationError


class ComplexityValidator:
    def validate(self, password, user=None):
        errors = []
        if not re.search(r"[A-Z]", password):
            errors.append("an uppercase letter")
        if not re.search(r"[a-z]", password):
            errors.append("a lowercase letter")
        if not re.search(r"\d", password):
            errors.append("a digit")
        if not re.search(r"[^\w\s]", password):
            errors.append("a special character")
        if errors:
            raise ValidationError(
                "The password must contain " + ", ".join(errors) + ".",
                code="password_too_simple",
            )

    def get_help_text(self):
        return "Your password must contain uppercase, lowercase, a digit and a special character."
