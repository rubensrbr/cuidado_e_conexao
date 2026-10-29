from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clinicas.helpers_de_teste import grupo_com_todas_as_permissoes
from clinicas.models import Clinica, Membro
from clinicas.tenancy import clinica_atual

from .filters import ProfissionalFilter
from .models import Profissional, TipoProfissional

User = get_user_model()


def criar_profissional(nome, sobrenome="Lima", tipo=None, **kwargs):
    dados = {
        "primeiro_nome": nome,
        "sobrenome": sobrenome,
        "email": f"{nome.lower()}@example.com",
        "tipo_profissional": tipo or TipoProfissional.objects.first(),
        "numero_registro": "123",
        "valor_hora": Decimal("100.00"),
    }
    dados.update(kwargs)
    return Profissional.objects.create(**dados)


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
        cls.psicologo = TipoProfissional.objects.get(descricao="Psicólogo")
        cls.nutricionista = TipoProfissional.objects.get(descricao="Nutricionista")

    def nomes(self, queryset):
        return sorted(p.primeiro_nome for p in queryset)


class ProfissionalFilterTests(BaseComClinicas):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        with clinica_atual(cls.vida):
            criar_profissional(
                "Ana", tipo=cls.psicologo, numero_registro="CRP-0001"
            )
            criar_profissional(
                "Bruno", sobrenome="Souza", tipo=cls.nutricionista, ativo=False
            )
        with clinica_atual(cls.sol):
            criar_profissional("Carla", tipo=cls.psicologo)

    def filtrar(self, **dados):
        with clinica_atual(self.vida):
            filtro = ProfissionalFilter(dados, queryset=Profissional.objects.all())
            self.assertTrue(filtro.is_valid(), filtro.form.errors)
            return self.nomes(filtro.qs)

    def test_sem_filtro_devolve_todos_da_clinica(self):
        self.assertEqual(self.filtrar(), ["Ana", "Bruno"])

    def test_busca_por_nome_sobrenome_email_e_registro(self):
        for termo, esperado in [
            ("ana", ["Ana"]),
            ("SOUZA", ["Bruno"]),
            ("bruno@example", ["Bruno"]),
            ("crp-0001", ["Ana"]),
            ("ana lima", ["Ana"]),
            ("ana souza", []),
        ]:
            with self.subTest(termo=termo):
                self.assertEqual(self.filtrar(busca=termo), esperado)

    def test_filtro_de_especialidade(self):
        self.assertEqual(self.filtrar(tipo=self.nutricionista.pk), ["Bruno"])

    def test_filtro_de_situacao(self):
        self.assertEqual(self.filtrar(status="ativo"), ["Ana"])
        self.assertEqual(self.filtrar(status="inativo"), ["Bruno"])

    def test_filtros_se_combinam_com_e(self):
        self.assertEqual(self.filtrar(tipo=self.psicologo.pk, status="inativo"), [])

    def test_resultado_nunca_inclui_profissionais_de_outra_clinica(self):
        self.assertNotIn("Carla", self.filtrar(tipo=self.psicologo.pk))


class ListaDeProfissionaisComFiltrosTests(BaseComClinicas):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        with clinica_atual(cls.vida):
            criar_profissional("Ana", tipo=cls.psicologo)
            criar_profissional(
                "Bruno", sobrenome="Souza", tipo=cls.nutricionista, ativo=False
            )
        cls.url = reverse("profissionais:profissional_list")

    def abrir(self, **parametros):
        self.client.force_login(self.maria)
        return self.client.get(self.url, parametros)

    def nomes_da_tela(self, resposta):
        return sorted(p.primeiro_nome for p in resposta.context["profissionais"])

    def test_a_tela_mostra_o_formulario_de_filtros(self):
        resposta = self.abrir()
        self.assertEqual(resposta.status_code, 200)
        for nome in ("busca", "tipo", "status"):
            with self.subTest(campo=nome):
                self.assertContains(resposta, f'name="{nome}"')
        self.assertContains(resposta, "Filtrar")

    def test_sem_filtros_lista_todos_e_nao_mostra_limpar(self):
        resposta = self.abrir()
        self.assertEqual(self.nomes_da_tela(resposta), ["Ana", "Bruno"])
        self.assertNotContains(resposta, "Limpar")
        self.assertEqual(resposta.context["filtros_ativos"], 0)

    def test_filtrar_pela_url(self):
        casos = [
            ({"busca": "souza"}, ["Bruno"]),
            ({"tipo": self.psicologo.pk}, ["Ana"]),
            ({"status": "inativo"}, ["Bruno"]),
        ]
        for parametros, esperado in casos:
            with self.subTest(parametros=parametros):
                resposta = self.abrir(**parametros)
                self.assertEqual(self.nomes_da_tela(resposta), esperado)

    def test_com_filtros_mostra_limpar_e_contagem(self):
        resposta = self.abrir(status="ativo", busca="ana")
        self.assertContains(resposta, "Limpar")
        self.assertEqual(resposta.context["filtros_ativos"], 2)

    def test_filtro_sem_resultado_mostra_mensagem_propria(self):
        resposta = self.abrir(busca="inexistente")
        self.assertContains(resposta, "Nenhum profissional encontrado com esses filtros.")

    def test_filtro_invalido_mostra_lista_vazia_em_vez_de_tudo(self):
        resposta = self.abrir(tipo="999999")
        self.assertEqual(self.nomes_da_tela(resposta), [])

    def test_filtro_continua_aplicado_ao_voltar_de_editar(self):
        self.client.force_login(self.maria)
        self.client.get(self.url, {"status": "ativo"})
        resposta = self.client.get(self.url, follow=True)
        self.assertEqual(resposta.request["QUERY_STRING"], "status=ativo")
        self.assertEqual(self.nomes_da_tela(resposta), ["Ana"])

    def test_limpar_esquece_os_filtros(self):
        self.client.force_login(self.maria)
        self.client.get(self.url, {"status": "ativo"})
        resposta = self.client.get(self.url, {"limpar": 1}, follow=True)
        self.assertEqual(self.nomes_da_tela(resposta), ["Ana", "Bruno"])
