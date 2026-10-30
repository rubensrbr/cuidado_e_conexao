from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clinicas.models import Membro

from .models import TentativaDeCadastro

User = get_user_model()

SENHA = "Zm9!kQ7#xLp2"  # forte: 12 caracteres, maiúscula, minúscula, número, símbolo


def dados(**kwargs):
    base = {
        "first_name": "Ana",
        "last_name": "Souza",
        "email": "ana@clinica.com",
        "password1": SENHA,
        "password2": SENHA,
    }
    base.update(kwargs)
    return base


class LinkDeCadastroTests(TestCase):
    def test_login_tem_link_para_o_cadastro_logo_abaixo_do_formulario(self):
        resposta = self.client.get(reverse("login"))
        html = resposta.content.decode()
        self.assertContains(resposta, f'href="{reverse("cadastro")}"')
        # O link vem depois do botão Entrar.
        self.assertGreater(html.index(reverse("cadastro")), html.index("Entrar</button>"))

    def test_cadastro_tem_link_de_volta_para_o_login(self):
        resposta = self.client.get(reverse("cadastro"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, f'href="{reverse("login")}"')


class CadastroTests(TestCase):
    def setUp(self):
        self.url = reverse("cadastro")

    def test_cria_a_conta_e_volta_para_o_login_com_aviso(self):
        resposta = self.client.post(self.url, dados())
        self.assertRedirects(resposta, reverse("login"))

        usuario = User.objects.get(email="ana@clinica.com")
        self.assertEqual((usuario.first_name, usuario.last_name), ("Ana", "Souza"))
        self.assertTrue(usuario.check_password(SENHA))
        self.assertNotEqual(usuario.password, SENHA)  # guardada com hash

        avisos = [str(m) for m in get_messages(resposta.wsgi_request)]
        self.assertTrue(any("aprovar o seu cadastro" in a for a in avisos))

    def test_conta_nasce_inativa_e_aguardando_aprovacao(self):
        self.client.post(self.url, dados())
        usuario = User.objects.get(email="ana@clinica.com")
        self.assertFalse(usuario.is_active)
        self.assertTrue(usuario.cadastro_pendente)

    def test_conta_pendente_nao_consegue_entrar_e_ve_o_motivo(self):
        self.client.post(self.url, dados())
        resposta = self.client.post(
            reverse("login"), {"username": "ana@clinica.com", "password": SENHA}
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "aguardando a aprovação de um administrador")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_senha_errada_nao_revela_que_a_conta_existe(self):
        self.client.post(self.url, dados())
        resposta = self.client.post(
            reverse("login"), {"username": "ana@clinica.com", "password": "errada"}
        )
        self.assertContains(resposta, "E-mail ou senha inválidos")
        self.assertNotContains(resposta, "aguardando a aprovação")

    def test_conta_nova_nao_e_staff_nem_tem_clinica(self):
        self.client.post(self.url, dados())
        usuario = User.objects.get(email="ana@clinica.com")
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertFalse(Membro.objects.filter(user=usuario).exists())

    def test_nao_deixa_o_visitante_se_promover_por_campos_extras(self):
        self.client.post(
            self.url,
            dados(is_staff="on", is_superuser="on", change_password="on", is_active="on"),
        )
        usuario = User.objects.get(email="ana@clinica.com")
        self.assertFalse(usuario.is_staff or usuario.is_superuser or usuario.is_active)
        self.assertFalse(usuario.change_password)

    def test_email_e_guardado_em_minusculas(self):
        self.client.post(self.url, dados(email="  Ana@Clinica.COM "))
        self.assertTrue(User.objects.filter(email="ana@clinica.com").exists())

    def test_email_repetido_e_barrado_sem_diferenciar_maiusculas(self):
        User.objects.create_user("ana@clinica.com", password=SENHA)
        resposta = self.client.post(self.url, dados(email="ANA@clinica.com"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Já existe um usuário com este e-mail.")
        self.assertEqual(User.objects.count(), 1)

    def test_senhas_diferentes_sao_barradas(self):
        resposta = self.client.post(self.url, dados(password2="Outra#Senha9x"))
        self.assertContains(resposta, "As duas senhas digitadas não são iguais.")
        self.assertFalse(User.objects.exists())

    def test_senha_fraca_e_barrada(self):
        resposta = self.client.post(self.url, dados(password1="123", password2="123"))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("password2", resposta.context["form"].errors)
        self.assertFalse(User.objects.exists())

    def test_nome_e_sobrenome_sao_obrigatorios(self):
        resposta = self.client.post(self.url, dados(first_name="", last_name=""))
        erros = resposta.context["form"].errors
        self.assertIn("first_name", erros)
        self.assertIn("last_name", erros)
        self.assertFalse(User.objects.exists())

    def test_quem_ja_esta_logado_e_levado_para_o_inicio(self):
        usuario = User.objects.create_user("maria@clinica.com", password=SENHA)
        self.client.force_login(usuario)
        resposta = self.client.get(self.url)
        self.assertRedirects(resposta, reverse("home"), fetch_redirect_response=False)


@override_settings(CADASTRO_MAX_TENTATIVAS_POR_IP=3, CADASTRO_JANELA_EM_SEGUNDOS=3600)
class LimiteDeTentativasTests(TestCase):
    def setUp(self):
        self.url = reverse("cadastro")

    def enviar(self, n, ip="10.0.0.1", **extra):
        return self.client.post(
            self.url, dados(email=f"pessoa{n}@clinica.com", **extra), REMOTE_ADDR=ip
        )

    def test_passou_do_limite_do_ip_recebe_429_e_nada_e_criado(self):
        for n in range(3):
            self.assertEqual(self.enviar(n).status_code, 302)
        resposta = self.enviar(99)
        self.assertEqual(resposta.status_code, 429)
        self.assertContains(resposta, "Muitas tentativas", status_code=429)
        self.assertGreater(int(resposta["Retry-After"]), 0)
        self.assertFalse(User.objects.filter(email="pessoa99@clinica.com").exists())
        self.assertEqual(User.objects.count(), 3)

    def test_envios_com_erro_tambem_contam(self):
        for n in range(3):
            self.enviar(n, password2="outra")  # senhas diferentes: não cria conta
        self.assertEqual(self.enviar(9).status_code, 429)

    def test_outro_ip_nao_e_afetado(self):
        for n in range(3):
            self.enviar(n)
        self.assertEqual(self.enviar(10, ip="10.0.0.2").status_code, 302)

    def test_apenas_abrir_a_pagina_nao_conta(self):
        for _ in range(10):
            self.assertEqual(self.client.get(self.url, REMOTE_ADDR="10.0.0.1").status_code, 200)
        self.assertEqual(self.enviar(1).status_code, 302)

    def test_tentativas_antigas_saem_da_conta(self):
        antigas = timezone.now() - timedelta(hours=2)
        for _ in range(3):
            TentativaDeCadastro.objects.create(ip="10.0.0.1", criada_em=antigas)
        self.assertEqual(self.enviar(1).status_code, 302)
        self.assertEqual(TentativaDeCadastro.objects.count(), 1)  # as antigas foram apagadas

    def test_ip_do_proxy_so_vale_quando_configurado(self):
        cabecalho = {"HTTP_X_FORWARDED_FOR": "1.1.1.1, 2.2.2.2"}
        # Desligado: cabeçalho forjado é ignorado, vale o REMOTE_ADDR.
        for n in range(3):
            self.client.post(self.url, dados(email=f"a{n}@x.com"), REMOTE_ADDR="10.0.0.1", **cabecalho)
        resposta = self.client.post(self.url, dados(email="a9@x.com"), REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="9.9.9.9")
        self.assertEqual(resposta.status_code, 429)

        TentativaDeCadastro.objects.all().delete()
        with override_settings(CADASTRO_CONFIAR_X_FORWARDED_FOR=True):
            for n in range(3):
                self.client.post(self.url, dados(email=f"b{n}@x.com"), REMOTE_ADDR="10.0.0.1", **cabecalho)
            # Último valor do cabeçalho = IP visto pelo proxy; outro IP ainda passa.
            ok = self.client.post(self.url, dados(email="b9@x.com"), REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="3.3.3.3")
            self.assertEqual(ok.status_code, 302)
            bloqueado = self.client.post(self.url, dados(email="b8@x.com"), REMOTE_ADDR="10.0.0.1", **cabecalho)
            self.assertEqual(bloqueado.status_code, 429)


@override_settings(CADASTRO_MAX_PENDENTES=2, CADASTRO_MAX_TENTATIVAS_POR_IP=100)
class LimiteDePendentesTests(TestCase):
    def test_cadastro_fecha_quando_ha_pendentes_demais(self):
        url = reverse("cadastro")
        for n in range(2):
            self.assertEqual(
                self.client.post(url, dados(email=f"p{n}@x.com"), REMOTE_ADDR=f"10.0.0.{n}").status_code,
                302,
            )
        resposta = self.client.post(url, dados(email="p9@x.com"), REMOTE_ADDR="10.0.0.9")
        self.assertEqual(resposta.status_code, 503)
        self.assertContains(resposta, "temporariamente fechados", status_code=503)
        self.assertFalse(User.objects.filter(email="p9@x.com").exists())

    def test_aprovar_libera_vaga(self):
        url = reverse("cadastro")
        for n in range(2):
            self.client.post(url, dados(email=f"p{n}@x.com"))
        User.objects.filter(email="p0@x.com").update(cadastro_pendente=False, is_active=True)
        self.assertEqual(self.client.post(url, dados(email="p9@x.com")).status_code, 302)


class AprovacaoNoAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin@clinica.com", password=SENHA)

    def setUp(self):
        self.client.post(reverse("cadastro"), dados())
        self.pendente = User.objects.get(email="ana@clinica.com")
        self.client.force_login(self.admin)

    def test_acao_aprovar_ativa_a_conta_e_ela_consegue_entrar(self):
        resposta = self.client.post(
            reverse("admin:core_user_changelist"),
            {"action": "aprovar_cadastros", "_selected_action": [self.pendente.pk]},
            follow=True,
        )
        self.assertContains(resposta, "1 cadastro(s) aprovado(s)")
        self.pendente.refresh_from_db()
        self.assertTrue(self.pendente.is_active)
        self.assertFalse(self.pendente.cadastro_pendente)

        self.client.logout()
        self.client.post(reverse("login"), {"username": "ana@clinica.com", "password": SENHA})
        self.assertEqual(self.client.session["_auth_user_id"], str(self.pendente.pk))

    def test_acao_aprovar_nao_reativa_conta_desativada_de_proposito(self):
        desativada = User.objects.create_user("bia@clinica.com", password=SENHA, is_active=False)
        self.client.post(
            reverse("admin:core_user_changelist"),
            {"action": "aprovar_cadastros", "_selected_action": [desativada.pk]},
        )
        desativada.refresh_from_db()
        self.assertFalse(desativada.is_active)

    def test_marcar_ativo_na_edicao_tambem_aprova(self):
        url = reverse("admin:core_user_change", args=[self.pendente.pk])
        self.client.post(
            url,
            {
                "email": self.pendente.email,
                "password": self.pendente.password,
                "first_name": "Ana",
                "last_name": "Souza",
                "is_active": "on",
                "cadastro_pendente": "on",
                "date_joined_0": "2026-10-29",
                "date_joined_1": "10:00:00",
            },
        )
        self.pendente.refresh_from_db()
        self.assertTrue(self.pendente.is_active)
        self.assertFalse(self.pendente.cadastro_pendente)
