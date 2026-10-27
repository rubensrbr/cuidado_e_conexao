# ruff: noqa: E402
from unittest import SkipTest

from django.apps import apps

if not apps.is_installed("faturamentos"):
    raise SkipTest("app 'faturamentos' não está em INSTALLED_APPS neste release")

from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from clinicas.models import Clinica, Membro
from clinicas.helpers_de_teste import grupo_com_todas_as_permissoes
from clinicas.tenancy import ClinicaIncorreta, SemClinicaAtual, clinica_atual
from consultas.models import Consulta
from pacientes.models import Paciente
from profissionais.models import Profissional, TipoProfissional

from .forms import FaturamentoForm
from .models import Faturamento
from .views import FaturamentoListView

CNPJ_VIDA = "11222333000181"
CNPJ_SOL = "11444777000161"


def criar_paciente(nome):
    return Paciente.objects.create(
        primeiro_nome=nome,
        sobrenome="Silva",
        data_nascimento=date(2000, 1, 1),
        genero="outro",
    )


def criar_consulta(paciente):
    tipo, _ = TipoProfissional.objects.get_or_create(descricao="Psicólogo")
    profissional = Profissional.objects.create(
        primeiro_nome="Dra",
        sobrenome=paciente.primeiro_nome,
        email=f"dra.{paciente.primeiro_nome.lower()}@example.com",
        tipo_profissional=tipo,
        numero_registro="1",
        valor_hora=Decimal("100.00"),
    )
    return Consulta.objects.create(
        paciente=paciente,
        profissional=profissional,
        data_consulta=date(2026, 11, 3),
        hora_inicio=time(9),
        hora_fim=time(10),
        tipo_consulta="retorno",
    )


def criar_faturamento(paciente, consulta=None, **kwargs):
    dados = {
        "paciente": paciente,
        "consulta": consulta,
        "data_servico": date(2026, 11, 3),
        "valor_cobrado": Decimal("150.00"),
    }
    dados.update(kwargs)
    return Faturamento.objects.create(**dados)


class FaturamentosTenantBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vida = Clinica.objects.create(nome="Vida", cnpj=CNPJ_VIDA, slug="vida")
        cls.sol = Clinica.objects.create(nome="Sol", cnpj=CNPJ_SOL, slug="sol")
        with clinica_atual(cls.vida):
            cls.ana = criar_paciente("Ana")
            cls.consulta_vida = criar_consulta(cls.ana)
            cls.fat_vida = criar_faturamento(cls.ana, cls.consulta_vida)
        with clinica_atual(cls.sol):
            cls.beto = criar_paciente("Beto")
            cls.consulta_sol = criar_consulta(cls.beto)
            cls.fat_sol = criar_faturamento(cls.beto, cls.consulta_sol)


class FaturamentoTenantModelTests(FaturamentosTenantBase):
    def test_faturamento_recebe_a_clinica_atual(self):
        self.assertEqual(self.fat_vida.clinica, self.vida)
        self.assertEqual(self.fat_sol.clinica, self.sol)

    def test_cada_clinica_ve_so_os_proprios_faturamentos(self):
        with clinica_atual(self.vida):
            self.assertEqual(list(Faturamento.objects.all()), [self.fat_vida])
            self.assertEqual(list(self.ana.faturamentos.all()), [self.fat_vida])
            self.assertEqual(
                list(self.consulta_vida.faturamentos.all()), [self.fat_vida]
            )
        with clinica_atual(self.sol):
            self.assertEqual(list(Faturamento.objects.all()), [self.fat_sol])

    def test_sem_clinica_atual_nao_ve_nem_grava(self):
        self.assertEqual(Faturamento.objects.count(), 0)
        with self.assertRaises(SemClinicaAtual):
            criar_faturamento(self.ana)

    def test_nao_altera_faturamento_de_outra_clinica(self):
        with clinica_atual(self.vida), self.assertRaises(ClinicaIncorreta):
            self.fat_sol.save()

    def test_todas_enxerga_as_duas_clinicas(self):
        self.assertEqual(Faturamento.todas.count(), 2)

    def test_clean_rejeita_consulta_de_outra_clinica(self):
        self.fat_vida.consulta = self.consulta_sol
        with self.assertRaises(ValidationError) as erro:
            self.fat_vida.clean()
        self.assertIn("consulta", erro.exception.message_dict)

    def test_clean_aceita_consulta_da_mesma_clinica_e_sem_consulta(self):
        self.fat_vida.clean()
        self.fat_vida.consulta = None
        self.fat_vida.clean()


class FaturamentoFormTenantTests(FaturamentosTenantBase):
    def dados(self, paciente, consulta=None, **kwargs):
        dados = {
            "paciente": paciente.pk,
            "consulta": consulta.pk if consulta else "",
            "data_servico": "2026-11-10",
            "valor_cobrado": "200.00",
            "valor_pago": "0",
            "status_pagamento": "pendente",
        }
        dados.update(kwargs)
        return dados

    def test_formulario_aceita_paciente_e_consulta_da_propria_clinica(self):
        with clinica_atual(self.vida):
            form = FaturamentoForm(data=self.dados(self.ana, self.consulta_vida))
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.save().clinica, self.vida)

    def test_formulario_rejeita_paciente_de_outra_clinica(self):
        with clinica_atual(self.vida):
            form = FaturamentoForm(data=self.dados(self.beto))
            self.assertFalse(form.is_valid())
            self.assertIn("paciente", form.errors)

    def test_formulario_rejeita_consulta_de_outra_clinica(self):
        with clinica_atual(self.vida):
            form = FaturamentoForm(data=self.dados(self.ana, self.consulta_sol))
            self.assertFalse(form.is_valid())
            self.assertIn("consulta", form.errors)

    def test_formulario_lista_so_pacientes_e_consultas_da_clinica(self):
        with clinica_atual(self.vida):
            form = FaturamentoForm()
            self.assertEqual(list(form.fields["paciente"].queryset), [self.ana])
            self.assertEqual(
                list(form.fields["consulta"].queryset), [self.consulta_vida]
            )


class FaturamentoViewsTenantTests(FaturamentosTenantBase):
    # O app ainda não tem templates, então só testamos o que não renderiza
    # página: o queryset da listagem, os 404 e os POSTs que redirecionam.
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.maria = get_user_model().objects.create_user("maria", password="x")
        grupo = grupo_com_todas_as_permissoes("Recepção")
        Membro.objects.create(user=cls.maria, clinica=cls.vida, grupo=grupo)

    def setUp(self):
        self.client.force_login(self.maria)

    def test_listagem_mostra_so_a_clinica_atual(self):
        view = FaturamentoListView()
        view.setup(RequestFactory().get("/"))
        with clinica_atual(self.vida):
            self.assertEqual(list(view.get_queryset()), [self.fat_vida])
        with clinica_atual(self.sol):
            self.assertEqual(list(view.get_queryset()), [self.fat_sol])

    def test_faturamento_de_outra_clinica_da_404(self):
        for nome in ("faturamento_detail", "faturamento_update", "faturamento_delete"):
            with self.subTest(view=nome):
                url = reverse(f"faturamentos:{nome}", kwargs={"uuid": self.fat_sol.uuid})
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_nao_deleta_faturamento_de_outra_clinica(self):
        url = reverse(
            "faturamentos:faturamento_delete", kwargs={"uuid": self.fat_sol.uuid}
        )
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(Faturamento.todas.filter(pk=self.fat_sol.pk).exists())

    def test_deleta_faturamento_da_propria_clinica(self):
        url = reverse(
            "faturamentos:faturamento_delete", kwargs={"uuid": self.fat_vida.uuid}
        )
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(Faturamento.todas.filter(pk=self.fat_vida.pk).exists())

    def test_novo_faturamento_nasce_na_clinica_do_usuario(self):
        resposta = self.client.post(
            reverse("faturamentos:faturamento_create"),
            {
                "paciente": self.ana.pk,
                "consulta": "",
                "data_servico": "2026-11-12",
                "valor_cobrado": "80.00",
                "valor_pago": "0",
                "status_pagamento": "pendente",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        novo = Faturamento.todas.get(data_servico=date(2026, 11, 12))
        self.assertEqual(novo.clinica, self.vida)
