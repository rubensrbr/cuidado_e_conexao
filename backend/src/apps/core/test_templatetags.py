from decimal import Decimal

from django.test import SimpleTestCase

from core.templatetags.core_extras import brl


class BrlFilterTests(SimpleTestCase):
    def test_formata_no_padrao_brasileiro(self):
        casos = [
            (Decimal("100.00"), "R$ 100,00"),
            (Decimal("1234.5"), "R$ 1.234,50"),
            (1234567.891, "R$ 1.234.567,89"),
            ("0", "R$ 0,00"),
        ]
        for valor, esperado in casos:
            with self.subTest(valor=valor):
                self.assertEqual(brl(valor), esperado)

    def test_vazio_ou_invalido_vira_traco(self):
        for valor in (None, "", "abc"):
            with self.subTest(valor=valor):
                self.assertEqual(brl(valor), "-")
