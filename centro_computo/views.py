"""
Vistas del módulo Centro de Cómputo — confirmación de adeudos.
"""
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import ListView, TemplateView, View

from alumnos.models import Notificacion
from expediente.adeudo_queries import (
    expedientes_adeudo_pendientes,
    expedientes_con_adeudos,
    expedientes_liberados,
)
from expediente.mixins import CentroComputoRequeridoMixin
from expediente.models import ConfirmacionAdeudo, EstadoExpediente, Expediente
from expediente.notifications import notificar_alumno
from oficina_titulacion.services import registrar_confirmacion_adeudo


AREA = ConfirmacionAdeudo.Area.CENTRO_COMPUTO


class DashboardCentroComputoView(CentroComputoRequeridoMixin, TemplateView):
    template_name = 'centro_computo/dashboard.html'

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
        ctx['expedientes_recientes'] = expedientes_adeudo_pendientes(AREA)[:10]
        return ctx


class AdeudosPendientesView(CentroComputoRequeridoMixin, ListView):
    model = Expediente
    template_name = 'centro_computo/adeudos_pendientes.html'
    context_object_name = 'expedientes'
    paginate_by = 20

    def get_queryset(self):
        qs = expedientes_adeudo_pendientes(AREA)
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
        ctx['area_label'] = 'Centro de Cómputo'
        return ctx


class ConfirmarAdeudoView(CentroComputoRequeridoMixin, View):
    def post(self, request, pk):
        expediente = get_object_or_404(Expediente, pk=pk)
        if expediente.estado != EstadoExpediente.ADEUDOS_EN_REVISION:
            messages.error(request, 'El expediente no está en confirmación de adeudos.')
            return redirect('centro_computo:adeudos_pendientes')

        accion = request.POST.get('accion')
        observaciones = request.POST.get('observaciones', '').strip()
        sin_adeudos = accion == 'LIBERAR'

        if accion not in ('LIBERAR', 'ADEUDO'):
            messages.error(request, 'Acción no válida.')
            return redirect('centro_computo:adeudos_pendientes')

        if accion == 'ADEUDO' and not observaciones:
            messages.error(request, 'Indica las observaciones cuando el alumno tiene adeudos.')
            return redirect('centro_computo:adeudos_pendientes')

        registrar_confirmacion_adeudo(
            expediente, AREA, sin_adeudos, request.user, observaciones,
        )

        estado_txt = 'liberado sin adeudos' if sin_adeudos else 'marcado con adeudos pendientes'
        notificar_alumno(
            expediente,
            'INFO' if sin_adeudos else 'URGENTE',
            'Confirmación de adeudos — Centro de Cómputo',
            f'Centro de Cómputo te ha {estado_txt}.'
            + (f' Observaciones: {observaciones}' if observaciones else ''),
            url=reverse('alumnos:expediente'),
        )
        messages.success(request, f'Confirmación registrada: alumno {estado_txt}.')
        return redirect('centro_computo:adeudos_pendientes')


class NotificacionesBandejaView(CentroComputoRequeridoMixin, TemplateView):
    template_name = 'centro_computo/notificaciones.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        notifs = Notificacion.objects.filter(
            destinatario=self.request.user,
        ).order_by('-fecha')[:50]
        notifs.filter(leida=False).update(leida=True)
        ctx['notificaciones'] = notifs
        ctx['pendientes'] = expedientes_adeudo_pendientes(AREA)[:20]
        ctx['liberados'] = expedientes_liberados(AREA)
        ctx['con_adeudos'] = expedientes_con_adeudos(AREA)
        return ctx
