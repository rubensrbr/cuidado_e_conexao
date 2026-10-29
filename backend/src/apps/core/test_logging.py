"""Configuração de logs: sem linhas duplicadas e sem dados pessoais."""

import logging
import runpy

from django.conf import settings
from django.test import SimpleTestCase


class ConfiguracaoDeLogsTests(SimpleTestCase):
    def test_root_e_django_escrevem_no_console(self):
        self.assertEqual(settings.LOGGING["root"]["handlers"], ["console"])
        self.assertEqual(settings.LOGGING["loggers"]["django"]["handlers"], ["console"])

    def test_django_nao_propaga_para_o_root(self):
        # Se propagasse, cada linha do Django sairia duas vezes (própria + root).
        self.assertFalse(settings.LOGGING["loggers"]["django"]["propagate"])

    def test_sql_com_parametros_nunca_e_registrado(self):
        # Em DEBUG o Django loga cada SQL com os parâmetros (dados de pacientes).
        sql = logging.getLogger("django.db.backends")
        self.assertFalse(sql.isEnabledFor(logging.DEBUG))
        self.assertFalse(sql.isEnabledFor(logging.INFO))

    def test_requisicao_404_e_registrada_sem_a_query_string(self):
        with self.assertLogs("django.request", level="WARNING") as capturado:
            resposta = self.client.get("/nao-existe/?busca=Maria+Silva")
        self.assertEqual(resposta.status_code, 404)
        saida = "\n".join(capturado.output)
        self.assertIn("Not Found: /nao-existe/", saida)
        self.assertNotIn("Maria", saida)


class GunicornConfTests(SimpleTestCase):
    """O gunicorn grava o access log; a busca de pacientes é um GET."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conf = runpy.run_path(str(settings.BASE_DIR / "gunicorn.conf.py"))

    def test_access_log_vai_para_stdout(self):
        self.assertEqual(self.conf["accesslog"], "-")
        self.assertEqual(self.conf["errorlog"], "-")

    def test_access_log_registra_so_o_caminho_nunca_a_query_string(self):
        formato = self.conf["access_log_format"]
        self.assertIn("%(U)s", formato)  # caminho, sem query string
        self.assertNotIn("%(r)s", formato)  # requisição inteira (inclui ?busca=Nome)
        self.assertNotIn("%(q)s", formato)  # query string
        self.assertNotIn("%(f)s", formato)  # Referer (pode ter a query da lista)
