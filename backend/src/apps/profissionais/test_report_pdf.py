from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clinicas.models import Clinica, Membro
from clinicas.helpers_de_teste import grupo_com_todas_as_permissoes
from clinicas.tenancy import clinica_atual
from telefones.models import Telefone

from .models import Profissional, TipoProfissional


def criar_profissional(nome, email, **kwargs):
    dados = {
        "primeiro_nome": nome,
        "sobrenome": "Lima",
        "email": email,
        "tipo_profissional": TipoProfissional.objects.first(),
        "numero_registro": "123",
        "valor_hora": Decimal("1234.50"),
    }
    dados.update(kwargs)
    return Profissional.objects.create(**dados)


class RelatorioPdfProfissionaisTests(TestCase):
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
            cls.ana = criar_profissional("Ana", "ana@example.com")
            criar_profissional("Caio", "caio@example.com", ativo=False)
            Telefone.objects.create(
                numero="11988887777",
                tipo="celular",
                principal=True,
                profissionais=cls.ana,
            )
        with clinica_atual(cls.sol):
            criar_profissional("Beto", "beto@example.com")

        cls.url = reverse("profissionais:profissional_report_pdf")

    def gerar(self):
        """Gera o PDF e devolve (resposta, html que foi enviado ao WeasyPrint)."""
        capturado = {}

        def espiar(*args, **kwargs):
            from django.template.loader import render_to_string

            capturado["html"] = render_to_string(*args, **kwargs)
            return capturado["html"]

        with mock.patch("profissionais.views.render_to_string", side_effect=espiar):
            resposta = self.client.get(self.url)
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
        self.assertTrue(disposicao.startswith('attachment; filename="profissionais_'))
        self.assertTrue(disposicao.endswith('.pdf"'))

    def test_relatorio_traz_so_a_clinica_atual(self):
        self.client.force_login(self.maria)
        _, html = self.gerar()
        self.assertIn("Ana Lima", html)
        self.assertIn("Caio Lima", html)  # inativos também entram
        self.assertNotIn("Beto", html)
        self.assertIn("Vida", html)
        self.assertIn("11.222.333/0001-81", html)

    def test_resumo_e_formatacao(self):
        self.client.force_login(self.maria)
        _, html = self.gerar()
        self.assertIn("R$ 1.234,50", html)
        self.assertIn("11988887777", html)
        self.assertIn("principal", html)
        self.assertIn("Inativo", html)

    def test_usuario_sem_clinica_nao_gera_o_relatorio(self):
        # Sem vínculo com clínica ativa não há papel, logo não há permissão.
        self.client.force_login(self.sem_clinica)
        resposta, html = self.gerar()
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(html, "")  # nem chegou a montar o relatório

    def test_lista_tem_botao_gerar_pdf(self):
        self.client.force_login(self.maria)
        resposta = self.client.get(reverse("profissionais:profissional_list"))
        self.assertContains(resposta, self.url)
        self.assertContains(resposta, "Gerar PDF")
        # O botão principal continua lá.
        self.assertContains(resposta, "Novo profissional")
