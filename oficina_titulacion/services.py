"""Servicios SIGET — generación automática de documentos."""
from django.core.files.base import ContentFile
from django.urls import reverse

from expediente.models import EstadoExpediente, ConfirmacionAdeudo
from expediente.workflow import todas_confirmaciones_adeudo
from expediente.notifications import (
    registrar_cambio_estado,
    notificar_alumno,
    notificar_oficina_titulacion,
    notificar_usuarios_por_rol,
)


def intentar_generar_constancia_no_adeudos(expediente, realizado_por=None):
    """Genera constancia de no adeudos cuando las 3 áreas confirman sin adeudo."""
    if not todas_confirmaciones_adeudo(expediente):
        return False

    if expediente.constancia_no_adeudos:
        # Ya existe: solo intenta avanzar estado si aplica
        _verificar_documentos_oficiales_listos(expediente, realizado_por)
        return False

    from oficina_titulacion.pdf_constancia import generar_constancia_no_adeudos_pdf

    pdf = generar_constancia_no_adeudos_pdf(expediente)
    if not pdf:
        return False

    if not isinstance(pdf, ContentFile):
        pdf = ContentFile(pdf)

    expediente.constancia_no_adeudos.save(
        f'constancia_no_adeudos_{expediente.pk}.pdf',
        pdf,
        save=False,
    )
    expediente.save(update_fields=['constancia_no_adeudos', 'fecha_ultima_actualizacion'])

    notificar_alumno(
        expediente,
        'AVANCE',
        'Constancia de no adeudos disponible',
        'Las tres áreas (Finanzas, Centro de Cómputo y Centro de Información) '
        'confirmaron que no tienes adeudos. Ya puedes descargar tu Constancia '
        'de no adeudos desde tu expediente en SIGET.',
        url=reverse('alumnos:expediente'),
    )
    notificar_oficina_titulacion(
        expediente,
        'Constancia de no adeudos generada',
        f'Se generó automáticamente la constancia de no adeudos para '
        f'{expediente.alumno.get_full_name()}.',
        url=reverse('oficina_titulacion:expediente_detalle', kwargs={'pk': expediente.pk}),
        tipo='AVANCE',
    )
    _verificar_documentos_oficiales_listos(expediente, realizado_por)
    return True


def _limpiar_constancia_si_hay_adeudo(expediente):
    """Si alguna área marca adeudo, la constancia previa deja de ser válida."""
    if not expediente.constancia_no_adeudos:
        return
    expediente.constancia_no_adeudos.delete(save=False)
    expediente.constancia_no_adeudos = None
    expediente.save(update_fields=['constancia_no_adeudos', 'fecha_ultima_actualizacion'])


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

    # Aviso interno al área que registró
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
