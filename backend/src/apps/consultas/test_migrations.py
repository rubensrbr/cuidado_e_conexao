from datetime import date, datetime, time, timezone
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

ANTES = [("consultas", "0004_consulta_lembrete_listaespera_clinica")]
PREENCHIDA = [("consultas", "0005_preencher_clinica")]
# Estado final dos apps de que as consultas dependem (Paciente/Profissional já
# com `clinica`), para criar as linhas de teste no estado certo.
DEPENDENCIAS = [
    ("pacientes", "0005_clinica_obrigatoria"),
    ("profissionais", "0005_clinica_obrigatoria_email_por_clinica"),
]


class PreencherClinicaMigrationTests(TransactionTestCase):
    """Roda a migração de dados 0005 contra linhas criadas no estado da 0004."""

    def migrar(self, alvo):
        executor = MigrationExecutor(connection)
        executor.migrate(alvo)
        return executor.loader.project_state(alvo + DEPENDENCIAS).apps

    def setUp(self):
        self.apps_antes = self.migrar(ANTES)

    def tearDown(self):
        # Limpa o que os testes criaram e volta ao estado final.
        for app, modelo in (
            ("consultas", "Lembrete"),
            ("consultas", "Consulta"),
            ("consultas", "ListaEspera"),
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

    def criar_dados_da_clinica(self, clinica, nome):
        """Paciente, profissional, consulta, lembrete e espera, sem `clinica` nos três últimos."""
        apps = self.apps_antes
        paciente = apps.get_model("pacientes", "Paciente").objects.create(
            clinica=clinica,
            primeiro_nome=nome,
            sobrenome="Silva",
            data_nascimento=date(2000, 1, 1),
            genero="outro",
        )
        tipo, _ = apps.get_model("profissionais", "TipoProfissional").objects.get_or_create(
            descricao="Psicólogo"
        )
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
            paciente=paciente,
            profissional=profissional,
            data_consulta=date(2026, 11, 3),
            hora_inicio=time(9),
            hora_fim=time(10),
            tipo_consulta="retorno",
        )
        lembrete = apps.get_model("consultas", "Lembrete").objects.create(
            consulta=consulta,
            tipo_lembrete="email",
            data_hora_envio=datetime(2026, 11, 2, 9, tzinfo=timezone.utc),
        )
        espera = apps.get_model("consultas", "ListaEspera").objects.create(
            paciente=paciente
        )
        return consulta, lembrete, espera

    def clinica_de(self, apps, app, modelo, pk):
        return apps.get_model(app, modelo).objects.get(pk=pk).clinica_id

    def test_cada_registro_herda_a_clinica_do_paciente(self):
        vida = self.criar_clinica("vida", "11222333000181")
        consulta, lembrete, espera = self.criar_dados_da_clinica(vida, "Ana")

        apps = self.migrar(PREENCHIDA)

        self.assertEqual(self.clinica_de(apps, "consultas", "Consulta", consulta.pk), vida.pk)
        self.assertEqual(self.clinica_de(apps, "consultas", "Lembrete", lembrete.pk), vida.pk)
        self.assertEqual(self.clinica_de(apps, "consultas", "ListaEspera", espera.pk), vida.pk)

    def test_funciona_com_varias_clinicas_cada_uma_com_os_proprios_dados(self):
        vida = self.criar_clinica("vida", "11222333000181")
        sol = self.criar_clinica("sol", "11444777000161")
        c_vida, l_vida, e_vida = self.criar_dados_da_clinica(vida, "Ana")
        c_sol, l_sol, e_sol = self.criar_dados_da_clinica(sol, "Beto")

        apps = self.migrar(PREENCHIDA)

        for objeto, modelo, esperada in (
            (c_vida, "Consulta", vida),
            (l_vida, "Lembrete", vida),
            (e_vida, "ListaEspera", vida),
            (c_sol, "Consulta", sol),
            (l_sol, "Lembrete", sol),
            (e_sol, "ListaEspera", sol),
        ):
            with self.subTest(modelo=modelo, clinica=esperada.slug):
                self.assertEqual(
                    self.clinica_de(apps, "consultas", modelo, objeto.pk), esperada.pk
                )

    def test_banco_sem_consultas_migra_sem_erro(self):
        self.migrar(PREENCHIDA)
