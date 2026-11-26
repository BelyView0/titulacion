"""Búsqueda de texto compatible con SQLite y PostgreSQL.

En PostgreSQL usa la extensión unaccent; en SQLite (y otros) cae a icontains.
"""
from django.db import connection
from django.db.models import Q


def soporta_unaccent():
    return connection.vendor == 'postgresql'


def q_busca(term, *fields):
    """
    Construye un Q OR sobre los campos dados.

    Ejemplo:
        qs.filter(q_busca(q, 'first_name', 'last_name', 'username'))
        qs.filter(q_busca(q, 'alumno__first_name', 'alumno__numero_control'))
    """
    term = (term or '').strip()
    if not term or not fields:
        return Q()

    lookup = 'unaccent__icontains' if soporta_unaccent() else 'icontains'
    query = Q()
    for field in fields:
        query |= Q(**{f'{field}__{lookup}': term})
    return query
