"""
Vistas del módulo Académico (División de Estudios Profesionales).
Revisión inicial de expediente, validación de documentos, empastado, jurado, acto.
"""
from django.views.generic import TemplateView, ListView, View, CreateView, UpdateView, DetailView
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone

from expediente.mixins import AcademicoRequeridoMixin
from expediente.models import (
    Expediente, Documento, ValidacionDocumento,
    RecepcionEmpastado, AsignacionJurado, ActoProtocolario,
    EstadoExpediente, EstadoDocumento, EstadoValidacion, Modalidad
)
from expediente.notifications import notificar_alumno, registrar_cambio_estado, registrar_cambio_documento
from expediente.workflow import actualizar_estado_documento, verificar_avance_expediente
from administracion.models import Usuario


from administracion.models import Carrera


class CalendarioAcademicoView(AcademicoRequeridoMixin, TemplateView):
    template_name = 'academico/calendario.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['carreras'] = Carrera.objects.filter(activa=True).order_by('nombre')
        return ctx


class DashboardAcademicoView(AcademicoRequeridoMixin, TemplateView):
    template_name = 'academico/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['expedientes_para_revision_inicial'] = Expediente.objects.filter(
            estado=EstadoExpediente.EN_REVISION_ACADEMICO
        ).count()
        ctx['documentos_para_revisar'] = Documento.objects.filter(
            expediente__estado=EstadoExpediente.EN_REVISION_DOCUMENTOS,
            estado=EstadoDocumento.CARGADO
        ).count()
        ctx['expedientes_empastado_pendiente'] = Expediente.objects.filter(
            estado=EstadoExpediente.EMPASTADO_PENDIENTE
        ).count()
        ctx['expedientes_jurado_pendiente'] = Expediente.objects.filter(
            estado=EstadoExpediente.EMPASTADO_RECIBIDO
        ).count()
        ctx['expedientes_activos'] = Expediente.objects.exclude(
            estado__in=[EstadoExpediente.BORRADOR, EstadoExpediente.CONCLUIDO, EstadoExpediente.CANCELADO]
        ).count()
        ctx['expedientes_concluidos'] = Expediente.objects.filter(
            estado=EstadoExpediente.CONCLUIDO
        ).count()

        # Búsqueda y paginación
        qs = Expediente.objects.exclude(
            estado__in=[EstadoExpediente.BORRADOR, EstadoExpediente.CANCELADO]
        ).select_related('alumno', 'modalidad', 'alumno__carrera').order_by('-fecha_ultima_actualizacion')
        busqueda = self.request.GET.get('q', '').strip()
        carrera_id = self.request.GET.get('carrera', '')
        modalidad_id = self.request.GET.get('modalidad', '')

        if busqueda:
            qs = qs.filter(
                Q(alumno__first_name__unaccent__icontains=busqueda) |
                Q(alumno__last_name__unaccent__icontains=busqueda) |
                Q(alumno__username__unaccent__icontains=busqueda) |
                Q(alumno__numero_control__unaccent__icontains=busqueda)
            )
        if carrera_id:
            qs = qs.filter(alumno__carrera_id=carrera_id)
        if modalidad_id:
            qs = qs.filter(modalidad_id=modalidad_id)

        ctx['busqueda'] = busqueda
        ctx['carrera_id'] = carrera_id
        ctx['modalidad_id'] = modalidad_id
        ctx['carreras_filter'] = Carrera.objects.filter(activa=True)
        ctx['modalidades_filter'] = Modalidad.objects.all()
        paginator = Paginator(qs, 20)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        ctx['expedientes_recientes'] = page_obj
        ctx['page_obj'] = page_obj
        ctx['is_paginated'] = page_obj.has_other_pages()
        return ctx


class ExpedienteListaAcademicoView(AcademicoRequeridoMixin, ListView):
    model = Expediente
    template_name = 'academico/expedientes/lista.html'
    context_object_name = 'expedientes'
    paginate_by = 20

    def get_queryset(self):
        qs = Expediente.objects.exclude(
            estado=EstadoExpediente.BORRADOR
        ).select_related(
            'alumno', 'modalidad', 'alumno__carrera'
        ).order_by('-fecha_ultima_actualizacion')
        estado = self.request.GET.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        busqueda = self.request.GET.get('q', '').strip()
        if busqueda:
            qs = qs.filter(
                Q(alumno__first_name__unaccent__icontains=busqueda) |
                Q(alumno__last_name__unaccent__icontains=busqueda) |
                Q(alumno__username__unaccent__icontains=busqueda) |
                Q(alumno__numero_control__unaccent__icontains=busqueda)
            )

        carrera_id = self.request.GET.get('carrera', '')
        modalidad_id = self.request.GET.get('modalidad', '')

        if carrera_id:
            qs = qs.filter(alumno__carrera_id=carrera_id)
        if modalidad_id:
            qs = qs.filter(modalidad_id=modalidad_id)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['estado_filtro'] = self.request.GET.get('estado', '')
        ctx['busqueda'] = self.request.GET.get('q', '')
        ctx['estados'] = EstadoExpediente.choices

        ctx['carrera_id'] = self.request.GET.get('carrera', '')
        ctx['modalidad_id'] = self.request.GET.get('modalidad', '')
        ctx['carreras_filter'] = Carrera.objects.filter(activa=True)
        ctx['modalidades_filter'] = Modalidad.objects.all()

        return ctx


class ExpedienteDetalleAcademicoView(AcademicoRequeridoMixin, DetailView):
    model = Expediente
    template_name = 'academico/expedientes/detalle.html'
    context_object_name = 'expediente'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        expediente = self.object
        ctx['documentos'] = expediente.documentos.select_related(
            'tipo_documento'
        ).prefetch_related('validaciones').order_by('tipo_documento__orden')
        ctx['historial'] = expediente.historial.select_related('realizado_por')[:15]
        
        # Obtener jurado si existe
        ctx['jurado'] = AsignacionJurado.objects.filter(
            expediente=expediente
        ).select_related('presidente', 'secretario', 'vocal_propietario', 'vocal_suplente').first()
        
        return ctx


class ValidarExpedienteInicialView(AcademicoRequeridoMixin, View):
    """División aprueba o rechaza el expediente inicial del alumno."""

    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk,
                                        estado=EstadoExpediente.EN_REVISION_ACADEMICO)
        accion = request.POST.get('accion')
        observaciones = request.POST.get('observaciones', '').strip()

        if accion == 'APROBAR':
            # Validación de seguridad: no aprobar si faltan datos críticos
            if not expediente.titulo_trabajo or not expediente.nombre_empresa or not expediente.modalidad:
                messages.error(request, 'No se puede aprobar: El expediente tiene datos incompletos (título, empresa o modalidad).')
                return redirect('academico:expediente_detalle', pk=pk)

            expediente.observaciones_division = observaciones
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.DOCUMENTOS_PENDIENTES,
                realizado_por=request.user,
                descripcion='División de Estudios aprobó la revisión inicial. Alumno debe cargar documentos.'
            )
            notificar_alumno(
                expediente=expediente,
                tipo='APROBADO',
                titulo='División de Estudios aprobó tu expediente inicial',
                mensaje='Tu expediente inicial fue revisado y aprobado. Ahora debes cargar todos los documentos requeridos en el sistema.',
            )
            messages.success(request, 'Expediente aprobado. El alumno puede cargar sus documentos.')

        elif accion == 'RECHAZAR':
            expediente.observaciones_division = observaciones
            expediente.save(update_fields=['observaciones_division'])
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.EN_CORRECCION,
                realizado_por=request.user,
                descripcion=f'División rechazó el expediente inicial. Observaciones: {observaciones}'
            )
            # Luego volver a BORRADOR para que el alumno pueda reenviar
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.BORRADOR,
                realizado_por=request.user,
                descripcion='Expediente devuelto al alumno para corrección.'
            )
            notificar_alumno(
                expediente=expediente,
                tipo='RECHAZADO',
                titulo='Tu expediente requiere correcciones',
                mensaje=f'División de Estudios ha regresado tu expediente con las siguientes observaciones: {observaciones}',
            )
            messages.warning(request, 'Expediente devuelto al alumno con observaciones.')

        return redirect('academico:expediente_detalle', pk=pk)


class ValidarDocumentoAcademicoView(AcademicoRequeridoMixin, View):
    """División revisa y valida un documento individual."""

    def post(self, request, pk):
        documento = get_object_or_404(Documento, pk=pk)
        accion = request.POST.get('accion')
        observaciones = request.POST.get('observaciones', '').strip()

        estado_map = {
            'APROBAR': EstadoValidacion.APROBADO,
            'RECHAZAR': EstadoValidacion.RECHAZADO,
            'CORRECCION': EstadoValidacion.REQUIERE_CORRECCION,
        }
        if accion not in estado_map:
            messages.error(request, 'Acción no válida.')
            return redirect('academico:expediente_detalle', pk=documento.expediente.pk)

        validacion, _ = ValidacionDocumento.objects.get_or_create(
            documento=documento,
            departamento='DIVISION',
        )
        validacion.estado = estado_map[accion]
        validacion.validado_por = request.user
        validacion.observaciones = observaciones
        if not validacion.fecha_primera_revision:
            validacion.fecha_primera_revision = timezone.now()
        validacion.save()

        # Actualizar estado del documento usando lógica compartida (requiere AMBOS departamentos)
        actualizar_estado_documento(documento, realizado_por=request.user)

        if accion == 'APROBAR':
            if documento.estado == EstadoDocumento.APROBADO:
                tipo_notif = 'APROBADO'
                msg_alumno = f'El documento "{documento.tipo_documento.nombre}" ha sido aprobado por todos los departamentos.'
            else:
                tipo_notif = 'INFO'
                msg_alumno = f'División de Estudios aprobó the documento "{documento.tipo_documento.nombre}". Pendiente revisión de Servicios Escolares.'
        elif accion == 'RECHAZAR':
            tipo_notif = 'RECHAZADO'
            msg_alumno = f'División de Estudios rechazó el documento "{documento.tipo_documento.nombre}". {observaciones}'
        else:
            tipo_notif = 'CORRECCION'
            msg_alumno = f'El documento "{documento.tipo_documento.nombre}" requiere correcciones. {observaciones}'

        registrar_cambio_documento(
            documento=documento,
            accion=f'División de Estudios: {accion}',
            realizado_por=request.user,
            observaciones=observaciones,
            departamento='DIVISION'
        )
        notificar_alumno(
            expediente=documento.expediente,
            tipo=tipo_notif,
            titulo=f'Revisión de documento — División',
            mensaje=msg_alumno,
        )

        # Verificar si el expediente puede avanzar (todos los docs aprobados por ambos)
        verificar_avance_expediente(documento.expediente)

        participio = {
            'APROBAR': 'aprobado',
            'RECHAZAR': 'rechazado',
            'CORRECCION': 'marcado para corrección'
        }.get(accion, accion.lower())

        messages.success(request, f'Documento {participio}.')
        return redirect('academico:expediente_detalle', pk=documento.expediente.pk)


class RecepcionEmpastadoView(AcademicoRequeridoMixin, CreateView):
    model = RecepcionEmpastado
    template_name = 'academico/empastado/recibir.html'
    fields = ['fecha_recepcion', 'estado', 'observaciones']

    def get_initial(self):
        initial = super().get_initial()
        initial['fecha_recepcion'] = timezone.now().date()
        return initial

    def get_expediente(self):
        return get_object_or_404(
            Expediente, pk=self.kwargs['pk'],
            estado__in=[
                EstadoExpediente.EMPASTADO_PENDIENTE,
                EstadoExpediente.EMPASTADO_RECIBIDO,
            ]
        )

    def form_valid(self, form):
        expediente = self.get_expediente()

        # Usar update_or_create para evitar IntegrityError si ya existe un registro
        recepcion, created = RecepcionEmpastado.objects.update_or_create(
            expediente=expediente,
            defaults={
                'fecha_recepcion': form.cleaned_data['fecha_recepcion'],
                'estado': form.cleaned_data['estado'],
                'observaciones': form.cleaned_data.get('observaciones', ''),
                'recibido_por': self.request.user,
            }
        )

        # Solo registrar cambio de estado si aún no estaba en EMPASTADO_RECIBIDO
        if expediente.estado != EstadoExpediente.EMPASTADO_RECIBIDO:
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.EMPASTADO_RECIBIDO,
                realizado_por=self.request.user,
                descripcion=f'División recibió el empastado. Estado: {recepcion.get_estado_display()}'
            )
            notificar_alumno(
                expediente=expediente,
                tipo='AVANCE',
                titulo='Empastado recibido por División de Estudios',
                mensaje='División de Estudios ha recibido y revisado tu trabajo empastado. El siguiente paso es la asignación de jurado.',
            )

        accion = 'registrada' if created else 'actualizada'
        messages.success(self.request, f'Recepción de empastado {accion} correctamente.')
        return redirect('academico:expediente_detalle', pk=expediente.pk)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        expediente = self.get_expediente()
        ctx['expediente'] = expediente
        # Pre-cargar datos existentes si ya hay recepción registrada
        try:
            ctx['recepcion_existente'] = RecepcionEmpastado.objects.get(expediente=expediente)
        except RecepcionEmpastado.DoesNotExist:
            ctx['recepcion_existente'] = None
        return ctx



class ActoProtocolarioView(AcademicoRequeridoMixin, CreateView):
    model = ActoProtocolario
    template_name = 'academico/acto/programar.html'
    fields = ['fecha_acto', 'lugar', 'observaciones']

    def get_initial(self):
        initial = super().get_initial()
        initial['fecha_acto'] = timezone.now().date()
        return initial

    def get_expediente(self):
        return get_object_or_404(Expediente, pk=self.kwargs['pk'],
                                  estado=EstadoExpediente.JURADO_ASIGNADO)

    def form_valid(self, form):
        expediente = self.get_expediente()
        acto = form.save(commit=False)
        acto.expediente = expediente
        acto.jurado = expediente.jurado
        acto.resultado = 'PENDIENTE'
        acto.programado_por = self.request.user
        acto.save()

        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.ACTO_PROGRAMADO,
            realizado_por=self.request.user,
            descripcion=f'Acto protocolario programado para el {acto.fecha_acto} en {acto.lugar}'
        )
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='¡Tu examen profesional está programado!',
            mensaje=f'Tu acto protocolario ha sido programado para el {acto.fecha_acto.strftime("%d/%m/%Y a las %H:%M")} en {acto.lugar}.',
        )

        # Crear confirmaciones y enviar correos individuales con botón de confirmación
        jurado = expediente.jurado
        if jurado:
            import secrets
            from django.core.mail import EmailMultiAlternatives
            from django.conf import settings
            from expediente.models import ConfirmacionActo

            participantes = [
                ('PRESIDENTE', jurado.presidente.get_nombre_corto(), jurado.presidente.email),
                ('SECRETARIO', jurado.secretario.get_nombre_corto(), jurado.secretario.email),
            ]
            if jurado.vocal_propietario:
                participantes.append(('VOCAL_PROPIETARIO', jurado.vocal_propietario.get_nombre_corto(), jurado.vocal_propietario.email))
            if jurado.vocal_suplente:
                participantes.append(('VOCAL_SUPLENTE', jurado.vocal_suplente.get_nombre_corto(), jurado.vocal_suplente.email))
            participantes.append(('ALUMNO', expediente.alumno.get_full_name(), expediente.alumno.email))

            fecha_fmt = acto.fecha_acto.strftime('%d de %B de %Y a las %H:%M')
            base_url = self.request.build_absolute_uri('/')[:-1]

            for rol, nombre, email in participantes:
                if not email:
                    continue
                token = secrets.token_urlsafe(48)
                ConfirmacionActo.objects.update_or_create(
                    acto=acto, rol=rol,
                    defaults={
                        'nombre_participante': nombre,
                        'email': email,
                        'token': token,
                        'confirmado': False,
                    }
                )
                confirm_url = f'{base_url}/confirmar/{token}/'
                rol_display = dict(ConfirmacionActo.ROL_CHOICES).get(rol, rol)

                # Texto diferente para alumno vs jurado
                if rol == 'ALUMNO':
                    intro_html = (
                        '<p style="font-size:14px;color:#555;">Se le informa que se ha asignado '
                        '<strong style="color:#0057B8;">fecha y lugar</strong> para su '
                        'acto de recepci&oacute;n profesional.</p>'
                    )
                    alumno_row = ''
                else:
                    intro_html = (
                        f'<p style="font-size:14px;color:#555;">Se le invita a participar como '
                        f'<strong style="color:#0057B8;">{rol_display}</strong> en el acto de '
                        f'recepci&oacute;n profesional del alumno(a):</p>'
                    )
                    alumno_row = (
                        f'<tr><td style="padding:6px 12px;font-weight:700;color:#6c757d;font-size:13px;">Alumno(a)</td>'
                        f'<td style="padding:6px 12px;font-size:14px;font-weight:700;">{expediente.alumno.get_full_name()}</td></tr>'
                    )

                html_body = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background:#f4f6f8;">
<div style="max-width:600px;margin:0 auto;padding:20px;">
  <div style="background:linear-gradient(135deg,#0057B8,#003d82);border-radius:12px 12px 0 0;padding:30px;text-align:center;">
    <div style="font-size:36px;color:#fff;">&#x1F393;</div>
    <h2 style="color:#fff;margin:10px 0 5px;font-size:20px;">Acto Protocolario</h2>
    <p style="color:rgba(255,255,255,.8);margin:0;font-size:13px;">Instituto Tecnol&oacute;gico de Apizaco &mdash; TecNM</p>
  </div>
  <div style="background:#fff;padding:30px;border-radius:0 0 12px 12px;box-shadow:0 4px 20px rgba(0,0,0,.08);">
    <p style="font-size:15px;color:#333;">Estimado(a) <strong>{nombre}</strong>,</p>
    {intro_html}

    <div style="background:#f8f9fa;border-radius:8px;padding:16px;margin:20px 0;border-left:4px solid #0057B8;">
      <table style="width:100%;border-collapse:collapse;">
        {alumno_row}
        <tr><td style="padding:6px 12px;font-weight:700;color:#6c757d;font-size:13px;">Carrera</td>
            <td style="padding:6px 12px;font-size:14px;">{expediente.alumno.carrera or '&mdash;'}</td></tr>
        <tr><td style="padding:6px 12px;font-weight:700;color:#6c757d;font-size:13px;">Modalidad</td>
            <td style="padding:6px 12px;font-size:14px;">{expediente.modalidad or '&mdash;'}</td></tr>
        <tr><td style="padding:6px 12px;font-weight:700;color:#6c757d;font-size:13px;">T&iacute;tulo del trabajo</td>
            <td style="padding:6px 12px;font-size:14px;">{expediente.titulo_trabajo or '&mdash;'}</td></tr>
      </table>
    </div>

    <div style="background:linear-gradient(135deg,#f0f7ff,#f3e8ff);border-radius:8px;padding:20px;margin:20px 0;text-align:center;">
      <div style="font-size:12px;color:#6c757d;font-weight:700;text-transform:uppercase;letter-spacing:1px;">Fecha y lugar probable</div>
      <div style="font-size:20px;font-weight:700;color:#7c3aed;margin:8px 0;">{fecha_fmt}</div>
      <div style="font-size:14px;color:#555;">&#128205; {acto.lugar}</div>
    </div>

    {'<div style="background:#dbeafe;border-radius:8px;padding:20px;margin:20px 0;text-align:center;">'
      '<div style="font-size:14px;color:#1e40af;font-weight:700;margin-bottom:8px;">&#128232; Confirme su asistencia</div>'
      '<p style="font-size:13px;color:#333;margin:0;">'
      + ('Por favor confirme su asistencia ingresando a la '
         '<strong>Plataforma de Titulaci&oacute;n</strong> del Instituto Tecnol&oacute;gico de Apizaco.'
         if rol == 'ALUMNO' else
         'Por favor comun&iacute;quese con el <strong>Jefe de Departamento</strong> '
         'correspondiente para confirmar su asistencia.')
      + '</p></div>'}

    <div style="background:#fef3c7;border-radius:8px;padding:12px 16px;font-size:12px;color:#92400e;">
      <strong>&#9888;&#65039; Importante:</strong> Si no se confirma la asistencia de todos los participantes,
      el protocolo ser&aacute; reprogramado. Una vez confirmado por todos, recibir&aacute; un correo con los detalles completos.
    </div>
  </div>
  <p style="text-align:center;font-size:11px;color:#999;margin-top:16px;">
    Este mensaje fue generado autom&aacute;ticamente por el Sistema de Gesti&oacute;n de Titulaci&oacute;n.<br>
    Instituto Tecnol&oacute;gico de Apizaco &mdash; TecNM.
  </p>
</div>
</body></html>'''

                if rol == 'ALUMNO':
                    text_body = (
                        f'Estimado(a) {nombre},\n\n'
                        f'Se le ha asignado fecha para su acto de recepción profesional.\n'
                        f'Fecha probable: {fecha_fmt}\nLugar: {acto.lugar}\n\n'
                        f'Confirme su asistencia en: {confirm_url}\n\n'
                        f'Instituto Tecnológico de Apizaco — TecNM'
                    )
                else:
                    text_body = (
                        f'Estimado(a) {nombre},\n\n'
                        f'Se le invita como {rol_display} al acto protocolario.\n'
                        f'Alumno: {expediente.alumno.get_full_name()}\n'
                        f'Título: {expediente.titulo_trabajo or "N/A"}\n'
                        f'Fecha probable: {fecha_fmt}\nLugar: {acto.lugar}\n\n'
                        f'Confirme su asistencia en: {confirm_url}\n\n'
                        f'Instituto Tecnológico de Apizaco — TecNM'
                    )

                try:
                    msg = EmailMultiAlternatives(
                        subject=f'[ITA Titulación] Confirme Asistencia — Acto Protocolario',
                        body=text_body,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[email],
                    )
                    msg.attach_alternative(html_body, "text/html")
                    msg.send(fail_silently=True)
                except Exception:
                    pass

        messages.success(self.request, 'Acto protocolario programado. Se enviaron correos de confirmación al jurado y al alumno.')
        return redirect('academico:expediente_detalle', pk=expediente.pk)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['expediente'] = self.get_expediente()
        return ctx


class RegistrarResultadoActoView(AcademicoRequeridoMixin, UpdateView):
    model = ActoProtocolario
    template_name = 'academico/acto/resultado.html'
    fields = ['resultado', 'calificacion', 'observaciones']

    def dispatch(self, request, *args, **kwargs):
        acto = self.get_object()
        # Solo permitir registrar resultado si la fecha del acto ya pasó
        if acto.fecha_acto > timezone.now():
            messages.warning(
                request,
                f'No puedes registrar el resultado aún. El acto está programado para el '
                f'{acto.fecha_acto.strftime("%d/%m/%Y a las %H:%M")}.'
            )
            return redirect('academico:expediente_detalle', pk=acto.expediente.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        acto = form.save()
        expediente = acto.expediente
        if acto.resultado in ['APROBADO', 'APROBADO_MENCION']:
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.CONCLUIDO,
                realizado_por=self.request.user,
                descripcion=f'Proceso concluido. Resultado del acto protocolario: {acto.get_resultado_display()}'
            )
            expediente.fecha_conclusion = timezone.now()
            expediente.save(update_fields=['fecha_conclusion'])
            notificar_alumno(
                expediente=expediente,
                tipo='APROBADO',
                titulo='¡Felicidades! Proceso de titulación concluido',
                mensaje=f'Has concluido exitosamente tu proceso de titulación. Resultado: {acto.get_resultado_display()}. ¡Enhorabuena!',
            )
        elif acto.resultado in ['SUSPENDIDO', 'NO_PRESENTADO']:
            notificar_alumno(
                expediente=expediente,
                tipo='RECHAZADO',
                titulo='Resultado del Acto Protocolario',
                mensaje=f'El resultado de tu acto protocolario fue: {acto.get_resultado_display()}. Contacta a División de Estudios para más información.',
            )
        messages.success(self.request, f'Resultado registrado: {acto.get_resultado_display()}')
        return redirect('academico:expediente_detalle', pk=expediente.pk)


class MarcarFotografiaAcademicoView(AcademicoRequeridoMixin, View):
    """División de Estudios marca la fotografía física como entregada."""
    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)
        
        entregada = request.POST.get('entregada') == 'on'
        expediente.foto_fisica_division = entregada
        expediente.save(update_fields=['foto_fisica_division', 'fecha_ultima_actualizacion'])
        
        status_txt = 'RECIBIDA' if entregada else 'PENDIENTE'
        messages.success(request, f'Fotografía física marcada como {status_txt} en División.')
        
        # Auditoría
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=expediente.estado,
            realizado_por=request.user,
            descripcion=f'Fotografía física marcada como {status_txt} por División de Estudios.'
        )
        
        notificar_alumno(
            expediente=expediente,
            tipo='INFO',
            titulo=f'Fotografía física en División: {status_txt.lower()}',
            mensaje=f'División de Estudios ha marcado tu fotografía física como {status_txt.lower()}.',
        )
        
        return redirect('academico:expediente_detalle', pk=pk)


class ToggleConfirmacionView(AcademicoRequeridoMixin, View):
    """
    POST — Confirma o quita la confirmación de asistencia de un participante.
    Envía correo de recibo al confirmar y correo final si se completan todas.
    """

    def post(self, request, pk):
        from expediente.models import ConfirmacionActo
        from expediente.views_confirmacion import (
            _enviar_correo_confirmacion_recibida,
            _enviar_correo_acto_confirmado,
        )

        confirmacion = get_object_or_404(ConfirmacionActo, pk=pk)
        acto = confirmacion.acto
        expediente = acto.expediente

        if not confirmacion.confirmado:
            # Confirmar
            confirmacion.confirmado = True
            confirmacion.fecha_confirmacion = timezone.now()
            confirmacion.save()
            messages.success(request, f'Asistencia de {confirmacion.nombre_participante} confirmada.')

            # Enviar correo de recibo
            _enviar_correo_confirmacion_recibida(confirmacion, acto)

            # Si con esta se completan todas → correo final
            if acto.confirmaciones_completas():
                _enviar_correo_acto_confirmado(acto)
                messages.info(request, '¡Todas las confirmaciones completas! Se envió correo con detalles del jurado a todos.')
        else:
            # Quitar confirmación
            confirmacion.confirmado = False
            confirmacion.fecha_confirmacion = None
            confirmacion.save()
            messages.warning(request, f'Se quitó la confirmación de {confirmacion.nombre_participante}.')

        return redirect('academico:expediente_detalle', pk=expediente.pk)
