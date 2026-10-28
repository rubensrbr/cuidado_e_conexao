"""Geradores de dados fictícios para o comando `popular_dados_ficticios`.

Só Python puro, sem banco e sem bibliotecas externas: tudo recebe um
`random.Random`, então a mesma semente gera sempre os mesmos dados (e a imagem
de produção, que não instala as dependências de desenvolvimento, não precisa de
nada a mais).
"""

import re
import unicodedata
from datetime import date, timedelta

from clinicas.validators import _digito_cnpj

NOMES_FEMININOS = (
    "Ana", "Beatriz", "Camila", "Daniela", "Eduarda", "Fernanda", "Gabriela",
    "Helena", "Isabela", "Juliana", "Karina", "Larissa", "Mariana", "Natália",
    "Olívia", "Patrícia", "Quitéria", "Rafaela", "Sabrina", "Tatiane",
    "Valentina", "Vitória", "Luiza", "Marina", "Renata", "Simone", "Aline",
    "Bianca", "Cláudia", "Débora",
)
NOMES_MASCULINOS = (
    "André", "Bruno", "Carlos", "Diego", "Eduardo", "Felipe", "Gustavo",
    "Henrique", "Igor", "João", "Kléber", "Lucas", "Marcelo", "Nelson",
    "Otávio", "Paulo", "Rafael", "Samuel", "Thiago", "Vinícius", "Wagner",
    "Rodrigo", "Fábio", "Leandro", "Matheus", "Pedro", "Ricardo", "Sérgio",
    "Túlio", "Ulisses",
)
SOBRENOMES = (
    "Silva", "Souza", "Oliveira", "Santos", "Pereira", "Lima", "Costa",
    "Ferreira", "Rodrigues", "Almeida", "Nascimento", "Carvalho", "Araújo",
    "Ribeiro", "Gomes", "Martins", "Rocha", "Barbosa", "Moreira", "Cardoso",
    "Teixeira", "Mendes", "Freitas", "Barros", "Pinto", "Moura", "Cavalcante",
    "Dias", "Castro", "Campos", "Correia", "Monteiro", "Vieira", "Nunes",
)

NOMES_CLINICA = (
    "Vida Plena", "Bem-Estar", "Equilíbrio", "Mente Aberta", "Caminhos",
    "Sol Nascente", "Acolher", "Horizonte",
)

CONVENIOS = ("Unimed", "Amil", "Bradesco Saúde", "SulAmérica", "Hapvida", "Cassi")

LOGRADOUROS = (
    "Rua das Flores", "Avenida Brasil", "Rua Goiás", "Rua Sete de Setembro",
    "Avenida Central", "Rua das Acácias", "Rua Quinze de Novembro",
    "Alameda dos Ipês", "Rua do Comércio", "Avenida Paulista",
)
BAIRROS = (
    "Centro", "Jardim América", "Vila Nova", "Setor Sul", "Bela Vista",
    "Parque Industrial", "Jardim das Palmeiras", "Santa Maria",
)

# (codigo_ibge_estado, sigla, nome, [(codigo_ibge_cidade, nome), ...])
# Usado só se a tabela de cidades estiver vazia (antes de `carregar_localidades`).
# São códigos reais do IBGE: a carga completa depois apenas atualiza estas linhas.
LOCALIDADES_PADRAO = (
    (52, "GO", "Goiás", [(5208707, "Goiânia"), (5201108, "Anápolis")]),
    (53, "DF", "Distrito Federal", [(5300108, "Brasília")]),
    (35, "SP", "São Paulo", [(3550308, "São Paulo"), (3509502, "Campinas")]),
    (33, "RJ", "Rio de Janeiro", [(3304557, "Rio de Janeiro")]),
    (31, "MG", "Minas Gerais", [(3106200, "Belo Horizonte")]),
    (23, "CE", "Ceará", [(2304400, "Fortaleza")]),
    (29, "BA", "Bahia", [(2927408, "Salvador")]),
    (41, "PR", "Paraná", [(4106902, "Curitiba")]),
    (43, "RS", "Rio Grande do Sul", [(4314902, "Porto Alegre")]),
)

CIDS = (
    ("F32.0", "episódio depressivo leve"),
    ("F33.1", "transtorno depressivo recorrente, episódio atual moderado"),
    ("F41.0", "transtorno de pânico"),
    ("F41.1", "ansiedade generalizada"),
    ("F43.1", "transtorno de estresse pós-traumático"),
    ("F90.0", "transtorno de déficit de atenção com hiperatividade"),
    ("F42.1", "transtorno obsessivo-compulsivo"),
    ("Z73.0", "esgotamento (burnout)"),
)

QUEIXAS = (
    "Relata dificuldade para dormir e preocupação constante nas últimas semanas.",
    "Refere desânimo e queda de interesse pelas atividades do dia a dia.",
    "Queixa de crises de ansiedade em situações de trabalho.",
    "Procura acompanhamento após perda familiar recente.",
    "Dificuldade de concentração e organização de rotina.",
    "Conflitos frequentes no relacionamento e irritabilidade.",
)
PLANOS = (
    "Sessões semanais de 50 minutos, com reavaliação em 8 semanas.",
    "Acompanhamento quinzenal e exercícios de regulação entre as sessões.",
    "Psicoeducação inicial, seguida de terapia focada em habilidades.",
    "Sessões semanais e encaminhamento para avaliação médica complementar.",
)
EVOLUCOES = (
    "Paciente colaborativo, relata melhora parcial do sono. Mantém o plano.",
    "Discutidas estratégias de enfrentamento; refere uso das técnicas em casa.",
    "Sessão focada em situações de trabalho. Humor estável, sem intercorrências.",
    "Retomada de atividades prazerosas. Segue em acompanhamento regular.",
)
MEDICAMENTOS = ("", "", "Sem medicação em uso.", "Em uso de medicação prescrita por outro profissional.")
AVALIACOES_RISCO = ("Sem risco aparente.", "Risco baixo; reavaliar na próxima sessão.", "")
NOTAS_SESSAO = (
    "Sessão realizada conforme planejado.",
    "Paciente chegou pontualmente e participou ativamente.",
    "Tema principal: rotina e qualidade do sono.",
    "Combinadas tarefas para a próxima semana.",
)
MOTIVOS_CANCELAMENTO = (
    "Paciente avisou que não poderá comparecer.",
    "Imprevisto de trabalho do paciente.",
    "Profissional indisponível no horário.",
    "Remarcação a pedido do paciente.",
)
OBSERVACOES_ESPERA = (
    "Prefere horários após o expediente.",
    "Aceita encaixe em caso de desistência.",
    "Indicação de outro paciente da clínica.",
    "",
)


def sem_acentos(texto: str) -> str:
    """\"João Álvaro\" -> \"Joao Alvaro\"."""
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def para_email(texto: str) -> str:
    """Só letras minúsculas e números: serve de parte local de e-mail."""
    return re.sub(r"[^a-z0-9]", "", sem_acentos(texto).lower())


def nome_pessoa(rng):
    """(primeiro_nome, sobrenome, gênero) de uma pessoa fictícia."""
    if rng.random() < 0.5:
        primeiro, genero = rng.choice(NOMES_FEMININOS), "feminino"
    else:
        primeiro, genero = rng.choice(NOMES_MASCULINOS), "masculino"
    sobrenome = rng.choice(SOBRENOMES)
    if rng.random() < 0.5:
        sobrenome = f"{sobrenome} {rng.choice(SOBRENOMES)}"
    # Uma pequena parte dos pacientes não informa o gênero binário.
    if rng.random() < 0.06:
        genero = rng.choice(("nao_binario", "outro", "prefiro_nao_informar"))
    return primeiro, sobrenome, genero


def cnpj_valido(rng) -> str:
    """CNPJ (14 dígitos) com dígitos verificadores corretos."""
    base = str(rng.randint(10_000_000, 99_999_999)) + "0001"
    d1 = _digito_cnpj(base)
    d2 = _digito_cnpj(base + d1)
    return base + d1 + d2


def telefone(rng, tipo: str) -> str:
    """Só dígitos, no formato aceito pelo model (DDD + número)."""
    ddd = rng.choice(("11", "21", "31", "41", "51", "61", "62", "71", "81", "85"))
    if tipo == "celular":
        return f"{ddd}9{rng.randint(10_000_000, 99_999_999)}"
    return f"{ddd}3{rng.randint(1_000_000, 9_999_999)}"


def cep(rng) -> str:
    return f"{rng.randint(10_000, 99_999)}-{rng.randint(100, 999)}"


def data_nascimento(rng, hoje: date) -> date:
    """Entre 6 e 85 anos de idade, com mais peso para adultos."""
    idade = rng.choice((rng.randint(6, 17), rng.randint(18, 60), rng.randint(18, 60), rng.randint(61, 85)))
    return hoje - timedelta(days=idade * 365 + rng.randint(0, 364))


def registro_profissional(rng, tipo_descricao: str) -> str:
    """Número de conselho plausível para o tipo de profissional."""
    tipo = sem_acentos(tipo_descricao).lower()
    numero = rng.randint(10_000, 99_999)
    if "psicolog" in tipo:
        return f"CRP {rng.randint(1, 24):02d}/{numero}"
    if "medic" in tipo or "psiquiatr" in tipo:
        return f"CRM {numero}"
    return f"REG {numero}"
