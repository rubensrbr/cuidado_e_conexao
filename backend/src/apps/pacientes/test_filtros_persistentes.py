from datetime import date
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clinicas.helpers_de_teste import grupo_com_todas_as_permissoes
from clinicas.models import Clinica, Membro
from clinicas.tenancy import clinica_atual

from .models import Paciente

User = get_user_model()


def criar_paciente(nome, **kwargs):
    dados = {
        "primeiro_nome": nome,
        "sobrenome": "Silva",
        "data_nascimento": date(1990, 1, 1),
        "genero": "outro",
    }
    dados.update(kwargs)
    return Paciente.objects.create(**dados)


class FiltrosPersistentesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vida = Clinica.objects.create(
            nome="Vida", cnpj="11222333000181", slug="vida"
        )
        cls.sol = Clinica.objects.create(nome="Sol", cnpj="11444777000161", slug="sol")
        cls.maria = User.objects.create_user("maria@example.com", password="x")
        grupo = grupo_com_todas_as_permissoes("Administração")
        Membro.objects.create(user=cls.maria, clinica=cls.vida, grupo=grupo)
        Membro.objects.create(user=cls.maria, clinica=cls.sol, grupo=grupo)
        with clinica_atual(cls.vida):
            cls.ana = criar_paciente("Ana", genero="feminino")
            cls.bruno = criar_paciente("Bruno", genero="masculino")

    def setUp(self):
        self.client.force_login(self.maria)
        self.escolher_clinica(self.vida)
        self.url = reverse("pacientes:paciente_list")

    def escolher_clinica(self, clinica):
        sessao = self.client.session
        sessao["clinica_uuid"] = str(clinica.uuid)
        sessao.save()

    def nomes(self, resposta):
        return sorted(p.primeiro_nome for p in resposta.context["pacientes"])

    # --- o caso pedido: ir para editar/excluir e voltar ---------------------
    def test_filtro_continua_aplicado_ao_voltar_de_editar(self):
        resposta = self.client.get(self.url, {"genero": "feminino"})
        self.assertEqual(self.nomes(resposta), ["Ana"])

        # Abre a tela de edição e volta para a lista (link do menu / Cancelar).
        editar = reverse("pacientes:paciente_update", args=[self.ana.uuid])
        self.assertEqual(self.client.get(editar).status_code, 200)

        resposta = self.client.get(self.url, follow=True)
        self.assertEqual(self.nomes(resposta), ["Ana"])
        self.assertEqual(resposta.request["QUERY_STRING"], "genero=feminino")
        self.assertEqual(resposta.context["filtros_ativos"], 1)

    def test_filtro_continua_aplicado_depois_de_excluir(self):
        self.client.get(self.url, {"genero": "masculino"})
        excluir = reverse("pacientes:paciente_delete", args=[self.bruno.uuid])
        self.assertEqual(self.client.get(excluir).status_code, 200)

        # O POST redireciona para a lista sem parâmetros, que restaura o filtro.
        resposta = self.client.post(excluir, follow=True)
        self.assertEqual(resposta.request["QUERY_STRING"], "genero=masculino")
        self.assertEqual(self.nomes(resposta), [])
        self.assertEqual(resposta.context["filtros_ativos"], 1)

    def test_sem_filtro_guardado_a_lista_abre_normalmente(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.nomes(resposta), ["Ana", "Bruno"])

    # --- Limpar --------------------------------------------------------------
    def test_limpar_esquece_o_filtro(self):
        self.client.get(self.url, {"genero": "feminino", "busca": "ana"})

        resposta = self.client.get(self.url, {"limpar": "1"})
        self.assertRedirects(resposta, self.url)

        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.nomes(resposta), ["Ana", "Bruno"])
        self.assertEqual(resposta.context["filtros_ativos"], 0)

    def test_botao_limpar_da_tela_aponta_para_limpar(self):
        resposta = self.client.get(self.url, {"genero": "feminino"})
        self.assertContains(resposta, f'href="{self.url}?limpar=1"')

    def test_enviar_o_formulario_vazio_tambem_limpa(self):
        self.client.get(self.url, {"genero": "feminino"})
        self.client.get(self.url, {"busca": "", "genero": "", "status": "", "profissional": ""})
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.nomes(resposta), ["Ana", "Bruno"])

    def test_novo_filtro_substitui_o_anterior(self):
        self.client.get(self.url, {"genero": "feminino"})
        self.client.get(self.url, {"busca": "bruno"})
        resposta = self.client.get(self.url, follow=True)
        self.assertEqual(resposta.request["QUERY_STRING"], "busca=bruno")
        self.assertEqual(self.nomes(resposta), ["Bruno"])

    # --- paginação -----------------------------------------------------------
    def test_pagina_e_mantida_junto_com_o_filtro_guardado(self):
        self.client.get(self.url, {"genero": "feminino"})
        resposta = self.client.get(self.url, {"page": "2"})
        self.assertEqual(resposta.status_code, 302)
        consulta = parse_qs(urlparse(resposta["Location"]).query)
        self.assertEqual(consulta, {"genero": ["feminino"], "page": ["2"]})

    # --- isolamento ----------------------------------------------------------
    def test_filtros_de_uma_clinica_nao_valem_na_outra(self):
        self.client.get(self.url, {"genero": "feminino"})

        self.escolher_clinica(self.sol)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)  # sem redirecionar

        self.escolher_clinica(self.vida)
        resposta = self.client.get(self.url, follow=True)
        self.assertEqual(resposta.request["QUERY_STRING"], "genero=feminino")

    def test_filtros_de_um_usuario_nao_aparecem_para_outro(self):
        self.client.get(self.url, {"genero": "feminino"})

        outro = User.objects.create_user("joao@example.com", password="x")
        Membro.objects.create(
            user=outro,
            clinica=self.vida,
            grupo=grupo_com_todas_as_permissoes("Administração"),
        )
        self.client.force_login(outro)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.nomes(resposta), ["Ana", "Bruno"])
