"""
Infraestrutura de multi-tenancy (uma clínica = um tenant).

Estratégia: banco e schema compartilhados, com uma ForeignKey `clinica` em cada
tabela que pertence a uma clínica. A "clínica atual" fica numa ContextVar
(definida pelo middleware a cada requisição) e o manager padrão dos modelos
filtra por ela automaticamente.

Regras importantes:
- Sem clínica atual o manager devolve NADA (falha fechada), nunca "tudo".
- `Modelo.todas` é o manager SEM filtro: use só em admin da plataforma,
  comandos de manutenção e testes.
- `Model.objects` é o manager padrão (`_default_manager`), então ModelForms
  (ModelChoiceField) e relações reversas (`paciente.consultas`) já são
  filtrados por clínica sem código extra.
"""

from contextlib import contextmanager
from contextvars import ContextVar

from django.db import models

from core.models import BaseModel

_clinica_atual: ContextVar = ContextVar("clinica_atual", default=None)


def get_clinica_atual():
    return _clinica_atual.get()


def set_clinica_atual(clinica):
    """Define a clínica atual e devolve um token para `reset_clinica_atual`."""
    return _clinica_atual.set(clinica)


def reset_clinica_atual(token):
    _clinica_atual.reset(token)


@contextmanager
def clinica_atual(clinica):
    """
    Executa um bloco como se `clinica` fosse a clínica atual.

        with clinica_atual(clinica):
            Paciente.objects.all()   # só pacientes dessa clínica

    Útil em testes, comandos de gerenciamento, shell e tarefas em segundo plano.
    """
    token = set_clinica_atual(clinica)
    try:
        yield clinica
    finally:
        reset_clinica_atual(token)


class SemClinicaAtual(Exception):
    """Tentativa de gravar dados de uma clínica sem haver clínica atual."""


class ClinicaIncorreta(Exception):
    """Tentativa de gravar dados de uma clínica diferente da clínica atual."""


class TenantQuerySet(models.QuerySet):
    def bulk_create(self, objs, *args, **kwargs):
        # bulk_create não chama save(), então preenchemos a clínica aqui.
        objs = list(objs)
        for obj in objs:
            obj._definir_clinica()
        return super().bulk_create(objs, *args, **kwargs)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    def get_queryset(self):
        queryset = super().get_queryset()
        clinica = get_clinica_atual()
        if clinica is None:
            return queryset.none()
        return queryset.filter(clinica=clinica)


class TenantModel(BaseModel):
    """
    Base abstrata para tudo que pertence a uma clínica.

    - `clinica` é preenchida automaticamente a partir da clínica atual e não
      aparece em formulários nem no admin (editable=False).
    - Gravar com uma clínica diferente da atual é bloqueado.
    """

    clinica = models.ForeignKey(
        "clinicas.Clinica",
        on_delete=models.PROTECT,
        editable=False,
        verbose_name="Clínica",
    )

    objects = TenantManager()  # primeiro manager = _default_manager
    todas = models.Manager()  # sem filtro de clínica (uso restrito)

    class Meta:
        abstract = True

    def _definir_clinica(self):
        atual = get_clinica_atual()
        if self.clinica_id is None:
            if atual is None:
                raise SemClinicaAtual(
                    f"Não há clínica atual para gravar {self.__class__.__name__}."
                )
            self.clinica = atual
        elif atual is not None and self.clinica_id != atual.pk:
            raise ClinicaIncorreta(
                f"{self.__class__.__name__} pertence a outra clínica."
            )

    def save(self, *args, **kwargs):
        self._definir_clinica()
        super().save(*args, **kwargs)
