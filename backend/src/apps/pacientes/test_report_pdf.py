from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from clinicas.helpers_de_teste import grupo_com_todas_as_permissoes
from clinicas.models import Clinica, Membro
from clinicas.tenancy import clinica_atual
from telefones.models import Telefone

from .models import Paciente


def criar_paciente(nome, **kwargs):
    dados = {
        "primeiro_nome": nome,
        "sobrenome": "Silva",
        "data_nascimento": date(1990, 5, 17),
        "genero": "feminino",
        "email": f"{nome.lower()}@example.com",
    }
    dados.update(kwargs)
    return Paciente.objects.create(**dados)


class RelatorioPdfPacientesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vida = Clinica.objects.create(
            nome="Vida", cnpj="11222333000181", slug="vida"
        )
        cls.sol = Clinica.objects.create(nome="Sol", cnpj="11444777000161", slug="sol")
        grupo = grupo_com_todas_as_permissoes("Recepção")
        Usuario = get_user_model()
        cls.maria = Usuario.objects.create_user("maria", password="x")
        Membro.objects.create(user=cls.maria, clinica=cls.vida, grupo=grupo)
        cls.sem_clinica = Usuario.objects.create_user("sem_clinica", password="x")

        with clinica_atual(cls.vida):
            cls.ana = criar_paciente("Ana", convenio="Unimed")
            criar_paciente("Caio", genero="masculino", ativo=False)
            Telefone.objects.create(
                numero="11988887777",
                tipo="celular",
                principal=True,
                pacientes=cls.ana,
            )
        with clinica_atual(cls.sol):
            criar_paciente("Beto", genero="masculino")

        cls.url = reverse("pacientes:paciente_report_pdf")

    def gerar(self, **parametros):
        """Gera o PDF e devolve (resposta, html que foi enviado ao WeasyPrint)."""
        capturado = {}

        def espiar(*args, **kwargs):
            capturado["html"] = render_to_string(*args, **kwargs)
            return capturado["html"]

        with mock.patch("pacientes.views.render_to_string", side_effect=espiar):
            resposta = self.client.get(self.url, parametros)
        return resposta, capturado.get("html", "")

    def test_exige_login(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta["Location"].startswith("/login/"))

    def test_devolve_um_pdf_para_download(self):
        self.client.force_login(self.maria)
        resposta, _ = self.gerar()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "application/pdf")
        self.assertTrue(resposta.content.startswith(b"%PDF"))
        disposicao = resposta["Content-Disposition"]
        self.assertTrue(disposicao.startswith('attachment; filename="pacientes_'))
        self.assertTrue(disposicao.endswith('.pdf"'))

    def test_relatorio_traz_so_a_clinica_atual(self):
        self.client.force_login(self.maria)
        _, html = self.gerar()
        self.assertIn("Ana Silva", html)
        self.assertIn("Caio Silva", html)  # inativos também entram
        self.assertNotIn("Beto", html)
        self.assertIn("Vida", html)
        self.assertIn("11.222.333/0001-81", html)

    def test_resumo_e_formatacao(self):
        self.client.force_login(self.maria)
        _, html = self.gerar()
        self.assertIn("17/05/1990", html)
        self.assertIn("Unimed", html)
        self.assertIn("Particular", html)  # Caio não tem convênio
        self.assertIn("11988887777", html)
        self.assertIn("principal", html)
        self.assertIn("Inativo", html)

    def test_respeita_os_filtros_da_lista(self):
        self.client.force_login(self.maria)
        _, html = self.gerar(genero="masculino")
        self.assertIn("Caio Silva", html)
        self.assertNotIn("Ana Silva", html)
        self.assertIn("1 filtro aplicado", html)

    def test_filtro_invalido_nao_vira_todos_os_pacientes(self):
        self.client.force_login(self.maria)
        _, html = self.gerar(profissional="999999")
        self.assertNotIn("Ana Silva", html)
        self.assertIn("Nenhum paciente encontrado com esses filtros.", html)

    def test_usuario_sem_clinica_nao_gera_o_relatorio(self):
        # Sem vínculo com clínica ativa não há papel, logo não há permissão.
        self.client.force_login(self.sem_clinica)
        resposta, html = self.gerar()
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(html, "")  # nem chegou a montar o relatório

    def test_lista_tem_botao_gerar_pdf_que_leva_os_filtros(self):
        self.client.force_login(self.maria)
        resposta = self.client.get(
            reverse("pacientes:paciente_list"), {"genero": "feminino", "page": 1}
        )
        self.assertContains(resposta, "Gerar PDF")
        self.assertContains(resposta, f"{self.url}?genero=feminino")
        self.assertNotContains(resposta, f"{self.url}?genero=feminino&amp;page")
        # O botão principal continua lá.
        self.assertContains(resposta, "Novo paciente")
