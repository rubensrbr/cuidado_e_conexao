# ruff: noqa: E402
from unittest import SkipTest

from django.apps import apps

if not apps.is_installed("salas"):
    raise SkipTest("app 'salas' não está em INSTALLED_APPS neste release")

from datetime import date, time

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

ANTES = [("salas", "0002_sala_agendasala_clinica")]
PREENCHIDA = [("salas", "0003_preencher_clinica")]


class PreencherClinicaMigrationTests(TransactionTestCase):
    """Roda a migração de dados 0003 contra linhas criadas no estado da 0002."""

    def migrar(self, alvo):
        executor = MigrationExecutor(connection)
        executor.migrate(alvo)
        return executor.loader.project_state(alvo).apps

    def setUp(self):
        self.apps_antes = self.migrar(ANTES)

    def tearDown(self):
        # Limpa o que os testes criaram (inclusive linhas sem clínica, que
        # impediriam a 0004) e volta ao estado final.
        for app, modelo in (
            ("salas", "AgendaSala"),
            ("salas", "Sala"),
            ("clinicas", "Clinica"),
        ):
            self.apps_antes.get_model(app, modelo).objects.all().delete()
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def criar_clinica(self, slug, cnpj):
        return self.apps_antes.get_model("clinicas", "Clinica").objects.create(
            nome=slug, slug=slug, cnpj=cnpj
        )

    def criar_sala_com_agendamento(self, numero="1"):
        apps = self.apps_antes
        sala = apps.get_model("salas", "Sala").objects.create(numero_sala=numero)
        agenda = apps.get_model("salas", "AgendaSala").objects.create(
            sala=sala,
            data=date(2026, 11, 3),
            hora_inicio=time(9),
            hora_fim=time(10),
        )
        return sala, agenda

    def clinica_de(self, apps, modelo, pk):
        return apps.get_model("salas", modelo).objects.get(pk=pk).clinica_id

    def test_preenche_com_a_unica_clinica_existente(self):
        clinica = self.criar_clinica("vida", "11222333000181")
        sala, agenda = self.criar_sala_com_agendamento()

        apps = self.migrar(PREENCHIDA)

        self.assertEqual(self.clinica_de(apps, "Sala", sala.pk), clinica.pk)
        self.assertEqual(self.clinica_de(apps, "AgendaSala", agenda.pk), clinica.pk)

    def test_agendamento_herda_a_clinica_da_sala(self):
        clinica = self.criar_clinica("vida", "11222333000181")
        sala, agenda = self.criar_sala_com_agendamento()
        # Sala já preenchida e agendamento ainda não: o agendamento a segue,
        # sem exigir "uma única clínica".
        self.apps_antes.get_model("salas", "Sala").objects.filter(pk=sala.pk).update(
            clinica=clinica
        )
        self.criar_clinica("sol", "11444777000161")

        apps = self.migrar(PREENCHIDA)

        self.assertEqual(self.clinica_de(apps, "AgendaSala", agenda.pk), clinica.pk)

    def test_banco_sem_salas_migra_sem_clinica(self):
        self.migrar(PREENCHIDA)

    def test_banco_sem_salas_migra_com_varias_clinicas(self):
        self.criar_clinica("vida", "11222333000181")
        self.criar_clinica("sol", "11444777000161")
        self.migrar(PREENCHIDA)

    def test_para_com_aviso_se_ha_salas_e_nenhuma_clinica(self):
        self.criar_sala_com_agendamento()
        with self.assertRaisesMessage(RuntimeError, "nenhuma clínica"):
            self.migrar(PREENCHIDA)

    def test_para_com_aviso_se_ha_salas_e_varias_clinicas(self):
        self.criar_clinica("vida", "11222333000181")
        self.criar_clinica("sol", "11444777000161")
        self.criar_sala_com_agendamento()
        with self.assertRaisesMessage(RuntimeError, "mais de uma clínica"):
            self.migrar(PREENCHIDA)
