from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, models, transaction
from django.db.models import ProtectedError
from django.forms import modelform_factory
from django.test import SimpleTestCase, TestCase

from .models import Clinica, Membro, TenantModel
from .tenancy import (
    ClinicaIncorreta,
    SemClinicaAtual,
    clinica_atual,
    get_clinica_atual,
)
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


class MembroTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("maria", password="x")
        cls.vida = Clinica.objects.create(
            nome="Vida", cnpj=CNPJ_VALIDO, slug="vida"
        )
        cls.sol = Clinica.objects.create(
            nome="Sol", cnpj=OUTRO_CNPJ_VALIDO, slug="sol"
        )
        cls.recepcao = Group.objects.create(name="Recepção")
        cls.admin = Group.objects.create(name="Administração")

    def test_str(self):
        membro = Membro.objects.create(
            user=self.user, clinica=self.vida, grupo=self.recepcao
        )
        self.assertEqual(str(membro), "maria @ Vida (Recepção)")
        self.assertTrue(membro.ativo)

    def test_usuario_pode_ter_papeis_diferentes_em_clinicas_diferentes(self):
        Membro.objects.create(user=self.user, clinica=self.vida, grupo=self.admin)
        Membro.objects.create(user=self.user, clinica=self.sol, grupo=self.recepcao)
        papeis = {m.clinica.slug: m.grupo.name for m in self.user.membros.all()}
        self.assertEqual(papeis, {"vida": "Administração", "sol": "Recepção"})

    def test_um_vinculo_por_usuario_e_clinica(self):
        Membro.objects.create(user=self.user, clinica=self.vida, grupo=self.admin)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Membro.objects.create(
                user=self.user, clinica=self.vida, grupo=self.recepcao
            )

    def test_grupo_em_uso_nao_pode_ser_apagado(self):
        Membro.objects.create(user=self.user, clinica=self.vida, grupo=self.admin)
        with self.assertRaises(ProtectedError):
            self.admin.delete()

    def test_apagar_usuario_ou_clinica_remove_o_vinculo(self):
        Membro.objects.create(user=self.user, clinica=self.vida, grupo=self.admin)
        self.user.delete()
        self.assertEqual(Membro.objects.count(), 0)


class Nota(TenantModel):
    """Modelo só para os testes: representa qualquer tabela de uma clínica."""

    texto = models.CharField(max_length=50)

    class Meta:
        app_label = "clinicas"


class TenantModelTests(TestCase):
    @classmethod
    def setUpClass(cls):
        # A tabela do modelo de teste não vem de migração; criamos fora da
        # transação do TestCase (o schema editor do SQLite exige isso).
        with connection.schema_editor() as editor:
            editor.create_model(Nota)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connection.schema_editor() as editor:
            editor.delete_model(Nota)

    @classmethod
    def setUpTestData(cls):
        cls.vida = Clinica.objects.create(
            nome="Vida", cnpj=CNPJ_VALIDO, slug="vida"
        )
        cls.sol = Clinica.objects.create(
            nome="Sol", cnpj=OUTRO_CNPJ_VALIDO, slug="sol"
        )
        with clinica_atual(cls.vida):
            cls.nota_vida = Nota.objects.create(texto="da Vida")
        with clinica_atual(cls.sol):
            cls.nota_sol = Nota.objects.create(texto="do Sol")

    def test_sem_clinica_atual_nao_devolve_nada(self):
        self.assertIsNone(get_clinica_atual())
        self.assertEqual(Nota.objects.count(), 0)
        self.assertEqual(Nota.todas.count(), 2)

    def test_cada_clinica_ve_so_os_proprios_dados(self):
        with clinica_atual(self.vida):
            self.assertEqual([n.texto for n in Nota.objects.all()], ["da Vida"])
        with clinica_atual(self.sol):
            self.assertEqual([n.texto for n in Nota.objects.all()], ["do Sol"])

    def test_objeto_de_outra_clinica_nao_e_encontrado(self):
        # É o que vira 404 nas views: acertar o uuid de outra clínica não adianta.
        with clinica_atual(self.vida):
            with self.assertRaises(Nota.DoesNotExist):
                Nota.objects.get(uuid=self.nota_sol.uuid)
            self.assertFalse(Nota.objects.filter(pk=self.nota_sol.pk).exists())

    def test_manager_padrao_e_o_filtrado(self):
        # ModelForms e relações reversas usam _default_manager.
        with clinica_atual(self.vida):
            self.assertEqual(Nota._default_manager.count(), 1)

    def test_clinica_atual_e_restaurada_ao_sair_do_bloco(self):
        with clinica_atual(self.vida):
            with clinica_atual(self.sol):
                self.assertEqual(get_clinica_atual(), self.sol)
            self.assertEqual(get_clinica_atual(), self.vida)
        self.assertIsNone(get_clinica_atual())

    def test_clinica_atual_e_restaurada_mesmo_com_erro(self):
        with self.assertRaises(RuntimeError):
            with clinica_atual(self.vida):
                raise RuntimeError("falha")
        self.assertIsNone(get_clinica_atual())

    def test_save_preenche_a_clinica_atual(self):
        with clinica_atual(self.vida):
            nota = Nota(texto="nova")
            nota.save()
        self.assertEqual(nota.clinica, self.vida)

    def test_save_sem_clinica_atual_falha(self):
        with self.assertRaises(SemClinicaAtual):
            Nota(texto="solta").save()

    def test_nao_grava_dado_de_outra_clinica(self):
        with clinica_atual(self.vida):
            with self.assertRaises(ClinicaIncorreta):
                Nota(texto="invasão", clinica=self.sol).save()
            # nem alterando um objeto que veio de outra clínica
            with self.assertRaises(ClinicaIncorreta):
                self.nota_sol.save()
        self.assertEqual(Nota.todas.filter(texto="invasão").count(), 0)

    def test_bulk_create_preenche_a_clinica_atual(self):
        with clinica_atual(self.sol):
            Nota.objects.bulk_create([Nota(texto="a"), Nota(texto="b")])
        self.assertEqual(Nota.todas.filter(clinica=self.sol).count(), 3)
        self.assertEqual(Nota.todas.filter(clinica=self.vida).count(), 1)

    def test_campo_clinica_nao_aparece_em_formularios(self):
        Formulario = modelform_factory(Nota, fields="__all__")
        self.assertNotIn("clinica", Formulario.base_fields)

    def test_clinica_com_dados_nao_pode_ser_apagada(self):
        with self.assertRaises(ProtectedError):
            self.vida.delete()
