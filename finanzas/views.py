"""
Vistas del módulo Finanzas — pagos y confirmación de adeudos.
"""
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import Q
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
            estado=EstadoExpediente.PAGO_PENDIENTE,
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
        ctx['expedientes_pago_recientes'] = Expediente.objects.filter(
            estado__in=[EstadoExpediente.PAGO_PENDIENTE, EstadoExpediente.PAGO_VALIDADO],
        ).select_related('alumno', 'alumno__carrera').order_by('-fecha_ultima_actualizacion')[:10]
        return ctx


class ExpedientesPagoView(FinanzasRequeridoMixin, ListView):
    model = Expediente
    template_name = 'finanzas/expedientes_pago.html'
    context_object_name = 'expedientes'
    paginate_by = 20

    def get_queryset(self):
        qs = Expediente.objects.filter(
            estado__in=[EstadoExpediente.PAGO_PENDIENTE, EstadoExpediente.PAGO_VALIDADO],
        ).select_related('alumno', 'alumno__carrera', 'modalidad').prefetch_related('referencias_pago')

        estado = self.request.GET.get('estado', '').strip()
        if estado in (EstadoExpediente.PAGO_PENDIENTE, EstadoExpediente.PAGO_VALIDADO):
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

    def get_queryset(self):
        return Expediente.objects.filter(
            estado__in=[EstadoExpediente.PAGO_PENDIENTE, EstadoExpediente.PAGO_VALIDADO],
        ).select_related('alumno', 'alumno__carrera', 'modalidad').prefetch_related('referencias_pago')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['referencia_activa'] = self.object.referencias_pago.filter(activa=True).first()
        return ctx


class GenerarReferenciaPagoView(FinanzasRequeridoMixin, View):
    """Genera una referencia de pago para el expediente."""

    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)
        if expediente.estado != EstadoExpediente.PAGO_PENDIENTE:
            messages.error(request, 'El expediente no está en etapa de pago pendiente.')
            return redirect('finanzas:expediente_pago_detalle', pk=pk)

        monto_raw = request.POST.get('monto', '').strip()
        vigencia_raw = request.POST.get('vigencia', '').strip()
        pdf = request.FILES.get('pdf_referencia')

        try:
            monto = Decimal(monto_raw)
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
        referencia = ReferenciaPago.objects.create(
            expediente=expediente,
            folio=folio,
            monto=monto,
            vigencia=vigencia,
            pdf_referencia=pdf,
            generado_por=request.user,
            activa=True,
        )

        notificar_alumno(
            expediente,
            'AVANCE',
            'Referencia de pago generada',
            f'Se generó su referencia de pago {referencia.folio} por ${referencia.monto}. '
            f'Descárguela y realice el pago correspondiente.',
            url=reverse('alumnos:expediente'),
        )
        messages.success(request, f'Referencia {referencia.folio} generada correctamente.')
        return redirect('finanzas:expediente_pago_detalle', pk=pk)


class ValidarPagoView(FinanzasRequeridoMixin, View):
    """Aprueba o rechaza el comprobante de pago del alumno."""

    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)
        accion = request.POST.get('accion')
        observaciones = request.POST.get('observaciones', '').strip()

        if expediente.estado != EstadoExpediente.PAGO_PENDIENTE:
            messages.error(request, 'El expediente no está pendiente de validación de pago.')
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
                Q(alumno__username__unaccent__icontains=busqueda)
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
        notificar_alumno(
            expediente,
            'INFO' if sin_adeudos else 'URGENTE',
            f'Confirmación de adeudos — Finanzas',
            f'Finanzas te ha {estado_txt}.'
            + (f' Observaciones: {observaciones}' if observaciones else ''),
            url=reverse('alumnos:expediente'),
        )
        messages.success(request, f'Confirmación registrada: alumno {estado_txt}.')
        return redirect('finanzas:adeudos_pendientes')


class NotificacionesBandejaView(FinanzasRequeridoMixin, TemplateView):
    """Bandeja de notificaciones y seguimiento de alumnos pendientes/liberados."""

    template_name = 'finanzas/notificaciones.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        notifs = Notificacion.objects.filter(
            destinatario=self.request.user,
        ).order_by('-fecha')[:50]
        notifs.filter(leida=False).update(leida=True)
        ctx['notificaciones'] = notifs
        ctx['pendientes'] = expedientes_adeudo_pendientes(AREA_FINANZAS)[:20]
        ctx['liberados'] = expedientes_liberados(AREA_FINANZAS)
        ctx['con_adeudos'] = expedientes_con_adeudos(AREA_FINANZAS)
        return ctx
