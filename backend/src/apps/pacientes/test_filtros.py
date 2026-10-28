import html as html_lib
import re
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from clinicas.helpers_de_teste import (
    grupo_com_permissoes,
    grupo_com_todas_as_permissoes,
)
from clinicas.models import Clinica, Membro
from clinicas.tenancy import clinica_atual
from profissionais.models import Profissional, TipoProfissional
from telefones.models import Telefone

from .filters import PARTICULAR, PacienteFilter, data_ha_anos
from .models import Paciente

User = get_user_model()


def criar_paciente(nome, sobrenome="Silva", **kwargs):
    dados = {
        "primeiro_nome": nome,
        "sobrenome": sobrenome,
        "data_nascimento": date(1990, 1, 1),
        "genero": "outro",
        "email": "",
        "convenio": "",
    }
    dados.update(kwargs)
    return Paciente.objects.create(**dados)


def criar_profissional(nome, **kwargs):
    dados = {
        "primeiro_nome": nome,
        "sobrenome": "Lima",
        "email": f"{nome.lower()}@example.com",
        "tipo_profissional": TipoProfissional.objects.first(),
        "numero_registro": "123",
        "valor_hora": Decimal("100.00"),
    }
    dados.update(kwargs)
    return Profissional.objects.create(**dados)


def nascido_ha(anos, dias=0):
    """Data de nascimento de quem faz `anos` anos hoje (+ `dias` dias)."""
    return data_ha_anos(timezone.localdate(), anos) + timedelta(days=dias)


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

    def nomes(self, queryset):
        return sorted(p.primeiro_nome for p in queryset)


# --------------------------------------------------------------------------
# O FilterSet, sem passar pela tela
# --------------------------------------------------------------------------
class PacienteFilterTests(BaseComClinicas):
    def filtrar(self, **dados):
        """Aplica o filtro na clínica Vida e devolve os nomes encontrados."""
        with clinica_atual(self.vida):
            filtro = PacienteFilter(dados, queryset=Paciente.objects.all())
            self.assertTrue(filtro.is_valid(), filtro.form.errors)
            return self.nomes(filtro.qs)

    def test_sem_filtro_devolve_todos_da_clinica(self):
        with clinica_atual(self.vida):
            criar_paciente("Ana")
            criar_paciente("Bruno")
        self.assertEqual(self.filtrar(), ["Ana", "Bruno"])

    # --- busca ---
    def test_busca_por_nome_sobrenome_e_email_sem_diferenciar_caixa(self):
        with clinica_atual(self.vida):
            criar_paciente("Ana", "Souza", email="ana.s@clinica.com")
            criar_paciente("Bruno", "Alves", email="bruno@outro.com")
        self.assertEqual(self.filtrar(busca="ana"), ["Ana"])
        self.assertEqual(self.filtrar(busca="ALVES"), ["Bruno"])
        self.assertEqual(self.filtrar(busca="@clinica"), ["Ana"])
        self.assertEqual(self.filtrar(busca="zzz"), [])

    def test_busca_com_varias_palavras_exige_todas(self):
        with clinica_atual(self.vida):
            criar_paciente("Ana", "Souza")
            criar_paciente("Ana", "Alves")
            criar_paciente("Bruno", "Souza")
        # "ana souza": nome num campo, sobrenome no outro, e só um paciente serve.
        self.assertEqual(self.filtrar(busca="ana souza"), ["Ana"])
        self.assertEqual(self.filtrar(busca="  souza   ana  "), ["Ana"])

    def test_busca_trata_caracteres_especiais_como_texto(self):
        with clinica_atual(self.vida):
            criar_paciente("Ana", "Souza")
        self.assertEqual(self.filtrar(busca="%"), [])
        self.assertEqual(self.filtrar(busca="_"), [])

    # --- gênero e situação ---
    def test_filtro_de_genero(self):
        with clinica_atual(self.vida):
            criar_paciente("Ana", genero="feminino")
            criar_paciente("Bruno", genero="masculino")
        self.assertEqual(self.filtrar(genero="feminino"), ["Ana"])
        self.assertEqual(self.filtrar(genero="masculino"), ["Bruno"])

    def test_filtro_de_situacao(self):
        with clinica_atual(self.vida):
            criar_paciente("Ana", ativo=True)
            criar_paciente("Bruno", ativo=False)
        self.assertEqual(self.filtrar(status="ativo"), ["Ana"])
        self.assertEqual(self.filtrar(status="inativo"), ["Bruno"])

    # --- convênio ---
    def test_filtro_de_convenio_particular_e_especifico(self):
        with clinica_atual(self.vida):
            criar_paciente("Ana", convenio="Unimed")
            criar_paciente("Bruno", convenio="")
            criar_paciente("Carla", convenio="Amil")
        self.assertEqual(self.filtrar(convenio=PARTICULAR), ["Bruno"])
        self.assertEqual(self.filtrar(convenio="Unimed"), ["Ana"])

    def test_opcoes_de_convenio_vem_dos_dados_da_clinica_sem_repetir(self):
        with clinica_atual(self.vida):
            criar_paciente("Ana", convenio="Unimed")
            criar_paciente("Bia", convenio="Unimed")
            criar_paciente("Carla", convenio="Amil")
            criar_paciente("Davi", convenio="")
        with clinica_atual(self.sol):
            criar_paciente("Eva", convenio="Bradesco Saúde")
        with clinica_atual(self.vida):
            filtro = PacienteFilter({}, queryset=Paciente.objects.all())
            opcoes = [valor for valor, _ in filtro.form.fields["convenio"].choices]
        # vazio ("Todos") + particular + convênios da Vida em ordem alfabética
        self.assertEqual(opcoes, ["", PARTICULAR, "Amil", "Unimed"])

    def test_convenio_inexistente_na_clinica_e_invalido(self):
        with clinica_atual(self.vida):
            criar_paciente("Ana", convenio="Unimed")
        with clinica_atual(self.sol):
            criar_paciente("Eva", convenio="Bradesco Saúde")
        with clinica_atual(self.vida):
            filtro = PacienteFilter(
                {"convenio": "Bradesco Saúde"}, queryset=Paciente.objects.all()
            )
            self.assertFalse(filtro.is_valid())

    # --- profissional ---
    def test_filtro_por_profissional_responsavel(self):
        with clinica_atual(self.vida):
            dra_ana = criar_profissional("Ana")
            dr_beto = criar_profissional("Beto")
            p1 = criar_paciente("Carla")
            p2 = criar_paciente("Davi")
            criar_paciente("Eva")  # sem profissional
            p1.profissionais.add(dra_ana)
            p2.profissionais.add(dra_ana, dr_beto)
        self.assertEqual(self.filtrar(profissional=dra_ana.pk), ["Carla", "Davi"])
        self.assertEqual(self.filtrar(profissional=dr_beto.pk), ["Davi"])

    def test_paciente_com_varios_profissionais_nao_aparece_duplicado(self):
        with clinica_atual(self.vida):
            dra_ana = criar_profissional("Ana")
            dr_beto = criar_profissional("Beto")
            paciente = criar_paciente("Carla")
            paciente.profissionais.add(dra_ana, dr_beto)
        self.assertEqual(self.filtrar(profissional=dra_ana.pk), ["Carla"])

    def test_opcoes_de_profissional_sao_so_da_clinica_atual(self):
        with clinica_atual(self.vida):
            dra_ana = criar_profissional("Ana")
        with clinica_atual(self.sol):
            dr_sol = criar_profissional("Solar")
        with clinica_atual(self.vida):
            filtro = PacienteFilter({}, queryset=Paciente.objects.all())
            ids = set(filtro.form.fields["profissional"].queryset.values_list("pk", flat=True))
            self.assertIn(dra_ana.pk, ids)
            self.assertNotIn(dr_sol.pk, ids)

            # E mandar o id de outra clínica à mão não funciona.
            filtro = PacienteFilter(
                {"profissional": dr_sol.pk}, queryset=Paciente.objects.all()
            )
            self.assertFalse(filtro.is_valid())

    # --- idade ---
    def test_idade_minima_inclui_quem_faz_a_idade_hoje(self):
        with clinica_atual(self.vida):
            criar_paciente("FazHoje", data_nascimento=nascido_ha(18))
            criar_paciente("FazAmanha", data_nascimento=nascido_ha(18, dias=1))
            criar_paciente("Velho", data_nascimento=nascido_ha(40))
        self.assertEqual(self.filtrar(idade_min=18), ["FazHoje", "Velho"])

    def test_idade_maxima_inclui_quem_ainda_nao_fez_a_proxima(self):
        with clinica_atual(self.vida):
            criar_paciente("Tem30", data_nascimento=nascido_ha(30))
            criar_paciente("Faz31Amanha", data_nascimento=nascido_ha(31, dias=1))
            criar_paciente("Fez31Hoje", data_nascimento=nascido_ha(31))
            criar_paciente("Jovem", data_nascimento=nascido_ha(5))
        self.assertEqual(self.filtrar(idade_max=30), ["Faz31Amanha", "Jovem", "Tem30"])

    def test_faixa_de_idade_combina_minima_e_maxima(self):
        with clinica_atual(self.vida):
            criar_paciente("Crianca", data_nascimento=nascido_ha(8))
            criar_paciente("Adulto", data_nascimento=nascido_ha(35))
            criar_paciente("Idoso", data_nascimento=nascido_ha(70))
        self.assertEqual(self.filtrar(idade_min=18, idade_max=60), ["Adulto"])
        self.assertEqual(self.filtrar(idade_min=35, idade_max=35), ["Adulto"])

    def test_idade_zero_e_valida(self):
        with clinica_atual(self.vida):
            criar_paciente("Bebe", data_nascimento=nascido_ha(0))
            criar_paciente("Adulto", data_nascimento=nascido_ha(35))
        self.assertEqual(self.filtrar(idade_max=0), ["Bebe"])
        self.assertEqual(self.filtrar(idade_min=0), ["Adulto", "Bebe"])

    def test_idades_invalidas_sao_rejeitadas(self):
        casos = [
            {"idade_min": "-1"},
            {"idade_max": "131"},
            {"idade_min": "abc"},
            {"idade_min": "18.5"},
            {"idade_min": "60", "idade_max": "10"},  # mínima maior que a máxima
        ]
        with clinica_atual(self.vida):
            for dados in casos:
                with self.subTest(dados=dados):
                    filtro = PacienteFilter(dados, queryset=Paciente.objects.all())
                    self.assertFalse(filtro.is_valid())

    def test_erro_de_faixa_aparece_no_campo_da_idade_maxima(self):
        with clinica_atual(self.vida):
            filtro = PacienteFilter(
                {"idade_min": "60", "idade_max": "10"}, queryset=Paciente.objects.all()
            )
            self.assertIn("idade_max", filtro.form.errors)

    # --- combinações e isolamento ---
    def test_filtros_se_combinam_com_e(self):
        with clinica_atual(self.vida):
            criar_paciente(
                "Ana", genero="feminino", convenio="Unimed",
                data_nascimento=nascido_ha(30),
            )
            criar_paciente(
                "Bia", genero="feminino", convenio="Amil",
                data_nascimento=nascido_ha(30),
            )
            criar_paciente(
                "Caio", genero="masculino", convenio="Unimed",
                data_nascimento=nascido_ha(30),
            )
            criar_paciente(
                "Duda", genero="feminino", convenio="Unimed",
                data_nascimento=nascido_ha(70),
            )
        self.assertEqual(
            self.filtrar(genero="feminino", convenio="Unimed", idade_max=40), ["Ana"]
        )

    def test_resultado_nunca_inclui_pacientes_de_outra_clinica(self):
        with clinica_atual(self.vida):
            criar_paciente("Ana", genero="feminino")
        with clinica_atual(self.sol):
            criar_paciente("Anita", genero="feminino")
        self.assertEqual(self.filtrar(busca="ani"), [])  # "Anita" é da Sol
        self.assertEqual(self.filtrar(genero="feminino"), ["Ana"])


class DataHaAnosTests(SimpleTestCase):
    def test_data_comum(self):
        self.assertEqual(data_ha_anos(date(2026, 10, 28), 18), date(2008, 10, 28))

    def test_29_de_fevereiro_vira_28_em_ano_nao_bissexto(self):
        self.assertEqual(data_ha_anos(date(2024, 2, 29), 1), date(2023, 2, 28))

    def test_29_de_fevereiro_continua_em_ano_bissexto(self):
        self.assertEqual(data_ha_anos(date(2024, 2, 29), 4), date(2020, 2, 29))


# --------------------------------------------------------------------------
# A tela
# --------------------------------------------------------------------------
class ListaDePacientesComFiltrosTests(BaseComClinicas):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        with clinica_atual(cls.vida):
            cls.dra_ana = criar_profissional("Ana")
            cls.carla = criar_paciente(
                "Carla", genero="feminino", convenio="Unimed",
                data_nascimento=nascido_ha(30),
            )
            cls.bruno = criar_paciente(
                "Bruno", genero="masculino", data_nascimento=nascido_ha(50),
            )
            cls.carla.profissionais.add(cls.dra_ana)
        cls.url = reverse("pacientes:paciente_list")

    def abrir(self, **parametros):
        self.client.force_login(self.maria)
        return self.client.get(self.url, parametros)

    def nomes_da_tela(self, resposta):
        return sorted(p.primeiro_nome for p in resposta.context["pacientes"])

    def test_a_tela_mostra_o_formulario_de_filtros(self):
        resposta = self.abrir()
        self.assertEqual(resposta.status_code, 200)
        for nome in ("busca", "genero", "status", "convenio", "profissional",
                     "idade_min", "idade_max"):
            with self.subTest(campo=nome):
                self.assertContains(resposta, f'name="{nome}"')
        self.assertContains(resposta, "Filtrar")

    def test_sem_filtros_lista_todos_e_nao_mostra_limpar(self):
        resposta = self.abrir()
        self.assertEqual(self.nomes_da_tela(resposta), ["Bruno", "Carla"])
        self.assertNotContains(resposta, "Limpar")
        self.assertEqual(resposta.context["filtros_ativos"], 0)

    def test_filtrar_por_cada_campo_pela_url(self):
        casos = [
            ({"busca": "carla"}, ["Carla"]),
            ({"genero": "masculino"}, ["Bruno"]),
            ({"status": "ativo"}, ["Bruno", "Carla"]),
            ({"convenio": "Unimed"}, ["Carla"]),
            ({"convenio": PARTICULAR}, ["Bruno"]),
            ({"profissional": self.dra_ana.pk}, ["Carla"]),
            ({"idade_min": 40}, ["Bruno"]),
            ({"idade_max": 40}, ["Carla"]),
        ]
        for parametros, esperado in casos:
            with self.subTest(parametros=parametros):
                resposta = self.abrir(**parametros)
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(self.nomes_da_tela(resposta), esperado)

    def test_com_filtros_mostra_limpar_contagem_e_mantem_os_valores(self):
        resposta = self.abrir(genero="feminino", idade_max=40)
        self.assertEqual(resposta.context["filtros_ativos"], 2)
        self.assertContains(resposta, "Limpar")
        self.assertContains(resposta, "2 filtros em uso · 1 resultado")
        # Os campos continuam preenchidos depois de filtrar.
        self.assertContains(resposta, '<option value="feminino" selected>')
        self.assertContains(resposta, 'value="40"')
        # "Limpar" volta para a lista sem parâmetros.
        self.assertContains(resposta, f'href="{self.url}" class="btn btn-outline-secondary')

    def test_filtro_sem_resultado_mostra_mensagem_propria(self):
        resposta = self.abrir(busca="ninguem com esse nome")
        self.assertContains(resposta, "Nenhum paciente encontrado com esses filtros.")
        self.assertNotContains(resposta, "Nenhum paciente cadastrado.")

    def test_clinica_sem_pacientes_mantem_a_mensagem_original(self):
        sol_user = User.objects.create_user("joao@example.com", password="x")
        Membro.objects.create(
            user=sol_user, clinica=self.sol,
            grupo=grupo_com_todas_as_permissoes("Administração"),
        )
        self.client.force_login(sol_user)
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "Nenhum paciente cadastrado.")

    def test_filtro_invalido_mostra_erro_e_lista_vazia_em_vez_de_tudo(self):
        resposta = self.abrir(idade_min=60, idade_max=10)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.nomes_da_tela(resposta), [])
        self.assertContains(resposta, "A idade máxima não pode ser menor que a mínima.")

    def test_profissional_de_outra_clinica_nao_filtra_nada(self):
        with clinica_atual(self.sol):
            dr_sol = criar_profissional("Solar")
        resposta = self.abrir(profissional=dr_sol.pk)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.nomes_da_tela(resposta), [])  # inválido => vazio
        self.assertNotContains(resposta, "Solar")

    def test_nao_aparecem_opcoes_nem_pacientes_de_outra_clinica(self):
        with clinica_atual(self.sol):
            criar_profissional("Solar")
            criar_paciente("Eva", convenio="Bradesco Saúde")
        resposta = self.abrir()
        self.assertNotContains(resposta, "Solar")
        self.assertNotContains(resposta, "Bradesco Saúde")
        self.assertNotContains(resposta, "Eva")

    def test_exige_permissao_de_ver_mesmo_com_parametros(self):
        leitor = User.objects.create_user("sem@example.com", password="x")
        Membro.objects.create(
            user=leitor, clinica=self.vida,
            grupo=grupo_com_permissoes("Só profissionais", "profissionais.view_profissional"),
        )
        self.client.force_login(leitor)
        self.assertEqual(self.client.get(self.url, {"genero": "feminino"}).status_code, 403)

    def test_anonimo_vai_para_o_login(self):
        resposta = self.client.get(self.url, {"genero": "feminino"})
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta["Location"].startswith("/login/"))


class PaginacaoComFiltrosTests(BaseComClinicas):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        with clinica_atual(cls.vida):
            for i in range(12):
                criar_paciente(f"Mulher{i:02d}", genero="feminino")
            for i in range(3):
                criar_paciente(f"Homem{i:02d}", genero="masculino")
        cls.url = reverse("pacientes:paciente_list")

    def hrefs_de_pagina(self, resposta):
        achados = re.findall(r'href="([^"]*page=[^"]*)"', resposta.content.decode())
        return [html_lib.unescape(h) for h in achados]

    def test_links_de_pagina_mantem_os_filtros(self):
        self.client.force_login(self.maria)
        resposta = self.client.get(self.url, {"genero": "feminino", "busca": "mulher"})
        self.assertEqual(resposta.context["paginator"].count, 12)
        links = self.hrefs_de_pagina(resposta)
        self.assertTrue(links)
        for link in links:
            with self.subTest(link=link):
                params = parse_qs(urlparse(link).query)
                self.assertEqual(params["genero"], ["feminino"])
                self.assertEqual(params["busca"], ["mulher"])
                self.assertIn("page", params)

    def test_segunda_pagina_continua_filtrada(self):
        self.client.force_login(self.maria)
        resposta = self.client.get(self.url, {"genero": "feminino", "page": 2})
        nomes = [p.primeiro_nome for p in resposta.context["pacientes"]]
        self.assertEqual(len(nomes), 2)  # 12 mulheres: 10 + 2
        self.assertTrue(all(n.startswith("Mulher") for n in nomes))

    def test_trocar_filtro_volta_para_a_primeira_pagina(self):
        # O formulário de filtros não envia `page`, então a busca recomeça na 1.
        self.client.force_login(self.maria)
        resposta = self.client.get(self.url)
        self.assertNotContains(resposta, 'name="page"')

    def test_sem_filtros_os_links_continuam_simples(self):
        self.client.force_login(self.maria)
        resposta = self.client.get(self.url)
        self.assertIn("?page=2", self.hrefs_de_pagina(resposta))

    def test_paginacao_de_outras_listas_continua_funcionando(self):
        with clinica_atual(self.vida):
            for i in range(11):
                criar_profissional(f"Prof{i:02d}")
        self.client.force_login(self.maria)
        resposta = self.client.get(reverse("profissionais:profissional_list"))
        self.assertIn("?page=2", self.hrefs_de_pagina(resposta))


class DesempenhoDaListaTests(BaseComClinicas):
    def consultas_para(self, quantidade):
        with clinica_atual(self.vida):
            Paciente.objects.all().delete()
            for i in range(quantidade):
                paciente = criar_paciente(f"P{i}", genero="feminino")
                Telefone.objects.create(
                    numero=f"6199999{i:04d}", tipo="celular", principal=True,
                    pacientes=paciente,
                )
        self.client.force_login(self.maria)
        url = reverse("pacientes:paciente_list")
        # A primeira requisição paga custos únicos (sessão, cache de tipos de
        # conteúdo e de permissões); só a segunda é comparável entre cenários.
        self.client.get(url, {"genero": "feminino"})
        with CaptureQueriesContext(connection) as capturadas:
            self.client.get(url, {"genero": "feminino"})
        return len(capturadas)

    def test_numero_de_queries_nao_cresce_com_a_quantidade_de_pacientes(self):
        poucas = self.consultas_para(2)
        muitas = self.consultas_para(10)
        self.assertEqual(poucas, muitas)
