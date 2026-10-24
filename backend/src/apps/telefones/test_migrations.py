from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

# Estado "antes": telefones sem clínica preenchida, mas pacientes e
# profissionais (os donos) já com clínica obrigatória.
ANTES = [
    ("telefones", "0004_telefone_clinica"),
    ("pacientes", "0005_clinica_obrigatoria"),
    ("profissionais", "0005_clinica_obrigatoria_email_por_clinica"),
]
PREENCHIDA = [("telefones", "0005_preencher_clinica")]


class PreencherClinicaMigrationTests(TransactionTestCase):
    """Roda a migração de dados 0005 contra linhas criadas no estado da 0004."""

    def migrar(self, alvo):
        executor = MigrationExecutor(connection)
        executor.migrate(alvo)
        return executor.loader.project_state(alvo).apps

    def setUp(self):
        self.apps_antes = self.migrar(ANTES)

    def tearDown(self):
        # Limpa o que os testes criaram e volta ao estado final.
        apps = self.apps_antes
        for app, modelo in (
            ("telefones", "Telefone"),
            ("pacientes", "Paciente"),
            ("profissionais", "Profissional"),
            ("profissionais", "TipoProfissional"),
            ("clinicas", "Clinica"),
        ):
            apps.get_model(app, modelo).objects.all().delete()
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def criar_clinica(self, slug, cnpj):
        return self.apps_antes.get_model("clinicas", "Clinica").objects.create(
            nome=slug, slug=slug, cnpj=cnpj
        )

    def criar_paciente(self, clinica):
        return self.apps_antes.get_model("pacientes", "Paciente").objects.create(
            primeiro_nome="Ana",
            sobrenome="Silva",
            data_nascimento=date(2000, 1, 1),
            genero="outro",
            clinica=clinica,
        )

    def criar_profissional(self, clinica):
        tipo = self.apps_antes.get_model(
            "profissionais", "TipoProfissional"
        ).objects.create(descricao="Psicólogo")
        return self.apps_antes.get_model("profissionais", "Profissional").objects.create(
            primeiro_nome="Beto",
            sobrenome="Lima",
            email="beto@example.com",
            tipo_profissional=tipo,
            numero_registro="123",
            valor_hora="100.00",
            clinica=clinica,
        )

    def criar_telefone(self, **dono):
        return self.apps_antes.get_model("telefones", "Telefone").objects.create(
            numero="85912345678", tipo="celular", **dono
        )

    def test_telefone_herda_a_clinica_do_dono_com_varias_clinicas(self):
        vida = self.criar_clinica("vida", "11222333000181")
        sol = self.criar_clinica("sol", "11444777000161")
        tel_paciente = self.criar_telefone(pacientes=self.criar_paciente(vida))
        tel_profissional = self.criar_telefone(
            profissionais=self.criar_profissional(sol)
        )

        apps_depois = self.migrar(PREENCHIDA)

        Telefone = apps_depois.get_model("telefones", "Telefone")
        self.assertEqual(Telefone.objects.get(pk=tel_paciente.pk).clinica_id, vida.pk)
        self.assertEqual(Telefone.objects.get(pk=tel_profissional.pk).clinica_id, sol.pk)

    def test_banco_sem_telefones_migra_sem_erro(self):
        self.migrar(PREENCHIDA)
