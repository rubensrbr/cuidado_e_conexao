from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clinicas.helpers_de_teste import grupo_com_todas_as_permissoes
from clinicas.models import Clinica, Membro
from clinicas.tenancy import clinica_atual
from pacientes.models import Paciente
from profissionais.models import Profissional, TipoProfissional

from .filters import ConsultaFilter
from .models import Consulta

User = get_user_model()


def criar_paciente(nome, sobrenome="Silva"):
    return Paciente.objects.create(
        primeiro_nome=nome,
        sobrenome=sobrenome,
        data_nascimento=date(1990, 1, 1),
        genero="outro",
    )


def criar_profissional(nome, sobrenome="Lima"):
    return Profissional.objects.create(
        primeiro_nome=nome,
        sobrenome=sobrenome,
        email=f"{nome.lower()}@example.com",
        tipo_profissional=TipoProfissional.objects.first(),
        numero_registro="123",
        valor_hora=Decimal("100.00"),
    )


def criar_consulta(paciente, profissional, dia, **kwargs):
    dados = {
        "paciente": paciente,
        "profissional": profissional,
        "data_consulta": dia,
        "hora_inicio": time(9, 0),
        "hora_fim": time(10, 0),
        "tipo_consulta": "retorno",
        "status": "agendada",
    }
    dados.update(kwargs)
    return Consulta.objects.create(**dados)


class BaseComClinicas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vida = Clinica.objects.create(
            nome="Vida", cnpj="11222333000181", slug="vida"
        )
        cls.sol = Clinica.objects.create(nome="Sol", cnpj="11444777000161", slug="sol")
        cls.maria = User.objects.create_user("maria@example.com", password="x")
        Membro.objects.create(
            user=cls.maria,
            clinica=cls.vida,
            grupo=grupo_com_todas_as_permissoes("Administração"),
        )
        with clinica_atual(cls.vida):
            cls.ana = criar_paciente("Ana")
            cls.bruno = criar_paciente("Bruno", sobrenome="Souza")
            cls.dra_lima = criar_profissional("Carla")
            cls.dr_reis = criar_profissional("Davi", sobrenome="Reis")
            # Ana: retorno agendado em 10/10 com a Dra. Carla.
            criar_consulta(cls.ana, cls.dra_lima, date(2026, 10, 10))
            # Bruno: avaliação realizada em 20/10 com o Dr. Davi.
            criar_consulta(
                cls.bruno, cls.dr_reis, date(2026, 10, 20),
                tipo_consulta="avaliacao_inicial", status="realizada",
            )
        with clinica_atual(cls.sol):
            criar_consulta(
                criar_paciente("Erica"), criar_profissional("Fabio"), date(2026, 10, 15)
            )

    def pacientes(self, consultas):
        return sorted(c.paciente.primeiro_nome for c in consultas)


class ConsultaFilterTests(BaseComClinicas):
    def filtrar(self, **dados):
        with clinica_atual(self.vida):
            filtro = ConsultaFilter(dados, queryset=Consulta.objects.all())
            self.assertTrue(filtro.is_valid(), filtro.form.errors)
            return self.pacientes(filtro.qs)

    def test_sem_filtro_devolve_todas_da_clinica(self):
        self.assertEqual(self.filtrar(), ["Ana", "Bruno"])

    def test_busca_por_paciente_ou_profissional(self):
        for termo, esperado in [
            ("ana", ["Ana"]),
            ("SOUZA", ["Bruno"]),
            ("carla", ["Ana"]),
            ("reis", ["Bruno"]),
            ("ana lima", ["Ana"]),  # paciente + profissional, palavras em campos diferentes
            ("ana reis", []),
        ]:
            with self.subTest(termo=termo):
                self.assertEqual(self.filtrar(busca=termo), esperado)

    def test_filtros_de_status_e_tipo(self):
        self.assertEqual(self.filtrar(status="realizada"), ["Bruno"])
        self.assertEqual(self.filtrar(tipo="retorno"), ["Ana"])

    def test_filtro_por_profissional(self):
        self.assertEqual(self.filtrar(profissional=self.dr_reis.pk), ["Bruno"])

    def test_filtro_de_periodo_inclui_os_extremos(self):
        self.assertEqual(self.filtrar(data_de="2026-10-10"), ["Ana", "Bruno"])
        self.assertEqual(self.filtrar(data_de="2026-10-11"), ["Bruno"])
        self.assertEqual(self.filtrar(data_ate="2026-10-10"), ["Ana"])
        self.assertEqual(
            self.filtrar(data_de="2026-10-10", data_ate="2026-10-20"), ["Ana", "Bruno"]
        )

    def test_periodo_invertido_e_rejeitado(self):
        with clinica_atual(self.vida):
            filtro = ConsultaFilter(
                {"data_de": "2026-10-20", "data_ate": "2026-10-10"},
                queryset=Consulta.objects.all(),
            )
            self.assertFalse(filtro.is_valid())
            self.assertIn("data_ate", filtro.form.errors)

    def test_filtros_se_combinam_com_e(self):
        self.assertEqual(self.filtrar(status="realizada", tipo="retorno"), [])

    def test_opcoes_de_profissional_sao_so_da_clinica_atual(self):
        with clinica_atual(self.vida):
            filtro = ConsultaFilter({}, queryset=Consulta.objects.all())
            opcoes = {p.primeiro_nome for p in filtro.form.fields["profissional"].queryset}
        self.assertEqual(opcoes, {"Carla", "Davi"})

    def test_resultado_nunca_inclui_consultas_de_outra_clinica(self):
        self.assertNotIn("Erica", self.filtrar(data_de="2026-10-01"))


class ListaDeConsultasComFiltrosTests(BaseComClinicas):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.url = reverse("consultas:consulta_list")

    def abrir(self, **parametros):
        self.client.force_login(self.maria)
        return self.client.get(self.url, parametros)

    def da_tela(self, resposta):
        return self.pacientes(resposta.context["consultas"])

    def test_a_tela_mostra_o_formulario_de_filtros(self):
        resposta = self.abrir()
        self.assertEqual(resposta.status_code, 200)
        for nome in ("busca", "profissional", "status", "tipo", "data_de", "data_ate"):
            with self.subTest(campo=nome):
                self.assertContains(resposta, f'name="{nome}"')
        self.assertContains(resposta, "Filtrar")

    def test_sem_filtros_lista_todas_e_nao_mostra_limpar(self):
        resposta = self.abrir()
        self.assertEqual(self.da_tela(resposta), ["Ana", "Bruno"])
        self.assertNotContains(resposta, "Limpar")
        self.assertEqual(resposta.context["filtros_ativos"], 0)

    def test_filtrar_pela_url(self):
        casos = [
            ({"busca": "souza"}, ["Bruno"]),
            ({"status": "agendada"}, ["Ana"]),
            ({"tipo": "avaliacao_inicial"}, ["Bruno"]),
            ({"profissional": self.dra_lima.pk}, ["Ana"]),
            ({"data_de": "2026-10-15"}, ["Bruno"]),
        ]
        for parametros, esperado in casos:
            with self.subTest(parametros=parametros):
                self.assertEqual(self.da_tela(self.abrir(**parametros)), esperado)

    def test_com_filtros_mostra_limpar_e_contagem(self):
        resposta = self.abrir(status="agendada", busca="ana")
        self.assertContains(resposta, "Limpar")
        self.assertEqual(resposta.context["filtros_ativos"], 2)

    def test_filtro_sem_resultado_mostra_mensagem_propria(self):
        resposta = self.abrir(busca="inexistente")
        self.assertContains(resposta, "Nenhuma consulta encontrada com esses filtros.")

    def test_periodo_invalido_mostra_lista_vazia_em_vez_de_tudo(self):
        resposta = self.abrir(data_de="2026-10-20", data_ate="2026-10-10")
        self.assertEqual(self.da_tela(resposta), [])
        self.assertContains(resposta, "A data final não pode ser anterior à inicial.")

    def test_filtro_continua_aplicado_ao_voltar_de_editar(self):
        self.client.force_login(self.maria)
        self.client.get(self.url, {"status": "realizada"})
        resposta = self.client.get(self.url, follow=True)
        self.assertEqual(resposta.request["QUERY_STRING"], "status=realizada")
        self.assertEqual(self.da_tela(resposta), ["Bruno"])

    def test_limpar_esquece_os_filtros(self):
        self.client.force_login(self.maria)
        self.client.get(self.url, {"status": "realizada"})
        resposta = self.client.get(self.url, {"limpar": 1}, follow=True)
        self.assertEqual(self.da_tela(resposta), ["Ana", "Bruno"])
