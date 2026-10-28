"""Popula o banco com clínicas, pessoas e agenda FICTÍCIAS, para desenvolver e demonstrar.

Por que um comando (e não migração ou SQL puro): ele passa pelos models, então
respeita o isolamento por clínica, as validações, os hashes de senha e as
restrições de unicidade; pode ser repetido, desfeito e ajustado por opções; e
nunca roda em `migrate` nem no banco de testes.

Como é isolado do resto: tudo o que ele cria é identificável.
  * clínicas com identificador `demo-1`, `demo-2`, ...;
  * usuários com e-mail terminado em `@demo.example` (domínio reservado, não
    existe de verdade).
`--remover` apaga somente isso, nunca dados reais.

Cobre todos os apps de negócio presentes em INSTALLED_APPS. Os opcionais (salas,
faturamentos) só entram quando instalados.
"""

import random
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from clinicas.models import Clinica, Membro
from clinicas.papeis import sincronizar_papeis
from clinicas.tenancy import TenantModel, clinica_atual
from clinicas.validators import validar_cnpj
from consultas.models import Consulta, Lembrete, ListaEspera
from core import dados_ficticios as dados
from enderecos.models import Endereco
from localidades.models import Cidade, Estado
from pacientes.models import Paciente, Prontuario
from profissionais.models import Disponibilidade, Profissional, TipoProfissional
from telefones.models import Telefone

User = get_user_model()

PREFIXO_SLUG = "demo-"
SUFIXO_EMAIL = "@demo.example"
SENHA_PADRAO = "Demo#Clinica2026"

PAPEL_ADMIN = "Administração"
PAPEL_RECEPCAO = "Recepção"
PAPEL_LEITURA = "Somente leitura"
# Hoje o único papel com acesso a prontuário é a Administração. Quando existir um
# papel próprio para profissionais de saúde, é só trocar aqui.
PAPEL_PROFISSIONAL = PAPEL_ADMIN

# Quantos profissionais de cada clínica ganham um usuário para entrar no sistema.
PROFISSIONAIS_COM_USUARIO = 2

DIAS_SEMANA = ("segunda", "terca", "quarta", "quinta", "sexta")
HORAS_DE_ATENDIMENTO = (8, 9, 10, 11, 14, 15, 16, 17)


def _inteiro_nao_negativo(valor):
    numero = int(valor)
    if numero < 0:
        raise ValueError
    return numero


class Command(BaseCommand):
    help = (
        "Cria clínicas, usuários, pacientes, profissionais e agenda fictícios "
        "(só em desenvolvimento). Tudo é marcado como 'demo' e pode ser removido "
        "com --remover."
    )

    def add_arguments(self, parser):
        parser.add_argument("--clinicas", type=_inteiro_nao_negativo, default=2,
                            help="Quantidade de clínicas fictícias (padrão: 2).")
        parser.add_argument("--profissionais", type=_inteiro_nao_negativo, default=4,
                            help="Profissionais por clínica (padrão: 4).")
        parser.add_argument("--pacientes", type=_inteiro_nao_negativo, default=30,
                            help="Pacientes por clínica (padrão: 30).")
        parser.add_argument("--consultas", type=_inteiro_nao_negativo, default=3,
                            help="Média de consultas por paciente (padrão: 3).")
        parser.add_argument("--seed", type=int, default=42,
                            help="Semente: a mesma semente gera os mesmos dados (padrão: 42).")
        parser.add_argument("--senha", default=SENHA_PADRAO,
                            help=f"Senha dos usuários fictícios (padrão: {SENHA_PADRAO}).")
        parser.add_argument("--recriar", action="store_true",
                            help="Remove os dados fictícios que já existem e cria de novo.")
        parser.add_argument("--remover", action="store_true",
                            help="Só remove os dados fictícios e termina.")
        parser.add_argument("--forcar", action="store_true",
                            help="Permite rodar com DEBUG desligado. Nunca use em produção.")

    # ------------------------------------------------------------------ fluxo
    def handle(self, *args, **opcoes):
        if not settings.DEBUG and not opcoes["forcar"]:
            raise CommandError(
                "Este comando só roda com DEBUG ligado (ambiente de desenvolvimento). "
                "Use --forcar se tiver certeza de que este NÃO é um banco de produção."
            )

        if opcoes["remover"] or opcoes["recriar"]:
            self._remover()
            if opcoes["remover"]:
                return

        if Clinica.objects.filter(slug__startswith=PREFIXO_SLUG).exists():
            raise CommandError(
                "Já existem dados fictícios. Use --recriar para refazê-los "
                "ou --remover para apagá-los."
            )
        if opcoes["clinicas"] < 1:
            raise CommandError("Informe pelo menos 1 clínica (--clinicas).")

        sincronizar_papeis()  # garante os papéis (não altera os que já existem)
        papeis = self._papeis()
        # Todos os usuários fictícios têm a mesma senha: o hash (Argon2, de
        # propósito lento) é calculado uma vez só e reaproveitado.
        self.senha_hash = make_password(opcoes["senha"])

        rng = random.Random(opcoes["seed"])
        logins = []
        with transaction.atomic():
            cidades = self._cidades()
            resumos = [
                self._criar_clinica(i, opcoes, rng, papeis, cidades, logins)
                for i in range(1, opcoes["clinicas"] + 1)
            ]

        self._imprimir(resumos, logins, opcoes["senha"])

    # --------------------------------------------------------------- remoção
    def _remover(self):
        clinicas = Clinica.objects.filter(slug__startswith=PREFIXO_SLUG)
        ids = list(clinicas.values_list("pk", flat=True))
        removidos = defaultdict(int)
        with transaction.atomic():
            # Os models de negócio apontam para a clínica com PROTECT: primeiro
            # os dados, por último a clínica. A ordem entre os models de negócio
            # não importa (as ligações entre eles se apagam em cascata).
            for modelo in apps.get_models():
                if issubclass(modelo, TenantModel):
                    total, _ = modelo.todas.filter(clinica_id__in=ids).delete()
                    if total:
                        removidos[modelo._meta.verbose_name_plural] += total
            clinicas.delete()
            User.objects.filter(email__endswith=SUFIXO_EMAIL).delete()
        if ids:
            self.stdout.write(self.style.WARNING(
                f"Dados fictícios removidos ({len(ids)} clínica(s))."
            ))

    # --------------------------------------------------------------- apoio
    def _papeis(self):
        nomes = {PAPEL_ADMIN, PAPEL_RECEPCAO, PAPEL_LEITURA, PAPEL_PROFISSIONAL}
        grupos = {g.name: g for g in Group.objects.filter(name__in=nomes)}
        faltando = nomes - set(grupos)
        if faltando:
            raise CommandError(
                f"Papéis inexistentes: {sorted(faltando)}. Confira PAPEIS em "
                "clinicas/papeis.py e rode `manage.py sincronizar_papeis`."
            )
        return grupos

    def _cidades(self):
        """Cidades para os endereços: as do banco, ou um conjunto mínimo do IBGE."""
        if not Cidade.objects.exists():
            for cod_estado, sigla, nome, cidades in dados.LOCALIDADES_PADRAO:
                estado, _ = Estado.objects.update_or_create(
                    codigo_ibge=cod_estado, defaults={"sigla": sigla, "nome": nome}
                )
                for cod_cidade, nome_cidade in cidades:
                    Cidade.objects.update_or_create(
                        codigo_ibge=cod_cidade,
                        defaults={"nome": nome_cidade, "estado": estado},
                    )
        # Ordem fixa: com a mesma semente, as mesmas cidades.
        return list(Cidade.objects.order_by("codigo_ibge"))

    def _usuario(self, email, nome, sobrenome):
        return User.objects.create(
            email=email,
            password=self.senha_hash,
            first_name=nome,
            last_name=sobrenome,
        )

    # ------------------------------------------------------- uma clínica
    def _criar_clinica(self, indice, opcoes, rng, papeis, cidades, logins):
        base = dados.NOMES_CLINICA[(indice - 1) % len(dados.NOMES_CLINICA)]
        nome = f"Clínica {base}" + (
            f" {indice}" if indice > len(dados.NOMES_CLINICA) else ""
        )
        slug = f"{PREFIXO_SLUG}{indice}"
        cnpj = dados.cnpj_valido(rng)
        while Clinica.objects.filter(cnpj=cnpj).exists():
            cnpj = dados.cnpj_valido(rng)
        validar_cnpj(cnpj)

        clinica = Clinica.objects.create(
            nome=nome,
            razao_social=f"{nome} Serviços de Saúde Ltda",
            cnpj=cnpj,
            slug=slug,
            email=f"contato.{slug}{SUFIXO_EMAIL}",
        )
        resumo = defaultdict(int)
        resumo["clinica"] = clinica

        def novo_membro(email, primeiro, sobrenome, papel, profissional=False):
            user = self._usuario(email, primeiro, sobrenome)
            Membro.objects.create(user=user, clinica=clinica, grupo=papeis[papel])
            rotulo = f"{papel} (profissional)" if profissional else papel
            logins.append((nome, rotulo, email))
            return user

        with clinica_atual(clinica):
            # --- equipe administrativa (um usuário por papel)
            for papel, rotulo in (
                (PAPEL_ADMIN, "admin"),
                (PAPEL_RECEPCAO, "recepcao"),
                (PAPEL_LEITURA, "leitura"),
            ):
                primeiro, sobrenome, _ = dados.nome_pessoa(rng)
                novo_membro(f"{rotulo}.{slug}{SUFIXO_EMAIL}", primeiro, sobrenome, papel)
                resumo["usuários"] += 1

            profissionais = self._criar_profissionais(
                clinica, opcoes, rng, cidades, novo_membro, resumo
            )
            pacientes = self._criar_pacientes(
                clinica, opcoes, rng, cidades, profissionais, resumo
            )
            consultas = self._criar_consultas(
                opcoes, rng, pacientes, profissionais, resumo
            )
            self._criar_lista_espera(rng, pacientes, profissionais, resumo)
            self._criar_prontuarios(rng, consultas, resumo)

            # Apps opcionais (fora do release 1): só se estiverem instalados.
            if apps.is_installed("salas"):
                self._criar_salas(rng, consultas, resumo)
            if apps.is_installed("faturamentos"):
                self._criar_faturamentos(rng, consultas, resumo)
        return resumo

    # ------------------------------------------------------- profissionais
    def _criar_profissionais(self, clinica, opcoes, rng, cidades, novo_membro, resumo):
        tipos = list(TipoProfissional.objects.order_by("pk"))
        if not tipos:
            tipos = [TipoProfissional.objects.create(descricao="Psicólogo")]

        profissionais = []
        for n in range(1, opcoes["profissionais"] + 1):
            primeiro, sobrenome, _ = dados.nome_pessoa(rng)
            tipo = rng.choice(tipos)
            email = (
                f"{dados.para_email(primeiro)}.{dados.para_email(sobrenome)}"
                f".{n}.{clinica.slug}{SUFIXO_EMAIL}"
            )
            user = None
            if n <= PROFISSIONAIS_COM_USUARIO:
                user = novo_membro(
                    email, primeiro, sobrenome, PAPEL_PROFISSIONAL, profissional=True
                )
                resumo["usuários"] += 1
            profissional = Profissional.objects.create(
                user=user,
                primeiro_nome=primeiro,
                sobrenome=sobrenome,
                email=email,
                tipo_profissional=tipo,
                numero_registro=dados.registro_profissional(rng, tipo.descricao),
                especializacao=rng.choice(("", "Terapia cognitivo-comportamental", "Psicologia infantil", "Neuropsicologia")),
                valor_hora=rng.choice((120, 150, 180, 200, 250, 300)),
            )
            profissionais.append(profissional)
            resumo["profissionais"] += 1

            for dia in rng.sample(DIAS_SEMANA, k=rng.randint(3, 5)):
                for inicio, fim in rng.choice(
                    (((8, 12),), ((14, 18),), ((8, 12), (14, 18)))
                ):
                    Disponibilidade.objects.create(
                        profissional=profissional,
                        dia_semana=dia,
                        hora_inicio=time(inicio),
                        hora_fim=time(fim),
                    )
                    resumo["disponibilidades"] += 1
            self._contatos(rng, cidades, resumo, profissional=profissional)
        return profissionais

    # ----------------------------------------------------------- pacientes
    def _criar_pacientes(self, clinica, opcoes, rng, cidades, profissionais, resumo):
        hoje = timezone.localdate()
        pacientes = []
        for n in range(1, opcoes["pacientes"] + 1):
            primeiro, sobrenome, genero = dados.nome_pessoa(rng)
            com_convenio = rng.random() < 0.4
            paciente = Paciente.objects.create(
                primeiro_nome=primeiro,
                sobrenome=sobrenome,
                data_nascimento=dados.data_nascimento(rng, hoje),
                genero=genero,
                email=(
                    f"{dados.para_email(primeiro)}.{dados.para_email(sobrenome)}.{n}"
                    f"{SUFIXO_EMAIL}"
                    if rng.random() < 0.7
                    else ""
                ),
                convenio=rng.choice(dados.CONVENIOS) if com_convenio else "",
                numero_carteirinha=(
                    str(rng.randint(10**9, 10**10 - 1)) if com_convenio else ""
                ),
                ativo=rng.random() < 0.9,
            )
            if profissionais:
                paciente.profissionais.set(
                    rng.sample(profissionais, k=min(len(profissionais), rng.randint(1, 2)))
                )
            pacientes.append(paciente)
            resumo["pacientes"] += 1
            self._contatos(rng, cidades, resumo, paciente=paciente)
        return pacientes

    def _contatos(self, rng, cidades, resumo, paciente=None, profissional=None):
        """Telefones e um endereço, para um paciente OU um profissional."""
        dono = {"pacientes": paciente} if paciente else {"profissionais": profissional}
        tipos = rng.sample(("celular", "residencial", "comercial", "recado"), k=rng.randint(1, 2))
        for i, tipo in enumerate(tipos):
            Telefone.objects.create(
                numero=dados.telefone(rng, "celular" if tipo == "celular" else "fixo"),
                tipo=tipo,
                principal=(i == 0),
                **dono,
            )
            resumo["telefones"] += 1
        if cidades:
            Endereco.objects.create(
                logradouro=rng.choice(dados.LOGRADOUROS),
                numero=str(rng.randint(1, 2500)),
                complemento=rng.choice(("", "", "Apto 101", "Sala 3", "Casa 2")),
                bairro=rng.choice(dados.BAIRROS),
                cidade=rng.choice(cidades),
                cep=dados.cep(rng),
                **dono,
            )
            resumo["endereços"] += 1

    # ------------------------------------------------------------ consultas
    def _criar_consultas(self, opcoes, rng, pacientes, profissionais, resumo):
        """Agenda sem choque de horário para o mesmo profissional."""
        if not profissionais:
            return []
        hoje = timezone.localdate()
        base = self._primeiro_dia_util(hoje)
        ocupados = set()  # (profissional, data, hora)
        consultas = []
        for paciente in pacientes:
            quantas = rng.randint(0, 2 * opcoes["consultas"])
            candidatos = list(paciente.profissionais.all()) or profissionais
            # Sorteia em DIAS ÚTEIS a partir de hoje (negativo = passado), e não em
            # dias corridos: assim a agenda não depende do dia da semana em que o
            # comando roda, e a mesma semente gera sempre o mesmo conteúdo.
            deslocamentos = sorted(rng.randint(-65, 22) for _ in range(quantas))
            for posicao, deslocamento in enumerate(deslocamentos):
                data = self._dia_util(base, deslocamento)
                profissional = rng.choice(candidatos)
                hora = rng.choice(HORAS_DE_ATENDIMENTO)
                if (profissional.pk, data, hora) in ocupados:
                    continue
                ocupados.add((profissional.pk, data, hora))

                status, motivo = self._status(rng, data, hoje)
                consulta = Consulta.objects.create(
                    paciente=paciente,
                    profissional=profissional,
                    data_consulta=data,
                    hora_inicio=time(hora, 0),
                    hora_fim=time(hora, 50),
                    tipo_consulta=(
                        "avaliacao_inicial"
                        if posicao == 0
                        else rng.choices(
                            ("retorno", "sessao_grupo", "emergencia"), weights=(90, 6, 4)
                        )[0]
                    ),
                    status=status,
                    notas_sessao=(
                        rng.choice(dados.NOTAS_SESSAO) if status == "realizada" else ""
                    ),
                    motivo_cancelamento=motivo,
                )
                consultas.append(consulta)
                resumo["consultas"] += 1
                self._criar_lembrete(rng, consulta, hoje, resumo)
        return consultas

    @staticmethod
    def _primeiro_dia_util(dia):
        """O próprio dia, ou a segunda-feira seguinte se cair no fim de semana."""
        return dia + timedelta(days=(7 - dia.weekday()) if dia.weekday() >= 5 else 0)

    @staticmethod
    def _dia_util(base, deslocamento):
        """O dia útil que fica `deslocamento` dias úteis depois de `base` (negativo = antes)."""
        passo = 1 if deslocamento >= 0 else -1
        dia, restantes = base, abs(deslocamento)
        while restantes:
            dia += timedelta(days=passo)
            if dia.weekday() < 5:
                restantes -= 1
        return dia

    @staticmethod
    def _status(rng, data, hoje):
        """(status, motivo_cancelamento) coerentes com a data da consulta."""
        if data < hoje:
            status = rng.choices(("realizada", "falta", "cancelada"), weights=(70, 10, 20))[0]
        else:
            status = rng.choices(
                ("agendada", "confirmada", "reagendada", "cancelada"), weights=(45, 40, 10, 5)
            )[0]
        motivo = rng.choice(dados.MOTIVOS_CANCELAMENTO) if status == "cancelada" else ""
        return status, motivo

    @staticmethod
    def _criar_lembrete(rng, consulta, hoje, resumo):
        # Os sorteios acontecem SEMPRE, na mesma ordem. Se fossem pulados em
        # alguns casos, o resto dos dados mudaria conforme o dia/hora da execução.
        sorteio = rng.random()
        tipo = rng.choice(("email", "sms", "whatsapp", "telefone"))
        atraso = rng.randint(1, 20)

        if consulta.status in ("cancelada", "falta") or sorteio < 0.3:
            return  # só uma parte das consultas tem lembrete
        dia_envio = consulta.data_consulta - timedelta(days=1)
        envio = timezone.make_aware(datetime.combine(dia_envio, time(9, 0)))
        enviado = dia_envio < hoje  # decidido pela data, não pela hora do relógio
        Lembrete.objects.create(
            consulta=consulta,
            tipo_lembrete=tipo,
            data_hora_envio=envio,
            enviado_em=envio + timedelta(minutes=atraso) if enviado else None,
            status="enviado" if enviado else "pendente",
        )
        resumo["lembretes"] += 1

    # -------------------------------------------------- espera e prontuários
    @staticmethod
    def _criar_lista_espera(rng, pacientes, profissionais, resumo):
        for paciente in rng.sample(pacientes, k=len(pacientes) // 8):
            ListaEspera.objects.create(
                paciente=paciente,
                profissional_preferido=rng.choice(profissionais + [None]) if profissionais else None,
                dias_preferidos=rng.sample(DIAS_SEMANA, k=rng.randint(1, 3)),
                horario_preferido=rng.choice(("manha", "tarde", "noite", "qualquer")),
                prioridade=rng.choices(
                    ("urgente", "alta", "normal", "baixa"), weights=(10, 25, 50, 15)
                )[0],
                observacoes=rng.choice(dados.OBSERVACOES_ESPERA),
                status=rng.choices(("ativa", "agendada", "cancelada"), weights=(70, 20, 10))[0],
            )
            resumo["lista de espera"] += 1

    @staticmethod
    def _criar_prontuarios(rng, consultas, resumo):
        """Um prontuário para parte das consultas realizadas, escrito pelo profissional dela."""
        for consulta in consultas:
            if consulta.status != "realizada" or rng.random() > 0.75:
                continue
            codigo, descricao = rng.choice(dados.CIDS)
            Prontuario.objects.create(
                paciente=consulta.paciente,
                profissional=consulta.profissional,
                consulta=consulta,
                data_registro=consulta.data_consulta,
                codigo_cid=codigo,
                queixa_principal=rng.choice(dados.QUEIXAS),
                plano_tratamento=rng.choice(dados.PLANOS),
                evolucao=f"{rng.choice(dados.EVOLUCOES)} (Hipótese: {descricao}. Dado fictício.)",
                medicamentos=rng.choice(dados.MEDICAMENTOS),
                avaliacao_risco=rng.choice(dados.AVALIACOES_RISCO),
            )
            resumo["prontuários"] += 1

    # ------------------------------------------ apps opcionais (release 2)
    @staticmethod
    def _criar_salas(rng, consultas, resumo):
        Sala = apps.get_model("salas", "Sala")
        AgendaSala = apps.get_model("salas", "AgendaSala")
        salas = [
            Sala.objects.create(numero_sala=str(n), nome=nome, capacidade=capacidade)
            for n, (nome, capacidade) in enumerate(
                (("Sala Azul", 1), ("Sala Verde", 1), ("Sala de Grupo", 8)), start=1
            )
        ]
        resumo["salas"] += len(salas)
        ocupadas = set()
        for consulta in consultas:
            if consulta.status in ("cancelada", "falta"):
                continue
            livres = [
                s for s in salas
                if (s.pk, consulta.data_consulta, consulta.hora_inicio) not in ocupadas
            ]
            if not livres:
                continue
            sala = rng.choice(livres)
            ocupadas.add((sala.pk, consulta.data_consulta, consulta.hora_inicio))
            AgendaSala.objects.create(
                sala=sala,
                consulta=consulta,
                data=consulta.data_consulta,
                hora_inicio=consulta.hora_inicio,
                hora_fim=consulta.hora_fim,
            )
            resumo["agenda de salas"] += 1

    @staticmethod
    def _criar_faturamentos(rng, consultas, resumo):
        Faturamento = apps.get_model("faturamentos", "Faturamento")
        hoje = timezone.localdate()
        for consulta in consultas:
            if consulta.status != "realizada":
                continue
            valor = Decimal(consulta.profissional.valor_hora)
            paciente = consulta.paciente
            antigo = (hoje - consulta.data_consulta).days > 30
            situacao = rng.choices(
                ("pago", "parcialmente_pago", "atrasado") if antigo else ("pendente", "pago"),
                weights=(60, 20, 20) if antigo else (50, 50),
            )[0]
            pago = {"pago": valor, "parcialmente_pago": valor / 2}.get(situacao, Decimal(0))
            Faturamento.objects.create(
                paciente=paciente,
                consulta=consulta,
                data_servico=consulta.data_consulta,
                valor_cobrado=valor,
                valor_pago=pago,
                valor_convenio=(
                    (valor * Decimal("0.7")).quantize(Decimal("0.01"))
                    if paciente.convenio
                    else None
                ),
                metodo_pagamento=(
                    "convenio" if paciente.convenio
                    else rng.choice(("pix", "dinheiro", "cartao_credito", "cartao_debito"))
                ) if pago else "",
                status_pagamento=situacao,
                numero_nota=str(rng.randint(1000, 99999)) if situacao == "pago" else "",
            )
            resumo["faturamentos"] += 1

    # ---------------------------------------------------------------- saída
    def _imprimir(self, resumos, logins, senha):
        self.stdout.write(self.style.SUCCESS("Dados fictícios criados."))
        for resumo in resumos:
            clinica = resumo.pop("clinica")
            itens = ", ".join(f"{total} {nome}" for nome, total in resumo.items())
            self.stdout.write(f"\n{clinica.nome} ({clinica.slug}): {itens}")
        self.stdout.write("\nLogins (todos com a mesma senha):")
        for clinica, papel, email in logins:
            self.stdout.write(f"  {clinica:<20} {papel:<28} {email}")
        self.stdout.write(f"\nSenha: {senha}")
        self.stdout.write(
            "Para apagar tudo isto: python manage.py popular_dados_ficticios --remover"
        )
