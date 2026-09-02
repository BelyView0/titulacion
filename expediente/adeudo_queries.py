"""Consultas reutilizables para confirmación de adeudos por área."""
from expediente.models import EstadoExpediente, Expediente


def expedientes_adeudo_pendientes(area):
    return Expediente.objects.filter(
        estado=EstadoExpediente.ADEUDOS_EN_REVISION,
    ).exclude(
        confirmaciones_adeudo__area=area,
    ).select_related('alumno', 'alumno__carrera', 'modalidad').order_by('-fecha_ultima_actualizacion')


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
