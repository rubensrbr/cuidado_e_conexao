"""
Configuração do gunicorn (lida automaticamente de /app/gunicorn.conf.py).

Fica num só lugar para o Dockerfile e o compose.prod.yaml não divergirem.
"""

import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("WEB_CONCURRENCY", 3))

# Logs na saída padrão, onde o Docker os coleta.
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info").lower()

# IMPORTANTE: logar só o caminho (%(U)s), nunca a requisição inteira (%(r)s) nem
# a query string (%(q)s). A busca de pacientes é um GET (?busca=Nome+Sobrenome),
# então a query string contém dados pessoais.
access_log_format = '%(h)s "%(m)s %(U)s" %(s)s %(b)s %(L)ss'
