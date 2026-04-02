"""
Funciones compartidas de flujo de trabajo del expediente.
Usadas por los módulos académico y escolares para verificar avance.
"""
from expediente.models import (
    Expediente, Documento, ValidacionDocumento,
    EstadoExpediente, EstadoDocumento, EstadoValidacion
)


def verificar_documento_aprobado(documento):
    """
    Verifica si un documento tiene aprobación de TODOS los departamentos
    que deben validarlo (según configuración del TipoDocumento).
    Retorna True si está completamente aprobado.
    """
    tipo = documento.tipo_documento

    # Verificar aprobación de División (si aplica)
    if tipo.valida_division:
        div_val = ValidacionDocumento.objects.filter(
            documento=documento, departamento='DIVISION'
        ).first()
        if not div_val or div_val.estado != EstadoValidacion.APROBADO:
            return False

    # Verificar aprobación de Escolares (si aplica)
    if tipo.valida_escolares:
        esc_val = ValidacionDocumento.objects.filter(
            documento=documento, departamento='ESCOLARES'
        ).first()
        if not esc_val or esc_val.estado != EstadoValidacion.APROBADO:
            return False

    return True


def actualizar_estado_documento(documento):
    """
    Actualiza el estado del documento basándose en las validaciones
    de AMBOS departamentos. Un documento solo se marca APROBADO cuando
    todos los departamentos que deben validarlo lo han aprobado.
    """
    if verificar_documento_aprobado(documento):
        documento.estado = EstadoDocumento.APROBADO
    else:
        # Si al menos un departamento aprobó pero falta el otro → EN_REVISION
        tipo = documento.tipo_documento
        alguno_aprobado = False

        if tipo.valida_division:
            div_val = ValidacionDocumento.objects.filter(
                documento=documento, departamento='DIVISION'
            ).first()
            if div_val and div_val.estado == EstadoValidacion.APROBADO:
                alguno_aprobado = True
            elif div_val and div_val.estado == EstadoValidacion.RECHAZADO:
                documento.estado = EstadoDocumento.RECHAZADO
                documento.save()
                return
            elif div_val and div_val.estado == EstadoValidacion.REQUIERE_CORRECCION:
                documento.estado = EstadoDocumento.REQUIERE_CORRECCION
                documento.save()
                return

        if tipo.valida_escolares:
            esc_val = ValidacionDocumento.objects.filter(
                documento=documento, departamento='ESCOLARES'
            ).first()
            if esc_val and esc_val.estado == EstadoValidacion.APROBADO:
                alguno_aprobado = True
            elif esc_val and esc_val.estado == EstadoValidacion.RECHAZADO:
                documento.estado = EstadoDocumento.RECHAZADO
                documento.save()
                return
            elif esc_val and esc_val.estado == EstadoValidacion.REQUIERE_CORRECCION:
                documento.estado = EstadoDocumento.REQUIERE_CORRECCION
                documento.save()
                return

        if alguno_aprobado:
            documento.estado = EstadoDocumento.EN_REVISION
        # Si nadie ha revisado, queda como está

    documento.save()


def verificar_avance_expediente(expediente):
    """
    Verifica si TODOS los documentos del expediente están aprobados
    (por AMBOS departamentos donde aplique) para avanzar el estado.
    """
    if not expediente.todos_documentos_aprobados():
        return False

    if expediente.estado in (
        EstadoExpediente.EN_REVISION_DOCUMENTOS,
        EstadoExpediente.DOCUMENTOS_PENDIENTES,
    ):
        expediente.estado = EstadoExpediente.LISTO_INTEGRACION
        expediente.save(update_fields=['estado', 'fecha_ultima_actualizacion'])
        return True

    return False
