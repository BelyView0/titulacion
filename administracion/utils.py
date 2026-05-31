from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.conf import settings
from administracion.pdf_oficio import generar_oficio_jurado_pdf

def procesar_resolucion_solicitud(solicitud, aprobada):
    """
    Procesa la aprobación o rechazo/expiración de una solicitud de cambio de jefe.
    Si es aprobada, actualiza el JefeDepartamento oficial.
    Si es rechazada o expira, busca todas las asignaciones de jurado que usaron esta solicitud
    temporalmente y regenera sus PDFs usando el jefe oficial, notificando al autor.
    """
    if aprobada:
        solicitud.estado = 'APROBADO'
        # Actualizar o crear JefeDepartamento
        from administracion.models import JefeDepartamento
        jefe, created = JefeDepartamento.objects.get_or_create(
            departamento=solicitud.departamento,
            defaults={
                'titulo_academico': solicitud.titulo_academico_nuevo,
                'nombre': solicitud.nombre_nuevo,
                'apellido_paterno': solicitud.apellido_paterno_nuevo,
                'apellido_materno': solicitud.apellido_materno_nuevo,
                'genero': solicitud.genero_nuevo,
            }
        )
        if not created:
            jefe.titulo_academico = solicitud.titulo_academico_nuevo
            jefe.nombre = solicitud.nombre_nuevo
            jefe.apellido_paterno = solicitud.apellido_paterno_nuevo
            jefe.apellido_materno = solicitud.apellido_materno_nuevo
            jefe.genero = solicitud.genero_nuevo
            jefe.save()
            
        solicitud.save()
        return

    # Rechazada o Expirada
    asignaciones_afectadas = solicitud.asignaciones_jurado.all()
    if asignaciones_afectadas.exists():
        # Regenerar PDFs
        for jurado in asignaciones_afectadas:
            # generar_oficio_jurado_pdf sin jefe_custom usará el jefe oficial
            pdf_bytes = generar_oficio_jurado_pdf(jurado)
            filename = f'Oficio_Jurado_{jurado.expediente.alumno.username}.pdf'
            
            # Borrar archivo anterior
            if jurado.oficio_pdf:
                jurado.oficio_pdf.delete(save=False)
                
            jurado.oficio_pdf.save(filename, ContentFile(pdf_bytes), save=False)
            jurado.solicitud_jefe_usada = None
            jurado.save()

        # Notificar al jefe de proyectos autor (el que solicitó el cambio)
        if solicitud.solicitante and solicitud.solicitante.email:
            resumen_expedientes = "\n".join([f"- Expediente de {j.expediente.alumno.get_full_name()}" for j in asignaciones_afectadas])
            asunto = f"Solicitud de Cambio de Jefe {solicitud.estado.lower()}"
            mensaje = (
                f"Hola {solicitud.solicitante.get_full_name()},\n\n"
                f"Tu solicitud de actualización de Jefe de Departamento fue {solicitud.estado.lower()} por el Administrador o expiró.\n"
                f"Debido a esto, el sistema ha regenerado de forma automática los siguientes oficios de jurado que generaste de emergencia con los datos temporales:\n\n"
                f"{resumen_expedientes}\n\n"
                f"Estos oficios ahora contienen nuevamente la firma del Jefe de Departamento oficial vigente.\n\n"
                f"Atentamente,\nSistema de Titulación"
            )
            send_mail(
                subject=asunto,
                message=mensaje,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[solicitud.solicitante.email],
                fail_silently=True,
            )
    
    solicitud.save()
