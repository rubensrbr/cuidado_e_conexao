import re
from datetime import timedelta
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import PedidoDeRecuperacao

User = get_user_model()

SENHA = "Zm9!kQ7#xLp2"
NOVA = "Qw3#rTy9!uIo"


def link_do_email():
    corpo = mail.outbox[-1].body
    achado = re.search(r"https?://\S+/redefinir-senha/\S+", corpo)
    assert achado, corpo
    return urlparse(achado.group(0)).path


class LinkTests(TestCase):
    def test_login_tem_link_esqueci_minha_senha(self):
        resposta = self.client.get(reverse("login"))
        self.assertContains(resposta, f'href="{reverse("senha_esquecida")}"')
        self.assertContains(resposta, "Esqueci minha senha")

    def test_formulario_abre_e_tem_link_de_volta(self):
        resposta = self.client.get(reverse("senha_esquecida"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, f'href="{reverse("login")}"')

    def test_quem_ja_esta_logado_e_levado_para_o_inicio(self):
        usuario = User.objects.create_user("ana@clinica.com", password=SENHA)
        self.client.force_login(usuario)
        resposta = self.client.get(reverse("senha_esquecida"))
        self.assertRedirects(resposta, reverse("home"), fetch_redirect_response=False)


class PedidoDeLinkTests(TestCase):
    def setUp(self):
        self.url = reverse("senha_esquecida")
        self.usuario = User.objects.create_user(
            "ana@clinica.com", password=SENHA, first_name="Ana"
        )

    def test_conta_ativa_recebe_o_email_com_o_link(self):
        resposta = self.client.post(self.url, {"email": "ana@clinica.com"})
        self.assertRedirects(resposta, reverse("senha_esquecida_enviada"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@clinica.com"])
        self.assertIn("Ana", mail.outbox[0].body)
        self.assertIn("/redefinir-senha/", mail.outbox[0].body)

    def test_email_em_maiusculas_tambem_funciona(self):
        self.client.post(self.url, {"email": "ANA@Clinica.com"})
        self.assertEqual(len(mail.outbox), 1)

    def test_email_desconhecido_tem_a_mesma_resposta_e_nao_envia_nada(self):
        resposta = self.client.post(self.url, {"email": "ninguem@clinica.com"})
        self.assertRedirects(resposta, reverse("senha_esquecida_enviada"))
        self.assertEqual(len(mail.outbox), 0)

    def test_conta_aguardando_aprovacao_nao_recebe_email(self):
        User.objects.filter(pk=self.usuario.pk).update(
            is_active=False, cadastro_pendente=True
        )
        resposta = self.client.post(self.url, {"email": "ana@clinica.com"})
        self.assertRedirects(resposta, reverse("senha_esquecida_enviada"))
        self.assertEqual(len(mail.outbox), 0)

    def test_email_invalido_mostra_erro(self):
        resposta = self.client.post(self.url, {"email": "isso-nao-e-email"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Digite um e-mail válido.")
        self.assertEqual(len(mail.outbox), 0)

    def test_email_vazio_mostra_erro(self):
        resposta = self.client.post(self.url, {"email": ""})
        self.assertContains(resposta, "Este campo é obrigatório.")

    def test_pagina_de_enviado_nao_confirma_se_o_email_existe(self):
        resposta = self.client.get(reverse("senha_esquecida_enviada"))
        self.assertContains(resposta, "Se o e-mail informado estiver cadastrado")


class RedefinirTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("ana@clinica.com", password=SENHA)
        self.client.post(reverse("senha_esquecida"), {"email": "ana@clinica.com"})
        self.link = link_do_email()

    def abrir_link(self):
        # O Django guarda o token na sessão e redireciona para uma URL "set-password".
        return self.client.get(self.link, follow=True)

    def test_fluxo_completo_troca_a_senha(self):
        resposta = self.abrir_link()
        self.assertContains(resposta, "Criar nova senha")
        url_form = resposta.redirect_chain[-1][0]

        resposta = self.client.post(
            url_form, {"new_password1": NOVA, "new_password2": NOVA}
        )
        self.assertRedirects(resposta, reverse("senha_redefinida"))

        self.assertTrue(self.client.login(username="ana@clinica.com", password=NOVA))
        self.client.logout()
        self.assertFalse(self.client.login(username="ana@clinica.com", password=SENHA))

    def test_nao_entra_sozinho_depois_de_redefinir(self):
        url_form = self.abrir_link().redirect_chain[-1][0]
        self.client.post(url_form, {"new_password1": NOVA, "new_password2": NOVA})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_link_so_vale_uma_vez(self):
        url_form = self.abrir_link().redirect_chain[-1][0]
        self.client.post(url_form, {"new_password1": NOVA, "new_password2": NOVA})
        self.client.logout()
        resposta = self.client.get(self.link, follow=True)
        self.assertContains(resposta, "Link inválido")

    def test_link_adulterado_e_invalido(self):
        resposta = self.client.get(self.link[:-2] + "xx/", follow=True)
        self.assertContains(resposta, "Link inválido")
        self.assertContains(resposta, f'href="{reverse("senha_esquecida")}"')

    def test_link_expirado_e_invalido(self):
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            resposta = self.client.get(self.link, follow=True)
        self.assertContains(resposta, "Link inválido")

    def test_senhas_diferentes_sao_barradas(self):
        url_form = self.abrir_link().redirect_chain[-1][0]
        resposta = self.client.post(
            url_form, {"new_password1": NOVA, "new_password2": "outra"}
        )
        self.assertContains(resposta, "As duas senhas digitadas não são iguais.")
        self.assertTrue(User.objects.get(pk=self.usuario.pk).check_password(SENHA))

    def test_senha_fraca_e_barrada(self):
        url_form = self.abrir_link().redirect_chain[-1][0]
        resposta = self.client.post(
            url_form, {"new_password1": "12345678", "new_password2": "12345678"}
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(User.objects.get(pk=self.usuario.pk).check_password(SENHA))

    def test_redefinir_tira_a_exigencia_de_trocar_a_senha(self):
        User.objects.filter(pk=self.usuario.pk).update(change_password=True)
        url_form = self.abrir_link().redirect_chain[-1][0]
        self.client.post(url_form, {"new_password1": NOVA, "new_password2": NOVA})
        self.assertFalse(User.objects.get(pk=self.usuario.pk).change_password)


@override_settings(RECUPERACAO_MAX_PEDIDOS_POR_IP=3, RECUPERACAO_JANELA_EM_SEGUNDOS=3600)
class LimiteDePedidosTests(TestCase):
    def setUp(self):
        self.url = reverse("senha_esquecida")
        User.objects.create_user("ana@clinica.com", password=SENHA)

    def pedir(self, ip="10.0.0.1", email="ana@clinica.com"):
        return self.client.post(self.url, {"email": email}, REMOTE_ADDR=ip)

    def test_passou_do_limite_recebe_429_e_nenhum_email_sai(self):
        for _ in range(3):
            self.assertEqual(self.pedir().status_code, 302)
        resposta = self.pedir()
        self.assertEqual(resposta.status_code, 429)
        self.assertContains(resposta, "Muitos pedidos", status_code=429)
        self.assertGreater(int(resposta["Retry-After"]), 0)
        self.assertEqual(len(mail.outbox), 3)

    def test_email_desconhecido_tambem_conta(self):
        for n in range(3):
            self.pedir(email=f"x{n}@clinica.com")
        self.assertEqual(self.pedir().status_code, 429)

    def test_outro_ip_nao_e_afetado(self):
        for _ in range(3):
            self.pedir()
        self.assertEqual(self.pedir(ip="10.0.0.2").status_code, 302)

    def test_apenas_abrir_a_pagina_nao_conta(self):
        for _ in range(10):
            self.assertEqual(self.client.get(self.url, REMOTE_ADDR="10.0.0.1").status_code, 200)
        self.assertEqual(self.pedir().status_code, 302)

    def test_pedidos_antigos_saem_da_conta(self):
        antigos = timezone.now() - timedelta(hours=2)
        for _ in range(3):
            PedidoDeRecuperacao.objects.create(ip="10.0.0.1", criada_em=antigos)
        self.assertEqual(self.pedir().status_code, 302)
        self.assertEqual(PedidoDeRecuperacao.objects.count(), 1)
