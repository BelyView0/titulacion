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


def puede_escolares_validar(documento):
    """
    Determina si Servicios Escolares puede validar un documento.
    Si el documento requiere validación de División de Estudios, 
    ésta debe estar APROBADA primero.
    """
    tipo = documento.tipo_documento
    if not tipo.valida_escolares:
        return False
        
    if tipo.valida_division:
        div_val = ValidacionDocumento.objects.filter(
            documento=documento, departamento='DIVISION'
        ).first()
        if not div_val or div_val.estado != EstadoValidacion.APROBADO:
            return False
            
    return True


def actualizar_estado_documento(documento, realizado_por=None):
    """
    Actualiza el estado del documento basándose en las validaciones
    de AMBOS departamentos. Un documento solo se marca APROBADO cuando
    todos los departamentos que deben validarlo lo han aprobado.
    Si un documento es rechazado, el expediente completo regresa a
    carga de documentos para que el alumno corrija.
    """
    estado_original = documento.estado
    rechazo_detectado = False

    if verificar_documento_aprobado(documento):
        documento.estado = EstadoDocumento.APROBADO
    else:
        # Si al menos un departamento aprobó pero falta el otro → EN_REVISION
        tipo = documento.tipo_documento
        alguno_aprobado = False

        # Revisar División
        if tipo.valida_division:
            div_val = ValidacionDocumento.objects.filter(
                documento=documento, departamento='DIVISION'
            ).first()
            if div_val:
                if div_val.estado == EstadoValidacion.APROBADO:
                    alguno_aprobado = True
                elif div_val.estado in [EstadoValidacion.RECHAZADO, EstadoValidacion.REQUIERE_CORRECCION]:
                    documento.estado = (EstadoDocumento.RECHAZADO 
                                      if div_val.estado == EstadoValidacion.RECHAZADO 
                                      else EstadoDocumento.REQUIERE_CORRECCION)
                    rechazo_detectado = True

        # Revisar Escolares (si no se detectó rechazo crítico arriba o para complementar)
        if tipo.valida_escolares and not rechazo_detectado:
            esc_val = ValidacionDocumento.objects.filter(
                documento=documento, departamento='ESCOLARES'
            ).first()
            if esc_val:
                if esc_val.estado == EstadoValidacion.APROBADO:
                    alguno_aprobado = True
                elif esc_val.estado in [EstadoValidacion.RECHAZADO, EstadoValidacion.REQUIERE_CORRECCION]:
                    documento.estado = (EstadoDocumento.RECHAZADO 
                                      if esc_val.estado == EstadoValidacion.RECHAZADO 
                                      else EstadoDocumento.REQUIERE_CORRECCION)
                    rechazo_detectado = True

        if not rechazo_detectado and alguno_aprobado:
            documento.estado = EstadoDocumento.EN_REVISION
        # Si nadie ha revisado o no hay cambios críticos, queda como está

    documento.save()

    # Si hubo rechazo y tenemos al usuario que valida, regresamos el expediente completo
    if rechazo_detectado and realizado_por:
        expediente = documento.expediente
        if expediente.estado != EstadoExpediente.DOCUMENTOS_PENDIENTES:
            from expediente.notifications import registrar_cambio_estado, notificar_alumno
            
            # Cambiar estado del expediente
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.DOCUMENTOS_PENDIENTES,
                realizado_por=realizado_por,
                descripcion=f'Rechazo en documento "{documento.tipo_documento.nombre}". El expediente regresa a corrección.'
            )


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
