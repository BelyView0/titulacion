"""
Funciones compartidas de flujo de trabajo del expediente SIGET.
Validación única por Oficina de Titulación.
"""
from expediente.models import (
    Expediente, Documento, ValidacionDocumento,
    EstadoExpediente, EstadoDocumento, EstadoValidacion,
    CitaDocumentoFisico,
)


def verificar_documento_aprobado(documento):
    """Un documento está aprobado si su estado es APROBADO."""
    return documento.estado == EstadoDocumento.APROBADO


def actualizar_estado_documento(documento, realizado_por=None):
    """
    Actualiza el estado del documento según la validación única de Oficina.
    Si hay rechazo, regresa el expediente a corrección.
    """
    validacion = getattr(documento, 'validacion', None)
    if not validacion:
        return

    rechazo_detectado = False
    if validacion.estado == EstadoValidacion.APROBADO:
        documento.estado = EstadoDocumento.APROBADO
        documento.revisado_por = validacion.validado_por
        documento.observaciones_revision = validacion.observaciones
        documento.fecha_revision = validacion.fecha
    elif validacion.estado in (EstadoValidacion.RECHAZADO, EstadoValidacion.REQUIERE_CORRECCION):
        documento.estado = (
            EstadoDocumento.RECHAZADO
            if validacion.estado == EstadoValidacion.RECHAZADO
            else EstadoDocumento.REQUIERE_CORRECCION
        )
        documento.revisado_por = validacion.validado_por
        documento.observaciones_revision = validacion.observaciones
        documento.fecha_revision = validacion.fecha
        rechazo_detectado = True
    elif validacion.estado == EstadoValidacion.PENDIENTE and documento.archivo:
        documento.estado = EstadoDocumento.EN_REVISION
    documento.save()

    if rechazo_detectado and realizado_por:
        expediente = documento.expediente
        if expediente.estado not in (EstadoExpediente.CARGA_DOCUMENTOS, EstadoExpediente.EN_CORRECCION):
            from expediente.notifications import registrar_cambio_estado
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.EN_CORRECCION,
                realizado_por=realizado_por,
                descripcion=(
                    f'Rechazo en documento "{documento.tipo_documento.nombre}". '
                    'El expediente regresa a corrección.'
                ),
            )


def cita_certificado_confirmada(expediente):
    """True si el alumno confirmó (o ya completó) la cita de certificado."""
    return expediente.citas_fisicas.filter(
        tipo=CitaDocumentoFisico.TipoCita.CERTIFICADO,
        estado__in=(
            CitaDocumentoFisico.EstadoCita.CONFIRMADA_ALUMNO,
            CitaDocumentoFisico.EstadoCita.COMPLETADA,
        ),
    ).exists()


def habilitar_carga_documentos(expediente, realizado_por=None):
    """
    Habilita la carga de documentos tras cita confirmada y certificado firmado.
    Retorna True si el expediente avanzó a CARGA_DOCUMENTOS.
    """
    if expediente.estado in (
        EstadoExpediente.CARGA_DOCUMENTOS,
        EstadoExpediente.EN_REVISION,
        EstadoExpediente.EN_CORRECCION,
    ):
        return False

    if not cita_certificado_confirmada(expediente):
        return False

    if expediente.estado not in (
        EstadoExpediente.CERTIFICADO_FIRMADO,
        EstadoExpediente.CERTIFICADO_CITA_PROGRAMADA,
    ):
        return False

    from expediente.notifications import registrar_cambio_estado, notificar_alumno

    if expediente.estado == EstadoExpediente.CERTIFICADO_CITA_PROGRAMADA:
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.CERTIFICADO_FIRMADO,
            realizado_por=realizado_por,
            descripcion='Certificado firmado en cita confirmada por el alumno.',
        )

    registrar_cambio_estado(
        expediente=expediente,
        estado_nuevo=EstadoExpediente.CARGA_DOCUMENTOS,
        realizado_por=realizado_por,
        descripcion='Certificado firmado y cita confirmada. El alumno puede cargar sus documentos.',
    )
    notificar_alumno(
        expediente=expediente,
        tipo='AVANCE',
        titulo='Carga de documentos habilitada',
        mensaje=(
            'Tu certificado fue firmado y la cita quedó confirmada. '
            'Ya puedes cargar tus documentos y enviarlos a revisión de Oficina de Titulación.'
        ),
    )
    return True


def verificar_avance_expediente(expediente):
    """Si todos los documentos obligatorios están aprobados, avanza a expediente aprobado."""
    if not expediente.todos_documentos_aprobados():
        return False

    if expediente.estado in (
        EstadoExpediente.EN_REVISION,
        EstadoExpediente.CARGA_DOCUMENTOS,
        EstadoExpediente.EN_REVISION_DOCUMENTOS,
    ):
        from expediente.notifications import registrar_cambio_estado, notificar_alumno
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.EXPEDIENTE_APROBADO,
            realizado_por=None,
            descripcion='Todos los documentos aprobados por Oficina de Titulación.',
        )
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Expediente aprobado',
            mensaje='Tu expediente fue aprobado por Oficina de Titulación. Se continuará con el Oficio de Autorización de Publicación.',
        )
        return True
    return False


def todas_confirmaciones_adeudo(expediente):
    """True si las 3 áreas confirmaron sin adeudos."""
    from expediente.models import ConfirmacionAdeudo
    areas = {
        ConfirmacionAdeudo.Area.FINANZAS,
        ConfirmacionAdeudo.Area.CENTRO_COMPUTO,
        ConfirmacionAdeudo.Area.CENTRO_INFORMACION,
    }
    confirmadas = expediente.confirmaciones_adeudo.filter(
        area__in=areas, sin_adeudos=True
    ).values_list('area', flat=True)
    return areas.issubset(set(confirmadas))
