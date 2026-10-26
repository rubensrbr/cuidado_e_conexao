from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

ANTES = [("core", "0002_user_change_password")]
PREPARADA = [("core", "0003_validar_emails")]


class ValidarEmailsMigrationTests(TransactionTestCase):
    """Roda a migração de dados 0003 contra usuários criados no estado da 0002
    (ainda com `username`)."""

    def migrar(self, alvo):
        executor = MigrationExecutor(connection)
        executor.migrate(alvo)
        return executor.loader.project_state(alvo).apps

    def setUp(self):
        self.apps_antes = self.migrar(ANTES)
        self.User = self.apps_antes.get_model("core", "User")

    def tearDown(self):
        # Limpa o que os testes criaram e volta ao estado final.
        self.User.objects.all().delete()
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def criar(self, username, email):
        return self.User.objects.create(username=username, email=email, password="x")

    def email_de(self, apps, pk):
        return apps.get_model("core", "User").objects.get(pk=pk).email

    def test_padroniza_os_emails_existentes(self):
        ana = self.criar("ana", "Ana@Clinica.com")
        beto = self.criar("beto", "  beto@clinica.com ")
        carla = self.criar("carla", "carla@clinica.com")

        apps = self.migrar(PREPARADA)

        self.assertEqual(self.email_de(apps, ana.pk), "ana@clinica.com")
        self.assertEqual(self.email_de(apps, beto.pk), "beto@clinica.com")
        self.assertEqual(self.email_de(apps, carla.pk), "carla@clinica.com")

    def test_banco_sem_usuarios_migra_sem_erro(self):
        self.migrar(PREPARADA)

    def test_para_citando_quem_nao_tem_email(self):
        self.criar("ana", "ana@clinica.com")
        self.criar("beto", "")
        self.criar("carla", "   ")
        with self.assertRaisesMessage(RuntimeError, "Usuários sem e-mail: beto, carla."):
            self.migrar(PREPARADA)

    def test_para_citando_emails_repetidos_mesmo_com_caixa_diferente(self):
        self.criar("ana", "Ana@Clinica.com")
        self.criar("ana2", "ana@clinica.com")
        self.criar("beto", "beto@clinica.com")
        with self.assertRaisesMessage(
            RuntimeError, "E-mails repetidos: ana@clinica.com (ana, ana2)."
        ):
            self.migrar(PREPARADA)

    def test_quando_para_nao_altera_nenhum_email(self):
        ana = self.criar("ana", "Ana@Clinica.com")
        self.criar("beto", "")
        with self.assertRaises(RuntimeError):
            self.migrar(PREPARADA)
        self.assertEqual(self.User.objects.get(pk=ana.pk).email, "Ana@Clinica.com")
