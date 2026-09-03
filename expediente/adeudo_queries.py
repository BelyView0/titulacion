"""Consultas reutilizables para confirmación de adeudos por área."""
from django.db.models import Q

from expediente.models import EstadoExpediente, Expediente


def expedientes_adeudo_pendientes(area):
    """
    Expedientes en revisión de adeudos que el área aún no ha liberado:
    - sin confirmación del área, o
    - confirmados con adeudos (para poder marcar sin adeudos después de resolver).
    """
    return Expediente.objects.filter(
        estado=EstadoExpediente.ADEUDOS_EN_REVISION,
    ).filter(
        Q(~Q(confirmaciones_adeudo__area=area))
        | Q(confirmaciones_adeudo__area=area, confirmaciones_adeudo__sin_adeudos=False)
    ).distinct().select_related(
        'alumno', 'alumno__carrera', 'modalidad',
    ).prefetch_related('confirmaciones_adeudo').order_by('-fecha_ultima_actualizacion')


def expedientes_liberados(area, limite=20):
    return Expediente.objects.filter(
        confirmaciones_adeudo__area=area,
        confirmaciones_adeudo__sin_adeudos=True,
    ).select_related('alumno', 'alumno__carrera').order_by('-confirmaciones_adeudo__fecha')[:limite]


def expedientes_con_adeudos(area, limite=20):
    return Expediente.objects.filter(
        confirmaciones_adeudo__area=area,
        confirmaciones_adeudo__sin_adeudos=False,
    ).select_related('alumno', 'alumno__carrera').order_by('-confirmaciones_adeudo__fecha')[:limite]
