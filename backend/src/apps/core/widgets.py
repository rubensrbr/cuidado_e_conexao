from django import forms


class DateInput(forms.DateInput):
    """Campo de data nativo do navegador (`<input type="date">`).

    O navegador só aceita o valor inicial em ISO (AAAA-MM-DD). Com
    `LANGUAGE_CODE = "pt-br"` o Django formataria a data como 05/11/2026 e o
    campo apareceria vazio ao editar um registro. Por isso o formato é fixo aqui;
    use este widget em vez de `forms.DateInput(attrs={"type": "date"})`.

    Quem envia o formulário continua mandando ISO, que o campo aceita.
    """

    input_type = "date"

    def __init__(self, attrs=None, format="%Y-%m-%d"):
        super().__init__(attrs={"class": "form-control", **(attrs or {})}, format=format)
