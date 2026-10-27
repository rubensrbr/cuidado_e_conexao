from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import (
    password_validators_help_texts,
    validate_password,
)
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

User = get_user_model()
SENHA = "Zm9!kQ7#xLp2"
NOVA = "Abc123!xyzQ"

# Pedaços dos textos originais do Django: nenhum pode aparecer na tela.
INGLES = (
    "Your ",
    "This password",
    "The password",
    "This field",
    "didn’t match",
    "Enter the same",
    "entered incorrectly",
)


def mensagens(senha, user=None):
    """Mensagens de erro da validação (falha o teste se a senha for aceita)."""
    try:
        validate_password(senha, user)
    except ValidationError as erro:
        return erro.messages
    raise AssertionError(f"A senha {senha!r} deveria ser recusada.")


class ValidadoresEmPortuguesTests(TestCase):
    def test_senha_curta(self):
        texto = " ".join(mensagens("Ab1!xyz"))
        self.assertIn("muito curta", texto)
        self.assertIn("pelo menos 8 caracteres", texto)

    def test_senha_comum(self):
        self.assertIn("Esta senha é muito comum.", mensagens("password"))

    def test_senha_so_numerica(self):
        self.assertIn(
            "Esta senha é totalmente numérica.", mensagens("123456789012")
        )

    def test_parecida_com_o_email(self):
        user = User(email="maria@clinica.com", first_name="Maria", last_name="Souza")
        self.assertIn(
            "Esta senha é muito parecida com o seu e-mail.",
            mensagens("maria@clinica.com1", user),
        )

    def test_parecida_com_nome_e_sobrenome(self):
        user = User(email="x@y.com", first_name="Mariana", last_name="Albuquerque")
        self.assertIn(
            "Esta senha é muito parecida com o seu nome.", mensagens("Mariana1!", user)
        )
        self.assertIn(
            "Esta senha é muito parecida com o seu sobrenome.",
            mensagens("Albuquerque1!", user),
        )

    def test_nenhuma_mensagem_em_ingles(self):
        user = User(email="maria@clinica.com", first_name="Maria")
        for senha in ("maria", "123456789012", "password", "Ab1!xyz", "maria@clinica.com"):
            for texto in mensagens(senha, user):
                with self.subTest(senha=senha, texto=texto):
                    for ingles in INGLES:
                        self.assertNotIn(ingles, texto)

    def test_a_regra_continua_a_do_django(self):
        # Só a mensagem mudou: senha boa passa, e o código do erro é o original.
        validate_password(SENHA)
        with self.assertRaises(ValidationError) as erro:
            validate_password("123456789012")
        codigos = {e.code for e in erro.exception.error_list}
        self.assertIn("password_entirely_numeric", codigos)

    def test_dicas_de_senha_em_portugues(self):
        dicas = password_validators_help_texts()
        self.assertEqual(len(dicas), 5)
        self.assertIn("Sua senha precisa ter pelo menos 8 caracteres.", dicas)
        self.assertIn("Sua senha não pode ser totalmente numérica.", dicas)
        for dica in dicas:
            with self.subTest(dica=dica):
                self.assertNotIn("Your ", dica)


class TelaTrocaDeSenhaEmPortuguesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "maria@clinica.com", password=SENHA, first_name="Maria", last_name="Souza"
        )
        self.client.force_login(self.user)
        self.url = reverse("alterar_senha")

    def enviar(self, atual=SENHA, nova=NOVA, confirmacao=None):
        return self.client.post(
            self.url,
            {
                "old_password": atual,
                "new_password1": nova,
                "new_password2": nova if confirmacao is None else confirmacao,
            },
        )

    def assertSemIngles(self, resposta):
        conteudo = resposta.content.decode()
        for ingles in INGLES:
            with self.subTest(ingles=ingles):
                self.assertNotIn(ingles, conteudo)

    def test_pagina_mostra_as_dicas_em_portugues(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "Sua senha precisa ter pelo menos 8 caracteres.")
        self.assertContains(resposta, "Digite a mesma senha novamente, para confirmação.")
        self.assertSemIngles(resposta)

    def test_campos_vazios(self):
        resposta = self.enviar(atual="", nova="")
        self.assertContains(resposta, "Este campo é obrigatório.")
        self.assertSemIngles(resposta)

    def test_senha_atual_errada(self):
        resposta = self.enviar(atual="errada")
        self.assertContains(resposta, "Sua senha atual está incorreta.")
        self.assertSemIngles(resposta)

    def test_confirmacao_diferente(self):
        resposta = self.enviar(confirmacao="Outra123!xyz")
        self.assertContains(resposta, "As duas senhas digitadas não são iguais.")
        self.assertSemIngles(resposta)

    def test_senha_fraca_mostra_os_erros_em_portugues(self):
        resposta = self.enviar(nova="maria")
        self.assertContains(resposta, "muito curta")
        self.assertContains(resposta, "muito parecida com o seu nome")
        self.assertSemIngles(resposta)

    def test_senha_parecida_com_o_email(self):
        resposta = self.enviar(nova="Maria@Clinica1")
        self.assertContains(resposta, "muito parecida com o seu e-mail")
        self.assertSemIngles(resposta)

    def test_troca_valida_continua_funcionando(self):
        resposta = self.enviar()
        self.assertEqual(resposta.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NOVA))
