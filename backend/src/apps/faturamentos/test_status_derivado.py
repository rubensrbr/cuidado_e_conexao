# ruff: noqa: E402
from unittest import SkipTest

from django.apps import apps

if not apps.is_installed("faturamentos"):
    raise SkipTest("app 'faturamentos' não está em INSTALLED_APPS neste release")

from datetime import date, time
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase

from .forms import FaturamentoForm
from .models import Faturamento, status_do_pagamento
from .resumo import resumir
from .test_pro_bono_pacotes import Base, dados_form

D = Decimal


class StatusDoPagamentoTests(SimpleTestCase):
    def test_status_vem_dos_valores(self):
        casos = [
            # (cobrado, pago, pro_bono, marcação) -> status
            ("150", "0", False, "", "pendente"),
            ("150", "50", False, "", "parcialmente_pago"),
            ("150", "149.99", False, "", "parcialmente_pago"),
            ("150", "150", False, "", "pago"),
            ("0", "0", True, "", "pago"),  # pro bono: nada a cobrar
        ]
        for cobrado, pago, pro_bono, marcacao, esperado in casos:
            with self.subTest(cobrado=cobrado, pago=pago, pro_bono=pro_bono):
                self.assertEqual(
                    status_do_pagamento(D(cobrado), D(pago), pro_bono, marcacao),
                    esperado,
                )

    def test_cancelado_vale_sempre(self):
        for pago in ("0", "50", "150"):
            with self.subTest(pago=pago):
                self.assertEqual(
                    status_do_pagamento(D("150"), D(pago), marcacao="cancelado"),
                    "cancelado",
                )

    def test_atrasado_vale_so_enquanto_falta_pagar(self):
        self.assertEqual(status_do_pagamento(D("150"), D("0"), marcacao="atrasado"), "atrasado")
        self.assertEqual(status_do_pagamento(D("150"), D("50"), marcacao="atrasado"), "atrasado")
        self.assertEqual(status_do_pagamento(D("150"), D("150"), marcacao="atrasado"), "pago")

    def test_status_antigos_na_marcacao_sao_ignorados(self):
        # "pendente", "pago" e "parcialmente_pago" nunca são marcados à mão.
        for marcacao in ("pendente", "pago", "parcialmente_pago", "qualquer"):
            with self.subTest(marcacao=marcacao):
                self.assertEqual(
                    status_do_pagamento(D("150"), D("0"), marcacao=marcacao), "pendente"
                )

    def test_aceita_texto_e_vazio(self):
        self.assertEqual(status_do_pagamento("150.00", "150.00"), "pago")
        self.assertEqual(status_do_pagamento(None, None), "pendente")


class ModeloDerivaOStatusTests(Base):
    def criar(self, status, cobrado="150", pago="0", **extra):
        return Faturamento.objects.create(
            paciente=self.ana,
            data_servico=date(2026, 11, 3),
            valor_cobrado=D(cobrado),
            valor_pago=D(pago),
            status_pagamento=status,
            **extra,
        )

    def test_combinacoes_contraditorias_sao_corrigidas_ao_salvar(self):
        casos = [
            ("pendente", "150", "pago"),  # pendente com tudo pago
            ("pendente", "50", "parcialmente_pago"),  # pendente com pagamento
            ("parcialmente_pago", "0", "pendente"),  # parcial sem pagamento
            ("parcialmente_pago", "150", "pago"),  # parcial com tudo pago
            ("pago", "0", "pendente"),  # pago sem pagamento
            ("pago", "50", "parcialmente_pago"),  # pago pela metade
            ("atrasado", "150", "pago"),  # atrasado já quitado
        ]
        for status, pago, esperado in casos:
            with self.subTest(status=status, pago=pago):
                self.assertEqual(self.criar(status, pago=pago).status_pagamento, esperado)

    def test_atrasado_e_cancelado_sao_mantidos(self):
        self.assertEqual(self.criar("atrasado").status_pagamento, "atrasado")
        self.assertEqual(self.criar("atrasado", pago="50").status_pagamento, "atrasado")
        self.assertEqual(self.criar("cancelado", pago="150").status_pagamento, "cancelado")

    def test_registrar_o_pagamento_depois_atualiza_o_status(self):
        fat = self.criar("pendente")
        fat.valor_pago = D("50")
        fat.save()
        fat.refresh_from_db()
        self.assertEqual(fat.status_pagamento, "parcialmente_pago")
        fat.valor_pago = D("150")
        fat.save()
        fat.refresh_from_db()
        self.assertEqual(fat.status_pagamento, "pago")

    def test_atrasado_quitado_depois_vira_pago(self):
        fat = self.criar("atrasado")
        fat.valor_pago = D("150")
        fat.save()
        fat.refresh_from_db()
        self.assertEqual(fat.status_pagamento, "pago")

    def test_save_com_update_fields_tambem_atualiza_o_status(self):
        fat = self.criar("pendente")
        fat.valor_pago = D("150")
        fat.save(update_fields=["valor_pago"])
        fat.refresh_from_db()
        self.assertEqual(fat.status_pagamento, "pago")

    def test_pro_bono_fica_pago(self):
        fat = self.criar("pendente", cobrado="0", pro_bono=True)
        self.assertEqual(fat.status_pagamento, "pago")


class FormularioDerivaOStatusTests(Base):
    def status_salvo(self, **dados):
        form = FaturamentoForm(dados_form(self.ana, **dados))
        self.assertTrue(form.is_valid(), form.errors)
        return form.save().status_pagamento

    def test_automatico_segue_o_valor_pago(self):
        self.assertEqual(self.status_salvo(valor_pago="0"), "pendente")
        self.assertEqual(self.status_salvo(valor_pago="50"), "parcialmente_pago")
        self.assertEqual(self.status_salvo(valor_pago="150"), "pago")

    def test_so_atrasado_e_cancelado_sao_escolhas_manuais(self):
        campo = FaturamentoForm().fields["status_pagamento"]
        self.assertEqual([v for v, _ in campo.choices], ["", "atrasado", "cancelado"])
        for status in ("pendente", "parcialmente_pago", "pago"):
            with self.subTest(status=status):
                form = FaturamentoForm(dados_form(self.ana, status_pagamento=status))
                self.assertFalse(form.is_valid())
                self.assertIn("status_pagamento", form.errors)

    def test_atrasado_com_pagamento_parcial_ou_nenhum(self):
        self.assertEqual(self.status_salvo(status_pagamento="atrasado"), "atrasado")
        self.assertEqual(
            self.status_salvo(status_pagamento="atrasado", valor_pago="50"), "atrasado"
        )

    def test_atrasado_com_tudo_pago_e_recusado(self):
        form = FaturamentoForm(
            dados_form(self.ana, status_pagamento="atrasado", valor_pago="150")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("status_pagamento", form.errors)

    def test_cancelado_vale_mesmo_com_pagamento(self):
        self.assertEqual(
            self.status_salvo(status_pagamento="cancelado", valor_pago="150"), "cancelado"
        )

    def test_pro_bono_e_pago_e_nao_pode_ser_atrasado(self):
        self.assertEqual(
            self.status_salvo(pro_bono="on", valor_cobrado="", valor_pago=""), "pago"
        )
        form = FaturamentoForm(
            dados_form(
                self.ana,
                pro_bono="on",
                valor_cobrado="",
                valor_pago="",
                status_pagamento="atrasado",
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn("status_pagamento", form.errors)

    def test_valor_invalido_nao_gera_erro_extra_de_status(self):
        form = FaturamentoForm(dados_form(self.ana, valor_pago="999"))
        self.assertFalse(form.is_valid())
        self.assertEqual(list(form.errors), ["valor_pago"])

    def test_edicao_mostra_so_marcacao_manual_e_recalcula(self):
        fat = Faturamento.objects.create(
            paciente=self.ana,
            data_servico=date(2026, 11, 3),
            valor_cobrado=D("150"),
            valor_pago=D("50"),
        )
        self.assertEqual(fat.status_pagamento, "parcialmente_pago")
        # Status derivado aparece como "Automático".
        self.assertEqual(FaturamentoForm(instance=fat).initial["status_pagamento"], "")
        # Pagar o restante pelo formulário de edição quita o faturamento.
        form = FaturamentoForm(dados_form(self.ana, valor_pago="150"), instance=fat)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().status_pagamento, "pago")

        atrasado = Faturamento.objects.create(
            paciente=self.ana,
            data_servico=date(2026, 11, 4),
            valor_cobrado=D("150"),
            status_pagamento="atrasado",
        )
        self.assertEqual(
            FaturamentoForm(instance=atrasado).initial["status_pagamento"], "atrasado"
        )


class ResumoCoerenteTests(Base):
    def test_cartoes_e_totais_concordam_mesmo_com_entradas_contraditorias(self):
        # Entradas que antes quebravam o Resumo: o status é recalculado ao salvar.
        entradas = [
            ("pendente", "150"),
            ("parcialmente_pago", "0"),
            ("parcialmente_pago", "150"),
            ("atrasado", "150"),
            ("pago", "0"),
            ("pago", "40"),
            ("atrasado", "40"),
            ("cancelado", "150"),
        ]
        for dia, (status, pago) in enumerate(entradas, start=1):
            Faturamento.objects.create(
                paciente=self.ana,
                data_servico=date(2026, 11, dia),
                valor_cobrado=D("150"),
                valor_pago=D(pago),
                status_pagamento=status,
            )
        resumo = resumir(Faturamento.objects.all())
        por_status = {linha.status: linha for linha in resumo.por_status}

        # O que um cartão de status diz sobre os valores é verdade.
        self.assertEqual(por_status["pago"].pago, por_status["pago"].cobrado)
        self.assertEqual(por_status["pendente"].pago, D("0"))
        parcial = por_status["parcialmente_pago"]
        self.assertTrue(D("0") < parcial.pago < parcial.cobrado)

        # Total pago = pago de todos os cartões, exceto o cancelado.
        soma = sum(
            (linha.pago for linha in resumo.por_status if linha.status != "cancelado"),
            D("0"),
        )
        self.assertEqual(resumo.total_pago, soma)
        self.assertEqual(
            resumo.total_pago + resumo.total_pendente, resumo.total_cobrado
        )


class MigracaoCorrigeStatusTests(TransactionTestCase):
    """Roda a migração de dados 0007 contra linhas criadas no estado da 0006."""

    ANTES = [("faturamentos", "0006_proteger_historico_financeiro")]
    DEPOIS = [("faturamentos", "0007_status_derivado_do_pagamento")]
    DEPENDENCIAS = [
        ("pacientes", "0006_paciente_pro_bono"),
        ("profissionais", "0005_clinica_obrigatoria_email_por_clinica"),
        ("consultas", "0006_clinica_obrigatoria"),
    ]

    def migrar(self, alvo):
        executor = MigrationExecutor(connection)
        executor.migrate(alvo)
        return executor.loader.project_state(alvo + self.DEPENDENCIAS).apps

    def setUp(self):
        self.apps_antes = self.migrar(self.ANTES)

    def tearDown(self):
        for app, modelo in (
            ("faturamentos", "Faturamento"),
            ("pacientes", "Paciente"),
            ("clinicas", "Clinica"),
        ):
            self.apps_antes.get_model(app, modelo)._base_manager.all().delete()
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def criar(self, paciente, dia, status, cobrado, pago, **extra):
        Faturamento = self.apps_antes.get_model("faturamentos", "Faturamento")
        return Faturamento.objects.create(
            clinica=paciente.clinica,
            paciente=paciente,
            data_servico=date(2026, 11, dia),
            valor_cobrado=D(cobrado),
            valor_pago=D(pago),
            status_pagamento=status,
            **extra,
        ).pk

    def test_corrige_as_contradicoes_e_preserva_cancelado_e_atrasado(self):
        apps = self.apps_antes
        clinica = apps.get_model("clinicas", "Clinica").objects.create(
            nome="Vida", slug="vida", cnpj="11222333000181"
        )
        paciente = apps.get_model("pacientes", "Paciente").objects.create(
            clinica=clinica,
            primeiro_nome="Ana",
            sobrenome="Silva",
            data_nascimento=date(2000, 1, 1),
            genero="outro",
        )
        esperados = {
            self.criar(paciente, 1, "pendente", "150", "150"): "pago",
            self.criar(paciente, 2, "pendente", "150", "50"): "parcialmente_pago",
            self.criar(paciente, 3, "parcialmente_pago", "150", "0"): "pendente",
            self.criar(paciente, 4, "parcialmente_pago", "150", "150"): "pago",
            self.criar(paciente, 5, "pago", "150", "0"): "pendente",
            self.criar(paciente, 6, "atrasado", "150", "150"): "pago",
            self.criar(paciente, 7, "atrasado", "150", "50"): "atrasado",
            self.criar(paciente, 8, "atrasado", "150", "0"): "atrasado",
            self.criar(paciente, 9, "cancelado", "150", "150"): "cancelado",
            self.criar(paciente, 10, "pago", "0", "0", pro_bono=True): "pago",
            self.criar(paciente, 11, "pago", "150", "150"): "pago",  # já correto
        }

        apps_depois = self.migrar(self.DEPOIS)

        Faturamento = apps_depois.get_model("faturamentos", "Faturamento")
        for pk, esperado in esperados.items():
            with self.subTest(pk=pk, esperado=esperado):
                self.assertEqual(
                    Faturamento._base_manager.get(pk=pk).status_pagamento, esperado
                )

    def test_banco_sem_faturamentos_migra_sem_erro(self):
        self.migrar(self.DEPOIS)
