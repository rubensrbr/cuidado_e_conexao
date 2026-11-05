# ruff: noqa: E402
from unittest import SkipTest

from django.apps import apps

if not apps.is_installed("faturamentos"):
    raise SkipTest("app 'faturamentos' não está em INSTALLED_APPS neste release")

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clinicas.helpers_de_teste import grupo_com_todas_as_permissoes
from clinicas.models import Clinica, Membro
from clinicas.tenancy import clinica_atual
from pacientes.models import Paciente

from .filters import FaturamentoFilter
from .models import Faturamento

User = get_user_model()


def criar_paciente(nome, sobrenome="Silva"):
    return Paciente.objects.create(
        primeiro_nome=nome,
        sobrenome=sobrenome,
        data_nascimento=date(1990, 1, 1),
        genero="outro",
    )


def criar_faturamento(paciente, dia, status="pendente"):
    return Faturamento.objects.create(
        paciente=paciente,
        data_servico=dia,
        valor_cobrado=Decimal("100.00"),
        status_pagamento=status,
    )


class BaseComClinicas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vida = Clinica.objects.create(
            nome="Vida", cnpj="11222333000181", slug="vida"
        )
        cls.sol = Clinica.objects.create(nome="Sol", cnpj="11444777000161", slug="sol")
        cls.maria = User.objects.create_user("maria@example.com", password="x")
        Membro.objects.create(
            user=cls.maria,
            clinica=cls.vida,
            grupo=grupo_com_todas_as_permissoes("Administração"),
        )
        with clinica_atual(cls.vida):
            ana = criar_paciente("Ana")
            bruno = criar_paciente("Bruno", sobrenome="Souza")
            # Ana: pendente em 05/01/2027. Bruno: pago em 20/01/2027.
            criar_faturamento(ana, date(2027, 1, 5))
            criar_faturamento(bruno, date(2027, 1, 20), status="pago")
        with clinica_atual(cls.sol):
            criar_faturamento(criar_paciente("Erica"), date(2027, 1, 10))

    def pacientes(self, faturamentos):
        return sorted(f.paciente.primeiro_nome for f in faturamentos)


class FaturamentoFilterTests(BaseComClinicas):
    def filtrar(self, **dados):
        with clinica_atual(self.vida):
            filtro = FaturamentoFilter(dados, queryset=Faturamento.objects.all())
            self.assertTrue(filtro.is_valid(), filtro.form.errors)
            return self.pacientes(filtro.qs)

    def test_sem_filtro_devolve_todos_da_clinica(self):
        self.assertEqual(self.filtrar(), ["Ana", "Bruno"])

    def test_busca_por_nome_do_paciente(self):
        for termo, esperado in [
            ("ana", ["Ana"]),
            ("SOUZA", ["Bruno"]),
            ("silva", ["Ana"]),
            ("bruno souza", ["Bruno"]),
            ("ana souza", []),
            ("erica", []),  # paciente de outra clínica
        ]:
            with self.subTest(termo=termo):
                self.assertEqual(self.filtrar(busca=termo), esperado)

    def test_filtro_de_status(self):
        self.assertEqual(self.filtrar(status="pago"), ["Bruno"])
        self.assertEqual(self.filtrar(status="pendente"), ["Ana"])
        self.assertEqual(self.filtrar(status="cancelado"), [])

    def test_filtro_de_periodo_inclui_os_extremos(self):
        self.assertEqual(self.filtrar(data_de="2027-01-05"), ["Ana", "Bruno"])
        self.assertEqual(self.filtrar(data_de="2027-01-06"), ["Bruno"])
        self.assertEqual(self.filtrar(data_ate="2027-01-05"), ["Ana"])
        self.assertEqual(
            self.filtrar(data_de="2027-01-01", data_ate="2027-01-30"), ["Ana", "Bruno"]
        )
        self.assertEqual(
            self.filtrar(data_de="2027-01-06", data_ate="2027-01-19"), []
        )

    def test_periodo_invertido_e_rejeitado(self):
        with clinica_atual(self.vida):
            filtro = FaturamentoFilter(
                {"data_de": "2027-01-30", "data_ate": "2027-01-01"},
                queryset=Faturamento.objects.all(),
            )
            self.assertFalse(filtro.is_valid())
            self.assertIn("data_ate", filtro.form.errors)

    def test_filtros_se_combinam_com_e(self):
        self.assertEqual(self.filtrar(status="pago", busca="ana"), [])
        self.assertEqual(
            self.filtrar(status="pago", busca="bruno", data_de="2027-01-15"), ["Bruno"]
        )


class FaturamentoListaFiltradaTests(BaseComClinicas):
    def setUp(self):
        self.client.force_login(self.maria)
        self.url = reverse("faturamentos:faturamento_list")

    def test_lista_aplica_filtros_da_url(self):
        resposta = self.client.get(
            self.url, {"data_de": "2027-01-01", "data_ate": "2027-01-10"}
        )
        self.assertEqual(self.pacientes(resposta.context["faturamentos"]), ["Ana"])
        self.assertEqual(resposta.context["filtros_ativos"], 2)

    def test_periodo_invertido_nao_vira_mostrar_tudo(self):
        resposta = self.client.get(
            self.url, {"data_de": "2027-01-30", "data_ate": "2027-01-01"}
        )
        self.assertEqual(list(resposta.context["faturamentos"]), [])
        self.assertContains(resposta, "A data final não pode ser anterior à inicial.")

    def test_nao_vaza_faturamento_de_outra_clinica(self):
        resposta = self.client.get(self.url, {"busca": "erica"})
        self.assertEqual(list(resposta.context["faturamentos"]), [])
