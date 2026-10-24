# ruff: noqa: E402
from unittest import SkipTest

from django.apps import apps

if not apps.is_installed("faturamentos"):
    raise SkipTest("app 'faturamentos' não está em INSTALLED_APPS neste release")

from datetime import date, time
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

ANTES = [("faturamentos", "0002_faturamento_clinica")]
PREENCHIDA = [("faturamentos", "0003_preencher_clinica")]
# Estado final dos apps de que os faturamentos dependem (Paciente, Profissional
# e Consulta já com `clinica`), para criar as linhas de teste no estado certo.
DEPENDENCIAS = [
    ("pacientes", "0005_clinica_obrigatoria"),
    ("profissionais", "0005_clinica_obrigatoria_email_por_clinica"),
    ("consultas", "0006_clinica_obrigatoria"),
]


class PreencherClinicaMigrationTests(TransactionTestCase):
    """Roda a migração de dados 0003 contra linhas criadas no estado da 0002."""

    def migrar(self, alvo):
        executor = MigrationExecutor(connection)
        executor.migrate(alvo)
        return executor.loader.project_state(alvo + DEPENDENCIAS).apps

    def setUp(self):
        self.apps_antes = self.migrar(ANTES)

    def tearDown(self):
        # Limpa o que os testes criaram e volta ao estado final.
        for app, modelo in (
            ("faturamentos", "Faturamento"),
            ("consultas", "Consulta"),
            ("pacientes", "Paciente"),
            ("profissionais", "Profissional"),
            ("clinicas", "Clinica"),
        ):
            self.apps_antes.get_model(app, modelo).objects.all().delete()
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def criar_clinica(self, slug, cnpj):
        Clinica = self.apps_antes.get_model("clinicas", "Clinica")
        return Clinica.objects.create(nome=slug, slug=slug, cnpj=cnpj)

    def criar_faturamentos_da_clinica(self, clinica, nome):
        """Um faturamento com consulta e outro sem, ambos sem `clinica`."""
        apps = self.apps_antes
        paciente = apps.get_model("pacientes", "Paciente").objects.create(
            clinica=clinica,
            primeiro_nome=nome,
            sobrenome="Silva",
            data_nascimento=date(2000, 1, 1),
            genero="outro",
        )
        tipo, _ = apps.get_model(
            "profissionais", "TipoProfissional"
        ).objects.get_or_create(descricao="Psicólogo")
        profissional = apps.get_model("profissionais", "Profissional").objects.create(
            clinica=clinica,
            primeiro_nome=nome,
            sobrenome="Lima",
            email=f"{nome.lower()}@example.com",
            tipo_profissional=tipo,
            numero_registro="1",
            valor_hora=Decimal("100.00"),
        )
        consulta = apps.get_model("consultas", "Consulta").objects.create(
            clinica=clinica,
            paciente=paciente,
            profissional=profissional,
            data_consulta=date(2026, 11, 3),
            hora_inicio=time(9),
            hora_fim=time(10),
            tipo_consulta="retorno",
        )
        Faturamento = apps.get_model("faturamentos", "Faturamento")
        com_consulta = Faturamento.objects.create(
            paciente=paciente,
            consulta=consulta,
            data_servico=date(2026, 11, 3),
            valor_cobrado=Decimal("150.00"),
        )
        sem_consulta = Faturamento.objects.create(
            paciente=paciente,
            data_servico=date(2026, 11, 4),
            valor_cobrado=Decimal("90.00"),
        )
        return com_consulta, sem_consulta

    def clinica_de(self, apps, pk):
        return apps.get_model("faturamentos", "Faturamento").objects.get(pk=pk).clinica_id

    def test_cada_faturamento_herda_a_clinica_do_paciente(self):
        vida = self.criar_clinica("vida", "11222333000181")
        com_consulta, sem_consulta = self.criar_faturamentos_da_clinica(vida, "Ana")

        apps = self.migrar(PREENCHIDA)

        self.assertEqual(self.clinica_de(apps, com_consulta.pk), vida.pk)
        self.assertEqual(self.clinica_de(apps, sem_consulta.pk), vida.pk)

    def test_funciona_com_varias_clinicas_cada_uma_com_os_proprios_dados(self):
        vida = self.criar_clinica("vida", "11222333000181")
        sol = self.criar_clinica("sol", "11444777000161")
        f_vida = self.criar_faturamentos_da_clinica(vida, "Ana")
        f_sol = self.criar_faturamentos_da_clinica(sol, "Beto")

        apps = self.migrar(PREENCHIDA)

        for faturamentos, esperada in ((f_vida, vida), (f_sol, sol)):
            for faturamento in faturamentos:
                with self.subTest(faturamento=faturamento.pk, clinica=esperada.slug):
                    self.assertEqual(
                        self.clinica_de(apps, faturamento.pk), esperada.pk
                    )

    def test_banco_sem_faturamentos_migra_sem_erro(self):
        self.migrar(PREENCHIDA)
