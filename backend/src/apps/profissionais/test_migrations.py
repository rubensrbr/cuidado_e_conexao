from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

ANTES = [("profissionais", "0003_profissional_disponibilidade_clinica")]
PREENCHIDA = [("profissionais", "0004_preencher_clinica")]


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
        self.apps_antes.get_model("profissionais", "Profissional").objects.all().delete()
        self.apps_antes.get_model("clinicas", "Clinica").objects.all().delete()
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def criar_clinica(self, apps, slug, cnpj):
        return apps.get_model("clinicas", "Clinica").objects.create(
            nome=slug, slug=slug, cnpj=cnpj
        )

    def criar_profissional(self, apps):
        # TransactionTestCase esvazia as tabelas ao terminar (inclusive os tipos
        # criados pela migração 0002), então garantimos um tipo aqui.
        tipo, _ = apps.get_model("profissionais", "TipoProfissional").objects.get_or_create(
            descricao="Psicólogo"
        )
        return apps.get_model("profissionais", "Profissional").objects.create(
            primeiro_nome="Ana",
            sobrenome="Lima",
            email="ana@example.com",
            tipo_profissional=tipo,
            numero_registro="123",
            valor_hora=Decimal("100.00"),
        )

    def test_preenche_com_a_unica_clinica_existente(self):
        clinica = self.criar_clinica(self.apps_antes, "vida", "11222333000181")
        profissional = self.criar_profissional(self.apps_antes)

        apps_depois = self.migrar(PREENCHIDA)

        Profissional = apps_depois.get_model("profissionais", "Profissional")
        self.assertEqual(
            Profissional.objects.get(pk=profissional.pk).clinica_id, clinica.pk
        )

    def test_banco_sem_profissionais_migra_sem_clinica(self):
        self.migrar(PREENCHIDA)  # não deve levantar erro

    def test_para_com_aviso_se_nao_ha_clinica(self):
        self.criar_profissional(self.apps_antes)
        with self.assertRaisesMessage(RuntimeError, "nenhuma clínica"):
            self.migrar(PREENCHIDA)

    def test_para_com_aviso_se_ha_varias_clinicas(self):
        self.criar_clinica(self.apps_antes, "vida", "11222333000181")
        self.criar_clinica(self.apps_antes, "sol", "11444777000161")
        self.criar_profissional(self.apps_antes)
        with self.assertRaisesMessage(RuntimeError, "mais de uma clínica"):
            self.migrar(PREENCHIDA)
