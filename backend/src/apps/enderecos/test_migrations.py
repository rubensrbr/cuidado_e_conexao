from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

# Estado "antes": endereços sem clínica preenchida, mas pacientes e
# profissionais (os donos) já com clínica obrigatória.
ANTES = [
    ("enderecos", "0004_endereco_clinica"),
    ("pacientes", "0005_clinica_obrigatoria"),
    ("profissionais", "0005_clinica_obrigatoria_email_por_clinica"),
]
PREENCHIDA = [("enderecos", "0005_preencher_clinica")]


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
            ("enderecos", "Endereco"),
            ("localidades", "Cidade"),
            ("localidades", "Estado"),
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

    def criar_cidade(self):
        estado = self.apps_antes.get_model("localidades", "Estado").objects.create(
            codigo_ibge=52, sigla="GO", nome="Goiás"
        )
        return self.apps_antes.get_model("localidades", "Cidade").objects.create(
            codigo_ibge=5208707, nome="Goiânia", estado=estado
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

    def criar_endereco(self, cidade, **dono):
        return self.apps_antes.get_model("enderecos", "Endereco").objects.create(
            logradouro="Rua A",
            numero="10",
            bairro="Centro",
            cidade=cidade,
            cep="70000-000",
            **dono,
        )

    def test_endereco_herda_a_clinica_do_dono_com_varias_clinicas(self):
        vida = self.criar_clinica("vida", "11222333000181")
        sol = self.criar_clinica("sol", "11444777000161")
        cidade = self.criar_cidade()
        end_paciente = self.criar_endereco(
            cidade, pacientes=self.criar_paciente(vida)
        )
        end_profissional = self.criar_endereco(
            cidade, profissionais=self.criar_profissional(sol)
        )

        apps_depois = self.migrar(PREENCHIDA)

        Endereco = apps_depois.get_model("enderecos", "Endereco")
        self.assertEqual(Endereco.objects.get(pk=end_paciente.pk).clinica_id, vida.pk)
        self.assertEqual(
            Endereco.objects.get(pk=end_profissional.pk).clinica_id, sol.pk
        )

    def test_banco_sem_enderecos_migra_sem_erro(self):
        self.migrar(PREENCHIDA)
