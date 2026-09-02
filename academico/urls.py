"""Redirecciones legadas hacia Oficina de Titulación."""
from django.shortcuts import redirect
from django.urls import path

app_name = 'academico'


def _redirect_dashboard(request):
    return redirect('oficina_titulacion:dashboard')


def _redirect_expedientes(request):
    return redirect('oficina_titulacion:expedientes')


def _redirect_expediente(request, pk):
    return redirect('oficina_titulacion:expediente_detalle', pk=pk)


urlpatterns = [
    path('', _redirect_dashboard, name='dashboard'),
    path('expedientes/', _redirect_expedientes, name='expedientes'),
    path('expedientes/<int:pk>/', _redirect_expediente, name='expediente_detalle'),
]
