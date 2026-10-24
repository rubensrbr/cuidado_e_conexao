from datetime import date

from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from clinicas.models import Clinica
from clinicas.tenancy import ClinicaIncorreta, SemClinicaAtual, clinica_atual
from pacientes.models import Paciente
from profissionais.models import Profissional, TipoProfissional

from .models import Telefone

CNPJ_VIDA = "11222333000181"
CNPJ_SOL = "11444777000161"


def criar_paciente(nome):
    return Paciente.objects.create(
        primeiro_nome=nome,
        sobrenome="Silva",
        data_nascimento=date(2000, 1, 1),
        genero="outro",
    )


def criar_profissional(nome):
    return Profissional.objects.create(
        primeiro_nome=nome,
        sobrenome="Lima",
        email=f"{nome.lower()}@example.com",
        tipo_profissional=TipoProfissional.objects.first(),
        numero_registro="123",
        valor_hora="100.00",
    )


class TelefoneTenantModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vida = Clinica.objects.create(nome="Vida", cnpj=CNPJ_VIDA, slug="vida")
        cls.sol = Clinica.objects.create(nome="Sol", cnpj=CNPJ_SOL, slug="sol")
        with clinica_atual(cls.vida):
            cls.ana = criar_paciente("Ana")
            cls.tel_ana = Telefone.objects.create(
                numero="85912345678", tipo="celular", pacientes=cls.ana
            )
        with clinica_atual(cls.sol):
            cls.dr_beto = criar_profissional("Beto")
            cls.tel_beto = Telefone.objects.create(
                numero="85987654321", tipo="comercial", profissionais=cls.dr_beto
            )

    def test_telefone_recebe_a_clinica_atual(self):
        self.assertEqual(self.tel_ana.clinica, self.vida)
        self.assertEqual(self.tel_beto.clinica, self.sol)

    def test_cada_clinica_ve_so_os_proprios_telefones(self):
        with clinica_atual(self.vida):
            self.assertEqual(list(Telefone.objects.all()), [self.tel_ana])
        with clinica_atual(self.sol):
            self.assertEqual(list(Telefone.objects.all()), [self.tel_beto])

    def test_sem_clinica_atual_nao_ve_nem_grava(self):
        self.assertEqual(Telefone.objects.count(), 0)
        with self.assertRaises(SemClinicaAtual):
            Telefone.objects.create(
                numero="85900000000", tipo="celular", pacientes=self.ana
            )

    def test_nao_altera_telefone_de_outra_clinica(self):
        with clinica_atual(self.vida), self.assertRaises(ClinicaIncorreta):
            self.tel_beto.save()

    def test_telefone_de_outra_clinica_nao_e_encontrado_por_uuid(self):
        with clinica_atual(self.vida):
            with self.assertRaises(Telefone.DoesNotExist):
                Telefone.objects.get(uuid=self.tel_beto.uuid)

    def test_relacao_reversa_do_paciente_e_filtrada(self):
        with clinica_atual(self.vida):
            self.assertEqual(list(self.ana.telefones.all()), [self.tel_ana])
        with clinica_atual(self.sol):
            self.assertEqual(list(self.ana.telefones.all()), [])

    def test_manager_todas_nao_filtra(self):
        self.assertEqual(Telefone.todas.count(), 2)


class TelefoneRotasAvulsasRemovidasTests(TestCase):
    """Telefones só são editados dentro de paciente/profissional (formsets)."""

    def test_nomes_de_url_nao_existem_mais(self):
        for nome in ("telefone_list", "telefone_create", "endereco_update"):
            with self.subTest(nome=nome), self.assertRaises(NoReverseMatch):
                reverse(f"telefones:{nome}")

    def test_caminho_antigo_devolve_404(self):
        for caminho in ("/telefones/", "/telefones/nova/"):
            with self.subTest(caminho=caminho):
                self.assertEqual(self.client.get(caminho).status_code, 404)
