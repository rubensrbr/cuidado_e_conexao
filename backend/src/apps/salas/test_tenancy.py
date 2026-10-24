# ruff: noqa: E402
from unittest import SkipTest

from django.apps import apps

if not apps.is_installed("salas"):
    raise SkipTest("app 'salas' não está em INSTALLED_APPS neste release")

from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase
from django.urls import reverse

from clinicas.models import Clinica, Membro
from clinicas.tenancy import ClinicaIncorreta, SemClinicaAtual, clinica_atual
from consultas.models import Consulta
from pacientes.models import Paciente
from profissionais.models import Profissional, TipoProfissional

from .forms import AgendaSalaForm, SalaForm
from .models import AgendaSala, Sala
from .views import AgendaSalaListView, SalaListView

CNPJ_VIDA = "11222333000181"
CNPJ_SOL = "11444777000161"


def criar_sala(numero="1", **kwargs):
    return Sala.objects.create(numero_sala=numero, **kwargs)


def criar_consulta(nome):
    paciente = Paciente.objects.create(
        primeiro_nome=nome,
        sobrenome="Silva",
        data_nascimento=date(2000, 1, 1),
        genero="outro",
    )
    tipo, _ = TipoProfissional.objects.get_or_create(descricao="Psicólogo")
    profissional = Profissional.objects.create(
        primeiro_nome="Dra",
        sobrenome=nome,
        email=f"dra.{nome.lower()}@example.com",
        tipo_profissional=tipo,
        numero_registro="1",
        valor_hora=Decimal("100.00"),
    )
    return Consulta.objects.create(
        paciente=paciente,
        profissional=profissional,
        data_consulta=date(2026, 11, 3),
        hora_inicio=time(9),
        hora_fim=time(10),
        tipo_consulta="retorno",
    )


def criar_agendamento(sala, consulta=None, **kwargs):
    dados = {
        "sala": sala,
        "consulta": consulta,
        "data": date(2026, 11, 3),
        "hora_inicio": time(9),
        "hora_fim": time(10),
    }
    dados.update(kwargs)
    return AgendaSala.objects.create(**dados)


class SalasTenantBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vida = Clinica.objects.create(nome="Vida", cnpj=CNPJ_VIDA, slug="vida")
        cls.sol = Clinica.objects.create(nome="Sol", cnpj=CNPJ_SOL, slug="sol")
        # As duas clínicas têm uma "Sala 1": o número só é único por clínica.
        with clinica_atual(cls.vida):
            cls.sala_vida = criar_sala("1", nome="Azul")
            cls.consulta_vida = criar_consulta("Ana")
            cls.agenda_vida = criar_agendamento(cls.sala_vida, cls.consulta_vida)
        with clinica_atual(cls.sol):
            cls.sala_sol = criar_sala("1", nome="Verde")
            cls.consulta_sol = criar_consulta("Beto")
            cls.agenda_sol = criar_agendamento(cls.sala_sol, cls.consulta_sol)


class SalasTenantModelTests(SalasTenantBase):
    def test_registros_recebem_a_clinica_atual(self):
        self.assertEqual(self.sala_vida.clinica, self.vida)
        self.assertEqual(self.agenda_vida.clinica, self.vida)
        self.assertEqual(self.sala_sol.clinica, self.sol)
        self.assertEqual(self.agenda_sol.clinica, self.sol)

    def test_cada_clinica_ve_so_o_proprio(self):
        with clinica_atual(self.vida):
            self.assertEqual(list(Sala.objects.all()), [self.sala_vida])
            self.assertEqual(list(AgendaSala.objects.all()), [self.agenda_vida])
            self.assertEqual(list(self.sala_vida.agendamentos.all()), [self.agenda_vida])
            self.assertEqual(
                list(self.consulta_vida.sala_agendada.all()), [self.agenda_vida]
            )
        with clinica_atual(self.sol):
            self.assertEqual(list(Sala.objects.all()), [self.sala_sol])
            self.assertEqual(list(AgendaSala.objects.all()), [self.agenda_sol])

    def test_sem_clinica_atual_nao_ve_nem_grava(self):
        self.assertEqual(Sala.objects.count(), 0)
        self.assertEqual(AgendaSala.objects.count(), 0)
        with self.assertRaises(SemClinicaAtual):
            criar_sala("9")

    def test_nao_altera_registro_de_outra_clinica(self):
        with clinica_atual(self.vida):
            with self.assertRaises(ClinicaIncorreta):
                self.sala_sol.save()
            with self.assertRaises(ClinicaIncorreta):
                self.agenda_sol.save()

    def test_numero_repetido_na_mesma_clinica_e_barrado_no_banco(self):
        with clinica_atual(self.vida):
            with self.assertRaises(IntegrityError), transaction.atomic():
                criar_sala("1")

    def test_mesmo_numero_em_clinicas_diferentes_e_permitido(self):
        self.assertEqual(Sala.todas.filter(numero_sala="1").count(), 2)

    def test_clean_do_agendamento_rejeita_consulta_de_outra_clinica(self):
        self.agenda_vida.consulta = self.consulta_sol
        with self.assertRaises(ValidationError) as erro:
            self.agenda_vida.clean()
        self.assertIn("consulta", erro.exception.message_dict)

    def test_clean_do_agendamento_aceita_mesma_clinica_e_sem_consulta(self):
        self.agenda_vida.clean()
        self.agenda_vida.consulta = None
        self.agenda_vida.clean()


class SalasFormsTenantTests(SalasTenantBase):
    def dados_agenda(self, sala, consulta=None, **kwargs):
        dados = {
            "sala": sala.pk,
            "consulta": consulta.pk if consulta else "",
            "data": "2026-11-10",
            "hora_inicio": "14:00",
            "hora_fim": "15:00",
        }
        dados.update(kwargs)
        return dados

    def dados_sala(self, numero, **kwargs):
        dados = {"numero_sala": numero, "nome": "Nova", "capacidade": 2, "ativa": True}
        dados.update(kwargs)
        return dados

    def test_sala_com_numero_novo_e_aceita_e_nasce_na_clinica_atual(self):
        with clinica_atual(self.vida):
            form = SalaForm(data=self.dados_sala("2"))
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.save().clinica, self.vida)

    def test_numero_repetido_na_mesma_clinica_vira_erro_de_formulario(self):
        with clinica_atual(self.vida):
            form = SalaForm(data=self.dados_sala("1"))
            self.assertFalse(form.is_valid())
            self.assertIn("nesta clínica", str(form.errors))

    def test_numero_igual_ao_de_outra_clinica_e_aceito(self):
        with clinica_atual(self.sol):
            criar_sala("7")
        with clinica_atual(self.vida):
            form = SalaForm(data=self.dados_sala("7"))
            self.assertTrue(form.is_valid(), form.errors)

    def test_editar_a_propria_sala_sem_mudar_numero_e_aceito(self):
        with clinica_atual(self.vida):
            form = SalaForm(
                data=self.dados_sala("1", nome="Renomeada"), instance=self.sala_vida
            )
            self.assertTrue(form.is_valid(), form.errors)

    def test_agendamento_aceita_sala_e_consulta_da_propria_clinica(self):
        with clinica_atual(self.vida):
            form = AgendaSalaForm(
                data=self.dados_agenda(self.sala_vida, self.consulta_vida)
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.save().clinica, self.vida)

    def test_agendamento_rejeita_sala_de_outra_clinica(self):
        with clinica_atual(self.vida):
            form = AgendaSalaForm(data=self.dados_agenda(self.sala_sol))
            self.assertFalse(form.is_valid())
            self.assertIn("sala", form.errors)

    def test_agendamento_rejeita_consulta_de_outra_clinica(self):
        with clinica_atual(self.vida):
            form = AgendaSalaForm(
                data=self.dados_agenda(self.sala_vida, self.consulta_sol)
            )
            self.assertFalse(form.is_valid())
            self.assertIn("consulta", form.errors)

    def test_conflito_de_horario_e_detectado_na_propria_sala(self):
        with clinica_atual(self.vida):
            form = AgendaSalaForm(
                data=self.dados_agenda(
                    self.sala_vida,
                    data="2026-11-03",
                    hora_inicio="09:30",
                    hora_fim="10:30",
                )
            )
            self.assertFalse(form.is_valid())
            self.assertIn("Já existe um agendamento", str(form.non_field_errors()))

    def test_formulario_lista_so_salas_e_consultas_da_clinica(self):
        with clinica_atual(self.vida):
            form = AgendaSalaForm()
            self.assertEqual(list(form.fields["sala"].queryset), [self.sala_vida])
            self.assertEqual(
                list(form.fields["consulta"].queryset), [self.consulta_vida]
            )


class SalasViewsTenantTests(SalasTenantBase):
    # O app ainda não tem templates, então só testamos o que não renderiza
    # página: o queryset das listagens, os 404 e os POSTs que redirecionam.
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.maria = get_user_model().objects.create_user("maria", password="x")
        grupo = Group.objects.create(name="Recepção")
        Membro.objects.create(user=cls.maria, clinica=cls.vida, grupo=grupo)

    def setUp(self):
        self.client.force_login(self.maria)

    def queryset(self, view_class, clinica):
        view = view_class()
        view.setup(RequestFactory().get("/"))
        with clinica_atual(clinica):
            return list(view.get_queryset())

    def test_listagens_mostram_so_a_clinica_atual(self):
        self.assertEqual(self.queryset(SalaListView, self.vida), [self.sala_vida])
        self.assertEqual(self.queryset(SalaListView, self.sol), [self.sala_sol])
        self.assertEqual(
            self.queryset(AgendaSalaListView, self.vida), [self.agenda_vida]
        )
        self.assertEqual(
            self.queryset(AgendaSalaListView, self.sol), [self.agenda_sol]
        )

    def test_sala_de_outra_clinica_da_404(self):
        url = reverse("salas:sala_update", kwargs={"uuid": self.sala_sol.uuid})
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"numero_sala": "X"}).status_code, 404)

    def test_agendamento_de_outra_clinica_da_404(self):
        url = reverse("salas:agendasala_update", kwargs={"uuid": self.agenda_sol.uuid})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_editar_sala_de_outra_clinica_nao_altera_nada(self):
        url = reverse("salas:sala_update", kwargs={"uuid": self.sala_sol.uuid})
        self.client.post(
            url, {"numero_sala": "99", "nome": "X", "capacidade": 1, "ativa": True}
        )
        self.sala_sol.refresh_from_db()
        self.assertEqual(self.sala_sol.numero_sala, "1")

    def test_nova_sala_nasce_na_clinica_do_usuario(self):
        resposta = self.client.post(
            reverse("salas:sala_create"),
            {"numero_sala": "5", "nome": "Nova", "capacidade": 3, "ativa": True},
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Sala.todas.get(numero_sala="5").clinica, self.vida)

    def test_edita_sala_da_propria_clinica(self):
        resposta = self.client.post(
            reverse("salas:sala_update", kwargs={"uuid": self.sala_vida.uuid}),
            {"numero_sala": "1", "nome": "Renomeada", "capacidade": 4, "ativa": True},
        )
        self.assertEqual(resposta.status_code, 302)
        self.sala_vida.refresh_from_db()
        self.assertEqual(self.sala_vida.nome, "Renomeada")

    def test_novo_agendamento_nasce_na_clinica_do_usuario(self):
        resposta = self.client.post(
            reverse("salas:agendasala_create"),
            {
                "sala": self.sala_vida.pk,
                "consulta": "",
                "data": "2026-11-12",
                "hora_inicio": "10:00",
                "hora_fim": "11:00",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        novo = AgendaSala.todas.get(data=date(2026, 11, 12))
        self.assertEqual(novo.clinica, self.vida)
