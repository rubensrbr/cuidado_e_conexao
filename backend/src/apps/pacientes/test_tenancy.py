from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from clinicas.models import Clinica, Membro
from clinicas.tenancy import ClinicaIncorreta, SemClinicaAtual, clinica_atual

from profissionais.models import Profissional, TipoProfissional

from .forms import ProntuarioForm
from .models import Paciente, Prontuario

CNPJ_VIDA = "11222333000181"
CNPJ_SOL = "11444777000161"


def criar_paciente(nome, **kwargs):
    dados = {
        "primeiro_nome": nome,
        "sobrenome": "Silva",
        "data_nascimento": date(2000, 1, 1),
        "genero": "outro",
    }
    dados.update(kwargs)
    return Paciente.objects.create(**dados)


class PacienteTenantModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vida = Clinica.objects.create(nome="Vida", cnpj=CNPJ_VIDA, slug="vida")
        cls.sol = Clinica.objects.create(nome="Sol", cnpj=CNPJ_SOL, slug="sol")
        with clinica_atual(cls.vida):
            cls.ana = criar_paciente("Ana")
        with clinica_atual(cls.sol):
            cls.beto = criar_paciente("Beto")

    def test_paciente_recebe_a_clinica_atual(self):
        self.assertEqual(self.ana.clinica, self.vida)
        self.assertEqual(self.beto.clinica, self.sol)

    def test_cada_clinica_ve_so_os_proprios_pacientes(self):
        with clinica_atual(self.vida):
            self.assertEqual([p.primeiro_nome for p in Paciente.objects.all()], ["Ana"])
        with clinica_atual(self.sol):
            self.assertEqual([p.primeiro_nome for p in Paciente.objects.all()], ["Beto"])

    def test_sem_clinica_atual_nao_ve_nem_grava(self):
        self.assertEqual(Paciente.objects.count(), 0)
        with self.assertRaises(SemClinicaAtual):
            criar_paciente("Solto")

    def test_nao_altera_paciente_de_outra_clinica(self):
        with clinica_atual(self.vida), self.assertRaises(ClinicaIncorreta):
            self.beto.save()

    def test_prontuario_segue_a_clinica_e_fica_isolado(self):
        profissional = Profissional.objects.create(
            primeiro_nome="Dra",
            sobrenome="Lima",
            email="lima@example.com",
            tipo_profissional=TipoProfissional.objects.first(),
            numero_registro="123",
            valor_hora="100.00",
        )
        with clinica_atual(self.vida):
            prontuario = Prontuario.objects.create(
                paciente=self.ana,
                profissional=profissional,
                data_registro=date(2026, 1, 1),
            )
            self.assertEqual(prontuario.clinica, self.vida)
            self.assertEqual(list(self.ana.prontuarios.all()), [prontuario])
        with clinica_atual(self.sol):
            self.assertEqual(Prontuario.objects.count(), 0)
            with self.assertRaises(Prontuario.DoesNotExist):
                Prontuario.objects.get(uuid=prontuario.uuid)

    def test_formulario_de_prontuario_lista_so_pacientes_da_clinica(self):
        with clinica_atual(self.vida):
            nomes = [p.primeiro_nome for p in ProntuarioForm().fields["paciente"].queryset]
        self.assertEqual(nomes, ["Ana"])


class PacienteViewsTenantTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.vida = Clinica.objects.create(nome="Vida", cnpj=CNPJ_VIDA, slug="vida")
        cls.sol = Clinica.objects.create(nome="Sol", cnpj=CNPJ_SOL, slug="sol")
        grupo = Group.objects.create(name="Recepção")
        cls.maria = User.objects.create_user("maria", password="x")
        Membro.objects.create(user=cls.maria, clinica=cls.vida, grupo=grupo)
        with clinica_atual(cls.vida):
            cls.ana = criar_paciente("Ana")
        with clinica_atual(cls.sol):
            cls.beto = criar_paciente("Beto")

    def setUp(self):
        self.client.force_login(self.maria)

    def test_lista_mostra_so_pacientes_da_clinica_do_usuario(self):
        resposta = self.client.get(reverse("pacientes:paciente_list"))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(list(resposta.context["pacientes"]), [self.ana])

    def test_paciente_da_propria_clinica_abre(self):
        for nome in ("paciente_update", "paciente_delete"):
            with self.subTest(view=nome):
                url = reverse(f"pacientes:{nome}", kwargs={"uuid": self.ana.uuid})
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_paciente_de_outra_clinica_da_404(self):
        for nome in ("paciente_update", "paciente_delete"):
            with self.subTest(view=nome):
                url = reverse(f"pacientes:{nome}", kwargs={"uuid": self.beto.uuid})
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_nao_deleta_paciente_de_outra_clinica(self):
        url = reverse("pacientes:paciente_delete", kwargs={"uuid": self.beto.uuid})
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(Paciente.todas.filter(pk=self.beto.pk).exists())

    def test_novo_paciente_nasce_na_clinica_do_usuario(self):
        resposta = self.client.post(
            reverse("pacientes:paciente_create"),
            {
                "primeiro_nome": "Carla",
                "sobrenome": "Souza",
                "data_nascimento": "1990-05-10",
                "genero": "feminino",
                "telefones-TOTAL_FORMS": "0",
                "telefones-INITIAL_FORMS": "0",
                "telefones-MIN_NUM_FORMS": "0",
                "telefones-MAX_NUM_FORMS": "1000",
            },
        )
        self.assertEqual(resposta.status_code, 302, getattr(resposta, "context", None))
        carla = Paciente.todas.get(primeiro_nome="Carla")
        self.assertEqual(carla.clinica, self.vida)
