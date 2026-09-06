"""Utilidades SIGET para expedientes."""
from expediente.models import EstadoExpediente

MAPEO_ESTADO_LEGADO = {
    'BORRADOR': EstadoExpediente.DATOS_EXPEDIENTE,
    'EN_REVISION_ACADEMICO': EstadoExpediente.EN_REVISION,
    'RECHAZADO_ACADEMICO': EstadoExpediente.EN_CORRECCION,
    'DOCUMENTOS_PENDIENTES': EstadoExpediente.CARGA_DOCUMENTOS,
    'EN_REVISION_DOCUMENTOS': EstadoExpediente.EN_REVISION,
    'LISTO_INTEGRACION': EstadoExpediente.CARGA_DOCUMENTOS,
    'RECIBI_PAPEL_ORIGINAL': EstadoExpediente.CARGA_DOCUMENTOS,
    'PAGO_EN_REVISION': EstadoExpediente.PAGO_PENDIENTE,
    'ESPERANDO_CONSTANCIA': EstadoExpediente.ADEUDOS_EN_REVISION,
    'CONSTANCIA_EN_REVISION': EstadoExpediente.ADEUDOS_EN_REVISION,
    'INTEGRADO': EstadoExpediente.DOCUMENTOS_OFICIALES_LISTOS,
    'EMPASTADO_PENDIENTE': EstadoExpediente.JURADO_ASIGNADO,
    'EMPASTADO_RECIBIDO': EstadoExpediente.JURADO_ASIGNADO,
    'ACTO_PROGRAMADO': EstadoExpediente.PROTOCOLO_PROGRAMADO,
    'ACTA_EXENCION': EstadoExpediente.ACTO_REALIZADO,
    'TRAMITE_DGP': EstadoExpediente.ACTO_REALIZADO,
    'CEDULA_EN_REVISION': EstadoExpediente.ACTO_REALIZADO,
    'CEDULA_RECHAZADA': EstadoExpediente.ACTO_REALIZADO,
    'CITA_ENTREGA': EstadoExpediente.ACTO_REALIZADO,
}


def paso_expediente_display(estado):
    return dict(EstadoExpediente.choices).get(estado, estado)


def expediente_completo(expediente):
    from expediente.models import EstadoDocumento
    obligatorios = expediente.documentos.filter(tipo_documento__es_obligatorio=True)
    if not obligatorios.exists():
        return False
    return all(d.estado == EstadoDocumento.APROBADO for d in obligatorios)
