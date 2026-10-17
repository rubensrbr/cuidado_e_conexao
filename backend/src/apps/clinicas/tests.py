from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from .models import Clinica
from .validators import validar_cnpj, validar_slug_nao_reservado

CNPJ_VALIDO = "11222333000181"
OUTRO_CNPJ_VALIDO = "11444777000161"


class ValidarCnpjTests(SimpleTestCase):
    def test_aceita_cnpj_valido_com_e_sem_mascara(self):
        validar_cnpj(CNPJ_VALIDO)
        validar_cnpj("11.222.333/0001-81")

    def test_rejeita_digito_verificador_errado(self):
        with self.assertRaises(ValidationError):
            validar_cnpj("11222333000182")

    def test_rejeita_tamanho_errado(self):
        for valor in ("", "123", "112223330001811"):
            with self.subTest(valor=valor), self.assertRaises(ValidationError):
                validar_cnpj(valor)

    def test_rejeita_digitos_repetidos(self):
        with self.assertRaises(ValidationError):
            validar_cnpj("00000000000000")


class ValidarSlugTests(SimpleTestCase):
    def test_rejeita_slug_reservado(self):
        for slug in ("admin", "www", "api"):
            with self.subTest(slug=slug), self.assertRaises(ValidationError):
                validar_slug_nao_reservado(slug)

    def test_aceita_slug_comum(self):
        validar_slug_nao_reservado("clinica-vida")


class ClinicaModelTests(TestCase):
    def criar(self, **kwargs):
        dados = {"nome": "Clínica Vida", "cnpj": CNPJ_VALIDO, "slug": "clinica-vida"}
        dados.update(kwargs)
        return Clinica.objects.create(**dados)

    def test_str_e_padroes(self):
        clinica = self.criar()
        self.assertEqual(str(clinica), "Clínica Vida")
        self.assertTrue(clinica.ativa)
        self.assertIsNotNone(clinica.uuid)

    def test_cnpj_com_mascara_e_salvo_so_com_digitos(self):
        clinica = self.criar(cnpj="11.222.333/0001-81")
        clinica.refresh_from_db()
        self.assertEqual(clinica.cnpj, CNPJ_VALIDO)
        self.assertEqual(clinica.cnpj_formatado, "11.222.333/0001-81")

    def test_cnpj_e_unico(self):
        self.criar()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.criar(nome="Outra", slug="outra")

    def test_slug_e_unico(self):
        self.criar()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.criar(nome="Outra", cnpj=OUTRO_CNPJ_VALIDO)

    def test_full_clean_valida_cnpj_e_slug_reservado(self):
        clinica = Clinica(nome="X", cnpj="123", slug="admin")
        with self.assertRaises(ValidationError) as ctx:
            clinica.full_clean()
        self.assertIn("cnpj", ctx.exception.message_dict)
        self.assertIn("slug", ctx.exception.message_dict)

    def test_full_clean_detecta_cnpj_duplicado_mesmo_com_mascara(self):
        self.criar()
        outra = Clinica(nome="Outra", cnpj="11.222.333/0001-81", slug="outra")
        with self.assertRaises(ValidationError) as ctx:
            outra.full_clean()
        self.assertIn("cnpj", ctx.exception.message_dict)

    def test_full_clean_normaliza_cnpj_com_mascara(self):
        clinica = Clinica(nome="X", cnpj="11.222.333/0001-81", slug="x")
        clinica.full_clean()
        self.assertEqual(clinica.cnpj, CNPJ_VALIDO)

    def test_ordenacao_por_nome(self):
        self.criar(nome="Zeta", slug="zeta")
        self.criar(nome="Alfa", cnpj=OUTRO_CNPJ_VALIDO, slug="alfa")
        self.assertEqual([c.nome for c in Clinica.objects.all()], ["Alfa", "Zeta"])
