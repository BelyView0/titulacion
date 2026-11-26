"""Helpers para tipos de documento según semestres cursados."""
from expediente.models import Documento, EstadoDocumento, TipoDocumento


def tipos_documento_para_alumno(modalidad, alumno):
    """Tipos aplicables a la modalidad del alumno (incluye exclusivos >12 si corresponde)."""
    qs = TipoDocumento.objects.filter(modalidad=modalidad).order_by('orden')
    if getattr(alumno, 'requiere_documentos_extensos', False):
        return qs
    return qs.filter(solo_mas_de_12_semestres=False)


def sincronizar_documentos_expediente(expediente):
    """
    Crea slots faltantes según semestres del alumno.
    Si deja de aplicar >12, elimina solo documentos exclusivos aún PENDIENTE sin archivo.
    """
    alumno = expediente.alumno
    modalidad = expediente.modalidad
    if not modalidad:
        return

    tipos = list(tipos_documento_para_alumno(modalidad, alumno))
    tipo_ids = {t.pk for t in tipos}

    for tipo in tipos:
        Documento.objects.get_or_create(
            expediente=expediente,
            tipo_documento=tipo,
            defaults={'estado': EstadoDocumento.PENDIENTE},
        )

    # Quitar exclusivos >12 que ya no aplican y nunca se cargaron
    extras = expediente.documentos.filter(
        tipo_documento__solo_mas_de_12_semestres=True,
    ).exclude(tipo_documento_id__in=tipo_ids)
    for doc in extras:
        if doc.estado == EstadoDocumento.PENDIENTE and not doc.archivo:
            doc.delete()
