from unittest import mock

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.urls import reverse


from .test_filtros import BaseComClinicas


class RelatorioPdfConsultasTests(BaseComClinicas):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.sem_clinica = get_user_model().objects.create_user(
            "sem_clinica@example.com", password="x"
        )
        cls.url = reverse("consultas:consulta_report_pdf")

    def gerar(self, **parametros):
        """Gera o PDF e devolve (resposta, html que foi enviado ao WeasyPrint)."""
        capturado = {}

        def espiar(*args, **kwargs):
            capturado["html"] = render_to_string(*args, **kwargs)
            return capturado["html"]

        with mock.patch("consultas.views.render_to_string", side_effect=espiar):
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
        self.assertTrue(disposicao.startswith('attachment; filename="consultas_'))
        self.assertTrue(disposicao.endswith('.pdf"'))

    def test_relatorio_traz_so_a_clinica_atual(self):
        self.client.force_login(self.maria)
        _, html = self.gerar()
        self.assertIn("Ana Silva", html)
        self.assertIn("Bruno Souza", html)
        self.assertNotIn("Erica", html)
        self.assertIn("Vida", html)
        self.assertIn("11.222.333/0001-81", html)

    def test_resumo_e_formatacao(self):
        self.client.force_login(self.maria)
        _, html = self.gerar()
        self.assertIn("10/10/2026", html)
        self.assertIn("09:00", html)
        self.assertIn("Avaliação Inicial", html)
        self.assertIn("Realizada", html)
        self.assertIn("Agendada", html)

    def test_respeita_os_filtros_da_lista(self):
        self.client.force_login(self.maria)
        _, html = self.gerar(status="realizada", data_de="2026-10-01")
        self.assertIn("Bruno Souza", html)
        self.assertNotIn("Ana Silva", html)
        self.assertIn("2 filtros aplicados", html)
        self.assertIn("de 01/10/2026", html)

    def test_filtro_invalido_nao_vira_todas_as_consultas(self):
        self.client.force_login(self.maria)
        _, html = self.gerar(data_de="2026-10-20", data_ate="2026-10-10")
        self.assertNotIn("Ana Silva", html)
        self.assertIn("Nenhuma consulta encontrada com esses filtros.", html)

    def test_usuario_sem_clinica_nao_gera_o_relatorio(self):
        # Sem vínculo com clínica ativa não há papel, logo não há permissão.
        self.client.force_login(self.sem_clinica)
        resposta, html = self.gerar()
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(html, "")  # nem chegou a montar o relatório

    def test_lista_tem_botao_gerar_pdf_que_leva_os_filtros(self):
        self.client.force_login(self.maria)
        resposta = self.client.get(
            reverse("consultas:consulta_list"), {"status": "agendada", "page": 1}
        )
        self.assertContains(resposta, "Gerar PDF")
        self.assertContains(resposta, f"{self.url}?status=agendada")
        self.assertNotContains(resposta, "status=agendada&amp;page")
        # O botão principal continua lá.
        self.assertContains(resposta, "Nova consulta")
