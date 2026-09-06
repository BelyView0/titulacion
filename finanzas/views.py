"""
Vistas del módulo Finanzas — pagos y confirmación de adeudos.
"""
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView, View

from alumnos.models import Notificacion
from expediente.mixins import FinanzasRequeridoMixin
from expediente.models import (
    ConfirmacionAdeudo,
    EstadoExpediente,
    Expediente,
    ReferenciaPago,
)
from expediente.notifications import (
    notificar_alumno,
    notificar_usuarios_por_rol,
    registrar_cambio_estado,
)
from finanzas.pago_queries import (
    ESTADOS_BANDEJA_PAGO_FINANZAS,
    ESTADOS_GENERAR_PREFICHA,
    expedientes_bandeja_pago_finanzas,
)
from finanzas.preficha_pago import (
    concepto_pago_expediente,
    generar_referencia_bancaria,
    guardar_preficha_pdf,
    monto_default_pago,
)
from oficina_titulacion.services import registrar_confirmacion_adeudo
from administracion.models import Rol
from expediente.adeudo_queries import (
    expedientes_adeudo_pendientes,
    expedientes_con_adeudos,
    expedientes_liberados,
)


AREA_FINANZAS = ConfirmacionAdeudo.Area.FINANZAS


class DashboardFinanzasView(FinanzasRequeridoMixin, TemplateView):
    template_name = 'finanzas/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pagos_pendientes'] = Expediente.objects.filter(
            estado__in=[EstadoExpediente.OFICIO_FIRMADO, EstadoExpediente.PAGO_PENDIENTE],
        ).count()
        ctx['pagos_validados'] = Expediente.objects.filter(
            estado=EstadoExpediente.PAGO_VALIDADO,
        ).count()
        ctx['comprobantes_por_validar'] = Expediente.objects.filter(
            estado=EstadoExpediente.PAGO_PENDIENTE,
            pago_validado='CARGADO',
        ).count()
        ctx['adeudos_pendientes'] = expedientes_adeudo_pendientes(AREA_FINANZAS).count()
        ctx['notificaciones_no_leidas'] = Notificacion.objects.filter(
            destinatario=self.request.user, leida=False,
        ).count()
        ctx['expedientes_pago_recientes'] = expedientes_bandeja_pago_finanzas().select_related(
            'alumno', 'alumno__carrera',
        ).order_by('-fecha_ultima_actualizacion')[:10]
        ctx['pendientes'] = expedientes_adeudo_pendientes(AREA_FINANZAS)[:20]
        ctx['liberados'] = expedientes_liberados(AREA_FINANZAS)
        ctx['con_adeudos'] = expedientes_con_adeudos(AREA_FINANZAS)
        return ctx


class ExpedientesPagoView(FinanzasRequeridoMixin, ListView):
    model = Expediente
    template_name = 'finanzas/expedientes_pago.html'
    context_object_name = 'expedientes'
    paginate_by = 20

    def get_queryset(self):
        qs = expedientes_bandeja_pago_finanzas().select_related(
            'alumno', 'alumno__carrera', 'modalidad',
        ).prefetch_related('referencias_pago')

        estado = self.request.GET.get('estado', '').strip()
        if estado in ESTADOS_BANDEJA_PAGO_FINANZAS:
            qs = qs.filter(estado=estado)

        busqueda = self.request.GET.get('q', '').strip()
        if busqueda:
            qs = qs.filter(
                Q(alumno__first_name__unaccent__icontains=busqueda) |
                Q(alumno__last_name__unaccent__icontains=busqueda) |
                Q(alumno__username__unaccent__icontains=busqueda) |
                Q(alumno__numero_control__unaccent__icontains=busqueda)
            )
        return qs.order_by('-fecha_ultima_actualizacion')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['estado_filtro'] = self.request.GET.get('estado', '')
        ctx['busqueda'] = self.request.GET.get('q', '')
        return ctx


class ExpedientePagoDetalleView(FinanzasRequeridoMixin, DetailView):
    model = Expediente
    template_name = 'finanzas/expediente_pago_detalle.html'
    context_object_name = 'expediente'

    def get(self, request, *args, **kwargs):
        expediente = get_object_or_404(
            Expediente.objects.select_related('alumno'),
            pk=kwargs['pk'],
        )
        if expediente.estado == EstadoExpediente.ADEUDOS_EN_REVISION:
            messages.info(
                request,
                'El pago ya fue validado. El expediente ahora está en confirmación de adeudos.',
            )
            return redirect('finanzas:adeudos_pendientes')
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return expedientes_bandeja_pago_finanzas().select_related(
            'alumno', 'alumno__carrera', 'modalidad',
        ).prefetch_related('referencias_pago')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['referencia_activa'] = self.object.referencias_pago.filter(activa=True).first()
        ctx['monto_default'] = monto_default_pago()
        return ctx


class GenerarReferenciaPagoView(FinanzasRequeridoMixin, View):
    """Genera la preficha de pago con referencia bancaria y PDF institucional."""

    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)
        if expediente.estado not in ESTADOS_GENERAR_PREFICHA:
            messages.error(request, 'El expediente no está en etapa de pago pendiente.')
            return redirect('finanzas:expediente_pago_detalle', pk=pk)

        if expediente.estado == EstadoExpediente.OFICIO_FIRMADO:
            registrar_cambio_estado(
                expediente,
                EstadoExpediente.PAGO_PENDIENTE,
                request.user,
                'Oficio firmado. El expediente avanza a pago de titulación.',
            )
            expediente.refresh_from_db()

        monto_raw = request.POST.get('monto', '').strip()
        vigencia_raw = request.POST.get('vigencia', '').strip()
        concepto = request.POST.get('concepto', '').strip() or concepto_pago_expediente(expediente)

        try:
            monto = Decimal(monto_raw) if monto_raw else monto_default_pago()
            if monto <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            messages.error(request, 'Indica un monto válido mayor a cero.')
            return redirect('finanzas:expediente_pago_detalle', pk=pk)

        vigencia = None
        if vigencia_raw:
            try:
                vigencia = datetime.strptime(vigencia_raw, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, 'La vigencia debe tener formato AAAA-MM-DD.')
                return redirect('finanzas:expediente_pago_detalle', pk=pk)

        expediente.referencias_pago.filter(activa=True).update(activa=False)
        folio = f'ITA-{timezone.now().year}-{expediente.pk:05d}-{uuid.uuid4().hex[:6].upper()}'
        referencia_bancaria = generar_referencia_bancaria(expediente.alumno)
        referencia = ReferenciaPago.objects.create(
            expediente=expediente,
            folio=folio,
            referencia_bancaria=referencia_bancaria,
            concepto=concepto,
            monto=monto,
            vigencia=vigencia,
            generado_por=request.user,
            activa=True,
        )

        try:
            guardar_preficha_pdf(referencia)
        except Exception as exc:
            referencia.delete()
            messages.error(request, f'No se pudo generar el PDF de la preficha: {exc}')
            return redirect('finanzas:expediente_pago_detalle', pk=pk)

        expediente.pago_validado = 'PENDIENTE'
        expediente.pago_observaciones = ''
        expediente.save(update_fields=[
            'pago_validado', 'pago_observaciones', 'fecha_ultima_actualizacion',
        ])

        notificar_alumno(
            expediente,
            'AVANCE',
            'Preficha de pago disponible',
            f'Se generó su preficha de depósito con referencia {referencia.referencia_bancaria} '
            f'por ${referencia.monto}. Descárguela, realice el pago en banco y suba su comprobante.',
            url=reverse('alumnos:expediente'),
        )
        messages.success(
            request,
            f'Preficha generada. Referencia bancaria: {referencia.referencia_bancaria}',
        )
        return redirect('finanzas:expediente_pago_detalle', pk=pk)


class DescargarPrefichaPagoView(FinanzasRequeridoMixin, View):
    """Descarga la preficha PDF activa — la regenera en tiempo real."""

    def get(self, request, pk):
        expediente = get_object_or_404(
            expedientes_bandeja_pago_finanzas(),
            pk=pk,
        )
        referencia = expediente.referencias_pago.filter(activa=True).first()
        if not referencia:
            raise Http404('No hay preficha de pago disponible.')
        from finanzas.preficha_pago import generar_preficha_pago_pdf
        from django.http import HttpResponse
        pdf_bytes = generar_preficha_pago_pdf(referencia)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        nombre = f'preficha_{referencia.referencia_bancaria}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{nombre}"'
        return response


class ValidarPagoView(FinanzasRequeridoMixin, View):
    """Aprueba o rechaza el comprobante de pago del alumno."""

    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)
        accion = request.POST.get('accion')
        observaciones = request.POST.get('observaciones', '').strip()

        if expediente.estado != EstadoExpediente.PAGO_PENDIENTE:
            messages.error(request, 'El expediente no está pendiente de validación de pago.')
            if expediente.estado == EstadoExpediente.ADEUDOS_EN_REVISION:
                return redirect('finanzas:adeudos_pendientes')
            return redirect('finanzas:expediente_pago_detalle', pk=pk)

        if not expediente.comprobante_pago:
            messages.error(request, 'El alumno aún no ha cargado un comprobante de pago.')
            return redirect('finanzas:expediente_pago_detalle', pk=pk)

        if accion == 'APROBAR':
            expediente.pago_validado = 'APROBADO'
            expediente.pago_observaciones = ''
            expediente.fecha_validacion_pago = timezone.now()
            expediente.save(update_fields=[
                'pago_validado', 'pago_observaciones', 'fecha_validacion_pago', 'fecha_ultima_actualizacion',
            ])

            registrar_cambio_estado(
                expediente,
                EstadoExpediente.PAGO_VALIDADO,
                request.user,
                'Finanzas aprobó el comprobante de pago.',
            )
            registrar_cambio_estado(
                expediente,
                EstadoExpediente.ADEUDOS_EN_REVISION,
                request.user,
                'El expediente avanza a confirmación de no adeudos.',
            )

            notificar_alumno(
                expediente,
                'APROBADO',
                'Pago de titulación aprobado',
                'Tu comprobante de pago fue aprobado. Las áreas institucionales revisarán tus adeudos.',
                url=reverse('alumnos:expediente'),
            )
            notificar_usuarios_por_rol(
                [Rol.FINANZAS, Rol.CENTRO_COMPUTO, Rol.CENTRO_INFORMACION],
                'Alumno pendiente de confirmación de adeudos',
                f'{expediente.alumno.get_full_name()} requiere confirmación de no adeudos.',
                tipo='URGENTE',
            )
            messages.success(request, 'Pago aprobado. El expediente avanzó a confirmación de adeudos.')
            return redirect('finanzas:adeudos_pendientes')

        elif accion == 'RECHAZAR':
            if not observaciones:
                messages.error(request, 'Debes indicar el motivo del rechazo.')
                return redirect('finanzas:expediente_pago_detalle', pk=pk)

            expediente.pago_validado = 'RECHAZADO'
            expediente.pago_observaciones = observaciones
            expediente.fecha_validacion_pago = timezone.now()
            expediente.save(update_fields=[
                'pago_validado', 'pago_observaciones', 'fecha_validacion_pago', 'fecha_ultima_actualizacion',
            ])

            notificar_alumno(
                expediente,
                'RECHAZADO',
                'Comprobante de pago rechazado',
                f'Tu comprobante fue rechazado. Observaciones: {observaciones}',
                url=reverse('alumnos:expediente'),
            )
            messages.success(request, 'Comprobante rechazado. Se notificó al alumno.')

        else:
            messages.error(request, 'Acción no válida.')

        return redirect('finanzas:expediente_pago_detalle', pk=pk)


class AdeudosPendientesView(FinanzasRequeridoMixin, ListView):
    model = Expediente
    template_name = 'finanzas/adeudos_pendientes.html'
    context_object_name = 'expedientes'
    paginate_by = 20

    def get_queryset(self):
        qs = expedientes_adeudo_pendientes(AREA_FINANZAS)
        busqueda = self.request.GET.get('q', '').strip()
        if busqueda:
            qs = qs.filter(
                Q(alumno__first_name__unaccent__icontains=busqueda) |
                Q(alumno__last_name__unaccent__icontains=busqueda) |
                Q(alumno__username__unaccent__icontains=busqueda) |
                Q(alumno__numero_control__unaccent__icontains=busqueda)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['busqueda'] = self.request.GET.get('q', '')
        ctx['area'] = AREA_FINANZAS
        return ctx


class ConfirmarAdeudoView(FinanzasRequeridoMixin, View):
    """Registra la confirmación de adeudos del área Finanzas."""

    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)
        if expediente.estado != EstadoExpediente.ADEUDOS_EN_REVISION:
            messages.error(request, 'El expediente no está en confirmación de adeudos.')
            return redirect('finanzas:adeudos_pendientes')

        accion = request.POST.get('accion')
        observaciones = request.POST.get('observaciones', '').strip()
        sin_adeudos = accion == 'LIBERAR'

        if accion not in ('LIBERAR', 'ADEUDO'):
            messages.error(request, 'Acción no válida.')
            return redirect('finanzas:adeudos_pendientes')

        if accion == 'ADEUDO' and not observaciones:
            messages.error(request, 'Indica las observaciones cuando el alumno tiene adeudos.')
            return redirect('finanzas:adeudos_pendientes')

        registrar_confirmacion_adeudo(
            expediente, AREA_FINANZAS, sin_adeudos, request.user, observaciones,
        )

        estado_txt = 'liberado sin adeudos' if sin_adeudos else 'marcado con adeudos pendientes'
        messages.success(request, f'Confirmación registrada: alumno {estado_txt}.')
        return redirect('finanzas:adeudos_pendientes')


class NotificacionesBandejaView(FinanzasRequeridoMixin, TemplateView):
    """Bandeja de notificaciones internas del área."""

    template_name = 'finanzas/notificaciones.html'

    def get_context_data(self, **kwargs):
        from expediente.notifications import marcar_notificaciones_leidas

        ctx = super().get_context_data(**kwargs)
        marcar_notificaciones_leidas(self.request.user)
        ctx['notificaciones'] = Notificacion.objects.filter(
            destinatario=self.request.user,
        ).order_by('-fecha')[:50]
        return ctx
