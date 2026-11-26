"""Servicios SIGET — generación automática de documentos."""
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from expediente.models import EstadoExpediente, ConfirmacionAdeudo
from expediente.workflow import todas_confirmaciones_adeudo
from expediente.notifications import (
    registrar_cambio_estado,
    notificar_alumno,
    notificar_oficina_titulacion,
    notificar_usuarios_por_rol,
)


def _guardar_pdf(filefield, nombre, pdf):
    if not pdf:
        return False
    if not isinstance(pdf, ContentFile):
        pdf = ContentFile(pdf)
    filefield.save(nombre, pdf, save=False)
    return True


def intentar_generar_constancia_no_adeudos(expediente, realizado_por=None):
    """
    Cuando las 3 áreas confirman sin adeudo (tras pago validado):
    genera Constancia de no adeudos y Constancia de no inconveniencia.
    """
    if not todas_confirmaciones_adeudo(expediente):
        return False

    from oficina_titulacion.pdf_constancia import (
        generar_constancia_no_adeudos_pdf,
        generar_constancia_no_inconveniencia_pdf,
    )

    genero_algo = False

    stamp = timezone.now().strftime('%Y%m%d%H%M%S')

    if not expediente.constancia_no_adeudos:
        pdf_adeudos = generar_constancia_no_adeudos_pdf(expediente)
        if _guardar_pdf(
            expediente.constancia_no_adeudos,
            f'constancia_no_adeudos_{expediente.pk}_{stamp}.pdf',
            pdf_adeudos,
        ):
            genero_algo = True

    if not expediente.constancia_no_inconveniencia:
        pdf_inconv = generar_constancia_no_inconveniencia_pdf(expediente)
        if _guardar_pdf(
            expediente.constancia_no_inconveniencia,
            f'no_inconveniencia_{expediente.pk}_{stamp}.pdf',
            pdf_inconv,
        ):
            expediente.fecha_constancia = timezone.now()
            genero_algo = True

    if genero_algo:
        campos = ['constancia_no_adeudos', 'constancia_no_inconveniencia', 'fecha_ultima_actualizacion']
        if expediente.fecha_constancia:
            campos.append('fecha_constancia')
        expediente.save(update_fields=campos)

        notificar_alumno(
            expediente,
            'AVANCE',
            'Documentos oficiales disponibles',
            'Las tres áreas confirmaron que no tienes adeudos. Ya puedes descargar '
            'tu Constancia de no adeudos y tu Constancia de no Inconveniencia '
            'para el Acto de Recepción Profesional desde tu expediente en SIGET.',
            url=reverse('alumnos:expediente'),
        )
        notificar_oficina_titulacion(
            expediente,
            'Constancias oficiales generadas',
            f'Se generaron automáticamente la constancia de no adeudos y la de '
            f'no inconveniencia para {expediente.alumno.get_full_name()}.',
            url=reverse('oficina_titulacion:expediente_detalle', kwargs={'pk': expediente.pk}),
            tipo='AVANCE',
        )

    _verificar_documentos_oficiales_listos(expediente, realizado_por)
    return genero_algo


def forzar_regenerar_constancia_no_adeudos(expediente):
    """Regenera la constancia de no adeudos (reemplaza el PDF previo)."""
    if not todas_confirmaciones_adeudo(expediente):
        return False

    from oficina_titulacion.pdf_constancia import generar_constancia_no_adeudos_pdf

    pdf = generar_constancia_no_adeudos_pdf(expediente)
    if not pdf:
        return False

    if expediente.constancia_no_adeudos:
        expediente.constancia_no_adeudos.delete(save=False)
    stamp = timezone.now().strftime('%Y%m%d%H%M%S')
    if not _guardar_pdf(
        expediente.constancia_no_adeudos,
        f'constancia_no_adeudos_{expediente.pk}_{stamp}.pdf',
        pdf,
    ):
        return False

    expediente.save(update_fields=['constancia_no_adeudos', 'fecha_ultima_actualizacion'])
    return True


def _limpiar_constancia_si_hay_adeudo(expediente):
    """Si alguna área marca adeudo, las constancias previas dejan de ser válidas."""
    campos = []
    if expediente.constancia_no_adeudos:
        expediente.constancia_no_adeudos.delete(save=False)
        expediente.constancia_no_adeudos = None
        campos.append('constancia_no_adeudos')
    if expediente.constancia_no_inconveniencia:
        expediente.constancia_no_inconveniencia.delete(save=False)
        expediente.constancia_no_inconveniencia = None
        expediente.fecha_constancia = None
        campos.extend(['constancia_no_inconveniencia', 'fecha_constancia'])
    if campos:
        campos.append('fecha_ultima_actualizacion')
        expediente.save(update_fields=campos)


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
    area_label = conf.get_area_display()

    notificar_usuarios_por_rol(
        [rol_map[area]],
        f'Alumno {"liberado" if sin_adeudos else "con adeudos"} — {area_label}',
        f'{expediente.alumno.get_full_name()} quedó marcado como '
        f'{"sin adeudos" if sin_adeudos else "con adeudos pendientes"} en {area_label}.',
        tipo='INFO' if sin_adeudos else 'URGENTE',
    )

    if sin_adeudos:
        notificar_alumno(
            expediente,
            'INFO',
            f'Sin adeudos — {area_label}',
            f'{area_label} confirmó que no tienes adeudos pendientes en esa área.'
            + (f' Observaciones: {observaciones}' if observaciones else ''),
            url=reverse('alumnos:expediente'),
        )
        intentar_generar_constancia_no_adeudos(expediente, usuario)
    else:
        _limpiar_constancia_si_hay_adeudo(expediente)
        obs = f' Motivo / observaciones: {observaciones}' if observaciones else ''
        from administracion.models import ContactoArea
        contacto = ContactoArea.por_area(area)
        if contacto:
            contacto_txt = (
                f' Contacto: {contacto.nombre_responsable}. '
                f'Tel. {contacto.telefono_completo()}. '
                f'Correo: {contacto.correo_departamento}.'
            )
        else:
            contacto_txt = f' Acude o comunícate con {area_label} para solucionarlos.'
        notificar_alumno(
            expediente,
            'URGENTE',
            f'Tienes adeudos — {area_label}',
            f'{area_label} registró que tienes adeudos pendientes.{obs}'
            f'{contacto_txt} '
            f'Cuando queden resueltos, esa área volverá a marcar tu expediente '
            f'como sin adeudos en SIGET.',
            url=reverse('alumnos:expediente'),
        )
        notificar_oficina_titulacion(
            expediente,
            f'Adeudo reportado — {area_label}',
            f'{expediente.alumno.get_full_name()} tiene adeudos en {area_label}.'
            + (f' Observaciones: {observaciones}' if observaciones else ''),
            url=reverse('oficina_titulacion:expediente_detalle', kwargs={'pk': expediente.pk}),
            tipo='URGENTE',
        )

    return conf


def _verificar_documentos_oficiales_listos(expediente, realizado_por):
    expediente.refresh_from_db()
    if (
        expediente.constancia_no_inconveniencia
        and expediente.constancia_no_adeudos
        and expediente.estado == EstadoExpediente.ADEUDOS_EN_REVISION
    ):
        registrar_cambio_estado(
            expediente,
            EstadoExpediente.DOCUMENTOS_OFICIALES_LISTOS,
            realizado_por,
            'No inconveniencia y constancia de no adeudos generadas automáticamente.',
        )
        from administracion.models import Rol
        notificar_usuarios_por_rol(
            [Rol.JEFE_ACADEMIA, Rol.JEFE_PROYECTO],
            'Expediente listo para asignación de jurado',
            f'El expediente de {expediente.alumno.get_full_name()} está listo para jurado.',
        )
        notificar_alumno(
            expediente,
            'AVANCE',
            'Documentos oficiales listos',
            'Tus constancias oficiales están completas. El proceso avanzará a la asignación de jurado.',
            url=reverse('alumnos:expediente'),
        )
