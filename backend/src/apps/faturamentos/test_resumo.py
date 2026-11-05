# ruff: noqa: E402
from unittest import SkipTest

from django.apps import apps

if not apps.is_installed("faturamentos"):
    raise SkipTest("app 'faturamentos' não está em INSTALLED_APPS neste release")

from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from clinicas.helpers_de_teste import grupo_com_todas_as_permissoes
from clinicas.models import Clinica, Membro
from clinicas.tenancy import clinica_atual
from pacientes.models import Paciente

from .filters import FaturamentoResumoFilter
from .models import Faturamento
from .resumo import mes_atual, periodo_da_query, resumir

User = get_user_model()
D = Decimal


def criar_paciente(nome):
    return Paciente.objects.create(
        primeiro_nome=nome,
        sobrenome="Silva",
        data_nascimento=date(1990, 1, 1),
        genero="outro",
    )


def cobrar(nome, dia, status, cobrado, pago="0", **extra):
    return Faturamento.objects.create(
        paciente=criar_paciente(nome),
        data_servico=dia,
        valor_cobrado=D(cobrado),
        valor_pago=D(pago),
        status_pagamento=status,
        **extra,
    )


class Base(TestCase):
    """Janeiro/2027 da clínica Vida (com um lançamento fora do período) e uma Sol."""

    @classmethod
    def setUpTestData(cls):
        cls.vida = Clinica.objects.create(nome="Vida", cnpj="11222333000181", slug="vida")
        cls.sol = Clinica.objects.create(nome="Sol", cnpj="11444777000161", slug="sol")
        cls.maria = User.objects.create_user("maria@example.com", password="x")
        Membro.objects.create(
            user=cls.maria,
            clinica=cls.vida,
            grupo=grupo_com_todas_as_permissoes("Administração"),
        )
        cls.sem_clinica = User.objects.create_user("solo@example.com", password="x")
        with clinica_atual(cls.vida):
            cobrar("Ana", date(2027, 1, 5), "pendente", "100")
            cobrar("Bruno", date(2027, 1, 6), "pago", "150", pago="150")
            cobrar("Caio", date(2027, 1, 7), "parcialmente_pago", "200", pago="50")
            cobrar("Dani", date(2027, 1, 8), "atrasado", "120")
            cobrar("Eva", date(2027, 1, 9), "cancelado", "500")
            cobrar("Fabi", date(2027, 1, 10), "pago", "0", pro_bono=True)
            cobrar("Gil", date(2027, 3, 10), "pendente", "100")  # fora de janeiro
        with clinica_atual(cls.sol):
            cobrar("Erica", date(2027, 1, 10), "pendente", "999")


class ResumirTests(Base):
    def resumo(self, **periodo):
        with clinica_atual(self.vida):
            filtro = FaturamentoResumoFilter(
                periodo, queryset=Faturamento.objects.all()
            )
            self.assertTrue(filtro.is_valid(), filtro.form.errors)
            return resumir(filtro.qs)

    def janeiro(self):
        return self.resumo(data_de="2027-01-01", data_ate="2027-01-31")

    def test_totais_ignoram_cancelados(self):
        resumo = self.janeiro()
        self.assertEqual(resumo.total_cobrado, D("570"))  # 100 + 150 + 200 + 120
        self.assertEqual(resumo.total_pago, D("200"))  # 150 + 50
        self.assertEqual(resumo.total_pendente, D("370"))  # cobrado - pago

    def test_taxa_de_recebimento(self):
        self.assertEqual(self.janeiro().taxa_recebimento, D("35.1"))  # 200 / 570

    def test_taxa_e_none_sem_nada_cobrado(self):
        resumo = self.resumo(data_de="2028-01-01", data_ate="2028-01-31")
        self.assertIsNone(resumo.taxa_recebimento)
        self.assertEqual(resumo.total_cobrado, 0)
        self.assertEqual(resumo.total_pendente, 0)

    def test_quantidade_e_valor_por_status(self):
        por_status = {item.status: item for item in self.janeiro().por_status}
        self.assertEqual(
            [item.status for item in self.janeiro().por_status],
            ["pendente", "pago", "parcialmente_pago", "atrasado", "cancelado"],
        )
        esperado = {
            # status: (quantidade, valor que interessa, legenda)
            "pendente": (1, D("100"), "em aberto"),
            "pago": (1, D("150"), "recebido"),
            "parcialmente_pago": (1, D("150"), "em aberto"),  # 200 - 50
            "atrasado": (1, D("120"), "em aberto"),
            "cancelado": (1, D("500"), "cancelado"),
        }
        for status, (qtd, valor, legenda) in esperado.items():
            with self.subTest(status=status):
                self.assertEqual(por_status[status].qtd, qtd)
                self.assertEqual(por_status[status].valor, valor)
                self.assertEqual(por_status[status].legenda, legenda)

    def test_cancelado_aparece_no_status_mas_nao_nos_totais(self):
        resumo = self.janeiro()
        cancelado = next(i for i in resumo.por_status if i.status == "cancelado")
        self.assertEqual(cancelado.qtd, 1)
        self.assertNotIn(D("500"), (resumo.total_cobrado, resumo.total_pendente))

    def test_pro_bono_e_contado_a_parte_e_nao_infla_o_pago(self):
        resumo = self.janeiro()
        self.assertEqual(resumo.pro_bono, 1)
        pago = next(i for i in resumo.por_status if i.status == "pago")
        self.assertEqual(pago.qtd, 1)  # só o Bruno; a Fabi (pro bono) fica de fora

    def test_periodo_restringe_os_lancamentos(self):
        marco = self.resumo(data_de="2027-03-01", data_ate="2027-03-31")
        self.assertEqual(marco.total_cobrado, D("100"))
        tudo = self.resumo()
        self.assertEqual(tudo.total_cobrado, D("670"))

    def test_so_soma_a_clinica_atual(self):
        # A Erica (R$ 999) é da clínica Sol.
        self.assertNotIn(D("999"), (self.resumo().total_cobrado,))
        with clinica_atual(self.sol):
            self.assertEqual(resumir(Faturamento.objects.all()).total_cobrado, D("999"))


class PeriodoTests(SimpleTestCase):
    def test_mes_atual_vai_do_primeiro_ao_ultimo_dia(self):
        self.assertEqual(
            mes_atual(date(2027, 2, 14)), (date(2027, 2, 1), date(2027, 2, 28))
        )
        self.assertEqual(
            mes_atual(date(2028, 2, 14)), (date(2028, 2, 1), date(2028, 2, 29))
        )

    def test_periodo_da_query_leva_so_as_datas(self):
        get = {"data_de": "2027-01-01", "data_ate": "", "status": "pago", "busca": "x"}
        self.assertEqual(periodo_da_query(get), "data_de=2027-01-01")
        self.assertEqual(periodo_da_query({}), "")


class ResumoViewTests(Base):
    url = reverse("faturamentos:faturamento_resumo")
    janeiro = {"data_de": "2027-01-01", "data_ate": "2027-01-31"}

    def test_exige_login(self):
        resposta = self.client.get(self.url, self.janeiro)
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta["Location"].startswith("/login/"))

    def test_usuario_sem_clinica_e_barrado(self):
        self.client.force_login(self.sem_clinica)
        self.assertEqual(self.client.get(self.url, self.janeiro).status_code, 403)

    def test_sem_periodo_abre_no_mes_atual(self):
        self.client.force_login(self.maria)
        with mock.patch("faturamentos.resumo.timezone.localdate") as hoje:
            hoje.return_value = date(2027, 1, 15)
            resposta = self.client.get(self.url)
        self.assertRedirects(
            resposta,
            f"{self.url}?data_de=2027-01-01&data_ate=2027-01-31",
            fetch_redirect_response=False,
        )

    def test_mostra_os_cards_do_periodo(self):
        self.client.force_login(self.maria)
        resposta = self.client.get(self.url, self.janeiro)
        self.assertEqual(resposta.status_code, 200)
        for texto in ("R$ 570,00", "R$ 200,00", "R$ 370,00", "35,1%"):
            with self.subTest(texto=texto):
                self.assertContains(resposta, texto)
        for rotulo in ("Pendente", "Pago", "Parcialmente Pago", "Atrasado", "Cancelado"):
            self.assertContains(resposta, rotulo)
        self.assertNotContains(resposta, "R$ 999")  # outra clínica

    def test_campos_vazios_significam_todo_o_periodo(self):
        self.client.force_login(self.maria)
        resposta = self.client.get(self.url, {"data_de": "", "data_ate": ""})
        self.assertEqual(resposta.status_code, 200)  # sem redirecionar para o mês
        self.assertContains(resposta, "R$ 670,00")  # janeiro + março

    def test_periodo_invertido_mostra_erro_e_nao_vira_todos(self):
        self.client.force_login(self.maria)
        resposta = self.client.get(
            self.url, {"data_de": "2027-01-31", "data_ate": "2027-01-01"}
        )
        self.assertContains(resposta, "A data final não pode ser anterior à inicial.")
        self.assertNotContains(resposta, "R$ 570,00")
        self.assertNotContains(resposta, "R$ 670,00")

    def test_sem_nada_cobrado_a_taxa_e_um_traco(self):
        self.client.force_login(self.maria)
        resposta = self.client.get(
            self.url, {"data_de": "2028-01-01", "data_ate": "2028-01-31"}
        )
        self.assertContains(resposta, "R$ 0,00")
        self.assertNotContains(resposta, "%</div>")

    def test_card_de_status_leva_para_a_lista_filtrada_no_mesmo_periodo(self):
        self.client.force_login(self.maria)
        resposta = self.client.get(self.url, self.janeiro)
        lista = reverse("faturamentos:faturamento_list")
        self.assertContains(
            resposta,
            f"{lista}?status=atrasado&amp;data_de=2027-01-01&amp;data_ate=2027-01-31",
        )

    def test_botao_de_pdf_leva_o_periodo(self):
        self.client.force_login(self.maria)
        resposta = self.client.get(self.url, self.janeiro)
        pdf = reverse("faturamentos:faturamento_report_pdf")
        self.assertContains(resposta, f"{pdf}?data_de=2027-01-01&amp;data_ate=2027-01-31")


class AbasTests(Base):
    def test_lista_e_resumo_tem_as_duas_abas_e_marcam_a_atual(self):
        self.client.force_login(self.maria)
        lista = reverse("faturamentos:faturamento_list")
        resumo = reverse("faturamentos:faturamento_resumo")

        na_lista = self.client.get(lista, {"limpar": 1}, follow=True)
        self.assertContains(na_lista, 'aria-label="Visões de faturamentos"')
        self.assertContains(na_lista, f'href="{resumo}"')
        self.assertContains(na_lista, 'aria-current="page"', count=1)

        no_resumo = self.client.get(
            resumo, {"data_de": "2027-01-01", "data_ate": "2027-01-31"}
        )
        self.assertContains(no_resumo, f'href="{lista}?data_de=2027-01-01&amp;data_ate=2027-01-31"')
        self.assertContains(no_resumo, 'aria-current="page"', count=1)

    def test_a_aba_resumo_leva_o_periodo_da_lista(self):
        self.client.force_login(self.maria)
        resposta = self.client.get(
            reverse("faturamentos:faturamento_list"),
            {"data_de": "2027-01-01", "data_ate": "2027-01-31"},
        )
        resumo = reverse("faturamentos:faturamento_resumo")
        self.assertContains(
            resposta, f'href="{resumo}?data_de=2027-01-01&amp;data_ate=2027-01-31"'
        )
