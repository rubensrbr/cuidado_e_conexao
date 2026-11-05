# ruff: noqa: E402
from unittest import SkipTest

from django.apps import apps

if not apps.is_installed("faturamentos"):
    raise SkipTest("app 'faturamentos' não está em INSTALLED_APPS neste release")

from datetime import date, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError, RestrictedError
from django.test import TestCase
from django.utils import timezone

from clinicas.models import Clinica
from clinicas.tenancy import clinica_atual
from consultas.models import Consulta
from pacientes.forms import PacienteForm
from pacientes.models import Paciente
from profissionais.models import Profissional, TipoProfissional

from .forms import FaturamentoForm
from .models import Faturamento, Pacote, SessaoPacote

CNPJ_VIDA = "11222333000181"
CNPJ_SOL = "11444777000161"


def criar_paciente(nome, **kwargs):
    return Paciente.objects.create(
        primeiro_nome=nome,
        sobrenome="Silva",
        data_nascimento=date(2000, 1, 1),
        genero="outro",
        **kwargs,
    )


def criar_profissional(nome="Dra"):
    tipo, _ = TipoProfissional.objects.get_or_create(descricao="Psicólogo")
    return Profissional.objects.create(
        primeiro_nome=nome,
        sobrenome="Souza",
        email=f"{nome.lower()}@example.com",
        tipo_profissional=tipo,
        numero_registro="1",
        valor_hora=Decimal("100.00"),
    )


def criar_consulta(paciente, profissional, dia=3, status="agendada"):
    return Consulta.objects.create(
        paciente=paciente,
        profissional=profissional,
        data_consulta=date(2026, 11, dia),
        hora_inicio=time(9),
        hora_fim=time(10),
        tipo_consulta="retorno",
        status=status,
    )


def criar_pacote(paciente, **kwargs):
    dados = {
        "paciente": paciente,
        "quantidade_sessoes": 4,
        "valor_total": Decimal("400.00"),
    }
    dados.update(kwargs)
    return Pacote.objects.create(**dados)


def dados_form(paciente, **kwargs):
    dados = {
        "paciente": paciente.pk,
        "data_servico": "2026-11-03",
        "valor_cobrado": "150.00",
        "valor_pago": "0",
        "status_pagamento": "pendente",
    }
    dados.update(kwargs)
    return dados


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vida = Clinica.objects.create(nome="Vida", cnpj=CNPJ_VIDA, slug="vida")
        cls.sol = Clinica.objects.create(nome="Sol", cnpj=CNPJ_SOL, slug="sol")
        with clinica_atual(cls.vida):
            cls.ana = criar_paciente("Ana")
            cls.bia = criar_paciente("Bia")
            cls.dra = criar_profissional("Dra")
            cls.dr = criar_profissional("Dr")
        with clinica_atual(cls.sol):
            cls.beto = criar_paciente("Beto")

    def setUp(self):
        # Cada teste roda como a clínica Vida, salvo quando troca de clínica.
        contexto = clinica_atual(self.vida)
        contexto.__enter__()
        self.addCleanup(contexto.__exit__, None, None, None)


class ProBonoModelTests(Base):
    def test_pro_bono_sem_valores_e_valido(self):
        fat = Faturamento(
            paciente=self.ana,
            data_servico=date(2026, 11, 3),
            valor_cobrado=Decimal("0"),
            pro_bono=True,
        )
        fat.full_clean()  # não levanta

    def test_pro_bono_com_valor_cobrado_e_recusado(self):
        fat = Faturamento(
            paciente=self.ana,
            data_servico=date(2026, 11, 3),
            valor_cobrado=Decimal("150"),
            pro_bono=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            fat.full_clean()
        self.assertIn("valor_cobrado", ctx.exception.message_dict)

    def test_pro_bono_com_valor_pago_e_recusado(self):
        fat = Faturamento(
            paciente=self.ana,
            data_servico=date(2026, 11, 3),
            valor_cobrado=Decimal("0"),
            valor_pago=Decimal("10"),
            pro_bono=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            fat.full_clean()
        self.assertIn("valor_pago", ctx.exception.message_dict)

    def test_pro_bono_nao_pode_ter_pacote(self):
        pacote = criar_pacote(self.ana)
        fat = Faturamento(
            paciente=self.ana,
            pacote=pacote,
            data_servico=date(2026, 11, 3),
            valor_cobrado=Decimal("0"),
            pro_bono=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            fat.full_clean()
        self.assertIn("pacote", ctx.exception.message_dict)


class PacoteModelTests(Base):
    def test_cobranca_do_pacote_nao_precisa_de_consulta(self):
        pacote = criar_pacote(self.ana)
        fat = Faturamento(
            paciente=self.ana,
            pacote=pacote,
            data_servico=date(2026, 11, 3),
            valor_cobrado=pacote.valor_total,
        )
        fat.full_clean()
        fat.save()
        self.assertIsNone(fat.consulta)
        self.assertEqual(list(pacote.faturamentos.all()), [fat])

    def test_cobranca_com_pacote_de_outro_paciente_e_recusada(self):
        pacote = criar_pacote(self.bia)
        fat = Faturamento(
            paciente=self.ana,
            pacote=pacote,
            data_servico=date(2026, 11, 3),
            valor_cobrado=Decimal("400"),
        )
        with self.assertRaises(ValidationError) as ctx:
            fat.full_clean()
        self.assertIn("pacote", ctx.exception.message_dict)

    def test_validade_nao_pode_ser_anterior_a_compra(self):
        pacote = Pacote(
            paciente=self.ana,
            quantidade_sessoes=4,
            valor_total=Decimal("400"),
            data_compra=date(2026, 11, 3),
            validade=date(2026, 11, 2),
        )
        with self.assertRaises(ValidationError) as ctx:
            pacote.full_clean()
        self.assertIn("validade", ctx.exception.message_dict)

    def test_quantidade_e_valor_precisam_ser_positivos(self):
        pacote = Pacote(
            paciente=self.ana, quantidade_sessoes=0, valor_total=Decimal("0")
        )
        with self.assertRaises(ValidationError) as ctx:
            pacote.full_clean()
        self.assertIn("quantidade_sessoes", ctx.exception.message_dict)
        self.assertIn("valor_total", ctx.exception.message_dict)

    def test_saldo_so_desconta_sessoes_realizadas(self):
        pacote = criar_pacote(self.ana)
        for dia, status in [
            (3, "realizada"),
            (4, "agendada"),
            (5, "cancelada"),
            (6, "realizada"),
        ]:
            SessaoPacote.objects.create(
                pacote=pacote, consulta=criar_consulta(self.ana, self.dra, dia, status)
            )
        self.assertEqual(pacote.sessoes_usadas, 2)
        self.assertEqual(pacote.saldo, 2)

    def test_esta_vencido(self):
        ontem = timezone.localdate() - timedelta(days=1)
        self.assertTrue(criar_pacote(self.ana, validade=ontem).esta_vencido)
        self.assertFalse(criar_pacote(self.ana).esta_vencido)

    def test_nao_apaga_pacote_com_cobranca_nem_paciente_com_historico(self):
        pacote = criar_pacote(self.ana)
        Faturamento.objects.create(
            paciente=self.ana,
            pacote=pacote,
            data_servico=date(2026, 11, 3),
            valor_cobrado=Decimal("400"),
        )
        with self.assertRaises(RestrictedError):
            pacote.delete()
        with self.assertRaises(ProtectedError):
            self.ana.delete()
        self.assertTrue(Paciente.objects.filter(pk=self.ana.pk).exists())
        self.assertTrue(Pacote.objects.filter(pk=pacote.pk).exists())
        self.assertEqual(Faturamento.objects.count(), 1)

    def test_nao_apaga_paciente_so_com_pacote_ou_so_com_faturamento(self):
        criar_pacote(self.ana)
        Faturamento.objects.create(
            paciente=self.bia,
            data_servico=date(2026, 11, 3),
            valor_cobrado=Decimal("150"),
        )
        for paciente in (self.ana, self.bia):
            with self.assertRaises(ProtectedError):
                paciente.delete()

    def test_apaga_paciente_sem_historico_financeiro(self):
        self.bia.delete()
        self.assertFalse(Paciente.objects.filter(pk=self.bia.pk).exists())


class SessaoPacoteTests(Base):
    def test_vincula_consulta_do_mesmo_paciente(self):
        pacote = criar_pacote(self.ana)
        sessao = SessaoPacote(
            pacote=pacote, consulta=criar_consulta(self.ana, self.dra)
        )
        sessao.full_clean()
        sessao.save()
        self.assertEqual(sessao.consulta.sessao_pacote, sessao)

    def test_consulta_de_outro_paciente_e_recusada(self):
        pacote = criar_pacote(self.ana)
        sessao = SessaoPacote(
            pacote=pacote, consulta=criar_consulta(self.bia, self.dra)
        )
        with self.assertRaises(ValidationError) as ctx:
            sessao.full_clean()
        self.assertIn("consulta", ctx.exception.message_dict)

    def test_pacote_de_um_profissional_recusa_consulta_de_outro(self):
        pacote = criar_pacote(self.ana, profissional=self.dra)
        sessao = SessaoPacote(
            pacote=pacote, consulta=criar_consulta(self.ana, self.dr)
        )
        with self.assertRaises(ValidationError) as ctx:
            sessao.full_clean()
        self.assertIn("consulta", ctx.exception.message_dict)

    def test_nao_passa_da_quantidade_do_pacote(self):
        pacote = criar_pacote(self.ana, quantidade_sessoes=2)
        for dia in (3, 4):
            SessaoPacote.objects.create(
                pacote=pacote, consulta=criar_consulta(self.ana, self.dra, dia)
            )
        extra = SessaoPacote(
            pacote=pacote, consulta=criar_consulta(self.ana, self.dra, 5)
        )
        with self.assertRaises(ValidationError) as ctx:
            extra.full_clean()
        self.assertIn("pacote", ctx.exception.message_dict)

    def test_consulta_cancelada_libera_a_vaga(self):
        pacote = criar_pacote(self.ana, quantidade_sessoes=1)
        primeira = criar_consulta(self.ana, self.dra, 3)
        SessaoPacote.objects.create(pacote=pacote, consulta=primeira)
        Consulta.objects.filter(pk=primeira.pk).update(status="cancelada")
        nova = SessaoPacote(
            pacote=pacote, consulta=criar_consulta(self.ana, self.dra, 4)
        )
        nova.full_clean()  # não levanta

    def test_pacote_inativo_nao_recebe_novas_sessoes(self):
        pacote = criar_pacote(self.ana, status="cancelado")
        sessao = SessaoPacote(
            pacote=pacote, consulta=criar_consulta(self.ana, self.dra)
        )
        with self.assertRaises(ValidationError) as ctx:
            sessao.full_clean()
        self.assertIn("pacote", ctx.exception.message_dict)

    def test_uma_consulta_so_pode_estar_em_um_pacote(self):
        consulta = criar_consulta(self.ana, self.dra)
        SessaoPacote.objects.create(pacote=criar_pacote(self.ana), consulta=consulta)
        outra = SessaoPacote(pacote=criar_pacote(self.ana), consulta=consulta)
        with self.assertRaises(ValidationError) as ctx:
            outra.full_clean()
        self.assertIn("consulta", ctx.exception.message_dict)


class FaturamentoFormTests(Base):
    def test_pro_bono_com_valores_em_branco_vira_zero_e_pago(self):
        form = FaturamentoForm(
            dados_form(self.ana, pro_bono="on", valor_cobrado="", valor_pago="")
        )
        self.assertTrue(form.is_valid(), form.errors)
        fat = form.save()
        self.assertTrue(fat.pro_bono)
        self.assertEqual(fat.valor_cobrado, Decimal("0"))
        self.assertEqual(fat.valor_pago, Decimal("0"))
        self.assertEqual(fat.status_pagamento, "pago")
        self.assertEqual(fat.valor_pendente, Decimal("0"))

    def test_pro_bono_com_valor_preenchido_e_recusado(self):
        form = FaturamentoForm(dados_form(self.ana, pro_bono="on"))
        self.assertFalse(form.is_valid())
        self.assertIn("valor_cobrado", form.errors)

    def test_paciente_pro_bono_com_valor_em_branco_e_marcado_como_pro_bono(self):
        paciente = criar_paciente("Caio", pro_bono=True)
        form = FaturamentoForm(dados_form(paciente, valor_cobrado="", valor_pago=""))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save().pro_bono)

    def test_paciente_pro_bono_pode_ter_cobranca_com_valor(self):
        paciente = criar_paciente("Caio", pro_bono=True)
        form = FaturamentoForm(dados_form(paciente))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.save().pro_bono)

    def test_valor_em_branco_continua_obrigatorio_para_paciente_comum(self):
        form = FaturamentoForm(dados_form(self.ana, valor_cobrado=""))
        self.assertFalse(form.is_valid())
        self.assertIn("valor_cobrado", form.errors)

    def test_valor_zero_continua_recusado_sem_pro_bono(self):
        form = FaturamentoForm(dados_form(self.ana, valor_cobrado="0"))
        self.assertFalse(form.is_valid())
        self.assertIn("valor_cobrado", form.errors)

    def test_cobranca_de_pacote_pelo_formulario(self):
        pacote = criar_pacote(self.ana)
        form = FaturamentoForm(
            dados_form(self.ana, pacote=pacote.pk, valor_cobrado="400.00")
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().pacote, pacote)

    def test_pacote_de_outro_paciente_e_recusado_no_formulario(self):
        pacote = criar_pacote(self.bia)
        form = FaturamentoForm(
            dados_form(self.ana, pacote=pacote.pk, valor_cobrado="400.00")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("pacote", form.errors)

    def test_lista_de_pacotes_so_tem_ativos_da_clinica_atual(self):
        ativo = criar_pacote(self.ana)
        criar_pacote(self.ana, status="concluido")
        with clinica_atual(self.sol):
            criar_pacote(self.beto)
        form = FaturamentoForm()
        self.assertEqual(list(form.fields["pacote"].queryset), [ativo])

    def test_edicao_mantem_pacote_ja_vinculado_mesmo_concluido(self):
        pacote = criar_pacote(self.ana, status="concluido")
        fat = Faturamento.objects.create(
            paciente=self.ana,
            pacote=pacote,
            data_servico=date(2026, 11, 3),
            valor_cobrado=Decimal("400"),
        )
        form = FaturamentoForm(instance=fat)
        self.assertIn(pacote, form.fields["pacote"].queryset)


class PacienteProBonoFormTests(Base):
    def test_formulario_do_paciente_tem_pro_bono(self):
        self.assertIn("pro_bono", PacienteForm().fields)


class OpcoesDoFormularioPorPacienteTests(Base):
    """Consulta e pacote só são oferecidos para o paciente da cobrança."""

    def setUp(self):
        super().setUp()
        self.pacote_ana = criar_pacote(self.ana)
        self.pacote_bia = criar_pacote(self.bia)
        self.pacote_ana_concluido = criar_pacote(self.ana, status="concluido")
        self.consulta_ana = criar_consulta(self.ana, self.dra, dia=3)
        self.consulta_bia = criar_consulta(self.bia, self.dr, dia=4)

    def opcoes(self, form, campo):
        return set(form.fields[campo].queryset)

    def test_com_paciente_escolhido_so_aparecem_as_opcoes_dele(self):
        form = FaturamentoForm(dados_form(self.ana))
        self.assertEqual(self.opcoes(form, "pacote"), {self.pacote_ana})
        self.assertEqual(self.opcoes(form, "consulta"), {self.consulta_ana})

    def test_pacote_de_outro_paciente_e_recusado(self):
        form = FaturamentoForm(dados_form(self.ana, pacote=self.pacote_bia.pk))
        self.assertFalse(form.is_valid())
        self.assertIn("pacote", form.errors)

    def test_consulta_de_outro_paciente_e_recusada(self):
        form = FaturamentoForm(dados_form(self.ana, consulta=self.consulta_bia.pk))
        self.assertFalse(form.is_valid())
        self.assertIn("consulta", form.errors)

    def test_formulario_novo_marca_cada_opcao_com_o_paciente_dono(self):
        html = str(FaturamentoForm()["pacote"])
        self.assertIn(f'value="{self.pacote_ana.pk}" data-paciente="{self.ana.pk}"', html)
        self.assertIn(f'value="{self.pacote_bia.pk}" data-paciente="{self.bia.pk}"', html)
        # Só pacotes ativos: o concluído não aparece.
        self.assertNotIn(f'value="{self.pacote_ana_concluido.pk}"', html)

    def test_edicao_mantem_o_pacote_ja_vinculado_do_proprio_paciente(self):
        fat = Faturamento.objects.create(
            paciente=self.ana,
            pacote=self.pacote_ana_concluido,
            data_servico=date(2026, 11, 3),
            valor_cobrado=Decimal("400"),
            valor_pago=Decimal("400"),
            status_pagamento="pago",
        )
        form = FaturamentoForm(instance=fat)
        self.assertEqual(
            self.opcoes(form, "pacote"), {self.pacote_ana, self.pacote_ana_concluido}
        )
