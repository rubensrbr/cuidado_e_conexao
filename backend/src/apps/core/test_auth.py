from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

SENHA = "Zm9!kQ7#xLp2"  # forte: 12 caracteres, maiúscula, minúscula, número, símbolo
OUTRA_SENHA = "Qw3#rTy9!uIo"


def criar_usuario(email="maria@clinica.com", senha=SENHA, **kwargs):
    return User.objects.create_user(email, password=senha, **kwargs)


class UserManagerTests(TestCase):
    def test_create_user_padroniza_o_email(self):
        usuario = criar_usuario("  Maria@Clinica.COM ")
        self.assertEqual(usuario.email, "maria@clinica.com")

    def test_create_user_exige_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user("", password=SENHA)

    def test_create_superuser_marca_as_permissoes(self):
        admin = User.objects.create_superuser("admin@clinica.com", password=SENHA)
        self.assertTrue(admin.is_staff and admin.is_superuser)

    def test_get_by_natural_key_ignora_maiusculas_e_espacos(self):
        usuario = criar_usuario()
        self.assertEqual(User.objects.get_by_natural_key(" MARIA@clinica.com "), usuario)

    def test_get_by_natural_key_vazio_nao_acha_ninguem(self):
        criar_usuario()
        with self.assertRaises(User.DoesNotExist):
            User.objects.get_by_natural_key("   ")


class UserModelTests(TestCase):
    def test_save_padroniza_o_email_mesmo_fora_do_manager(self):
        # É o caminho do admin e dos formulários.
        usuario = User(email=" Ana@Clinica.com ")
        usuario.set_password(SENHA)
        usuario.save()
        self.assertEqual(usuario.email, "ana@clinica.com")

    def test_email_repetido_e_barrado(self):
        criar_usuario("ana@clinica.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            criar_usuario("ANA@clinica.com")

    def test_banco_barra_email_repetido_so_por_maiusculas(self):
        # Grava por fora do save() para provar a constraint do banco.
        criar_usuario("ana@clinica.com")
        beto = criar_usuario("beto@clinica.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=beto.pk).update(email="ANA@clinica.com")

    def test_validacao_do_modelo_da_mensagem_em_portugues(self):
        criar_usuario("ana@clinica.com")
        outro = User(email="Ana@Clinica.com")
        with self.assertRaises(ValidationError) as erro:
            outro.validate_constraints()
        self.assertIn("Já existe um usuário com este e-mail.", str(erro.exception))


class LoginTests(TestCase):
    def setUp(self):
        self.usuario = criar_usuario("maria@clinica.com")
        self.url = reverse("login")

    def entrar(self, email, senha=SENHA):
        return self.client.post(self.url, {"username": email, "password": senha})

    def test_entra_com_o_email(self):
        resposta = self.entrar("maria@clinica.com")
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], "/")

    def test_entra_com_o_email_em_maiusculas_e_com_espacos(self):
        self.assertEqual(self.entrar("  MARIA@Clinica.com ").status_code, 302)

    def test_senha_errada_nao_entra(self):
        resposta = self.entrar("maria@clinica.com", "errada")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("E-mail ou senha inválidos", resposta.content.decode())

    def test_email_desconhecido_nao_entra(self):
        self.assertEqual(self.entrar("ninguem@clinica.com").status_code, 200)

    def test_usuario_inativo_nao_entra(self):
        User.objects.filter(pk=self.usuario.pk).update(is_active=False)
        self.assertEqual(self.entrar("maria@clinica.com").status_code, 200)

    def test_authenticate_aceita_email_de_qualquer_caixa(self):
        self.assertEqual(
            authenticate(username="MARIA@clinica.com", password=SENHA), self.usuario
        )

    def test_pagina_de_login_pede_email(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn('type="email"', html)
        self.assertNotIn("Digite seu usuário", html)

    def test_quem_precisa_trocar_a_senha_vai_para_a_troca(self):
        User.objects.filter(pk=self.usuario.pk).update(change_password=True)
        resposta = self.entrar("maria@clinica.com")
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta["Location"], reverse("alterar_senha"))


class PasswordValidatorsTests(TestCase):
    def mensagens(self, senha):
        with self.assertRaises(ValidationError) as erro:
            validate_password(senha)
        return " ".join(erro.exception.messages)

    def test_senha_forte_e_aceita(self):
        validate_password(SENHA)

    def test_exige_8_caracteres(self):
        # Tem de tudo, mas só 7 caracteres.
        self.assertIn("8", self.mensagens("Ab1!xyz"))

    def test_aceita_exatamente_8_caracteres(self):
        validate_password("Ab1!xyzw")

    def test_exige_cada_tipo_de_caractere(self):
        casos = {
            "SENHAFORTE123!": "minúscula",
            "senhaforte123!": "maiúscula",
            "SenhaForte!!!!": "número",
            "SenhaForte1234": "símbolo",
        }
        for senha, esperado in casos.items():
            with self.subTest(senha=senha):
                self.assertIn(esperado, self.mensagens(senha))

    def test_reconhece_letras_acentuadas(self):
        validate_password("ÁÉÍóú123!!abc")

    def test_lista_tudo_o_que_falta_de_uma_vez(self):
        texto = self.mensagens("abcdefghijklmn")
        for esperado in ("maiúscula", "número", "símbolo"):
            self.assertIn(esperado, texto)

    def test_senha_so_numerica_e_comum_continuam_barradas(self):
        self.assertIn("totalmente numérica", self.mensagens("123456789012"))


class PasswordChangeTests(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(change_password=True)
        self.client.force_login(self.usuario)
        self.url = reverse("alterar_senha")

    def trocar(self, nova):
        return self.client.post(
            self.url,
            {"old_password": SENHA, "new_password1": nova, "new_password2": nova},
        )

    def test_exige_login(self):
        self.client.logout()
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("login"), resposta["Location"])

    def test_pagina_abre_e_avisa_quem_precisa_trocar(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "defina uma nova senha")

    def test_senha_fraca_e_recusada_e_a_marca_continua(self):
        resposta = self.trocar("senhafraca1")
        self.assertEqual(resposta.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.change_password)
        self.assertTrue(self.usuario.check_password(SENHA))

    def test_senha_forte_troca_limpa_a_marca_e_mantem_o_login(self):
        resposta = self.trocar(OUTRA_SENHA)
        self.assertRedirects(resposta, "/", fetch_redirect_response=False)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.change_password)
        self.assertTrue(self.usuario.check_password(OUTRA_SENHA))
        self.assertEqual(self.client.get("/").status_code, 200)


class TrocaObrigatoriaMiddlewareTests(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(change_password=True)
        self.client.force_login(self.usuario)

    def test_quem_precisa_trocar_e_levado_a_troca_em_qualquer_pagina(self):
        for url in ("/", "/admin/"):
            with self.subTest(url=url):
                resposta = self.client.get(url)
                self.assertRedirects(
                    resposta, reverse("alterar_senha"), fetch_redirect_response=False
                )

    def test_pode_abrir_a_troca_e_sair(self):
        self.assertEqual(self.client.get(reverse("alterar_senha")).status_code, 200)
        resposta = self.client.post(reverse("logout"))
        self.assertEqual(resposta.status_code, 302)
        self.assertNotEqual(resposta["Location"], reverse("alterar_senha"))

    def test_quem_nao_precisa_trocar_usa_o_sistema_normalmente(self):
        User.objects.filter(pk=self.usuario.pk).update(change_password=False)
        self.assertEqual(self.client.get("/").status_code, 200)


class AdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin@clinica.com", password=SENHA)
        self.client.force_login(self.admin)

    def test_paginas_do_usuario_abrem(self):
        urls = (
            reverse("admin:core_user_changelist"),
            reverse("admin:core_user_add"),
            reverse("admin:core_user_change", args=[self.admin.pk]),
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def dados_novo_usuario(self, senha):
        return {
            "email": "Nova@Clinica.com",
            "first_name": "Nova",
            "last_name": "Pessoa",
            "usable_password": "true",
            "password1": senha,
            "password2": senha,
        }

    def test_cadastro_pelo_admin_com_senha_forte(self):
        resposta = self.client.post(
            reverse("admin:core_user_add"), self.dados_novo_usuario(SENHA)
        )
        self.assertEqual(resposta.status_code, 302)
        novo = User.objects.get(email="nova@clinica.com")
        self.assertTrue(novo.check_password(SENHA))

    def test_cadastro_pelo_admin_recusa_senha_fraca(self):
        resposta = self.client.post(
            reverse("admin:core_user_add"), self.dados_novo_usuario("senhafraca")
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(User.objects.filter(email="nova@clinica.com").exists())

    def test_cadastro_pelo_admin_recusa_email_repetido_em_outra_caixa(self):
        criar_usuario("nova@clinica.com")
        resposta = self.client.post(
            reverse("admin:core_user_add"), self.dados_novo_usuario(SENHA)
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(User.objects.filter(email__iexact="nova@clinica.com").count(), 1)

    def test_acao_exigir_troca_de_senha(self):
        alvo = criar_usuario("alvo@clinica.com")
        self.client.post(
            reverse("admin:core_user_changelist"),
            {
                "action": "exigir_troca_de_senha",
                "_selected_action": [alvo.pk],
            },
        )
        alvo.refresh_from_db()
        self.assertTrue(alvo.change_password)
