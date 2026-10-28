from django.http import QueryDict
from django.shortcuts import redirect


class FiltrosPersistentesMixin:
    """
    Lembra os filtros de uma lista (ListView com django-filter) na sessão.

    Quem abre a lista sem filtros na URL (voltando de editar/excluir, pelo menu,
    pelo "Cancelar"...) é redirecionado para a mesma lista com os últimos filtros
    aplicados. Só o botão "Limpar" (`?limpar=1`) esquece os filtros.

    Uso: `class MinhaLista(FiltrosPersistentesMixin, ListView)` com
    `filterset_class = MeuFilter`. Os filtros ficam separados por lista e por
    clínica (um id de profissional da clínica A não vale na clínica B).
    A página (`page`) não é guardada: só os filtros.
    """

    filterset_class = None
    parametro_limpar = "limpar"

    def nomes_dos_filtros(self):
        return list(self.filterset_class.base_filters)

    def chave_da_sessao(self):
        clinica = getattr(self.request, "clinica", None)
        clinica_uuid = clinica.uuid if clinica else "sem-clinica"
        return f"filtros:{self.request.resolver_match.view_name}:{clinica_uuid}"

    def get(self, request, *args, **kwargs):
        chave = self.chave_da_sessao()

        if self.parametro_limpar in request.GET:
            request.session.pop(chave, None)
            return redirect(request.path)

        nomes = self.nomes_dos_filtros()

        if any(nome in request.GET for nome in nomes):
            # O formulário foi enviado: guarda só o que foi preenchido
            # (formulário todo vazio = sem filtros).
            filtros = {}
            for nome in nomes:
                valores = [v.strip() for v in request.GET.getlist(nome) if v.strip()]
                if valores:
                    filtros[nome] = valores
            if filtros:
                request.session[chave] = filtros
            else:
                request.session.pop(chave, None)
        else:
            filtros = request.session.get(chave)
            if filtros:
                parametros = QueryDict(mutable=True)
                for nome, valores in filtros.items():
                    parametros.setlist(nome, valores)
                if "page" in request.GET:
                    parametros["page"] = request.GET["page"]
                return redirect(f"{request.path}?{parametros.urlencode()}")

        return super().get(request, *args, **kwargs)
