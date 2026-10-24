from datetime import date

from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from clinicas.models import Clinica
from clinicas.tenancy import ClinicaIncorreta, SemClinicaAtual, clinica_atual
from localidades.models import Cidade, Estado
from pacientes.models import Paciente
from profissionais.models import Profissional, TipoProfissional

from .models import Endereco

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


def criar_endereco(cidade, **dono):
    return Endereco.objects.create(
        logradouro="Rua A",
        numero="10",
        bairro="Centro",
        cidade=cidade,
        cep="70000-000",
        **dono,
    )


class EnderecoTenantModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        estado = Estado.objects.create(codigo_ibge=52, sigla="GO", nome="Goiás")
        cls.cidade = Cidade.objects.create(
            codigo_ibge=5208707, nome="Goiânia", estado=estado
        )
        cls.vida = Clinica.objects.create(nome="Vida", cnpj=CNPJ_VIDA, slug="vida")
        cls.sol = Clinica.objects.create(nome="Sol", cnpj=CNPJ_SOL, slug="sol")
        with clinica_atual(cls.vida):
            cls.dra_ana = criar_profissional("Ana")
            cls.end_ana = criar_endereco(cls.cidade, profissionais=cls.dra_ana)
        with clinica_atual(cls.sol):
            cls.beto = criar_paciente("Beto")
            cls.end_beto = criar_endereco(cls.cidade, pacientes=cls.beto)

    def test_endereco_recebe_a_clinica_atual(self):
        self.assertEqual(self.end_ana.clinica, self.vida)
        self.assertEqual(self.end_beto.clinica, self.sol)

    def test_cada_clinica_ve_so_os_proprios_enderecos(self):
        with clinica_atual(self.vida):
            self.assertEqual(list(Endereco.objects.all()), [self.end_ana])
        with clinica_atual(self.sol):
            self.assertEqual(list(Endereco.objects.all()), [self.end_beto])

    def test_sem_clinica_atual_nao_ve_nem_grava(self):
        self.assertEqual(Endereco.objects.count(), 0)
        with self.assertRaises(SemClinicaAtual):
            criar_endereco(self.cidade, pacientes=self.beto)

    def test_nao_altera_endereco_de_outra_clinica(self):
        with clinica_atual(self.vida), self.assertRaises(ClinicaIncorreta):
            self.end_beto.save()

    def test_endereco_de_outra_clinica_nao_e_encontrado_por_uuid(self):
        with clinica_atual(self.vida):
            with self.assertRaises(Endereco.DoesNotExist):
                Endereco.objects.get(uuid=self.end_beto.uuid)

    def test_relacao_reversa_do_profissional_e_filtrada(self):
        with clinica_atual(self.vida):
            self.assertEqual(list(self.dra_ana.enderecos.all()), [self.end_ana])
        with clinica_atual(self.sol):
            self.assertEqual(list(self.dra_ana.enderecos.all()), [])

    def test_manager_todas_nao_filtra(self):
        self.assertEqual(Endereco.todas.count(), 2)

    def test_cidade_continua_global(self):
        # Estado/Cidade são dados de referência compartilhados por todas as clínicas.
        with clinica_atual(self.vida):
            self.assertEqual(Cidade.objects.count(), 1)
        with clinica_atual(self.sol):
            self.assertEqual(Cidade.objects.count(), 1)


class EnderecoRotasAvulsasRemovidasTests(TestCase):
    """Endereços só são editados dentro do profissional (formset)."""

    def test_nomes_de_url_nao_existem_mais(self):
        for nome in ("endereco_list", "endereco_create", "endereco_update"):
            with self.subTest(nome=nome), self.assertRaises(NoReverseMatch):
                reverse(f"enderecos:{nome}")

    def test_caminho_antigo_devolve_404(self):
        for caminho in ("/enderecos/", "/enderecos/nova/"):
            with self.subTest(caminho=caminho):
                self.assertEqual(self.client.get(caminho).status_code, 404)


class EnderecoForaDoAdminTests(TestCase):
    def test_endereco_nao_esta_registrado_no_admin(self):
        from django.contrib import admin

        self.assertFalse(admin.site.is_registered(Endereco))
