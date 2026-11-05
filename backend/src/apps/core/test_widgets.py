from datetime import date
from importlib import import_module

from django import forms
from django.apps import apps
from django.test import SimpleTestCase, TestCase, override_settings

from core.widgets import DateInput
from pacientes.forms import PacienteForm
from pacientes.models import Paciente


def formularios_do_projeto():
    """Toda classe de formulário definida em `<app>/forms.py` dos apps instalados."""
    for config in apps.get_app_configs():
        try:
            modulo = import_module(f"{config.name}.forms")
        except ModuleNotFoundError:
            continue
        for nome, classe in vars(modulo).items():
            if (
                isinstance(classe, type)
                and issubclass(classe, forms.BaseForm)
                and classe.__module__ == modulo.__name__
            ):
                yield f"{config.name}.forms.{nome}", classe


class DateInputTests(SimpleTestCase):
    @override_settings(LANGUAGE_CODE="pt-br", USE_L10N=True)
    def test_renderiza_data_em_iso_mesmo_em_pt_br(self):
        html = DateInput().render("data", date(2026, 11, 5))
        self.assertIn('value="2026-11-05"', html)
        self.assertIn('type="date"', html)
        self.assertIn('class="form-control"', html)

    @override_settings(LANGUAGE_CODE="pt-br", USE_L10N=True)
    def test_o_widget_padrao_do_django_formata_em_pt_br_e_nao_serve(self):
        # Documenta o problema: este valor, em um <input type="date">, aparece vazio.
        html = forms.DateInput(attrs={"type": "date"}).render("data", date(2026, 11, 5))
        self.assertIn('value="05/11/2026"', html)

    def test_atributos_extras_sao_mantidos(self):
        html = DateInput(attrs={"class": "form-control form-control-sm", "min": "2000-01-01"}).render(
            "data", None
        )
        self.assertIn("form-control-sm", html)
        self.assertIn('min="2000-01-01"', html)

    def test_todo_campo_de_data_dos_formularios_usa_o_widget_iso(self):
        verificados = 0
        for caminho, classe in formularios_do_projeto():
            for nome, campo in classe.base_fields.items():
                if isinstance(campo, forms.DateField):
                    with self.subTest(formulario=caminho, campo=nome):
                        self.assertIsInstance(campo.widget, DateInput)
                    verificados += 1
        self.assertGreater(verificados, 0)


class EdicaoMostraADataTests(TestCase):
    @override_settings(LANGUAGE_CODE="pt-br", USE_L10N=True)
    def test_formulario_de_edicao_do_paciente_preenche_a_data(self):
        paciente = Paciente(
            primeiro_nome="Ana",
            sobrenome="Silva",
            data_nascimento=date(1990, 3, 7),
            genero="outro",
        )
        html = str(PacienteForm(instance=paciente)["data_nascimento"])
        self.assertIn('value="1990-03-07"', html)
