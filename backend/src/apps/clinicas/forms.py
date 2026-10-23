from .tenancy import TenantModel, get_clinica_atual


class TenantFormMixin:
    """
    Torna um ModelForm ciente da clínica atual. Faz duas coisas:

    1. Os campos de escolha (ModelChoiceField / ModelMultipleChoiceField) para
       modelos de clínica listam só objetos da clínica atual. Necessário porque
       o Django monta o queryset desses campos quando a classe do formulário é
       importada, antes de existir uma clínica atual: sem isto, o manager
       filtrado deixaria os campos permanentemente vazios.

    2. Em objetos novos, define `instance.clinica` já na construção e inclui
       `clinica` na validação. Sem isso, o Django ignora restrições de
       unicidade que envolvem `clinica` (ela não está no formulário) e um
       duplicado viraria erro 500 de banco em vez de erro de formulário.

    Uso (o mixin vem antes de ModelForm):

        class ProntuarioForm(TenantFormMixin, forms.ModelForm): ...

    Filtros extras específicos de um formulário devem ser aplicados no próprio
    `__init__`, depois de `super().__init__()`.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._escopar_campos_de_escolha()
        instance = self.instance
        if isinstance(instance, TenantModel) and instance.clinica_id is None:
            clinica = get_clinica_atual()
            if clinica is not None:
                instance.clinica = clinica

    def _escopar_campos_de_escolha(self):
        for field in self.fields.values():
            queryset = getattr(field, "queryset", None)
            if queryset is None or not issubclass(queryset.model, TenantModel):
                continue
            novo = queryset.model._default_manager.all()
            limite = field.get_limit_choices_to()
            if limite:
                novo = novo.complex_filter(limite)
            field.queryset = novo

    def _get_validation_exclusions(self):
        exclude = super()._get_validation_exclusions()
        if isinstance(self.instance, TenantModel) and self.instance.clinica_id:
            exclude.discard("clinica")
        return exclude
