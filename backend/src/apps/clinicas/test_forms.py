from datetime import date

from django.apps import apps
from django.test import TestCase

from clinicas.models import Clinica
from clinicas.tenancy import clinica_atual
from consultas.forms import ConsultaForm, ListaEsperaForm
from pacientes.models import Paciente
from profissionais.models import Profissional, TipoProfissional

if apps.is_installed("faturamentos"):
    from faturamentos.forms import FaturamentoForm


class TenantFormMixinTests(TestCase):
    """Os formulários de outros apps listam só pacientes/profissionais da clínica atual."""

    @classmethod
    def setUpTestData(cls):
        cls.vida = Clinica.objects.create(
            nome="Vida", cnpj="11222333000181", slug="vida"
        )
        cls.sol = Clinica.objects.create(nome="Sol", cnpj="11444777000161", slug="sol")
        tipo = TipoProfissional.objects.first()
        for clinica, nome in ((cls.vida, "Ana"), (cls.sol, "Beto")):
            with clinica_atual(clinica):
                Paciente.objects.create(
                    primeiro_nome=nome,
                    sobrenome="Silva",
                    data_nascimento=date(2000, 1, 1),
                    genero="outro",
                )
                Profissional.objects.create(
                    primeiro_nome=nome,
                    sobrenome="Lima",
                    email=f"{nome.lower()}@example.com",
                    tipo_profissional=tipo,
                    numero_registro="1",
                    valor_hora="100.00",
                )

    def nomes(self, form_class, campo, clinica):
        with clinica_atual(clinica):
            return [o.primeiro_nome for o in form_class().fields[campo].queryset]

    def test_formularios_listam_so_a_propria_clinica(self):
        casos = [
            (ConsultaForm, "paciente"),
            (ConsultaForm, "profissional"),
            (ListaEsperaForm, "paciente"),
        ]
        if apps.is_installed("faturamentos"):
            casos.append((FaturamentoForm, "paciente"))
        for form_class, campo in casos:
            with self.subTest(form=form_class.__name__, campo=campo):
                self.assertEqual(self.nomes(form_class, campo, self.vida), ["Ana"])
                self.assertEqual(self.nomes(form_class, campo, self.sol), ["Beto"])

    def test_sem_clinica_atual_os_campos_ficam_vazios(self):
        self.assertEqual(list(ConsultaForm().fields["paciente"].queryset), [])
