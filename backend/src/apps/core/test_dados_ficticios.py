import random
import re
from collections import Counter
from datetime import date, timedelta
from io import StringIO

from django.apps import apps
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from clinicas.models import Clinica, Membro
from clinicas.tenancy import TenantModel, clinica_atual
from clinicas.validators import validar_cnpj
from consultas.models import Consulta, Lembrete, ListaEspera
from core import dados_ficticios as dados
from enderecos.models import Endereco
from localidades.models import Cidade, Estado
from pacientes.models import Paciente, Prontuario
from profissionais.models import Disponibilidade, Profissional
from telefones.models import Telefone

User = get_user_model()

SENHA_PADRAO = "Demo#Clinica2026"
PEQUENO = {"clinicas": 2, "profissionais": 3, "pacientes": 10, "consultas": 3}


def rodar(*args, **opcoes):
    """Roda o comando (o teste roda com DEBUG desligado, então forçamos)."""
    saida = StringIO()
    opcoes.setdefault("forcar", True)
    call_command("popular_dados_ficticios", *args, stdout=saida, **opcoes)
    return saida.getvalue()


def modelos_de_negocio():
    """Models de clínica que têm tabela (alguns models de outros testes não têm)."""
    tabelas = set(connection.introspection.table_names())
    return [
        m
        for m in apps.get_models()
        if issubclass(m, TenantModel) and m._meta.db_table in tabelas
    ]


def clinicas_demo():
    return list(Clinica.objects.filter(slug__startswith="demo-").order_by("slug"))


class QuantidadesChecks:
    def test_cria_as_clinicas_pedidas(self):
        self.assertEqual([c.slug for c in self.clinicas], ["demo-1", "demo-2"])

    def test_cada_clinica_tem_o_pedido_de_pacientes_e_profissionais(self):
        for clinica in self.clinicas:
            with self.subTest(clinica=clinica.slug), clinica_atual(clinica):
                self.assertEqual(Paciente.objects.count(), PEQUENO["pacientes"])
                self.assertEqual(Profissional.objects.count(), PEQUENO["profissionais"])

    def test_gera_dados_de_todos_os_apps_instalados(self):
        for clinica in self.clinicas:
            with self.subTest(clinica=clinica.slug), clinica_atual(clinica):
                for modelo in (
                    Consulta, Lembrete, Prontuario, Telefone, Endereco, Disponibilidade,
                ):
                    self.assertGreater(modelo.objects.count(), 0, modelo.__name__)

    def test_apps_opcionais_nao_instalados_sao_ignorados(self):
        # Salas e faturamentos estão fora do release 1: nada deles é tocado.
        self.assertFalse(apps.is_installed("salas"))
        self.assertFalse(apps.is_installed("faturamentos"))

    def test_saida_lista_logins_e_senha(self):
        self.assertIn(SENHA_PADRAO, self.saida)
        for email in User.objects.filter(email__endswith="@demo.example").values_list(
            "email", flat=True
        ):
            self.assertIn(email, self.saida)


class ValidadeDosDadosChecks:
    def test_todos_os_registros_passam_na_validacao_dos_models(self):
        """Mesmas regras do admin e dos formulários: campos, escolhas e restrições."""
        for clinica in self.clinicas:
            clinica.full_clean()
            for modelo in modelos_de_negocio():
                with clinica_atual(clinica):
                    for objeto in modelo.objects.all():
                        with self.subTest(modelo=modelo.__name__, objeto=str(objeto)):
                            objeto.full_clean()

    def test_cnpj_das_clinicas_e_valido(self):
        for clinica in self.clinicas:
            validar_cnpj(clinica.cnpj)


class IsolamentoChecks:
    """Nada de uma clínica aponta para dados de outra."""

    def test_consulta_liga_paciente_e_profissional_da_mesma_clinica(self):
        for c in Consulta.todas.select_related("paciente", "profissional"):
            self.assertEqual(c.paciente.clinica_id, c.clinica_id)
            self.assertEqual(c.profissional.clinica_id, c.clinica_id)

    def test_prontuario_e_coerente_com_a_consulta(self):
        total = 0
        for p in Prontuario.todas.select_related("consulta", "paciente", "profissional"):
            total += 1
            self.assertEqual(p.consulta.paciente_id, p.paciente_id)
            self.assertEqual(p.consulta.profissional_id, p.profissional_id)
            self.assertEqual(p.paciente.clinica_id, p.clinica_id)
            self.assertEqual(p.consulta.status, "realizada")
        self.assertGreater(total, 0)

    def test_contatos_pertencem_a_um_dono_da_mesma_clinica(self):
        for modelo in (Telefone, Endereco):
            for contato in modelo.todas.select_related("pacientes", "profissionais"):
                dono = contato.pacientes or contato.profissionais
                self.assertEqual(dono.clinica_id, contato.clinica_id)

    def test_lembretes_e_lista_de_espera_na_mesma_clinica(self):
        for lembrete in Lembrete.todas.select_related("consulta"):
            self.assertEqual(lembrete.consulta.clinica_id, lembrete.clinica_id)
        for espera in ListaEspera.todas.select_related("paciente", "profissional_preferido"):
            self.assertEqual(espera.paciente.clinica_id, espera.clinica_id)
            if espera.profissional_preferido:
                self.assertEqual(espera.profissional_preferido.clinica_id, espera.clinica_id)

    def test_cada_clinica_enxerga_so_o_que_e_seu(self):
        total = Paciente.todas.count()
        vistos = 0
        for clinica in self.clinicas:
            with clinica_atual(clinica):
                vistos += Paciente.objects.count()
        self.assertEqual(vistos, total)


class AgendaChecks:
    def test_nenhum_profissional_tem_dois_atendimentos_no_mesmo_horario(self):
        chaves = Counter(
            (c.profissional_id, c.data_consulta, c.hora_inicio) for c in Consulta.todas.all()
        )
        self.assertEqual([k for k, n in chaves.items() if n > 1], [])

    def test_consultas_so_em_dias_uteis(self):
        for c in Consulta.todas.all():
            self.assertLess(c.data_consulta.weekday(), 5, c.data_consulta)

    def test_consulta_so_entre_paciente_e_um_dos_seus_profissionais(self):
        # Tabela de ligação direta: o manager do model filtra pela clínica atual.
        ligacao = Paciente.profissionais.through.objects
        for c in Consulta.todas.all():
            self.assertTrue(
                ligacao.filter(
                    paciente_id=c.paciente_id, profissional_id=c.profissional_id
                ).exists(),
                str(c),
            )

    def test_status_combinam_com_a_data(self):
        hoje = timezone.localdate()
        for c in Consulta.todas.all():
            with self.subTest(consulta=str(c), status=c.status):
                if c.data_consulta < hoje:
                    self.assertIn(c.status, ("realizada", "falta", "cancelada"))
                else:
                    self.assertNotIn(c.status, ("realizada", "falta"))
                if c.status == "cancelada":
                    self.assertTrue(c.motivo_cancelamento)

    def test_primeira_consulta_de_cada_paciente_e_avaliacao_inicial(self):
        for paciente in Paciente.todas.all():
            consultas = list(paciente.consultas.order_by("data_consulta", "hora_inicio"))
            if consultas:
                self.assertEqual(consultas[0].tipo_consulta, "avaliacao_inicial")


class UsuariosChecks:
    def test_cada_clinica_tem_um_usuario_por_papel_e_profissionais_com_usuario(self):
        for clinica in self.clinicas:
            papeis = Counter(m.grupo.name for m in Membro.objects.filter(clinica=clinica))
            with self.subTest(clinica=clinica.slug):
                self.assertEqual(papeis["Recepção"], 1)
                self.assertEqual(papeis["Somente leitura"], 1)
                # 1 administrador + 2 profissionais com usuário (hoje no papel Administração).
                self.assertEqual(papeis["Administração"], 3)

    def test_cada_usuario_fictício_pertence_a_uma_unica_clinica(self):
        for user in User.objects.filter(email__endswith="@demo.example"):
            self.assertEqual(Membro.objects.filter(user=user).count(), 1, user.email)

    def test_todos_entram_com_a_senha_padrao(self):
        for user in User.objects.filter(email__endswith="@demo.example"):
            self.assertIsNotNone(
                authenticate(username=user.email, password=SENHA_PADRAO), user.email
            )

    def test_profissionais_com_usuario_estao_ligados_a_membro_da_propria_clinica(self):
        ligados = Profissional.todas.filter(user__isnull=False)
        self.assertEqual(ligados.count(), 2 * len(self.clinicas))
        for profissional in ligados:
            membro = Membro.objects.get(user=profissional.user)
            self.assertEqual(membro.clinica_id, profissional.clinica_id)
            self.assertEqual(profissional.user.email, profissional.email)


class TabelasDeModelosDeTeste:
    """Cria a tabela de models de clínica registrados só por outros testes.

    `Nota`, em clinicas/tests.py, é um model de teste: fica registrado no Django
    por toda a execução, mas sua tabela só existe durante aquela classe. Ao
    apagar uma clínica, o Django consulta a tabela de TODO model que aponta para
    ela, e quebraria. Os testes que apagam clínicas usam este mixin para a
    tabela existir enquanto rodam (e some no fim).
    """

    @classmethod
    def setUpClass(cls):
        existentes = set(connection.introspection.table_names())
        cls._modelos_sem_tabela = [
            m
            for m in apps.get_models()
            if issubclass(m, TenantModel) and m._meta.db_table not in existentes
        ]
        # Fora da transação do TestCase, como no próprio teste do `Nota`.
        with connection.schema_editor() as editor:
            for modelo in cls._modelos_sem_tabela:
                editor.create_model(modelo)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connection.schema_editor() as editor:
            for modelo in cls._modelos_sem_tabela:
                editor.delete_model(modelo)


class DadosGeradosTests(
    QuantidadesChecks,
    ValidadeDosDadosChecks,
    IsolamentoChecks,
    AgendaChecks,
    UsuariosChecks,
    TestCase,
):
    """Roda o comando UMA vez e confere os dados gerados (os testes só leem)."""

    @classmethod
    def setUpTestData(cls):
        cls.saida = rodar(**PEQUENO)
        cls.clinicas = clinicas_demo()


class RepetibilidadeTests(TabelasDeModelosDeTeste, TestCase):
    def nomes(self):
        return list(
            Paciente.todas.order_by("clinica__slug", "primeiro_nome", "sobrenome", "email")
            .values_list("clinica__slug", "primeiro_nome", "sobrenome", "genero")
        )

    def test_mesma_semente_gera_os_mesmos_dados(self):
        rodar(seed=7, **PEQUENO)
        primeira = self.nomes()
        consultas = Consulta.todas.count()
        rodar(seed=7, recriar=True, **PEQUENO)
        self.assertEqual(self.nomes(), primeira)
        self.assertEqual(Consulta.todas.count(), consultas)

    def test_mesma_semente_gera_a_mesma_agenda_em_qualquer_dia_da_semana(self):
        """As datas são relativas a hoje, mas o conteúdo não pode depender do dia.

        Antes, fins de semana deslocados para segunda-feira criavam choques de
        horário diferentes conforme o dia em que o comando rodava.
        """
        hoje = timezone.localdate()

        def resumo():
            return (
                Consulta.todas.count(),
                Lembrete.todas.count(),
                Prontuario.todas.count(),
                sorted(Counter(Consulta.todas.values_list("status", flat=True)).items()),
                sorted(Counter(Consulta.todas.values_list("tipo_consulta", flat=True)).items()),
            )

        # Poucos profissionais e muitos pacientes: bastante disputa por horário,
        # que é onde a diferença entre dias da semana aparecia.
        concorrido = {"clinicas": 1, "profissionais": 2, "pacientes": 40, "consultas": 4}
        referencia = None
        for dias in range(7):  # percorre todos os dias da semana
            hoje_simulado = hoje + timedelta(days=dias)
            with mock.patch("django.utils.timezone.localdate", return_value=hoje_simulado):
                rodar(seed=11, recriar=True, **concorrido)
            if referencia is None:
                referencia = resumo()
            with self.subTest(hoje=hoje_simulado, dia_da_semana=hoje_simulado.weekday()):
                self.assertEqual(resumo(), referencia)

    def test_semente_diferente_gera_dados_diferentes(self):
        rodar(seed=1, **PEQUENO)
        primeira = self.nomes()
        rodar(seed=2, recriar=True, **PEQUENO)
        self.assertNotEqual(self.nomes(), primeira)


class SegurancaDoComandoTests(TabelasDeModelosDeTeste, TestCase):
    def test_nao_roda_duas_vezes_sem_pedir(self):
        rodar(**PEQUENO)
        with self.assertRaisesMessage(CommandError, "--recriar"):
            rodar(**PEQUENO)
        self.assertEqual(len(clinicas_demo()), 2)

    def test_recriar_substitui_em_vez_de_acumular(self):
        rodar(**PEQUENO)
        usuarios = User.objects.filter(email__endswith="@demo.example").count()
        rodar(recriar=True, **PEQUENO)
        self.assertEqual(len(clinicas_demo()), 2)
        self.assertEqual(Paciente.todas.count(), 2 * PEQUENO["pacientes"])
        self.assertEqual(
            User.objects.filter(email__endswith="@demo.example").count(), usuarios
        )

    def test_recusa_rodar_com_debug_desligado(self):
        with override_settings(DEBUG=False), self.assertRaisesMessage(CommandError, "DEBUG"):
            call_command("popular_dados_ficticios", stdout=StringIO())
        self.assertEqual(Clinica.objects.count(), 0)

    def test_roda_com_debug_ligado_sem_forcar(self):
        with override_settings(DEBUG=True):
            call_command("popular_dados_ficticios", stdout=StringIO(), **PEQUENO)
        self.assertEqual(len(clinicas_demo()), 2)

    def test_forcar_permite_rodar_com_debug_desligado(self):
        with override_settings(DEBUG=False):
            rodar(forcar=True, **PEQUENO)
        self.assertEqual(len(clinicas_demo()), 2)

    def test_argumento_negativo_e_recusado(self):
        with self.assertRaises(CommandError):
            call_command("popular_dados_ficticios", "--pacientes=-1", forcar=True)

    def test_exige_pelo_menos_uma_clinica(self):
        with self.assertRaisesMessage(CommandError, "pelo menos 1 clínica"):
            rodar(clinicas=0)

    def test_senha_personalizada(self):
        rodar(senha="Outra#Senha2026", **PEQUENO)
        user = User.objects.get(email="admin.demo-1@demo.example")
        self.assertIsNotNone(authenticate(username=user.email, password="Outra#Senha2026"))
        self.assertIsNone(authenticate(username=user.email, password=SENHA_PADRAO))

    def test_sem_profissionais_nao_gera_agenda_mas_nao_quebra(self):
        rodar(clinicas=1, profissionais=0, pacientes=5, consultas=3)
        self.assertEqual(Paciente.todas.count(), 5)
        self.assertEqual(Consulta.todas.count(), 0)
        self.assertEqual(Prontuario.todas.count(), 0)


class RemocaoTests(TabelasDeModelosDeTeste, TestCase):
    def setUp(self):
        # Dados REAIS que a remoção nunca pode tocar.
        self.real = Clinica.objects.create(
            nome="Clínica Real", cnpj="11222333000181", slug="clinica-real"
        )
        self.usuario_real = User.objects.create_user(
            "gente.real@clinicareal.com.br", password="Zm9!kQ7#xLp2"
        )
        Membro.objects.create(
            user=self.usuario_real,
            clinica=self.real,
            grupo=Group.objects.get_or_create(name="Recepção")[0],
        )
        with clinica_atual(self.real):
            self.paciente_real = Paciente.objects.create(
                primeiro_nome="Paciente",
                sobrenome="Real",
                data_nascimento=date(1990, 1, 1),
                genero="outro",
            )

    def test_remover_apaga_so_os_dados_ficticios(self):
        rodar(**PEQUENO)
        rodar(remover=True)

        self.assertEqual(clinicas_demo(), [])
        self.assertFalse(User.objects.filter(email__endswith="@demo.example").exists())
        for modelo in modelos_de_negocio():
            restante = modelo.todas.exclude(clinica=self.real).count()
            self.assertEqual(restante, 0, modelo.__name__)
        # O que é real continua lá.
        self.assertTrue(Clinica.objects.filter(pk=self.real.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.usuario_real.pk).exists())
        self.assertTrue(Membro.objects.filter(user=self.usuario_real).exists())
        self.assertTrue(Paciente.todas.filter(pk=self.paciente_real.pk).exists())

    def test_gerar_dados_nao_mexe_nos_dados_reais(self):
        rodar(**PEQUENO)
        with clinica_atual(self.real):
            self.assertEqual(list(Paciente.objects.all()), [self.paciente_real])
        self.assertEqual(Profissional.todas.filter(clinica=self.real).count(), 0)

    def test_remover_sem_dados_ficticios_nao_da_erro(self):
        rodar(remover=True)
        self.assertTrue(Clinica.objects.filter(pk=self.real.pk).exists())


class LocalidadesTests(TabelasDeModelosDeTeste, TestCase):
    def test_sem_cidades_cria_um_conjunto_minimo_com_codigos_do_ibge(self):
        self.assertFalse(Cidade.objects.exists())
        rodar(**PEQUENO)
        esperadas = sum(len(c) for *_, c in dados.LOCALIDADES_PADRAO)
        self.assertEqual(Cidade.objects.count(), esperadas)
        self.assertTrue(Cidade.objects.filter(codigo_ibge=5208707, nome="Goiânia").exists())

    def test_com_cidades_ja_carregadas_usa_as_existentes(self):
        estado = Estado.objects.create(codigo_ibge=11, sigla="RO", nome="Rondônia")
        cidade = Cidade.objects.create(codigo_ibge=1100015, nome="Alta Floresta", estado=estado)
        rodar(**PEQUENO)
        self.assertEqual(list(Cidade.objects.all()), [cidade])
        self.assertEqual(set(Endereco.todas.values_list("cidade", flat=True)), {cidade.pk})

    def test_rodar_de_novo_nao_duplica_cidades(self):
        rodar(**PEQUENO)
        total = Cidade.objects.count()
        rodar(recriar=True, **PEQUENO)
        self.assertEqual(Cidade.objects.count(), total)


class GeradoresTests(TestCase):
    """Os geradores puros (sem banco)."""

    def test_cnpj_gerado_e_sempre_valido(self):
        for semente in range(300):
            validar_cnpj(dados.cnpj_valido(random.Random(semente)))

    def test_telefones_seguem_o_formato_aceito_pelo_model(self):
        padrao = re.compile(r"^\+?1?\d{9,15}$")
        rng = random.Random(1)
        for tipo in ("celular", "fixo"):
            for _ in range(200):
                self.assertRegex(dados.telefone(rng, tipo), padrao)

    def test_cep_tem_formato_de_cep(self):
        rng = random.Random(1)
        for _ in range(50):
            self.assertRegex(dados.cep(rng), r"^\d{5}-\d{3}$")

    def test_email_sem_acentos_nem_simbolos(self):
        self.assertEqual(dados.para_email("João Álvaro"), "joaoalvaro")
        self.assertEqual(dados.sem_acentos("Conceição"), "Conceicao")

    def test_registro_profissional_por_tipo(self):
        rng = random.Random(1)
        self.assertRegex(dados.registro_profissional(rng, "Psicólogo"), r"^CRP \d\d/\d{5}$")
        self.assertRegex(dados.registro_profissional(rng, "Psiquiatra"), r"^CRM \d{5}$")
        self.assertRegex(dados.registro_profissional(rng, "Nutricionista"), r"^REG \d{5}$")

    def test_data_de_nascimento_dentro_da_faixa_de_idade(self):
        rng = random.Random(1)
        hoje = date(2026, 10, 27)
        for _ in range(300):
            anos = (hoje - dados.data_nascimento(rng, hoje)).days / 365.25
            self.assertTrue(5.5 <= anos <= 86, anos)

    def test_nomes_cobrem_generos_e_repetem_com_a_mesma_semente(self):
        a = [dados.nome_pessoa(random.Random(5)) for _ in range(3)]
        b = [dados.nome_pessoa(random.Random(5)) for _ in range(3)]
        self.assertEqual(a, b)
        generos = {dados.nome_pessoa(random.Random(i))[2] for i in range(200)}
        self.assertTrue({"masculino", "feminino"} <= generos)
