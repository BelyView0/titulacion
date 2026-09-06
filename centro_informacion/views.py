"""
Vistas del módulo Centro de Información — confirmación de adeudos.
"""
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, TemplateView, View

from alumnos.models import Notificacion
from expediente.adeudo_queries import (
    expedientes_adeudo_pendientes,
    expedientes_con_adeudos,
    expedientes_liberados,
)
from expediente.mixins import CentroInformacionRequeridoMixin
from expediente.models import ConfirmacionAdeudo, EstadoExpediente, Expediente
from oficina_titulacion.services import registrar_confirmacion_adeudo


AREA = ConfirmacionAdeudo.Area.CENTRO_INFORMACION


class DashboardCentroInformacionView(CentroInformacionRequeridoMixin, TemplateView):
    template_name = 'centro_informacion/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['adeudos_pendientes'] = expedientes_adeudo_pendientes(AREA).count()
        ctx['liberados_count'] = Expediente.objects.filter(
            confirmaciones_adeudo__area=AREA,
            confirmaciones_adeudo__sin_adeudos=True,
        ).count()
        ctx['notificaciones_no_leidas'] = Notificacion.objects.filter(
            destinatario=self.request.user, leida=False,
        ).count()
        ctx['pendientes'] = expedientes_adeudo_pendientes(AREA)[:20]
        ctx['liberados'] = expedientes_liberados(AREA)
        ctx['con_adeudos'] = expedientes_con_adeudos(AREA)
        return ctx


class AdeudosPendientesView(CentroInformacionRequeridoMixin, ListView):
    model = Expediente
    template_name = 'centro_informacion/adeudos_pendientes.html'
    context_object_name = 'expedientes'
    paginate_by = 20

    def get_queryset(self):
        qs = expedientes_adeudo_pendientes(AREA)
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
        ctx['area_label'] = 'Centro de Información'
        ctx['area'] = AREA
        return ctx


class ConfirmarAdeudoView(CentroInformacionRequeridoMixin, View):
    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)
        if expediente.estado != EstadoExpediente.ADEUDOS_EN_REVISION:
            messages.error(request, 'El expediente no está en confirmación de adeudos.')
            return redirect('centro_informacion:adeudos_pendientes')

        accion = request.POST.get('accion')
        observaciones = request.POST.get('observaciones', '').strip()
        sin_adeudos = accion == 'LIBERAR'

        if accion not in ('LIBERAR', 'ADEUDO'):
            messages.error(request, 'Acción no válida.')
            return redirect('centro_informacion:adeudos_pendientes')

        if accion == 'ADEUDO' and not observaciones:
            messages.error(request, 'Indica las observaciones cuando el alumno tiene adeudos.')
            return redirect('centro_informacion:adeudos_pendientes')

        registrar_confirmacion_adeudo(
            expediente, AREA, sin_adeudos, request.user, observaciones,
        )

        estado_txt = 'liberado sin adeudos' if sin_adeudos else 'marcado con adeudos pendientes'
        messages.success(request, f'Confirmación registrada: alumno {estado_txt}.')
        return redirect('centro_informacion:adeudos_pendientes')


class NotificacionesBandejaView(CentroInformacionRequeridoMixin, TemplateView):
    template_name = 'centro_informacion/notificaciones.html'

    def get_context_data(self, **kwargs):
        from expediente.notifications import marcar_notificaciones_leidas

        ctx = super().get_context_data(**kwargs)
        marcar_notificaciones_leidas(self.request.user)
        ctx['notificaciones'] = Notificacion.objects.filter(
            destinatario=self.request.user,
        ).order_by('-fecha')[:50]
        return ctx
