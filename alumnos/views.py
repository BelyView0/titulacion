"""
Vistas del módulo Alumnos.
Panel principal, expediente, documentos, timeline, notificaciones.
"""
from django.views.generic import (
    TemplateView, CreateView, UpdateView, ListView, View, DetailView
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime

from expediente.mixins import AlumnoRequeridoMixin, ExpedientePropioMixin
from expediente.models import (
    Expediente, Documento, EstadoDocumento, EstadoExpediente,
    Modalidad, TipoDocumento, HistorialExpediente
)
from expediente.notifications import registrar_cambio_estado
from alumnos.models import PerfilAlumno, Notificacion
from .forms import ExpedienteForm


class DashboardAlumnoView(AlumnoRequeridoMixin, TemplateView):
    template_name = 'alumnos/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            ctx['expediente'] = self.request.user.expediente
        except Expediente.DoesNotExist:
            ctx['expediente'] = None
        ctx['notificaciones_no_leidas'] = Notificacion.objects.filter(
            destinatario=self.request.user, leida=False
        ).count()
        ctx['notificaciones_recientes'] = Notificacion.objects.filter(
            destinatario=self.request.user
        ).order_by('-fecha')[:5]
        return ctx


class ExpedienteCreateView(AlumnoRequeridoMixin, CreateView):
    """El alumno crea su expediente inicial seleccionando modalidad."""
    model = Expediente
    form_class = ExpedienteForm
    template_name = 'alumnos/expediente/crear.html'

    def dispatch(self, request, *args, **kwargs):
        # Verificar que el usuario tenga al menos un correo verificado
        user = request.user
        if not user.email_verificado and not user.correo_institucional_verificado:
            messages.warning(request, 'Debes verificar al menos uno de tus correos (Personal o Institucional) en tu perfil para poder aperturar tu expediente de titulación y asegurar la recepción de notificaciones.')
            return redirect('perfil')

        # Si ya tiene expediente, redirigir al detalle
        if hasattr(user, 'expediente'):
            return redirect('alumnos:expediente')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        expediente = form.save(commit=False)
        expediente.alumno = self.request.user
        expediente.estado = EstadoExpediente.CERTIFICADO_PENDIENTE_CITA
        if expediente.modalidad and not expediente.plan_estudios_id:
            expediente.plan_estudios = expediente.modalidad.plan_estudios
        expediente.save()

        tipos = TipoDocumento.objects.filter(modalidad=expediente.modalidad).order_by('orden')
        for tipo in tipos:
            Documento.objects.get_or_create(
                expediente=expediente,
                tipo_documento=tipo,
                defaults={'estado': EstadoDocumento.PENDIENTE},
            )

        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.CERTIFICADO_PENDIENTE_CITA,
            realizado_por=self.request.user,
            descripcion='Datos del expediente registrados. Pendiente cita para firma de certificado.',
        )
        messages.success(
            self.request,
            'Datos registrados. Espere la cita de Oficina de Titulación para firmar su certificado.'
        )
        return redirect('alumnos:expediente')


class ExpedienteUpdateView(ExpedientePropioMixin, UpdateView):
    """El alumno edita sus datos iniciales mientras esté en borrador o corrección."""
    model = Expediente
    form_class = ExpedienteForm
    template_name = 'alumnos/expediente/crear.html'  # Reutilizamos el mismo template
    success_url = reverse_lazy('alumnos:expediente')

    def get_queryset(self):
        # Solo permitir editar en estados iniciales
        return super().get_queryset().filter(
            estado__in=[
                EstadoExpediente.DATOS_EXPEDIENTE,
                EstadoExpediente.EN_CORRECCION,
                EstadoExpediente.CERTIFICADO_PENDIENTE_CITA,
                EstadoExpediente.CERTIFICADO_CITA_PROGRAMADA,
            ]
        )

    def form_valid(self, form):
        messages.success(self.request, 'Datos de expediente actualizados.')
        return super().form_valid(form)


class ExpedienteDetalleView(ExpedientePropioMixin, TemplateView):
    template_name = 'alumnos/expediente/detalle.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        expediente = self.get_expediente()
        if not expediente:
            return ctx
        ctx['expediente'] = expediente
        ctx['documentos'] = expediente.documentos.select_related(
            'tipo_documento'
        ).order_by('tipo_documento__orden')
        from expediente.models import CitaDocumentoFisico
        ctx['cita_certificado'] = expediente.citas_fisicas.filter(
            tipo=CitaDocumentoFisico.TipoCita.CERTIFICADO
        ).order_by('-fecha_creacion').first()
        ctx['cita_oficio'] = expediente.citas_fisicas.filter(
            tipo=CitaDocumentoFisico.TipoCita.OFICIO_PUBLICACION
        ).order_by('-fecha_creacion').first()
        ctx['puede_cargar_documentos'] = expediente.estado in (
            EstadoExpediente.CERTIFICADO_FIRMADO,
            EstadoExpediente.CARGA_DOCUMENTOS,
            EstadoExpediente.EN_CORRECCION,
        )
        ctx['historial'] = expediente.historial.select_related('realizado_por').all()[:10]
        return ctx


class SolicitarRevisionView(ExpedientePropioMixin, View):
    """Legado — redirige al flujo SIGET (sin revisión académica previa)."""

    def post(self, request, *args, **kwargs):
        messages.info(request, 'Tu expediente ya fue registrado. Espera la cita de Oficina de Titulación.')
        return redirect('alumnos:expediente')


class EnviarDocumentosRevisionView(ExpedientePropioMixin, View):
    """El alumno envía documentos a revisión de Oficina de Titulación."""

    def post(self, request, *args, **kwargs):
        expediente = self.get_expediente()
        if not expediente:
            messages.error(request, 'No tienes expediente activo.')
            return redirect('alumnos:dashboard')

        estados_ok = (
            EstadoExpediente.CERTIFICADO_FIRMADO,
            EstadoExpediente.CARGA_DOCUMENTOS,
            EstadoExpediente.EN_CORRECCION,
        )
        if expediente.estado not in estados_ok:
            messages.error(request, 'Tu expediente no permite enviar documentos en este momento.')
            return redirect('alumnos:expediente')

        docs_obligatorios = expediente.documentos.filter(tipo_documento__es_obligatorio=True)
        docs_sin_cargar = docs_obligatorios.filter(estado=EstadoDocumento.PENDIENTE)
        if docs_sin_cargar.exists():
            nombres = ', '.join(d.tipo_documento.nombre for d in docs_sin_cargar[:3])
            messages.error(request, f'Faltan documentos obligatorios: {nombres}...')
            return redirect('alumnos:expediente')

        from expediente.notifications import notificar_alumno, notificar_oficina_titulacion
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.EN_REVISION,
            realizado_por=request.user,
            descripcion='Alumno envió expediente completo a revisión.',
        )
        notificar_oficina_titulacion(
            expediente, 'Expediente en revisión',
            f'{expediente.alumno.get_full_name()} envió su expediente a revisión.',
        )
        notificar_alumno(
            expediente=expediente, tipo='AVANCE',
            titulo='Documentos enviados a revisión',
            mensaje='Tu expediente fue enviado a Oficina de Titulación para revisión.',
            url=reverse('alumnos:expediente'),
        )
        messages.success(request, '¡Expediente enviado a revisión!')
        return redirect('alumnos:expediente')


class DocumentoCargarView(ExpedientePropioMixin, UpdateView):
    """El alumno carga o reemplaza un documento."""
    model = Documento
    template_name = 'alumnos/documentos/cargar.html'
    fields = ['archivo', 'notas_alumno']

    def get_object(self):
        return get_object_or_404(
            Documento,
            pk=self.kwargs['pk'],
            expediente__alumno=self.request.user
        )

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        expediente = obj.expediente
        estados_exp = (
            EstadoExpediente.CERTIFICADO_FIRMADO,
            EstadoExpediente.CARGA_DOCUMENTOS,
            EstadoExpediente.EN_CORRECCION,
            EstadoExpediente.OFICIO_FIRMADO,
        )
        if expediente.estado not in estados_exp:
            messages.warning(
                request,
                'La carga de documentos estará disponible después de firmar su certificado en Oficina de Titulación.'
            )
            return redirect('alumnos:expediente')
        estados_permitidos = [
            EstadoDocumento.PENDIENTE,
            EstadoDocumento.RECHAZADO,
            EstadoDocumento.REQUIERE_CORRECCION,
        ]
        if obj.estado not in estados_permitidos:
            messages.warning(request, 'Este documento no requiere acción en este momento.')
            return redirect('alumnos:expediente')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        documento = form.save(commit=False)
        archivo = self.request.FILES.get('archivo')
        if archivo:
            from titulacion.validators import validar_archivo_tipo_documento
            try:
                validar_archivo_tipo_documento(archivo, documento.tipo_documento)
            except Exception as e:
                messages.error(self.request, str(e))
                return self.form_invalid(form)
        documento.estado = EstadoDocumento.CARGADO
        documento.version += 1
        documento.fecha_carga = timezone.now()
        documento.save()

        from expediente.models import ValidacionDocumento, EstadoValidacion
        ValidacionDocumento.objects.filter(documento=documento).delete()
        ValidacionDocumento.objects.create(
            documento=documento, estado=EstadoValidacion.PENDIENTE
        )

        from expediente.notifications import registrar_cambio_documento
        registrar_cambio_documento(
            documento=documento,
            accion=f'Alumno cargó versión {documento.version} del documento.',
            realizado_por=self.request.user,
        )
        if documento.expediente.estado == EstadoExpediente.CERTIFICADO_FIRMADO:
            registrar_cambio_estado(
                documento.expediente,
                EstadoExpediente.CARGA_DOCUMENTOS,
                self.request.user,
                'Alumno inició carga de documentos.',
            )
        messages.success(self.request, f'Documento "{documento.tipo_documento.nombre}" cargado exitosamente.')
        return redirect('alumnos:expediente')


class SubirComprobantePagoView(ExpedientePropioMixin, View):
    """El alumno sube o reemplaza su comprobante de pago PDF."""

    def post(self, request, *args, **kwargs):
        expediente = self.get_expediente()
        if not expediente:
            messages.error(request, 'No tienes expediente activo.')
            return redirect('alumnos:dashboard')

        if expediente.estado not in [EstadoExpediente.PAGO_PENDIENTE]:
            messages.error(request, 'No estás en la etapa de pago actualmente.')
            return redirect('alumnos:expediente')

        comprobante = request.FILES.get('comprobante_pago')
        if not comprobante:
            messages.error(request, 'Por favor, selecciona un archivo.')
            return redirect('alumnos:expediente')

        # Validar extensión
        if not comprobante.name.lower().endswith('.pdf'):
            messages.error(request, 'El comprobante debe ser un archivo en formato PDF.')
            return redirect('alumnos:expediente')

        # Guardar archivo y actualizar estado
        expediente.comprobante_pago = comprobante
        expediente.pago_validado = 'CARGADO'
        expediente.fecha_subida_pago = timezone.now()
        expediente.save(update_fields=[
            'comprobante_pago', 'pago_validado', 'fecha_subida_pago', 'fecha_ultima_actualizacion'
        ])

        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=expediente.estado,
            realizado_por=request.user,
            descripcion='Alumno cargó su comprobante de pago.'
        )

        from expediente.notifications import notificar_alumno, notificar_usuarios_por_rol
        from administracion.models import Rol
        notificar_usuarios_por_rol(
            [Rol.FINANZAS],
            'Comprobante de pago por validar',
            f'{expediente.alumno.get_full_name()} cargó su comprobante de pago.',
            tipo='URGENTE',
        )
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Comprobante de pago cargado',
            url=reverse('alumnos:expediente'),
            mensaje='Has subido tu comprobante de pago. Finanzas lo validará a la brevedad.'
        )

        messages.success(request, '¡Comprobante de pago subido correctamente! En espera de validación por Finanzas.')
        return redirect('alumnos:expediente')


class NotificacionListView(LoginRequiredMixin, ListView):
    model = Notificacion
    template_name = 'alumnos/notificaciones/lista.html'
    context_object_name = 'notificaciones'
    paginate_by = 20

    def get_queryset(self):
        # Marcar todas como leídas al entrar
        qs = Notificacion.objects.filter(destinatario=self.request.user).order_by('-fecha')
        qs.filter(leida=False).update(leida=True)
        return qs


class TimelineView(ExpedientePropioMixin, TemplateView):
    template_name = 'alumnos/expediente/timeline.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        expediente = self.get_expediente()
        ctx['expediente'] = expediente
        if expediente:
            ctx['historial'] = expediente.historial.select_related('realizado_por').all()

            # Etapas lineales del proceso para el mapa visual
            etapas_lineales = [
                (EstadoExpediente.DATOS_EXPEDIENTE, 'Datos del expediente'),
                (EstadoExpediente.CERTIFICADO_PENDIENTE_CITA, 'Cita certificado'),
                (EstadoExpediente.CERTIFICADO_FIRMADO, 'Certificado firmado'),
                (EstadoExpediente.CARGA_DOCUMENTOS, 'Carga de documentos'),
                (EstadoExpediente.EN_REVISION, 'Revisión Oficina'),
                (EstadoExpediente.EXPEDIENTE_APROBADO, 'Expediente aprobado'),
                (EstadoExpediente.OFICIO_FIRMADO, 'Oficio firmado'),
                (EstadoExpediente.PAGO_VALIDADO, 'Pago validado'),
                (EstadoExpediente.DOCUMENTOS_OFICIALES_LISTOS, 'Documentos oficiales'),
                (EstadoExpediente.JURADO_ASIGNADO, 'Jurado asignado'),
                (EstadoExpediente.PROTOCOLO_PROGRAMADO, 'Acto programado'),
                (EstadoExpediente.ACTO_REALIZADO, 'Acto realizado'),
                (EstadoExpediente.CONCLUIDO, 'Concluido'),
            ]
            ctx['estados_proceso'] = etapas_lineales

            # Determinar qué estados ya se pasaron
            valores_lineales = [e[0] for e in etapas_lineales]
            estado_actual = expediente.estado
            if estado_actual in valores_lineales:
                idx_actual = valores_lineales.index(estado_actual)
                ctx['estados_completados'] = valores_lineales[:idx_actual]
            else:
                ctx['estados_completados'] = []
        return ctx


class ConfirmarAsistenciaAlumnoView(AlumnoRequeridoMixin, View):
    """POST — El alumno confirma su propia asistencia al acto protocolario."""

    def post(self, request):
        from expediente.models import ConfirmacionActo
        from expediente.views_confirmacion import (
            _enviar_correo_confirmacion_recibida,
            _enviar_correo_acto_confirmado,
        )

        try:
            expediente = request.user.expediente
        except Expediente.DoesNotExist:
            messages.error(request, 'No tienes un expediente registrado.')
            return redirect('alumnos:dashboard')

        acto = getattr(expediente, 'acto_protocolario', None)
        if not acto:
            messages.error(request, 'No hay un acto protocolario programado.')
            return redirect('alumnos:dashboard')

        confirmacion = ConfirmacionActo.objects.filter(acto=acto, rol='ALUMNO').first()
        if not confirmacion:
            messages.error(request, 'No se encontró tu confirmación.')
            return redirect('alumnos:dashboard')

        if confirmacion.confirmado:
            messages.info(request, 'Ya confirmaste tu asistencia anteriormente.')
            return redirect('alumnos:dashboard')

        confirmacion.confirmado = True
        confirmacion.fecha_confirmacion = timezone.now()
        confirmacion.save()

        # Enviar correo de recibo
        _enviar_correo_confirmacion_recibida(confirmacion, acto)
        messages.success(request, '¡Tu asistencia ha sido confirmada exitosamente! Se te envió un correo de confirmación.')

        # Si con esta se completan todas → correo final
        if acto.confirmaciones_completas():
            _enviar_correo_acto_confirmado(acto)

        return redirect('alumnos:dashboard')


class ConfirmarCitaView(ExpedientePropioMixin, View):
    """Alumno confirma asistencia a cita de certificado u oficio."""

    def post(self, request, pk):
        from expediente.models import CitaDocumentoFisico
        cita = get_object_or_404(
            CitaDocumentoFisico, pk=pk, expediente__alumno=request.user
        )
        cita.estado = CitaDocumentoFisico.EstadoCita.CONFIRMADA_ALUMNO
        cita.save(update_fields=['estado'])
        messages.success(request, 'Cita confirmada. Le esperamos en la fecha indicada.')
        return redirect('alumnos:expediente')


class SolicitarReprogramacionCitaView(ExpedientePropioMixin, View):
    """Alumno solicita cambio de fecha/hora de cita."""

    def post(self, request, pk):
        from expediente.models import CitaDocumentoFisico
        cita = get_object_or_404(
            CitaDocumentoFisico, pk=pk, expediente__alumno=request.user
        )
        nueva_fecha = request.POST.get('propuesta_fecha')
        notas = request.POST.get('propuesta_notas', '')
        if nueva_fecha:
            try:
                dt = datetime.strptime(nueva_fecha, '%Y-%m-%dT%H:%M')
                cita.propuesta_alumno_fecha = timezone.make_aware(
                    dt, timezone.get_current_timezone()
                )
            except ValueError:
                messages.error(request, 'Formato de fecha inválido.')
                return redirect('alumnos:expediente')
        cita.propuesta_alumno_notas = notas
        cita.estado = CitaDocumentoFisico.EstadoCita.REPROGRAMACION_SOLICITADA
        cita.save()
        from expediente.notifications import notificar_oficina_titulacion
        notificar_oficina_titulacion(
            cita.expediente,
            'Solicitud de reprogramación de cita',
            f'{request.user.get_full_name()} solicitó reprogramar su cita.',
            tipo='URGENTE',
        )
        messages.success(request, 'Solicitud de reprogramación enviada.')
        return redirect('alumnos:expediente')

