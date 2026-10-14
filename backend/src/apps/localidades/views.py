from django.http import JsonResponse

from .models import Cidade


def cidades_por_estado(request):
    """Cidades de um estado, em JSON: GET ?estado=<id> -> [{"id": 1, "nome": "..."}]."""
    try:
        estado_id = int(request.GET.get("estado", ""))
    except ValueError:
        return JsonResponse([], safe=False)

    cidades = Cidade.objects.filter(estado_id=estado_id).order_by("nome")
    return JsonResponse(list(cidades.values("id", "nome")), safe=False)
