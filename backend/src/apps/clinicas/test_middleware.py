from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from .middleware import SESSION_KEY, ClinicaAtualMiddleware
from .models import Clinica, Membro
from .tenancy import get_clinica_atual

CNPJ_VALIDO = "11222333000181"
OUTRO_CNPJ_VALIDO = "11444777000161"


class ClinicaAtualMiddlewareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.maria = User.objects.create_user("maria", password="x")
        cls.joao = User.objects.create_user("joao", password="x")
        cls.vida = Clinica.objects.create(nome="Vida", cnpj=CNPJ_VALIDO, slug="vida")
        cls.sol = Clinica.objects.create(
            nome="Sol", cnpj=OUTRO_CNPJ_VALIDO, slug="sol"
        )
        cls.grupo = Group.objects.create(name="Recepção")

    def executar(self, user=None, session=None):
        """Roda o middleware e devolve (request, clínica vista pela view)."""
        visto = {}

        def view(request):
            visto["clinica"] = get_clinica_atual()
            return HttpResponse("ok")

        request = RequestFactory().get("/")
        request.user = user if user is not None else AnonymousUser()
        request.session = {} if session is None else session
        ClinicaAtualMiddleware(view)(request)
        return request, visto["clinica"]

    def vincular(self, user, clinica, **kwargs):
        return Membro.objects.create(
            user=user, clinica=clinica, grupo=self.grupo, **kwargs
        )

    def test_anonimo_nao_tem_clinica(self):
        request, clinica = self.executar()
        self.assertIsNone(clinica)
        self.assertIsNone(request.clinica)
        self.assertIsNone(request.membro)

    def test_usuario_sem_vinculo_nao_tem_clinica(self):
        _, clinica = self.executar(self.maria)
        self.assertIsNone(clinica)

    def test_vinculo_unico_define_a_clinica_e_guarda_na_sessao(self):
        membro = self.vincular(self.maria, self.vida)
        session = {}
        request, clinica = self.executar(self.maria, session)
        self.assertEqual(clinica, self.vida)
        self.assertEqual(request.clinica, self.vida)
        self.assertEqual(request.membro, membro)
        self.assertEqual(session[SESSION_KEY], str(self.vida.uuid))

    def test_varios_vinculos_sem_escolha_nao_tem_clinica(self):
        self.vincular(self.maria, self.vida)
        self.vincular(self.maria, self.sol)
        _, clinica = self.executar(self.maria)
        self.assertIsNone(clinica)

    def test_varios_vinculos_usa_a_clinica_da_sessao(self):
        self.vincular(self.maria, self.vida)
        self.vincular(self.maria, self.sol)
        _, clinica = self.executar(
            self.maria, {SESSION_KEY: str(self.sol.uuid)}
        )
        self.assertEqual(clinica, self.sol)

    def test_sessao_com_clinica_sem_vinculo_e_ignorada_e_limpa(self):
        # Maria só é da Vida; a sessão aponta para a Sol (ex.: adulterada).
        self.vincular(self.maria, self.vida)
        session = {SESSION_KEY: str(self.sol.uuid)}
        _, clinica = self.executar(self.maria, session)
        self.assertEqual(clinica, self.vida)
        self.assertEqual(session[SESSION_KEY], str(self.vida.uuid))

    def test_sessao_com_valor_invalido_nao_quebra(self):
        self.vincular(self.maria, self.vida)
        self.vincular(self.maria, self.sol)
        session = {SESSION_KEY: "isto-nao-e-uuid"}
        _, clinica = self.executar(self.maria, session)
        self.assertIsNone(clinica)
        self.assertNotIn(SESSION_KEY, session)

    def test_vinculo_inativo_nao_da_acesso(self):
        self.vincular(self.maria, self.vida, ativo=False)
        _, clinica = self.executar(
            self.maria, {SESSION_KEY: str(self.vida.uuid)}
        )
        self.assertIsNone(clinica)

    def test_clinica_suspensa_nao_da_acesso(self):
        self.vincular(self.maria, self.vida)
        Clinica.objects.filter(pk=self.vida.pk).update(ativa=False)
        _, clinica = self.executar(self.maria)
        self.assertIsNone(clinica)

    def test_vinculos_de_outro_usuario_nao_vazam(self):
        self.vincular(self.joao, self.sol)
        _, clinica = self.executar(self.maria)
        self.assertIsNone(clinica)

    def test_clinica_atual_e_restaurada_apos_a_requisicao(self):
        self.vincular(self.maria, self.vida)
        self.executar(self.maria)
        self.assertIsNone(get_clinica_atual())

    def test_clinica_atual_e_restaurada_mesmo_com_erro_na_view(self):
        self.vincular(self.maria, self.vida)

        def view(request):
            raise RuntimeError("falha")

        request = RequestFactory().get("/")
        request.user = self.maria
        request.session = {}
        with self.assertRaises(RuntimeError):
            ClinicaAtualMiddleware(view)(request)
        self.assertIsNone(get_clinica_atual())
