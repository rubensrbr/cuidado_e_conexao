from datetime import date, datetime, time, timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from clinicas.models import Clinica, Membro
from clinicas.tenancy import SemClinicaAtual, clinica_atual
from pacientes.models import Paciente
from profissionais.models import Profissional, TipoProfissional

from .forms import ConsultaForm, LembreteForm
from .models import Consulta, Lembrete, ListaEspera

CNPJ_VIDA = "11222333000181"
CNPJ_SOL = "11444777000161"


def criar_paciente(nome):
    return Paciente.objects.create(
        primeiro_nome=nome,
        sobrenome="Silva",
        data_nascimento=date(2000, 1, 1),
        genero="outro",
    )


def criar_profissional(nome):
    tipo, _ = TipoProfissional.objects.get_or_create(descricao="Psicólogo")
    return Profissional.objects.create(
        primeiro_nome=nome,
        sobrenome="Lima",
        email=f"{nome.lower()}@example.com",
        tipo_profissional=tipo,
        numero_registro="1",
        valor_hora=Decimal("100.00"),
    )


def criar_consulta(paciente, profissional, **kwargs):
    dados = {
        "paciente": paciente,
        "profissional": profissional,
        "data_consulta": date(2026, 11, 3),
        "hora_inicio": time(9),
        "hora_fim": time(10),
        "tipo_consulta": "retorno",
    }
    dados.update(kwargs)
    return Consulta.objects.create(**dados)


class ConsultasTenantBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vida = Clinica.objects.create(nome="Vida", cnpj=CNPJ_VIDA, slug="vida")
        cls.sol = Clinica.objects.create(nome="Sol", cnpj=CNPJ_SOL, slug="sol")
        with clinica_atual(cls.vida):
            cls.ana = criar_paciente("Ana")
            cls.dra_vida = criar_profissional("Vida")
            cls.consulta_vida = criar_consulta(cls.ana, cls.dra_vida)
            cls.lembrete_vida = Lembrete.objects.create(
                consulta=cls.consulta_vida,
                tipo_lembrete="email",
                data_hora_envio=datetime(2026, 11, 2, 9, tzinfo=timezone.utc),
            )
            cls.espera_vida = ListaEspera.objects.create(paciente=cls.ana)
        with clinica_atual(cls.sol):
            cls.beto = criar_paciente("Beto")
            cls.dra_sol = criar_profissional("Sol")
            cls.consulta_sol = criar_consulta(cls.beto, cls.dra_sol)
            cls.lembrete_sol = Lembrete.objects.create(
                consulta=cls.consulta_sol,
                tipo_lembrete="email",
                data_hora_envio=datetime(2026, 11, 2, 9, tzinfo=timezone.utc),
            )
            cls.espera_sol = ListaEspera.objects.create(paciente=cls.beto)


class ConsultasTenantModelTests(ConsultasTenantBase):
    def test_registros_recebem_a_clinica_atual(self):
        for objeto in (self.consulta_vida, self.lembrete_vida, self.espera_vida):
            self.assertEqual(objeto.clinica, self.vida)
        for objeto in (self.consulta_sol, self.lembrete_sol, self.espera_sol):
            self.assertEqual(objeto.clinica, self.sol)

    def test_cada_clinica_ve_so_o_proprio(self):
        with clinica_atual(self.vida):
            self.assertEqual(list(Consulta.objects.all()), [self.consulta_vida])
            self.assertEqual(list(Lembrete.objects.all()), [self.lembrete_vida])
            self.assertEqual(list(ListaEspera.objects.all()), [self.espera_vida])
            self.assertEqual(list(self.ana.consultas.all()), [self.consulta_vida])
        with clinica_atual(self.sol):
            self.assertEqual(list(Consulta.objects.all()), [self.consulta_sol])

    def test_sem_clinica_atual_nao_ve_nem_grava(self):
        self.assertEqual(Consulta.objects.count(), 0)
        self.assertEqual(Lembrete.objects.count(), 0)
        self.assertEqual(ListaEspera.objects.count(), 0)
        with self.assertRaises(SemClinicaAtual):
            ListaEspera.objects.create(paciente=self.ana)


class ConsultasFormsTenantTests(ConsultasTenantBase):
    def dados_consulta(self, paciente, profissional, **kwargs):
        dados = {
            "paciente": paciente.pk,
            "profissional": profissional.pk,
            "data_consulta": "2026-11-10",
            "hora_inicio": "14:00",
            "hora_fim": "15:00",
            "tipo_consulta": "retorno",
            "status": "agendada",
        }
        dados.update(kwargs)
        return dados

    def test_formulario_aceita_paciente_e_profissional_da_propria_clinica(self):
        with clinica_atual(self.vida):
            form = ConsultaForm(data=self.dados_consulta(self.ana, self.dra_vida))
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.save().clinica, self.vida)

    def test_formulario_rejeita_paciente_de_outra_clinica(self):
        with clinica_atual(self.vida):
            form = ConsultaForm(data=self.dados_consulta(self.beto, self.dra_vida))
            self.assertFalse(form.is_valid())
            self.assertIn("paciente", form.errors)

    def test_formulario_rejeita_profissional_de_outra_clinica(self):
        with clinica_atual(self.vida):
            form = ConsultaForm(data=self.dados_consulta(self.ana, self.dra_sol))
            self.assertFalse(form.is_valid())
            self.assertIn("profissional", form.errors)

    def test_conflito_de_horario_e_detectado_dentro_da_propria_clinica(self):
        with clinica_atual(self.vida):
            form = ConsultaForm(
                data=self.dados_consulta(
                    self.ana,
                    self.dra_vida,
                    data_consulta="2026-11-03",
                    hora_inicio="09:30",
                    hora_fim="10:30",
                )
            )
            self.assertFalse(form.is_valid())
            self.assertIn("já possui uma consulta", str(form.non_field_errors()))

    def test_formulario_de_lembrete_lista_so_consultas_da_clinica(self):
        with clinica_atual(self.vida):
            consultas = list(LembreteForm().fields["consulta"].queryset)
        self.assertEqual(consultas, [self.consulta_vida])


class ConsultasViewsTenantTests(ConsultasTenantBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.maria = get_user_model().objects.create_user("maria", password="x")
        grupo = Group.objects.create(name="Recepção")
        Membro.objects.create(user=cls.maria, clinica=cls.vida, grupo=grupo)

    def setUp(self):
        self.client.force_login(self.maria)

    def test_listas_mostram_so_a_clinica_do_usuario(self):
        resposta = self.client.get(reverse("consultas:consulta_list"))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(list(resposta.context["consultas"]), [self.consulta_vida])

        resposta = self.client.get(reverse("consultas:lista_espera_list"))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(list(resposta.context["lista_espera"]), [self.espera_vida])

    def test_consulta_da_propria_clinica_abre(self):
        for nome in ("consulta_update", "consulta_delete"):
            with self.subTest(view=nome):
                url = reverse(
                    f"consultas:{nome}", kwargs={"uuid": self.consulta_vida.uuid}
                )
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_consulta_de_outra_clinica_da_404(self):
        for nome in ("consulta_detail", "consulta_update", "consulta_delete"):
            with self.subTest(view=nome):
                url = reverse(
                    f"consultas:{nome}", kwargs={"uuid": self.consulta_sol.uuid}
                )
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_lista_espera_de_outra_clinica_da_404(self):
        for nome in ("lista_espera_update", "lista_espera_delete"):
            with self.subTest(view=nome):
                url = reverse(
                    f"consultas:{nome}", kwargs={"uuid": self.espera_sol.uuid}
                )
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_nao_deleta_registros_de_outra_clinica(self):
        url = reverse("consultas:consulta_delete", kwargs={"uuid": self.consulta_sol.uuid})
        self.assertEqual(self.client.post(url).status_code, 404)
        url = reverse(
            "consultas:lista_espera_delete", kwargs={"uuid": self.espera_sol.uuid}
        )
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(Consulta.todas.filter(pk=self.consulta_sol.pk).exists())
        self.assertTrue(ListaEspera.todas.filter(pk=self.espera_sol.pk).exists())

    def test_nova_consulta_nasce_na_clinica_do_usuario(self):
        resposta = self.client.post(
            reverse("consultas:consulta_create"),
            {
                "paciente": self.ana.pk,
                "profissional": self.dra_vida.pk,
                "data_consulta": "2026-11-12",
                "hora_inicio": "10:00",
                "hora_fim": "11:00",
                "tipo_consulta": "retorno",
                "status": "agendada",
            },
        )
        self.assertEqual(resposta.status_code, 302, getattr(resposta, "context", None))
        nova = Consulta.todas.get(data_consulta=date(2026, 11, 12))
        self.assertEqual(nova.clinica, self.vida)

    def test_nova_consulta_com_paciente_de_outra_clinica_e_recusada(self):
        resposta = self.client.post(
            reverse("consultas:consulta_create"),
            {
                "paciente": self.beto.pk,
                "profissional": self.dra_vida.pk,
                "data_consulta": "2026-11-12",
                "hora_inicio": "10:00",
                "hora_fim": "11:00",
                "tipo_consulta": "retorno",
                "status": "agendada",
            },
        )
        self.assertEqual(resposta.status_code, 200)  # formulário reaberto com erro
        self.assertFalse(Consulta.todas.filter(data_consulta=date(2026, 11, 12)).exists())
