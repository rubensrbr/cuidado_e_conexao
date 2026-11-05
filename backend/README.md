# Cuidado e Conexão

Aplicação web simples para clínicas de saúde gerenciarem **pacientes, profissionais, consultas e faturamento**, com suporte a várias clínicas na mesma instalação.

Feita com Django, PostgreSQL e Docker. A interface é em português do Brasil.

## O que ela faz

- **Clínicas e usuários**: cada clínica enxerga apenas os próprios dados. O login é feito com e-mail, e cada usuário tem um papel (Administração, Recepção ou Somente leitura).
- **Pacientes**: dados pessoais, telefones, endereços, convênio, prontuários e marcação de atendimento *pro bono*.
- **Profissionais**: cadastro, especialização, valor da hora e disponibilidade semanal.
- **Consultas**: agendamento, acompanhamento de status, lembretes, lista de espera e relatórios em PDF.
- **Faturamento**: pagamentos por consulta, pacotes de sessões (por exemplo, 4 sessões pagas de uma vez) e atendimentos pro bono.

> As salas (`salas`) existem no código, mas não vêm ativadas por padrão. Os apps opcionais ficam em `OPTIONAL_APPS`, em `backend/src/settings.py`.

## Requisitos

- [Docker](https://docs.docker.com/get-docker/) com Docker Compose
- [Task](https://taskfile.dev/installation/) (um executor de comandos simples; todos os comandos abaixo usam ele)

## Primeiros passos

```bash
cd backend
task setup
```

Isso cria o arquivo `.env`, constrói as imagens, sobe a aplicação e o banco de dados e roda as migrações.

Antes da primeira execução, abra o `backend/.env` e preencha os dados do banco:

```env
POSTGRES_DB=cuidado_e_conexao
POSTGRES_USER=cuidado
POSTGRES_PASSWORD=escolha-uma-senha
```

Depois, crie seu usuário administrador e acesse **http://localhost:8000**:

```bash
task createsuperuser
```

## Testando com dados de exemplo

Preenche o banco com clínicas, pacientes, consultas e faturamento fictícios:

```bash
task seed                                  # 2 clínicas, quantidades padrão
task seed -- --clinicas 3 --pacientes 50   # personaliza as quantidades
task seed -- --recriar                     # apaga os dados de exemplo e cria de novo
task seed -- --remover                     # remove só os dados de exemplo
```

Os dados de exemplo são identificáveis (clínicas `demo-1`, `demo-2`… e e-mails terminados em `@demo.example`), então seus dados reais nunca são tocados. O comando só roda em desenvolvimento.

Entre com qualquer e-mail listado no final da execução, por exemplo `admin.demo-1@demo.example`, usando a senha `Demo#Clinica2026`.

## Comandos do dia a dia

| Comando | O que faz |
| --- | --- |
| `task up` / `task down` | Sobe / para a aplicação |
| `task logs` | Acompanha os logs |
| `task test` | Roda os testes (`task test -- faturamentos` para um app) |
| `task migrate` | Aplica as migrações do banco |
| `task makemigrations` | Cria novas migrações |
| `task shell` | Shell do Django com todos os models carregados |
| `task dbshell` | Abre o `psql` no banco |
| `task reset-db` | Apaga o banco e recomeça do zero (pede confirmação) |
| `task` | Lista todos os comandos disponíveis |

## Estrutura do projeto

```
backend/
├── compose.yaml          # aplicação + banco (extras de dev em compose.override.yaml)
├── Taskfile.yml          # todos os comandos do task
├── pyproject.toml        # dependências (gerenciadas com uv)
└── src/
    ├── settings.py
    └── apps/
        ├── core/          # login, usuários, itens compartilhados, comando de dados de exemplo
        ├── clinicas/      # clínicas, papéis e permissões
        ├── pacientes/     # pacientes e prontuários
        ├── profissionais/ # profissionais e disponibilidade
        ├── consultas/     # consultas, lembretes, lista de espera
        ├── faturamentos/  # pagamentos, pacotes, pro bono
        ├── telefones/ enderecos/ localidades/
        └── salas/         # salas (opcional)
```

## Produção

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d
```

Antes, defina `DEBUG = False` e troque a `SECRET_KEY` em `settings.py`. O comando de dados de exemplo se recusa a rodar com `DEBUG` desligado.

## Licença

Veja [LICENSE](LICENSE).
