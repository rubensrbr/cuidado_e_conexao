from datetime import date
from decimal import Decimal
from io import StringIO

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import URLPattern, URLResolver, get_resolver, reverse
from django.views.generic import ListView

from pacientes.models import Paciente
from profissionais.models import Profissional, TipoProfissional

from . import papeis
from .helpers_de_teste import grupo_com_permissoes
from .middleware import SESSION_KEY
from .models import Clinica, Membro
from .permissions import (
    PermissaoAdicionar,
    PermissaoAlterar,
    PermissaoDoModeloMixin,
    PermissaoExcluir,
    PermissaoVer,
)
from .tenancy import clinica_atual

User = get_user_model()

CNPJ_VIDA = "11222333000181"
CNPJ_SOL = "11444777000161"

VER_PROF = "profissionais.view_profissional"
ADD_PROF = "profissionais.add_profissional"
CHANGE_PROF = "profissionais.change_profissional"
DELETE_PROF = "profissionais.delete_profissional"


def criar_profissional(nome="Ana", **kwargs):
    dados = {
        "primeiro_nome": nome,
        "sobrenome": "Lima",
        "email": f"{nome.lower()}@example.com",
        "tipo_profissional": TipoProfissional.objects.first(),
        "numero_registro": "123",
        "valor_hora": Decimal("100.00"),
    }
    dados.update(kwargs)
    return Profissional.objects.create(**dados)


class BaseComClinicas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vida = Clinica.objects.create(nome="Vida", cnpj=CNPJ_VIDA, slug="vida")
        cls.sol = Clinica.objects.create(nome="Sol", cnpj=CNPJ_SOL, slug="sol")

    @staticmethod
    def novo_usuario(email="maria@example.com", **kwargs):
        return User.objects.create_user(email, password="x", **kwargs)

    def escolher_clinica(self, clinica):
        sessao = self.client.session
        sessao[SESSION_KEY] = str(clinica.uuid)
        sessao.save()


# --------------------------------------------------------------------------
# 1. O backend: de onde vêm as permissões
# --------------------------------------------------------------------------
class MembroBackendTests(BaseComClinicas):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.leitor = grupo_com_permissoes("Leitor", VER_PROF)
        cls.gestor = grupo_com_permissoes("Gestor", VER_PROF, ADD_PROF, DELETE_PROF)
        cls.maria = cls.novo_usuario()

    def vinculo(self, clinica, grupo, **kwargs):
        return Membro.objects.create(
            user=self.maria, clinica=clinica, grupo=grupo, **kwargs
        )

    def test_permissoes_vem_do_papel_na_clinica_atual(self):
        self.vinculo(self.vida, self.gestor)
        with clinica_atual(self.vida):
            self.assertTrue(self.maria.has_perm(DELETE_PROF))
            self.assertTrue(self.maria.has_perms([VER_PROF, ADD_PROF]))
            # Não está no papel:
            self.assertFalse(self.maria.has_perm(CHANGE_PROF))

    def test_mesma_pessoa_tem_papeis_diferentes_em_clinicas_diferentes(self):
        self.vinculo(self.vida, self.gestor)
        self.vinculo(self.sol, self.leitor)
        # O MESMO objeto de usuário, consultado em duas clínicas (testa o cache).
        with clinica_atual(self.vida):
            self.assertTrue(self.maria.has_perm(DELETE_PROF))
        with clinica_atual(self.sol):
            self.assertTrue(self.maria.has_perm(VER_PROF))
            self.assertFalse(self.maria.has_perm(DELETE_PROF))
        with clinica_atual(self.vida):
            self.assertTrue(self.maria.has_perm(DELETE_PROF))

    def test_sem_clinica_atual_nao_ha_permissao(self):
        self.vinculo(self.vida, self.gestor)
        self.assertFalse(self.maria.has_perm(VER_PROF))  # fora de qualquer clínica
        with clinica_atual(None):
            self.assertFalse(self.maria.has_perm(VER_PROF))

    def test_sem_vinculo_com_a_clinica_atual_nao_ha_permissao(self):
        self.vinculo(self.vida, self.gestor)
        with clinica_atual(self.sol):  # tem papel na Vida, não na Sol
            self.assertFalse(self.maria.has_perm(VER_PROF))

    def test_vinculo_inativo_nao_da_permissao(self):
        self.vinculo(self.vida, self.gestor, ativo=False)
        with clinica_atual(self.vida):
            self.assertFalse(self.maria.has_perm(VER_PROF))

    def test_clinica_suspensa_nao_da_permissao(self):
        self.vinculo(self.vida, self.gestor)
        Clinica.objects.filter(pk=self.vida.pk).update(ativa=False)
        self.vida.refresh_from_db()
        with clinica_atual(self.vida):
            self.assertFalse(self.maria.has_perm(VER_PROF))

    def test_grupos_e_permissoes_soltos_no_usuario_nao_concedem_nada(self):
        # Seria um vazamento: o papel de uma clínica valendo em todas.
        self.maria.groups.add(self.gestor)
        self.maria.user_permissions.add(Permission.objects.get(codename="delete_profissional"))
        self.vinculo(self.sol, self.leitor)
        maria = User.objects.get(pk=self.maria.pk)  # sem cache
        with clinica_atual(self.sol):
            self.assertTrue(maria.has_perm(VER_PROF))
            self.assertFalse(maria.has_perm(DELETE_PROF))
        with clinica_atual(self.vida):
            self.assertFalse(maria.has_perm(VER_PROF))

    def test_superusuario_continua_com_tudo(self):
        admin = User.objects.create_superuser("root@example.com", password="x")
        self.assertTrue(admin.has_perm(DELETE_PROF))  # inclusive sem clínica

    def test_usuario_inativo_nao_tem_permissao(self):
        self.vinculo(self.vida, self.gestor)
        self.maria.is_active = False
        with clinica_atual(self.vida):
            self.assertFalse(self.maria.has_perm(VER_PROF))

    def test_anonimo_nao_tem_permissao(self):
        from django.contrib.auth.models import AnonymousUser

        with clinica_atual(self.vida):
            self.assertFalse(AnonymousUser().has_perm(VER_PROF))

    def test_permissao_por_objeto_nao_existe(self):
        self.vinculo(self.vida, self.gestor)
        with clinica_atual(self.vida):
            self.assertFalse(self.maria.has_perm(VER_PROF, obj=object()))

    def test_has_module_perms_segue_o_papel(self):
        self.vinculo(self.vida, self.leitor)
        with clinica_atual(self.vida):
            self.assertTrue(self.maria.has_module_perms("profissionais"))
            self.assertFalse(self.maria.has_module_perms("pacientes"))

    def test_get_all_permissions_lista_so_as_do_papel(self):
        self.vinculo(self.vida, self.leitor)
        with clinica_atual(self.vida):
            self.assertEqual(self.maria.get_all_permissions(), {VER_PROF})


# --------------------------------------------------------------------------
# 2. As views: o que acontece de fato quando falta permissão
# --------------------------------------------------------------------------
class ViewsExigemPermissaoTests(BaseComClinicas):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.maria = cls.novo_usuario()
        with clinica_atual(cls.vida):
            cls.ana = criar_profissional("Ana")

    def entrar_com(self, *permissoes, clinica=None, nome="Papel"):
        grupo = grupo_com_permissoes(nome, *permissoes)
        Membro.objects.update_or_create(
            user=self.maria, clinica=clinica or self.vida, defaults={"grupo": grupo}
        )
        self.client.force_login(self.maria)

    def url(self, nome, com_uuid=False):
        args = [self.ana.uuid] if com_uuid else []
        return reverse(f"profissionais:{nome}", args=args)

    def test_anonimo_vai_para_o_login_e_nao_recebe_403(self):
        for nome in ("profissional_list", "profissional_create", "profissional_report_pdf"):
            with self.subTest(nome=nome):
                resposta = self.client.get(self.url(nome))
                self.assertEqual(resposta.status_code, 302)
                self.assertTrue(resposta["Location"].startswith("/login/"))

    def test_papel_so_de_leitura_ve_mas_nao_altera(self):
        self.entrar_com(VER_PROF)
        self.assertEqual(self.client.get(self.url("profissional_list")).status_code, 200)
        self.assertEqual(self.client.get(self.url("profissional_report_pdf")).status_code, 200)
        for nome, uuid in [("profissional_create", False), ("profissional_update", True), ("profissional_delete", True)]:
            with self.subTest(nome=nome):
                self.assertEqual(self.client.get(self.url(nome, uuid)).status_code, 403)

    def test_post_tambem_e_barrado_e_nada_muda(self):
        self.entrar_com(VER_PROF)
        resposta = self.client.post(self.url("profissional_delete", True))
        self.assertEqual(resposta.status_code, 403)
        with clinica_atual(self.vida):
            self.assertTrue(Profissional.objects.filter(pk=self.ana.pk).exists())

        # Criar com dados válidos também não passa.
        resposta = self.client.post(self.url("profissional_create"), {"primeiro_nome": "Bia"})
        self.assertEqual(resposta.status_code, 403)
        with clinica_atual(self.vida):
            self.assertFalse(Profissional.objects.filter(primeiro_nome="Bia").exists())

    def test_papel_com_a_permissao_de_excluir_consegue_excluir(self):
        self.entrar_com(VER_PROF, DELETE_PROF)
        resposta = self.client.post(self.url("profissional_delete", True))
        self.assertEqual(resposta.status_code, 302)
        with clinica_atual(self.vida):
            self.assertFalse(Profissional.objects.filter(pk=self.ana.pk).exists())

    def test_cada_acao_exige_a_sua_permissao_e_nao_a_do_vizinho(self):
        # Só "excluir": não abre a lista nem a edição.
        self.entrar_com(DELETE_PROF)
        self.assertEqual(self.client.get(self.url("profissional_list")).status_code, 403)
        self.assertEqual(self.client.get(self.url("profissional_update", True)).status_code, 403)
        self.assertEqual(self.client.get(self.url("profissional_delete", True)).status_code, 200)

    def test_o_mesmo_usuario_tem_papeis_diferentes_por_clinica(self):
        admin = grupo_com_permissoes("Admin", VER_PROF, DELETE_PROF)
        leitor = grupo_com_permissoes("Leitor", VER_PROF)
        Membro.objects.create(user=self.maria, clinica=self.vida, grupo=admin)
        Membro.objects.create(user=self.maria, clinica=self.sol, grupo=leitor)
        self.client.force_login(self.maria)

        self.escolher_clinica(self.sol)
        self.assertEqual(self.client.get(self.url("profissional_delete", True)).status_code, 403)
        self.escolher_clinica(self.vida)
        self.assertEqual(self.client.get(self.url("profissional_delete", True)).status_code, 200)

    def test_usuario_sem_clinica_recebe_403_com_a_explicacao_certa(self):
        self.client.force_login(self.maria)  # sem Membro algum
        resposta = self.client.get(self.url("profissional_list"))
        self.assertEqual(resposta.status_code, 403)
        self.assertContains(resposta, "não está vinculada a uma clínica ativa", status_code=403)

    def test_pagina_403_cita_o_papel_do_usuario(self):
        self.entrar_com(VER_PROF, nome="Leitor da Vida")
        resposta = self.client.get(self.url("profissional_create"))
        self.assertContains(resposta, "Acesso negado", status_code=403)
        self.assertContains(resposta, "Leitor da Vida", status_code=403)

    def test_superusuario_acessa_tudo(self):
        admin = User.objects.create_superuser("root@example.com", password="x")
        self.client.force_login(admin)
        # Sem clínica não há dados (a lista vem vazia), mas a tela abre.
        self.assertEqual(self.client.get(self.url("profissional_create")).status_code, 200)


# --------------------------------------------------------------------------
# 3. A interface só mostra o que o papel permite
# --------------------------------------------------------------------------
class InterfaceRespeitaPermissoesTests(BaseComClinicas):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.maria = cls.novo_usuario()
        with clinica_atual(cls.vida):
            cls.ana = criar_profissional("Ana")

    def abrir_lista(self, *permissoes):
        grupo = grupo_com_permissoes("Papel", *permissoes)
        Membro.objects.create(user=self.maria, clinica=self.vida, grupo=grupo)
        self.client.force_login(self.maria)
        return self.client.get(reverse("profissionais:profissional_list"))

    def test_leitor_nao_ve_novo_editar_nem_excluir_mas_ve_o_pdf(self):
        resposta = self.abrir_lista(VER_PROF)
        self.assertNotContains(resposta, "Novo profissional")
        self.assertNotContains(resposta, reverse("profissionais:profissional_update", args=[self.ana.uuid]))
        self.assertNotContains(resposta, reverse("profissionais:profissional_delete", args=[self.ana.uuid]))
        self.assertContains(resposta, "Gerar PDF")

    def test_gestor_ve_todos_os_botoes(self):
        resposta = self.abrir_lista(VER_PROF, ADD_PROF, CHANGE_PROF, DELETE_PROF)
        self.assertContains(resposta, "Novo profissional")
        self.assertContains(resposta, reverse("profissionais:profissional_update", args=[self.ana.uuid]))
        self.assertContains(resposta, reverse("profissionais:profissional_delete", args=[self.ana.uuid]))

    def test_menu_lateral_so_lista_o_que_o_papel_pode_ver(self):
        resposta = self.abrir_lista(VER_PROF)
        self.assertContains(resposta, reverse("profissionais:profissional_list"))
        self.assertNotContains(resposta, reverse("pacientes:paciente_list"))
        self.assertNotContains(resposta, reverse("consultas:consulta_list"))

    def test_painel_so_mostra_cartoes_permitidos(self):
        grupo = grupo_com_permissoes("Papel", "pacientes.view_paciente")
        Membro.objects.create(user=self.maria, clinica=self.vida, grupo=grupo)
        self.client.force_login(self.maria)
        resposta = self.client.get(reverse("home"))
        self.assertContains(resposta, reverse("pacientes:paciente_list"))
        self.assertNotContains(resposta, reverse("consultas:consulta_list"))
        self.assertNotContains(resposta, reverse("consultas:lista_espera_list"))


# --------------------------------------------------------------------------
# 4. Papéis padrão (sincronizar_papeis) em uso de ponta a ponta
# --------------------------------------------------------------------------
class PapeisPadraoTests(BaseComClinicas):
    def setUp(self):
        papeis.sincronizar_papeis()

    def perfil(self, nome_do_papel, email="pessoa@example.com"):
        usuario = self.novo_usuario(email)
        Membro.objects.create(
            user=usuario, clinica=self.vida, grupo=Group.objects.get(name=nome_do_papel)
        )
        self.client.force_login(usuario)
        return usuario

    def test_cria_os_tres_papeis(self):
        self.assertEqual(
            set(Group.objects.values_list("name", flat=True)),
            {"Administração", "Recepção", "Somente leitura"},
        )

    def test_rodar_de_novo_nao_duplica_nem_mexe(self):
        relatorio = papeis.sincronizar_papeis()
        self.assertEqual({situacao for _, situacao, _ in relatorio}, {"mantido"})
        self.assertEqual(Group.objects.count(), 3)

    def test_papel_ajustado_no_admin_e_preservado_ate_pedir_para_atualizar(self):
        recepcao = Group.objects.get(name="Recepção")
        recepcao.permissions.clear()
        papeis.sincronizar_papeis()
        self.assertEqual(recepcao.permissions.count(), 0)  # mantido

        relatorio = dict((n, s) for n, s, _ in papeis.sincronizar_papeis(atualizar=True))
        self.assertEqual(relatorio["Recepção"], "atualizado")
        self.assertGreater(recepcao.permissions.count(), 0)

    def test_comando_imprime_o_resultado(self):
        saida = StringIO()
        call_command("sincronizar_papeis", stdout=saida)
        self.assertIn("Recepção: mantido", saida.getvalue())

    def test_definicao_com_permissao_inexistente_falha_alto(self):
        with self.assertRaises(CommandError):
            papeis.permissoes_do_papel({"pacientes.paciente": ("voar",)})

    def test_apps_nao_instalados_sao_ignorados(self):
        # No release 1 salas/faturamentos não estão instalados: sem erro e sem
        # permissões deles; no release 2 elas aparecem no papel de Administração.
        admin = Group.objects.get(name="Administração")
        tem = admin.permissions.filter(content_type__app_label="salas").exists()
        self.assertEqual(tem, apps.is_installed("salas"))

    def test_administracao_pode_tudo_inclusive_prontuario(self):
        usuario = self.perfil("Administração")
        with clinica_atual(self.vida):
            self.assertTrue(usuario.has_perm("pacientes.add_prontuario"))
            self.assertTrue(usuario.has_perm("pacientes.view_prontuario"))
            paciente = Paciente.objects.create(
                primeiro_nome="Zé", sobrenome="Silva",
                data_nascimento=date(2000, 1, 1), genero="outro",
            )
        resposta = self.client.post(reverse("pacientes:paciente_delete", args=[paciente.uuid]))
        self.assertEqual(resposta.status_code, 302)

    def test_recepcao_atende_mas_nao_exclui_cadastro_nem_ve_prontuario(self):
        self.perfil("Recepção")
        with clinica_atual(self.vida):
            paciente = Paciente.objects.create(
                primeiro_nome="Zé", sobrenome="Silva",
                data_nascimento=date(2000, 1, 1), genero="outro",
            )
        self.assertEqual(self.client.get(reverse("pacientes:paciente_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("pacientes:paciente_create")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("pacientes:paciente_update", args=[paciente.uuid])).status_code, 200
        )
        # Fora do papel:
        self.assertEqual(
            self.client.post(reverse("pacientes:paciente_delete", args=[paciente.uuid])).status_code, 403
        )
        self.assertEqual(self.client.get(reverse("pacientes:prontuario_create")).status_code, 403)
        with clinica_atual(self.vida):
            self.assertTrue(Paciente.objects.filter(pk=paciente.pk).exists())

    def test_somente_leitura_nao_cria_nada(self):
        self.perfil("Somente leitura")
        self.assertEqual(self.client.get(reverse("pacientes:paciente_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("pacientes:paciente_create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("consultas:consulta_create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("consultas:lista_espera_create")).status_code, 403)


# --------------------------------------------------------------------------
# 5. Rede de segurança: nenhuma tela nova fica sem permissão por esquecimento
# --------------------------------------------------------------------------
# Telas que NÃO são dados da clínica e por isso não usam permissão de model.
# Qualquer view fora desta lista precisa herdar de PermissaoDoModeloMixin.
TELAS_SEM_PERMISSAO_DE_MODELO = {
    "core.views.IndexView",  # painel (cada cartão já se esconde pelas permissões)
    "core.views.LoginView",
    "core.views.LogoutView",
    "core.views.PasswordChangeView",
}
# Funções-view; cada uma tem seu teste de comportamento abaixo.
FUNCOES_SO_COM_LOGIN = {"localidades.views.cidades_por_estado"}


def _callbacks(padroes, prefixo_ns=""):
    for padrao in padroes:
        if isinstance(padrao, URLResolver):
            ns = f"{prefixo_ns}{padrao.namespace}:" if padrao.namespace else prefixo_ns
            if padrao.namespace == "admin":
                continue  # o admin do Django tem o próprio sistema de permissões
            yield from _callbacks(padrao.url_patterns, ns)
        elif isinstance(padrao, URLPattern):
            yield prefixo_ns + (padrao.name or ""), padrao.callback


class TodaTelaExigePermissaoTests(SimpleTestCase):
    def test_toda_view_de_negocio_herda_de_permissao_do_modelo(self):
        sem_protecao = []
        for nome, callback in _callbacks(get_resolver().url_patterns):
            classe = getattr(callback, "view_class", None)
            if classe is None:
                caminho = f"{callback.__module__}.{callback.__name__}"
                if caminho not in FUNCOES_SO_COM_LOGIN:
                    sem_protecao.append(f"{nome} ({caminho}) é função e não está na lista")
                continue
            caminho = f"{classe.__module__}.{classe.__name__}"
            if caminho in TELAS_SEM_PERMISSAO_DE_MODELO:
                continue
            if not issubclass(classe, PermissaoDoModeloMixin):
                sem_protecao.append(f"{nome} ({caminho})")
        self.assertEqual(
            sem_protecao, [],
            "Views sem permissão (use PermissaoVer/Adicionar/Alterar/Excluir):\n"
            + "\n".join(sem_protecao),
        )

    def test_a_lista_de_excecoes_nao_tem_entradas_mortas(self):
        existentes = set()
        for _, callback in _callbacks(get_resolver().url_patterns):
            classe = getattr(callback, "view_class", None)
            existentes.add(
                f"{classe.__module__}.{classe.__name__}" if classe
                else f"{callback.__module__}.{callback.__name__}"
            )
        mortas = (TELAS_SEM_PERMISSAO_DE_MODELO | FUNCOES_SO_COM_LOGIN) - existentes
        self.assertEqual(mortas, set())

    def test_a_acao_de_cada_view_combina_com_o_tipo_dela(self):
        # Evita, por exemplo, uma DeleteView protegida só por "ver".
        esperado = {"DeleteView": "delete", "UpdateView": "change", "CreateView": "add"}
        erros = []
        for nome, callback in _callbacks(get_resolver().url_patterns):
            classe = getattr(callback, "view_class", None)
            if not classe or not issubclass(classe, PermissaoDoModeloMixin):
                continue
            for base in classe.__mro__:
                acao = esperado.get(base.__name__)
                if acao and base.__module__.startswith("django.views.generic"):
                    if classe.acao_permissao != acao:
                        erros.append(f"{nome}: {base.__name__} com acao_permissao={classe.acao_permissao!r}")
                    break
        self.assertEqual(erros, [])


class CidadesPorEstadoTests(TestCase):
    def test_exige_login(self):
        resposta = self.client.get(reverse("localidades:cidades"), {"estado": 1})
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta["Location"].startswith("/login/"))

    def test_logado_continua_funcionando(self):
        usuario = User.objects.create_user("a@example.com", password="x")
        self.client.force_login(usuario)
        resposta = self.client.get(reverse("localidades:cidades"), {"estado": 1})
        self.assertEqual(resposta.status_code, 200)


# --------------------------------------------------------------------------
# 6. O mixin em si
# --------------------------------------------------------------------------
class PermissaoDoModeloMixinTests(SimpleTestCase):
    def permissao_de(self, classe):
        view = classe()
        view.request = RequestFactory().get("/")
        return view.get_permission_required()

    def test_monta_a_permissao_com_o_model_da_view(self):
        class V(PermissaoExcluir, ListView):
            model = Profissional

        self.assertEqual(self.permissao_de(V), ["profissionais.delete_profissional"])

    def test_cada_atalho_usa_sua_acao(self):
        for mixin, acao in [(PermissaoVer, "view"), (PermissaoAdicionar, "add"), (PermissaoAlterar, "change")]:
            with self.subTest(acao=acao):
                V = type("V", (mixin, ListView), {"model": Profissional})
                self.assertEqual(self.permissao_de(V), [f"profissionais.{acao}_profissional"])

    def test_permission_required_explicito_tem_prioridade(self):
        class V(PermissaoVer, ListView):
            model = Profissional
            permission_required = "pacientes.view_prontuario"

        self.assertEqual(list(self.permissao_de(V)), ["pacientes.view_prontuario"])

    def test_sem_acao_falha_alto(self):
        class V(PermissaoDoModeloMixin, ListView):
            model = Profissional

        with self.assertRaises(ImproperlyConfigured):
            self.permissao_de(V)

    def test_sem_model_falha_alto(self):
        class V(PermissaoVer, ListView):
            pass

        with self.assertRaises(ImproperlyConfigured):
            self.permissao_de(V)
