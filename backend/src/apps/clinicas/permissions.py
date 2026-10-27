"""
Mixins que ligam uma view à permissão do papel (`Membro.grupo`) na clínica atual.

Cada view declara a AÇÃO que executa; a permissão completa é montada com o model
da própria view, no padrão do Django (`app_label.<acao>_<model>`):

    class ProfissionalDeleteView(PermissaoExcluir, DeleteView):
        model = Profissional
        # exige "profissionais.delete_profissional"

Comportamento (herdado do `PermissionRequiredMixin` do Django):

* não autenticado   -> redireciona para o login;
* autenticado sem a permissão -> 403 (vale para GET *e* POST: a checagem roda
  antes de qualquer lógica da view, então nada é lido nem alterado).

O mixin precisa vir ANTES da view genérica na herança (`(PermissaoVer, ListView)`).
"""

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ImproperlyConfigured


class PermissaoDoModeloMixin(PermissionRequiredMixin):
    """Exige `<acao_permissao>_<model>` do model da view."""

    # "view", "add", "change" ou "delete" (as quatro permissões padrão do Django).
    acao_permissao = None

    def get_permission_required(self):
        # Quem quiser uma permissão específica (ex.: "app.codename" própria)
        # pode definir `permission_required` na view e este mixin não interfere.
        if self.permission_required is not None:
            return super().get_permission_required()

        if self.acao_permissao is None:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} precisa definir `acao_permissao` "
                "(ou `permission_required`)."
            )
        modelo = getattr(self, "model", None)
        if modelo is None:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} precisa definir `model` para o "
                "mixin montar a permissão."
            )
        opcoes = modelo._meta
        return [f"{opcoes.app_label}.{self.acao_permissao}_{opcoes.model_name}"]


class PermissaoVer(PermissaoDoModeloMixin):
    """Listas, detalhes e relatórios: `view_<model>`."""

    acao_permissao = "view"


class PermissaoAdicionar(PermissaoDoModeloMixin):
    """Telas de cadastro: `add_<model>`."""

    acao_permissao = "add"


class PermissaoAlterar(PermissaoDoModeloMixin):
    """Telas de edição: `change_<model>`."""

    acao_permissao = "change"


class PermissaoExcluir(PermissaoDoModeloMixin):
    """Telas de exclusão: `delete_<model>`."""

    acao_permissao = "delete"
