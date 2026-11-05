# ruff: noqa: E402
from unittest import SkipTest

from django.apps import apps

if not apps.is_installed("faturamentos"):
    raise SkipTest("app 'faturamentos' não está em INSTALLED_APPS neste release")

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from clinicas.helpers_de_teste import (
    grupo_com_permissoes,
    grupo_com_todas_as_permissoes,
)
from clinicas.models import Membro
from clinicas.papeis import sincronizar_papeis
from clinicas.tenancy import clinica_atual
from consultas.models import Consulta

from .models import Faturamento, Pacote, SessaoPacote
from .test_pro_bono_pacotes import (
    Base,
    criar_consulta,
    criar_pacote,
)


class TelasDePacoteBase(Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        User = get_user_model()
        cls.admin = User.objects.create_user("admin", password="x")
        Membro.objects.create(
            user=cls.admin,
            clinica=cls.vida,
            grupo=grupo_com_todas_as_permissoes("Administração"),
        )
        # Papel sem nenhuma permissão de pacote (como a Recepção padrão).
        cls.recepcao = User.objects.create_user("recepcao", password="x")
        Membro.objects.create(
            user=cls.recepcao,
            clinica=cls.vida,
            grupo=grupo_com_permissoes("Recepção", "pacientes.view_paciente"),
        )

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def url(self, nome, *args):
        return reverse(f"faturamentos:{nome}", args=args)


class PacoteListaTests(TelasDePacoteBase):
    def test_lista_renderiza_com_saldo_e_sessoes_usadas(self):
        pacote = criar_pacote(self.ana, profissional=self.dra)
        for dia, status in ((3, "realizada"), (4, "agendada")):
            SessaoPacote.objects.create(
                pacote=pacote, consulta=criar_consulta(self.ana, self.dra, dia, status)
            )
        resposta = self.client.get(self.url("pacote_list"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Ana Silva")
        self.assertContains(resposta, "1/4")  # só a realizada gasta sessão
        self.assertContains(resposta, "saldo 3")
        self.assertContains(resposta, "R$ 400,00")

    def test_lista_vazia_mostra_mensagem(self):
        resposta = self.client.get(self.url("pacote_list"))
        self.assertContains(resposta, "Nenhum pacote registrado.")

    def test_lista_nao_mostra_pacote_de_outra_clinica(self):
        with clinica_atual(self.sol):
            criar_pacote(self.beto)
        resposta = self.client.get(self.url("pacote_list"))
        self.assertNotContains(resposta, "Beto")

    def test_pacote_ativo_vencido_ganha_selo(self):
        ontem = timezone.localdate() - timedelta(days=1)
        criar_pacote(self.ana, data_compra=ontem - timedelta(days=30), validade=ontem)
        resposta = self.client.get(self.url("pacote_list"))
        self.assertContains(resposta, "Vencido")

    def test_pacote_sem_profissional_mostra_qualquer_profissional(self):
        criar_pacote(self.ana)
        resposta = self.client.get(self.url("pacote_list"))
        self.assertContains(resposta, "Qualquer profissional")


class PacoteFormularioTests(TelasDePacoteBase):
    def dados(self, **kwargs):
        dados = {
            "paciente": self.ana.pk,
            "profissional": "",
            "quantidade_sessoes": "4",
            "valor_total": "400.00",
            "data_compra": "2026-11-03",
            "validade": "",
            "status": "ativo",
        }
        dados.update(kwargs)
        return dados

    def test_formulario_de_criacao_renderiza(self):
        resposta = self.client.get(self.url("pacote_create"))
        self.assertEqual(resposta.status_code, 200)
        for campo in ("paciente", "profissional", "quantidade_sessoes", "valor_total"):
            self.assertContains(resposta, f'name="{campo}"')
        self.assertContains(resposta, "Registrar pacote")

    def test_formulario_de_edicao_renderiza(self):
        pacote = criar_pacote(self.ana)
        resposta = self.client.get(self.url("pacote_update", pacote.uuid))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Salvar alterações")

    def test_criar_pacote_pelo_formulario(self):
        resposta = self.client.post(self.url("pacote_create"), self.dados())
        self.assertRedirects(resposta, self.url("pacote_list"))
        pacote = Pacote.objects.get()
        self.assertEqual(pacote.paciente, self.ana)
        self.assertEqual(pacote.valor_total, Decimal("400.00"))

    def test_erros_do_formulario_aparecem(self):
        resposta = self.client.post(
            self.url("pacote_create"),
            self.dados(data_compra="2026-11-10", validade="2026-11-01"),
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(
            resposta, "A validade não pode ser anterior à data da compra."
        )
        self.assertFalse(Pacote.objects.exists())

    def test_formulario_nao_oferece_paciente_de_outra_clinica(self):
        resposta = self.client.get(self.url("pacote_create"))
        self.assertContains(resposta, "Ana Silva")
        self.assertNotContains(resposta, "Beto Silva")


class PacoteDetalheTests(TelasDePacoteBase):
    def test_detalhe_mostra_sessoes_e_cobrancas(self):
        pacote = criar_pacote(self.ana, profissional=self.dra)
        consulta = criar_consulta(self.ana, self.dra, 5, "realizada")
        SessaoPacote.objects.create(pacote=pacote, consulta=consulta)
        Faturamento.objects.create(
            paciente=self.ana,
            pacote=pacote,
            data_servico=date(2026, 11, 3),
            valor_cobrado=Decimal("400.00"),
        )
        resposta = self.client.get(self.url("pacote_detail", pacote.uuid))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "05/11/2026")
        self.assertContains(resposta, "Realizada")
        self.assertContains(resposta, "R$ 400,00")
        self.assertContains(resposta, "Vincular consulta")

    def test_detalhe_sem_sessoes_nem_cobrancas_mostra_mensagens(self):
        pacote = criar_pacote(self.ana)
        resposta = self.client.get(self.url("pacote_detail", pacote.uuid))
        self.assertContains(resposta, "Nenhuma consulta vinculada a este pacote.")
        self.assertContains(resposta, "Nenhuma cobrança registrada para este pacote.")

    def test_pacote_nao_ativo_nao_oferece_vincular_consulta(self):
        pacote = criar_pacote(self.ana, status="cancelado")
        resposta = self.client.get(self.url("pacote_detail", pacote.uuid))
        self.assertNotContains(resposta, "Vincular consulta")

    def test_pacote_de_outra_clinica_da_404(self):
        with clinica_atual(self.sol):
            outro = criar_pacote(self.beto)
        for nome in ("pacote_detail", "pacote_update", "pacote_delete"):
            with self.subTest(view=nome):
                self.assertEqual(
                    self.client.get(self.url(nome, outro.uuid)).status_code, 404
                )


class PacoteExclusaoTests(TelasDePacoteBase):
    def test_tela_de_exclusao_renderiza(self):
        pacote = criar_pacote(self.ana)
        resposta = self.client.get(self.url("pacote_delete", pacote.uuid))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Sim, excluir pacote")

    def test_excluir_pacote_sem_cobranca(self):
        pacote = criar_pacote(self.ana)
        resposta = self.client.post(self.url("pacote_delete", pacote.uuid))
        self.assertRedirects(resposta, self.url("pacote_list"))
        self.assertFalse(Pacote.objects.filter(pk=pacote.pk).exists())

    def test_tela_avisa_quando_ha_cobranca(self):
        pacote = criar_pacote(self.ana)
        Faturamento.objects.create(
            paciente=self.ana,
            pacote=pacote,
            data_servico=date(2026, 11, 3),
            valor_cobrado=Decimal("400.00"),
        )
        resposta = self.client.get(self.url("pacote_delete", pacote.uuid))
        self.assertContains(resposta, "não pode ser excluído")

    def test_pacote_com_cobranca_nao_e_excluido_e_nao_da_500(self):
        pacote = criar_pacote(self.ana)
        Faturamento.objects.create(
            paciente=self.ana,
            pacote=pacote,
            data_servico=date(2026, 11, 3),
            valor_cobrado=Decimal("400.00"),
        )
        resposta = self.client.post(self.url("pacote_delete", pacote.uuid))
        self.assertRedirects(resposta, self.url("pacote_detail", pacote.uuid))
        mensagens = [str(m) for m in get_messages(resposta.wsgi_request)]
        self.assertTrue(any("cobranças" in m for m in mensagens), mensagens)
        self.assertTrue(Pacote.objects.filter(pk=pacote.pk).exists())


class SessaoPacoteTelasTests(TelasDePacoteBase):
    def test_formulario_oferece_so_consultas_elegiveis(self):
        pacote = criar_pacote(self.ana, profissional=self.dra)
        livre = criar_consulta(self.ana, self.dra, 5)
        criar_consulta(self.ana, self.dra, 6, "cancelada")  # cancelada: fora
        criar_consulta(self.ana, self.dr, 7)  # outro profissional: fora
        criar_consulta(self.bia, self.dra, 8)  # outro paciente: fora
        resposta = self.client.get(self.url("sessaopacote_create", pacote.uuid))
        self.assertEqual(resposta.status_code, 200)
        consultas = resposta.context["form"].fields["consulta"].queryset
        self.assertEqual(list(consultas), [livre])
        self.assertContains(resposta, "Vincular consulta")

    def test_formulario_sem_consultas_disponiveis_avisa(self):
        pacote = criar_pacote(self.ana)
        resposta = self.client.get(self.url("sessaopacote_create", pacote.uuid))
        self.assertContains(resposta, "Não há consultas disponíveis")

    def test_vincular_consulta_ao_pacote(self):
        pacote = criar_pacote(self.ana)
        consulta = criar_consulta(self.ana, self.dra, 5)
        resposta = self.client.post(
            self.url("sessaopacote_create", pacote.uuid),
            {"pacote": pacote.pk, "consulta": consulta.pk},
        )
        self.assertRedirects(resposta, self.url("pacote_detail", pacote.uuid))
        self.assertEqual(SessaoPacote.objects.get().pacote, pacote)

    def test_pacote_de_outra_clinica_da_404_ao_vincular(self):
        with clinica_atual(self.sol):
            outro = criar_pacote(self.beto)
        resposta = self.client.get(self.url("sessaopacote_create", outro.uuid))
        self.assertEqual(resposta.status_code, 404)

    def test_tela_de_desvincular_renderiza(self):
        pacote = criar_pacote(self.ana)
        sessao = SessaoPacote.objects.create(
            pacote=pacote, consulta=criar_consulta(self.ana, self.dra, 5)
        )
        resposta = self.client.get(self.url("sessaopacote_delete", sessao.uuid))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Sim, desvincular consulta")

    def test_desvincular_nao_apaga_a_consulta(self):
        pacote = criar_pacote(self.ana)
        consulta = criar_consulta(self.ana, self.dra, 5)
        sessao = SessaoPacote.objects.create(pacote=pacote, consulta=consulta)
        resposta = self.client.post(self.url("sessaopacote_delete", sessao.uuid))
        self.assertRedirects(resposta, self.url("pacote_detail", pacote.uuid))
        self.assertFalse(SessaoPacote.objects.filter(pk=sessao.pk).exists())
        self.assertTrue(Consulta.objects.filter(pk=consulta.pk).exists())


class PermissoesDePacoteTests(TelasDePacoteBase):
    def test_sem_permissao_as_telas_dao_403(self):
        pacote = criar_pacote(self.ana)
        self.client.force_login(self.recepcao)
        for nome, args in (
            ("pacote_list", ()),
            ("pacote_create", ()),
            ("pacote_detail", (pacote.uuid,)),
            ("pacote_update", (pacote.uuid,)),
            ("pacote_delete", (pacote.uuid,)),
            ("sessaopacote_create", (pacote.uuid,)),
        ):
            with self.subTest(view=nome):
                self.assertEqual(self.client.get(self.url(nome, *args)).status_code, 403)

    def test_papel_administracao_padrao_acessa_pacotes_e_recepcao_nao(self):
        sincronizar_papeis(atualizar=True)
        admin = Group.objects.get(name="Administração")
        recepcao = Group.objects.get(name="Recepção")
        for acao in ("view", "add", "change", "delete"):
            with self.subTest(acao=acao):
                for modelo in ("pacote", "sessaopacote"):
                    codename = f"{acao}_{modelo}"
                    self.assertTrue(admin.permissions.filter(codename=codename).exists())
                    self.assertFalse(
                        recepcao.permissions.filter(
                            content_type__app_label="faturamentos", codename=codename
                        ).exists()
                    )


class ExcluirPacienteComHistoricoFinanceiroTests(TelasDePacoteBase):
    """A view de exclusão do paciente não pode apagar o histórico financeiro."""

    def test_post_recusa_paciente_com_faturamento_e_nao_da_500(self):
        Faturamento.objects.create(
            paciente=self.ana,
            data_servico=date(2026, 11, 3),
            valor_cobrado=Decimal("150"),
        )
        resposta = self.client.post(reverse("pacientes:paciente_delete", args=[self.ana.uuid]))
        self.assertRedirects(resposta, reverse("pacientes:paciente_list"))
        mensagens = [str(m) for m in get_messages(resposta.wsgi_request)]
        self.assertTrue(any("histórico financeiro" in m for m in mensagens), mensagens)
        with clinica_atual(self.vida):
            self.assertTrue(type(self.ana).objects.filter(pk=self.ana.pk).exists())
        self.assertEqual(Faturamento.objects.count(), 1)

    def test_post_recusa_paciente_so_com_pacote(self):
        pacote = criar_pacote(self.ana)
        resposta = self.client.post(reverse("pacientes:paciente_delete", args=[self.ana.uuid]))
        self.assertRedirects(resposta, reverse("pacientes:paciente_list"))
        self.assertTrue(Pacote.objects.filter(pk=pacote.pk).exists())

    def test_post_apaga_paciente_sem_historico_financeiro(self):
        resposta = self.client.post(reverse("pacientes:paciente_delete", args=[self.bia.uuid]))
        self.assertRedirects(resposta, reverse("pacientes:paciente_list"))
        with clinica_atual(self.vida):
            self.assertFalse(type(self.bia).objects.filter(pk=self.bia.pk).exists())

    def test_tela_de_confirmacao_avisa_e_nao_oferece_excluir(self):
        criar_pacote(self.ana)
        url = reverse("pacientes:paciente_delete", args=[self.ana.uuid])
        resposta = self.client.get(url)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "não pode ser excluído")
        self.assertNotContains(resposta, "Sim, excluir paciente")

    def test_tela_de_confirmacao_oferece_excluir_sem_historico(self):
        resposta = self.client.get(reverse("pacientes:paciente_delete", args=[self.bia.uuid]))
        self.assertContains(resposta, "Sim, excluir paciente")
        self.assertNotContains(resposta, "não pode ser excluído")
