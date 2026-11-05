# O status de pagamento passa a ser derivado dos valores (ver
# `faturamentos.models.status_do_pagamento`). Esta migração corrige os
# faturamentos já gravados com status que contradiz os valores — por exemplo
# "pendente" com tudo pago —, que faziam o Resumo discordar de si mesmo.
#
# A regra é copiada aqui de propósito: uma migração não deve depender de código
# que pode mudar depois. "cancelado" nunca é alterado; "atrasado" é mantido
# enquanto falta pagar.

from decimal import Decimal

from django.db import migrations

ZERO = Decimal("0")


def status_correto(faturamento):
    if faturamento.status_pagamento == "cancelado":
        return "cancelado"
    cobrado = faturamento.valor_cobrado or ZERO
    pago = faturamento.valor_pago or ZERO
    if cobrado > ZERO and pago >= cobrado:
        calculado = "pago"
    elif pago > ZERO:
        calculado = "parcialmente_pago"
    elif faturamento.pro_bono:
        calculado = "pago"
    else:
        calculado = "pendente"
    if faturamento.status_pagamento == "atrasado" and calculado != "pago":
        return "atrasado"
    return calculado


def corrigir_status(apps, schema_editor):
    db = schema_editor.connection.alias
    Faturamento = apps.get_model("faturamentos", "Faturamento")
    # `_base_manager`: sem filtro de clínica (não há clínica atual numa migração).
    corrigidos = []
    for faturamento in Faturamento._base_manager.using(db).iterator():
        novo = status_correto(faturamento)
        if novo != faturamento.status_pagamento:
            faturamento.status_pagamento = novo
            corrigidos.append(faturamento)
    Faturamento._base_manager.using(db).bulk_update(
        corrigidos, ["status_pagamento"], batch_size=500
    )


class Migration(migrations.Migration):

    dependencies = [
        ("faturamentos", "0006_proteger_historico_financeiro"),
    ]

    operations = [
        # Reverter não restaura os status antigos (eles eram inconsistentes).
        migrations.RunPython(corrigir_status, migrations.RunPython.noop),
    ]
