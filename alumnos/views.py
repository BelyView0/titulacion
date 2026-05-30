"""
Vistas del módulo Alumnos.
Panel principal, expediente, documentos, timeline, notificaciones.
"""
from django.views.generic import (
    TemplateView, CreateView, UpdateView, ListView, View, DetailView
)
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone

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
        expediente.estado = EstadoExpediente.BORRADOR
        expediente.save()

        # Crear documentos pendientes basados en la modalidad seleccionada
        tipos = TipoDocumento.objects.filter(
            modalidad=expediente.modalidad
        ).order_by('orden')
        for tipo in tipos:
            Documento.objects.create(
                expediente=expediente,
                tipo_documento=tipo,
                estado=EstadoDocumento.PENDIENTE,
            )

        # Registrar en historial
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.BORRADOR,
            realizado_por=self.request.user,
            descripcion='Expediente creado por el alumno.'
        )

        # Marcar la foto física si subió digital
        if expediente.fotografia_digital:
            expediente.fotografia_fisica_entregada = False  # pendiente físico
            expediente.save(update_fields=['fotografia_fisica_entregada'])

        messages.success(self.request,
            '¡Expediente creado! Ahora puedes cargar tus documentos requeridos.')
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
            estado__in=[EstadoExpediente.BORRADOR, EstadoExpediente.EN_CORRECCION, EstadoExpediente.RECHAZADO_ACADEMICO]
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
        ).prefetch_related('validaciones').order_by('tipo_documento__orden')
        ctx['historial'] = expediente.historial.select_related('realizado_por').all()[:10]
        return ctx


class SolicitarRevisionView(ExpedientePropioMixin, View):
    """El alumno envía su expediente a revisión de División de Estudios."""

    def post(self, request, *args, **kwargs):
        expediente = self.get_expediente()
        if not expediente:
            messages.error(request, 'No tienes expediente activo.')
            return redirect('alumnos:dashboard')

        # Verificación de datos completos
        if not all([expediente.modalidad, expediente.titulo_trabajo, expediente.nombre_empresa]):
            messages.error(request, 'Debes completar todos los datos iniciales (modalidad, título y empresa) antes de solicitar revisión.')
            return redirect('alumnos:expediente')

        if expediente.estado != EstadoExpediente.BORRADOR:
            messages.error(request, 'Tu expediente no está en estado Borrador.')
            return redirect('alumnos:expediente')

        from expediente.notifications import notificar_alumno
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.EN_REVISION_ACADEMICO,
            realizado_por=request.user,
            descripcion='Alumno envió expediente a revisión de División de Estudios.'
        )
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Expediente enviado a revisión',
            mensaje='Tu expediente ha sido enviado a División de Estudios para revisión inicial.',
            url=reverse('alumnos:expediente')
        )
        messages.success(request, 'Expediente enviado a revisión de División de Estudios.')
        return redirect('alumnos:expediente')


class EnviarDocumentosRevisionView(ExpedientePropioMixin, View):
    """El alumno envía sus documentos cargados a revisión de Escolares y Académico."""

    def post(self, request, *args, **kwargs):
        expediente = self.get_expediente()
        if not expediente:
            messages.error(request, 'No tienes expediente activo.')
            return redirect('alumnos:dashboard')

        if expediente.estado not in [EstadoExpediente.DOCUMENTOS_PENDIENTES]:
            messages.error(request, 'Tu expediente no está en un estado que permita el envío de documentos.')
            return redirect('alumnos:expediente')

        # Verificar que todos los documentos obligatorios fueron cargados
        docs_obligatorios = expediente.documentos.filter(
            tipo_documento__es_obligatorio=True
        )
        docs_sin_cargar = docs_obligatorios.filter(estado=EstadoDocumento.PENDIENTE)

        if docs_sin_cargar.exists():
            nombres = ', '.join([d.tipo_documento.nombre for d in docs_sin_cargar[:3]])
            messages.error(
                request,
                f'Faltan documentos obligatorios por cargar: {nombres}...'
            )
            return redirect('alumnos:expediente')

        from expediente.notifications import notificar_alumno
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.EN_REVISION_DOCUMENTOS,
            realizado_por=request.user,
            descripcion='Alumno re-envió documentos a revisión tras correcciones (CDMX o Escolares).'
        )
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Documentos enviados a revisión',
            mensaje='Tus documentos han sido enviados a Servicios Escolares y División de Estudios para validación.',
            url=reverse('alumnos:expediente')
        )
        messages.success(request, '¡Documentos enviados a revisión! Escolares y División validarán tus documentos.')
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
        # Solo permite cargar si está en estado que lo permita
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
        documento.estado = EstadoDocumento.CARGADO
        documento.version += 1
        documento.fecha_carga = timezone.now()
        documento.save()

        # Resetear validaciones anteriores
        documento.validaciones.all().delete()

        from expediente.notifications import registrar_cambio_documento
        registrar_cambio_documento(
            documento=documento,
            accion=f'Alumno cargó versión {documento.version} del documento.',
            realizado_por=self.request.user,
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
        expediente.estado = EstadoExpediente.PAGO_EN_REVISION
        expediente.save(update_fields=[
            'comprobante_pago', 'pago_validado', 'fecha_subida_pago', 'estado', 'fecha_ultima_actualizacion'
        ])

        # Registrar en el historial
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.PAGO_EN_REVISION,
            realizado_por=request.user,
            descripcion='Alumno cargó su comprobante de pago.'
        )

        from expediente.notifications import notificar_alumno
        notificar_alumno(
            expediente=expediente,
            tipo='AVANCE',
            titulo='Comprobante de pago cargado',
            url=reverse('alumnos:expediente'),
            mensaje='Has subido tu comprobante de pago. Servicios Escolares lo validará a la brevedad.'
        )

        messages.success(request, '¡Comprobante de pago subido correctamente! En espera de validación de Servicios Escolares.')
        return redirect('alumnos:expediente')


class NotificacionListView(AlumnoRequeridoMixin, ListView):
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
                (EstadoExpediente.BORRADOR, 'Borrador'),
                (EstadoExpediente.EN_REVISION_ACADEMICO, 'Revisión División'),
                (EstadoExpediente.DOCUMENTOS_PENDIENTES, 'Carga de Documentos'),
                (EstadoExpediente.EN_REVISION_DOCUMENTOS, 'Revisión Documentos'),
                (EstadoExpediente.LISTO_INTEGRACION, 'Listo Integración'),
                (EstadoExpediente.RECIBI_PAPEL_ORIGINAL, 'Papeles Recibidos'),
                (EstadoExpediente.PAGO_PENDIENTE, 'Pago Pendiente'),
                (EstadoExpediente.PAGO_EN_REVISION, 'Pago en Revisión'),
                (EstadoExpediente.ESPERANDO_CONSTANCIA, 'Esperando Constancia'),
                (EstadoExpediente.CONSTANCIA_EN_REVISION, 'Constancia en Revisión'),
                (EstadoExpediente.INTEGRADO, 'Integrado'),
                (EstadoExpediente.EMPASTADO_PENDIENTE, 'Empastado Pendiente'),
                (EstadoExpediente.EMPASTADO_RECIBIDO, 'Empastado Recibido'),
                (EstadoExpediente.JURADO_ASIGNADO, 'Jurado Asignado'),
                (EstadoExpediente.ACTO_PROGRAMADO, 'Acto Programado'),
                (EstadoExpediente.ACTA_EXENCION, 'Acta de Exención'),
                (EstadoExpediente.TRAMITE_DGP, 'Captura en plataforma (e-títulos) de TNM'),
                (EstadoExpediente.CEDULA_EN_REVISION, 'Cédula en Revisión'),
                (EstadoExpediente.CITA_ENTREGA, 'Cita de Entrega'),
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


class SubirCedulaAlumnoView(ExpedientePropioMixin, View):
    """El alumno sube su Cédula Profesional en formato PDF."""

    def post(self, request):
        expediente = self.get_expediente()
        if not expediente:
            messages.error(request, 'No tienes expediente activo.')
            return redirect('alumnos:dashboard')

        if expediente.estado not in [EstadoExpediente.TRAMITE_DGP, EstadoExpediente.CEDULA_RECHAZADA]:
            messages.error(request, 'No puedes subir tu cédula en este momento.')
            return redirect('alumnos:expediente')

        archivo_cedula = request.FILES.get('cedula_pdf')
        if not archivo_cedula:
            messages.error(request, 'Debes seleccionar un archivo PDF con tu cédula.')
            return redirect('alumnos:expediente')

        if not archivo_cedula.name.lower().endswith('.pdf'):
            messages.error(request, 'El archivo de la cédula debe ser en formato PDF.')
            return redirect('alumnos:expediente')

        expediente.cedula_profesional_pdf = archivo_cedula
        expediente.fecha_subida_cedula = timezone.now()
        expediente.estado = EstadoExpediente.CEDULA_EN_REVISION
        expediente.save(update_fields=['cedula_profesional_pdf', 'fecha_subida_cedula', 'estado', 'fecha_ultima_actualizacion'])

        from expediente.notifications import registrar_cambio_estado
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=EstadoExpediente.CEDULA_EN_REVISION,
            realizado_por=request.user,
            descripcion='El alumno subió su Cédula Profesional Electrónica para revisión.'
        )

        messages.success(request, 'Tu Cédula Profesional ha sido cargada y enviada a revisión.')
        return redirect('alumnos:expediente')


class ConfirmarDatosDGPAlumnoView(ExpedientePropioMixin, View):
    """El alumno confirma que sus datos de título DGP son correctos."""

    def post(self, request):
        expediente = self.get_expediente()
        if not expediente:
            messages.error(request, 'No tienes expediente activo.')
            return redirect('alumnos:dashboard')

        if not expediente.notificacion_dgp_enviada:
            messages.error(request, 'Aún no se ha enviado la notificación DGP.')
            return redirect('alumnos:expediente')

        if expediente.datos_dgp_confirmados:
            messages.info(request, 'Ya confirmaste que tus datos son correctos anteriormente.')
            return redirect('alumnos:expediente')

        expediente.datos_dgp_confirmados = True
        expediente.save(update_fields=['datos_dgp_confirmados', 'fecha_ultima_actualizacion'])

        from expediente.notifications import registrar_cambio_estado
        registrar_cambio_estado(
            expediente=expediente,
            estado_nuevo=expediente.estado,
            realizado_por=request.user,
            descripcion='El alumno confirmó que sus datos concentrados de DGP son correctos.'
        )

        messages.success(request, 'Has confirmado que tus datos son correctos. Servicios Escolares ha sido notificado para continuar.')
        return redirect('alumnos:expediente')

