from django.db import models
from core.models import BaseModel


class Paciente(BaseModel):
    """Informações dos pacientes"""

    GENERO_CHOICES = [
        ("masculino", "Masculino"),
        ("feminino", "Feminino"),
        ("nao_binario", "Não-binário"),
        ("outro", "Outro"),
        ("prefiro_nao_informar", "Prefiro não informar"),
    ]

    primeiro_nome = models.CharField(
        max_length=100,
        verbose_name="Primeiro Nome",
    )
    sobrenome = models.CharField(
        max_length=100,
        verbose_name="Sobrenome",
    )
    data_nascimento = models.DateField(
        verbose_name="Data de Nascimento",
    )
    genero = models.CharField(
        max_length=30,
        choices=GENERO_CHOICES,
        verbose_name="Gênero",
    )
    email = models.EmailField(
        max_length=150,
        blank=True,
        verbose_name="E-mail",
    )

    # Informações do convênio
    convenio = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Convênio",
    )

    numero_carteirinha = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Número da Carteirinha",
    )

    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
    )

    class Meta:
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"
        ordering = ["sobrenome", "primeiro_nome"]

    def __str__(self):
        return f"{self.primeiro_nome} {self.sobrenome}"

    @property
    def nome_completo(self):
        return f"{self.primeiro_nome} {self.sobrenome}"


class Prontuario(BaseModel):
    """Prontuário médico/psicológico do paciente"""

    paciente = models.ForeignKey(
        "pacientes.Paciente",
        on_delete=models.CASCADE,
        related_name="prontuarios",
        verbose_name="Paciente",
    )
    profissional = models.ForeignKey(
        "profissionais.Profissional",
        on_delete=models.CASCADE,
        related_name="prontuarios",
        verbose_name="Profissional",
    )
    consulta = models.ForeignKey(
        "consultas.Consulta",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prontuarios",
        verbose_name="Consulta",
    )
    data_registro = models.DateField(verbose_name="Data do Registro")
    codigo_cid = models.CharField(
        max_length=20, blank=True, verbose_name="Código CID-10"
    )
    queixa_principal = models.TextField(blank=True, verbose_name="Queixa Principal")
    plano_tratamento = models.TextField(blank=True, verbose_name="Plano de Tratamento")
    evolucao = models.TextField(blank=True, verbose_name="Evolução")
    medicamentos = models.TextField(blank=True, verbose_name="Medicamentos")
    avaliacao_risco = models.TextField(blank=True, verbose_name="Avaliação de Risco")

    class Meta:
        verbose_name = "Prontuário"
        verbose_name_plural = "Prontuários"
        ordering = ["-data_registro"]

    def __str__(self):
        return f"Prontuário {self.paciente.nome_completo} - {self.data_registro}"
