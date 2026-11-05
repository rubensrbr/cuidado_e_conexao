# ruff: noqa: E402
from unittest import SkipTest

from django.apps import apps

if not apps.is_installed("faturamentos"):
    raise SkipTest("app 'faturamentos' não está em INSTALLED_APPS neste release")

import re
import uuid

from django.contrib.auth import get_user_model
from django.urls import reverse

from clinicas.helpers_de_teste import (
    grupo_com_permissoes,
    grupo_com_todas_as_permissoes,
)
from clinicas.models import Membro

from .test_pro_bono_pacotes import Base, criar_consulta, criar_pacote

ANCORA = re.compile(r'<a class="([^"]*)"\s+href="([^"]*)"')


class MenuFinanceiroTests(Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        User = get_user_model()

        def membro(nome, grupo):
            usuario = User.objects.create_user(nome, password="x")
            Membro.objects.create(user=usuario, clinica=cls.vida, grupo=grupo)
            return usuario

        cls.admin = membro("admin", grupo_com_todas_as_permissoes("Administração"))
        cls.so_faturamento = membro(
            "fat", grupo_com_permissoes("SoFat", "faturamentos.view_faturamento")
        )
        cls.so_pacote = membro(
            "pac", grupo_com_permissoes("SoPac", "faturamentos.view_pacote")
        )
        cls.sem_financeiro = membro(
            "rec", grupo_com_permissoes("Rec", "pacientes.view_paciente")
        )

    def links(self, resposta):
        """{href: classes} dos links do menu lateral."""
        html = resposta.content.decode()
        return {href: classes for classes, href in ANCORA.findall(html)}

    def abrir(self, usuario, url_name="home", *args):
        self.client.force_login(usuario)
        return self.client.get(reverse(url_name, args=args))

    @property
    def url_faturamentos(self):
        return reverse("faturamentos:faturamento_list")

    @property
    def url_pacotes(self):
        return reverse("faturamentos:pacote_list")

    def test_admin_ve_a_secao_financeiro_com_os_dois_links(self):
        resposta = self.abrir(self.admin)
        links = self.links(resposta)
        self.assertContains(resposta, "Financeiro")
        self.assertIn(self.url_faturamentos, links)
        self.assertIn(self.url_pacotes, links)

    def test_so_faturamento_nao_ve_o_link_de_pacotes(self):
        resposta = self.abrir(self.so_faturamento)
        links = self.links(resposta)
        self.assertContains(resposta, "Financeiro")
        self.assertIn(self.url_faturamentos, links)
        self.assertNotIn(self.url_pacotes, links)

    def test_so_pacote_nao_ve_o_link_de_faturamentos(self):
        resposta = self.abrir(self.so_pacote)
        links = self.links(resposta)
        self.assertContains(resposta, "Financeiro")
        self.assertIn(self.url_pacotes, links)
        self.assertNotIn(self.url_faturamentos, links)

    def test_sem_permissao_financeira_a_secao_some(self):
        resposta = self.abrir(self.sem_financeiro)
        links = self.links(resposta)
        self.assertNotContains(resposta, "Financeiro")
        self.assertNotIn(self.url_faturamentos, links)
        self.assertNotIn(self.url_pacotes, links)

    def test_na_lista_de_faturamentos_so_faturamentos_fica_ativo(self):
        links = self.links(self.abrir(self.admin, "faturamentos:faturamento_list"))
        self.assertIn("active", links[self.url_faturamentos])
        self.assertNotIn("active", links[self.url_pacotes])

    def test_nas_telas_de_pacote_so_pacotes_fica_ativo(self):
        pacote = criar_pacote(self.ana)
        paginas = (
            ("faturamentos:pacote_list", ()),
            ("faturamentos:pacote_create", ()),
            ("faturamentos:pacote_detail", (pacote.uuid,)),
            ("faturamentos:pacote_update", (pacote.uuid,)),
            ("faturamentos:sessaopacote_create", (pacote.uuid,)),
        )
        for nome, args in paginas:
            with self.subTest(pagina=nome):
                links = self.links(self.abrir(self.admin, nome, *args))
                self.assertIn("active", links[self.url_pacotes])
                self.assertNotIn("active", links[self.url_faturamentos])

    def test_ao_desvincular_consulta_pacotes_continua_ativo(self):
        from .models import SessaoPacote

        pacote = criar_pacote(self.ana)
        sessao = SessaoPacote.objects.create(
            pacote=pacote, consulta=criar_consulta(self.ana, self.dra, 5)
        )
        links = self.links(
            self.abrir(self.admin, "faturamentos:sessaopacote_delete", sessao.uuid)
        )
        self.assertIn("active", links[self.url_pacotes])
        self.assertNotIn("active", links[self.url_faturamentos])

    def test_outras_paginas_nao_ativam_os_links_financeiros(self):
        links = self.links(self.abrir(self.admin))
        self.assertNotIn("active", links[self.url_faturamentos])
        self.assertNotIn("active", links[self.url_pacotes])

    def test_pagina_inexistente_continua_renderizando(self):
        self.client.force_login(self.admin)
        resposta = self.client.get(
            reverse("faturamentos:pacote_detail", args=[uuid.uuid4()])
        )
        self.assertEqual(resposta.status_code, 404)
