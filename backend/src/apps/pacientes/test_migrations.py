from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

ANTES = [("pacientes", "0003_paciente_prontuario_clinica")]
PREENCHIDA = [("pacientes", "0004_preencher_clinica")]


class PreencherClinicaMigrationTests(TransactionTestCase):
    """Roda a migração de dados 0004 contra linhas criadas no estado da 0003."""

    def migrar(self, alvo):
        executor = MigrationExecutor(connection)
        executor.migrate(alvo)
        return executor.loader.project_state(alvo).apps

    def setUp(self):
        self.apps_antes = self.migrar(ANTES)

    def tearDown(self):
        # Limpa o que os testes criaram (inclusive linhas sem clínica, que
        # impediriam a 0005) e volta ao estado final.
        self.apps_antes.get_model("pacientes", "Paciente").objects.all().delete()
        self.apps_antes.get_model("clinicas", "Clinica").objects.all().delete()
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def criar_clinica(self, apps, slug, cnpj):
        return apps.get_model("clinicas", "Clinica").objects.create(
            nome=slug, slug=slug, cnpj=cnpj
        )

    def criar_paciente(self, apps):
        return apps.get_model("pacientes", "Paciente").objects.create(
            primeiro_nome="Ana",
            sobrenome="Silva",
            data_nascimento=date(2000, 1, 1),
            genero="outro",
        )

    def test_preenche_com_a_unica_clinica_existente(self):
        clinica = self.criar_clinica(self.apps_antes, "vida", "11222333000181")
        paciente = self.criar_paciente(self.apps_antes)

        apps_depois = self.migrar(PREENCHIDA)

        Paciente = apps_depois.get_model("pacientes", "Paciente")
        self.assertEqual(Paciente.objects.get(pk=paciente.pk).clinica_id, clinica.pk)

    def test_banco_sem_pacientes_migra_sem_clinica(self):
        self.migrar(PREENCHIDA)  # não deve levantar erro

    def test_para_com_aviso_se_nao_ha_clinica(self):
        self.criar_paciente(self.apps_antes)
        with self.assertRaisesMessage(RuntimeError, "nenhuma clínica"):
            self.migrar(PREENCHIDA)

    def test_para_com_aviso_se_ha_varias_clinicas(self):
        self.criar_clinica(self.apps_antes, "vida", "11222333000181")
        self.criar_clinica(self.apps_antes, "sol", "11444777000161")
        self.criar_paciente(self.apps_antes)
        with self.assertRaisesMessage(RuntimeError, "mais de uma clínica"):
            self.migrar(PREENCHIDA)
