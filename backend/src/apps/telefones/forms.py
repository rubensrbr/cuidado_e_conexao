from django import forms

from .models import Telefone


class TelefoneForm(forms.ModelForm):
    class Meta:
        model = Telefone
        fields = ["numero", "tipo", "principal"]
        widgets = {
            "numero": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "+55 85 91234-5678"}
            ),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "principal": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
