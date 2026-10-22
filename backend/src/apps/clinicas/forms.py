from .tenancy import TenantModel


class TenantFormMixin:
    """
    Faz os campos de escolha (ModelChoiceField / ModelMultipleChoiceField) de um
    formulário listarem só objetos da clínica atual.

    Necessário porque o Django monta o queryset dos campos de um ModelForm
    quando a classe é importada, antes de existir uma clínica atual: sem isto,
    o manager filtrado deixaria os campos permanentemente vazios.

    Uso (o mixin vem antes de ModelForm):

        class ProntuarioForm(TenantFormMixin, forms.ModelForm): ...

    Filtros extras específicos de um formulário devem ser aplicados no próprio
    `__init__`, depois de `super().__init__()`.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            queryset = getattr(field, "queryset", None)
            if queryset is None or not issubclass(queryset.model, TenantModel):
                continue
            novo = queryset.model._default_manager.all()
            limite = field.get_limit_choices_to()
            if limite:
                novo = novo.complex_filter(limite)
            field.queryset = novo
