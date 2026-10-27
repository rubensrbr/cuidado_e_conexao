"""
Backend de permissões por clínica.

No Django padrão, `user.has_perm("app.acao_modelo")` consulta os grupos e as
permissões ligados ao PRÓPRIO USUÁRIO, valendo em qualquer lugar. Aqui o papel de
uma pessoa depende da clínica: ela pode ser administradora numa e recepção em
outra. Por isso o papel fica em `Membro.grupo`, e este backend faz o
`has_perm` olhar para ele:

    permissões de quem está logado = permissões do `grupo` do seu `Membro`
                                     na CLÍNICA ATUAL

Regras:

* Sem clínica atual, sem vínculo, vínculo inativo ou clínica suspensa:
  nenhuma permissão. (Mesmo critério do `ClinicaAtualMiddleware`.)
* Os grupos e as permissões ligados diretamente ao usuário (`user.groups`,
  `user.user_permissions`) NÃO concedem nada: se valessem, o papel de uma clínica
  vazaria para as outras. Só `Membro.grupo` conta.
* Superusuário continua com tudo. Isso não é deste backend: o próprio
  `PermissionsMixin.has_perm` do Django responde `True` antes de consultá-lo.

Herda de `ModelBackend` para manter o login (`authenticate`) e a regra de
usuário inativo; só a parte de permissões muda.
"""

from django.contrib.auth.backends import ModelBackend

from .tenancy import get_clinica_atual


class MembroBackend(ModelBackend):
    # Nome do atributo onde o resultado fica guardado no objeto do usuário
    # (o equivalente ao `_perm_cache` do Django, mas separado por clínica).
    CACHE_ATTR = "_permissoes_do_papel_por_clinica"

    def get_user_permissions(self, user_obj, obj=None):
        # Permissões soltas no usuário não existem neste modelo.
        return set()

    def get_group_permissions(self, user_obj, obj=None):
        return self.get_all_permissions(user_obj, obj)

    def get_all_permissions(self, user_obj, obj=None):
        # Sem permissões por objeto (não usamos django-guardian & cia).
        if not user_obj.is_active or user_obj.is_anonymous or obj is not None:
            return set()

        clinica = get_clinica_atual()
        if clinica is None:
            return set()

        # Guardado por clínica: o mesmo objeto de usuário pode ser consultado
        # com clínicas atuais diferentes (testes, comandos, shell).
        cache = user_obj.__dict__.setdefault(self.CACHE_ATTR, {})
        if clinica.pk not in cache:
            cache[clinica.pk] = self._permissoes_do_papel(user_obj, clinica)
        return cache[clinica.pk]

    @staticmethod
    def _permissoes_do_papel(user_obj, clinica):
        # Import tardio: este módulo é carregado pelo sistema de autenticação
        # antes de os models estarem prontos.
        from django.contrib.auth.models import Permission

        from .models import Membro

        grupo_id = (
            Membro.objects.filter(
                user=user_obj, clinica=clinica, ativo=True, clinica__ativa=True
            )
            .values_list("grupo_id", flat=True)
            .first()
        )
        if grupo_id is None:
            return set()

        permissoes = Permission.objects.filter(group__pk=grupo_id).values_list(
            "content_type__app_label", "codename"
        )
        return {f"{app_label}.{codename}" for app_label, codename in permissoes}
