"""Servicios SIGET — generación automática de documentos."""
from django.utils import timezone

from expediente.models import EstadoExpediente, ConfirmacionAdeudo
from expediente.workflow import todas_confirmaciones_adeudo
from expediente.notifications import registrar_cambio_estado, notificar_alumno, notificar_oficina_titulacion


def intentar_generar_constancia_no_adeudos(expediente, realizado_por=None):
    """Genera constancia de no adeudos cuando las 3 áreas confirman."""
    if expediente.constancia_no_adeudos:
        return False
    if not todas_confirmaciones_adeudo(expediente):
        return False

    from oficina_titulacion.pdf_constancia import generar_constancia_no_adeudos_pdf
    pdf = generar_constancia_no_adeudos_pdf(expediente)
    if pdf:
        expediente.constancia_no_adeudos.save(
            f'constancia_no_adeudos_{expediente.pk}.pdf',
            pdf,
            save=False,
        )
    expediente.save(update_fields=['constancia_no_adeudos', 'fecha_ultima_actualizacion'])

    notificar_alumno(
        expediente,
        'AVANCE',
        'Constancia de no adeudos generada',
        'Se generó automáticamente su Constancia de no adeudos.',
    )
    notificar_oficina_titulacion(
        expediente,
        'Constancia de no adeudos generada',
        f'Se generó la constancia de no adeudos para {expediente.alumno.get_full_name()}.',
    )
    _verificar_documentos_oficiales_listos(expediente, realizado_por)
    return True


def registrar_confirmacion_adeudo(expediente, area, sin_adeudos, usuario, observaciones=''):
    conf, _ = ConfirmacionAdeudo.objects.update_or_create(
        expediente=expediente,
        area=area,
        defaults={
            'sin_adeudos': sin_adeudos,
            'confirmado_por': usuario,
            'observaciones': observaciones,
        },
    )
    from administracion.models import Rol
    rol_map = {
        ConfirmacionAdeudo.Area.FINANZAS: Rol.FINANZAS,
        ConfirmacionAdeudo.Area.CENTRO_COMPUTO: Rol.CENTRO_COMPUTO,
        ConfirmacionAdeudo.Area.CENTRO_INFORMACION: Rol.CENTRO_INFORMACION,
    }
    estado_txt = 'liberado' if sin_adeudos else 'con adeudos pendientes'
    from expediente.notifications import notificar_usuarios_por_rol
    notificar_usuarios_por_rol(
        [rol_map[area]],
        f'Alumno {estado_txt}',
        f'{expediente.alumno.get_full_name()} — {estado_txt} en {conf.get_area_display()}.',
        tipo='INFO' if sin_adeudos else 'URGENTE',
    )
    if sin_adeudos:
        intentar_generar_constancia_no_adeudos(expediente, usuario)
    return conf


def _verificar_documentos_oficiales_listos(expediente, realizado_por):
    if (
        expediente.constancia_no_inconveniencia
        and expediente.constancia_no_adeudos
        and expediente.estado == EstadoExpediente.ADEUDOS_EN_REVISION
    ):
        registrar_cambio_estado(
            expediente,
            EstadoExpediente.DOCUMENTOS_OFICIALES_LISTOS,
            realizado_por,
            'No inconveniencia y constancia de no adeudos completas.',
        )
        from administracion.models import Rol
        from expediente.notifications import notificar_usuarios_por_rol
        notificar_usuarios_por_rol(
            [Rol.JEFE_ACADEMIA, Rol.JEFE_PROYECTO],
            'Expediente listo para asignación de jurado',
            f'El expediente de {expediente.alumno.get_full_name()} está listo para jurado.',
        )
