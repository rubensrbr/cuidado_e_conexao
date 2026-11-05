# ruff: noqa: E402
from unittest import SkipTest

from django.apps import apps

if not apps.is_installed("faturamentos"):
    raise SkipTest("app 'faturamentos' não está em INSTALLED_APPS neste release")

from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
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


class RelatorioPdfFaturamentosTests(BaseComClinicas):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.sem_clinica = User.objects.create_user(
            "sem_clinica@example.com", password="x"
        )
        cls.url = reverse("faturamentos:faturamento_report_pdf")
        with clinica_atual(cls.vida):
            # Cancelado: aparece na tabela, mas fora dos totais.
            criar_faturamento(
                criar_paciente("Caio", sobrenome="Pinto"),
                date(2027, 1, 25),
                status="cancelado",
            )

    def gerar(self, **parametros):
        """Gera o PDF e devolve (resposta, html que foi enviado ao WeasyPrint)."""
        capturado = {}

        def espiar(*args, **kwargs):
            capturado["html"] = render_to_string(*args, **kwargs)
            return capturado["html"]

        with mock.patch("faturamentos.views.render_to_string", side_effect=espiar):
            resposta = self.client.get(self.url, parametros)
        return resposta, capturado.get("html", "")

    def test_exige_login(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta["Location"].startswith("/login/"))

    def test_devolve_um_pdf_para_download(self):
        self.client.force_login(self.maria)
        resposta, _ = self.gerar()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "application/pdf")
        self.assertTrue(resposta.content.startswith(b"%PDF"))
        disposicao = resposta["Content-Disposition"]
        self.assertTrue(disposicao.startswith('attachment; filename="faturamentos_'))
        self.assertTrue(disposicao.endswith('.pdf"'))

    def test_relatorio_traz_so_a_clinica_atual(self):
        self.client.force_login(self.maria)
        _, html = self.gerar()
        self.assertIn("Ana Silva", html)
        self.assertIn("Bruno Souza", html)
        self.assertNotIn("Erica", html)
        self.assertIn("Vida", html)
        self.assertIn("11.222.333/0001-81", html)

    def test_totais_ignoram_cancelados(self):
        self.client.force_login(self.maria)
        resposta, html = self.gerar()
        self.assertIn("Caio Pinto", html)  # cancelado aparece na tabela
        # Ana (pendente) + Bruno (pago): R$ 200 cobrados, nenhum pago, 200 pendentes.
        self.assertIn("R$ 200,00", html)
        self.assertNotIn("R$ 300,00", html)

    def test_respeita_os_filtros_da_lista(self):
        self.client.force_login(self.maria)
        _, html = self.gerar(status="pago", data_de="2027-01-01", data_ate="2027-01-30")
        self.assertIn("Bruno Souza", html)
        self.assertNotIn("Ana Silva", html)
        self.assertIn("3 filtros aplicados", html)
        self.assertIn("de 01/01/2027", html)
        self.assertIn("até 30/01/2027", html)

    def test_filtro_invalido_nao_vira_todos_os_faturamentos(self):
        self.client.force_login(self.maria)
        _, html = self.gerar(data_de="2027-01-30", data_ate="2027-01-01")
        self.assertNotIn("Ana Silva", html)
        self.assertIn("Nenhum faturamento encontrado com esses filtros.", html)

    def test_usuario_sem_clinica_nao_gera_o_relatorio(self):
        self.client.force_login(self.sem_clinica)
        resposta, html = self.gerar()
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(html, "")  # nem chegou a montar o relatório

    def test_lista_tem_botao_gerar_pdf_que_leva_os_filtros(self):
        self.client.force_login(self.maria)
        resposta = self.client.get(
            reverse("faturamentos:faturamento_list"), {"status": "pago", "page": 1}
        )
        self.assertContains(resposta, "Gerar PDF")
        self.assertContains(resposta, f"{self.url}?status=pago")
        self.assertNotContains(resposta, "status=pago&amp;page")
        # O botão principal continua lá.
        self.assertContains(resposta, "Novo faturamento")

    def test_botao_acompanha_filtros_lembrados_pela_sessao(self):
        # Volta à lista sem parâmetros: o mixin redireciona para os últimos
        # filtros, e o botão do PDF sai com eles.
        self.client.force_login(self.maria)
        lista = reverse("faturamentos:faturamento_list")
        self.client.get(lista, {"status": "pago"})
        resposta = self.client.get(lista, follow=True)
        self.assertContains(resposta, f"{self.url}?status=pago")
