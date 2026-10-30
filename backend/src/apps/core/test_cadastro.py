from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from clinicas.models import Membro

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
        self.assertTrue(usuario.is_active)
        self.assertTrue(usuario.check_password(SENHA))
        self.assertNotEqual(usuario.password, SENHA)  # guardada com hash

        avisos = [str(m) for m in get_messages(resposta.wsgi_request)]
        self.assertTrue(any("liberar o seu acesso" in a for a in avisos))

    def test_conta_nova_nao_e_staff_nem_tem_clinica(self):
        self.client.post(self.url, dados())
        usuario = User.objects.get(email="ana@clinica.com")
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertFalse(Membro.objects.filter(user=usuario).exists())

    def test_nao_deixa_o_visitante_se_promover_por_campos_extras(self):
        self.client.post(self.url, dados(is_staff="on", is_superuser="on", change_password="on"))
        usuario = User.objects.get(email="ana@clinica.com")
        self.assertFalse(usuario.is_staff or usuario.is_superuser)
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
