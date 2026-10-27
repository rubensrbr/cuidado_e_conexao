from datetime import time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from clinicas.models import Clinica, Membro
from clinicas.helpers_de_teste import grupo_com_todas_as_permissoes
from clinicas.tenancy import clinica_atual

from .forms import ProfissionalForm
from .models import Disponibilidade, Profissional, TipoProfissional

CNPJ_VIDA = "11222333000181"
CNPJ_SOL = "11444777000161"


def criar_profissional(nome, email, **kwargs):
    dados = {
        "primeiro_nome": nome,
        "sobrenome": "Lima",
        "email": email,
        "tipo_profissional": TipoProfissional.objects.first(),
        "numero_registro": "123",
        "valor_hora": Decimal("100.00"),
    }
    dados.update(kwargs)
    return Profissional.objects.create(**dados)


def dados_form(email, tipo):
    return {
        "primeiro_nome": "Novo",
        "sobrenome": "Profissional",
        "email": email,
        "tipo_profissional": tipo.pk,
        "numero_registro": "999",
        "valor_hora": "150.00",
        "ativo": "on",
    }


class ProfissionalTenantModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vida = Clinica.objects.create(nome="Vida", cnpj=CNPJ_VIDA, slug="vida")
        cls.sol = Clinica.objects.create(nome="Sol", cnpj=CNPJ_SOL, slug="sol")
        with clinica_atual(cls.vida):
            cls.ana = criar_profissional("Ana", "ana@example.com")
        with clinica_atual(cls.sol):
            cls.beto = criar_profissional("Beto", "beto@example.com")

    def test_cada_clinica_ve_so_os_proprios_profissionais(self):
        with clinica_atual(self.vida):
            self.assertEqual(list(Profissional.objects.all()), [self.ana])
        with clinica_atual(self.sol):
            self.assertEqual(list(Profissional.objects.all()), [self.beto])
        self.assertEqual(Profissional.objects.count(), 0)  # sem clínica atual

    def test_disponibilidade_segue_a_clinica(self):
        with clinica_atual(self.vida):
            disp = Disponibilidade.objects.create(
                profissional=self.ana,
                dia_semana="segunda",
                hora_inicio=time(9),
                hora_fim=time(12),
            )
            self.assertEqual(disp.clinica, self.vida)
            self.assertEqual(list(self.ana.disponibilidades.all()), [disp])
        with clinica_atual(self.sol):
            self.assertEqual(Disponibilidade.objects.count(), 0)

    def test_mesmo_email_em_clinicas_diferentes_e_permitido(self):
        with clinica_atual(self.sol):
            outro = criar_profissional("Ana", "ana@example.com")
        self.assertEqual(outro.clinica, self.sol)

    def test_mesmo_email_na_mesma_clinica_e_barrado_pelo_banco(self):
        with clinica_atual(self.vida), self.assertRaises(IntegrityError):
            with transaction.atomic():
                criar_profissional("Outra", "ana@example.com")

    def test_formulario_barra_email_repetido_na_mesma_clinica(self):
        tipo = TipoProfissional.objects.first()
        with clinica_atual(self.vida):
            form = ProfissionalForm(data=dados_form("ana@example.com", tipo))
            self.assertFalse(form.is_valid())
            self.assertIn(
                "Já existe um profissional com este e-mail nesta clínica.",
                form.non_field_errors(),
            )

    def test_formulario_aceita_email_que_so_existe_em_outra_clinica(self):
        tipo = TipoProfissional.objects.first()
        with clinica_atual(self.vida):
            form = ProfissionalForm(data=dados_form("beto@example.com", tipo))
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.save().clinica, self.vida)

    def test_formulario_ao_editar_nao_conflita_com_o_proprio_registro(self):
        tipo = TipoProfissional.objects.first()
        with clinica_atual(self.vida):
            form = ProfissionalForm(
                data=dados_form("ana@example.com", tipo), instance=self.ana
            )
            self.assertTrue(form.is_valid(), form.errors)


class ProfissionalViewsTenantTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vida = Clinica.objects.create(nome="Vida", cnpj=CNPJ_VIDA, slug="vida")
        cls.sol = Clinica.objects.create(nome="Sol", cnpj=CNPJ_SOL, slug="sol")
        cls.maria = get_user_model().objects.create_user("maria", password="x")
        grupo = grupo_com_todas_as_permissoes("Recepção")
        Membro.objects.create(user=cls.maria, clinica=cls.vida, grupo=grupo)
        with clinica_atual(cls.vida):
            cls.ana = criar_profissional("Ana", "ana@example.com")
        with clinica_atual(cls.sol):
            cls.beto = criar_profissional("Beto", "beto@example.com")

    def setUp(self):
        self.client.force_login(self.maria)

    def test_lista_mostra_so_profissionais_da_clinica_do_usuario(self):
        resposta = self.client.get(reverse("profissionais:profissional_list"))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(list(resposta.context["profissionais"]), [self.ana])

    def test_profissional_de_outra_clinica_da_404(self):
        for nome in ("profissional_update", "profissional_delete"):
            with self.subTest(view=nome):
                url = reverse(f"profissionais:{nome}", kwargs={"uuid": self.beto.uuid})
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_nao_deleta_profissional_de_outra_clinica(self):
        url = reverse(
            "profissionais:profissional_delete", kwargs={"uuid": self.beto.uuid}
        )
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(Profissional.todas.filter(pk=self.beto.pk).exists())
