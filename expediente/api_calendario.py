"""
API JSON para alimentar el calendario FullCalendar.js
Retorna los actos protocolarios como eventos JSON.
"""
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from expediente.models import ActoProtocolario, AsignacionJurado


@login_required
def eventos_calendario(request):
    """
    GET /api/calendario/eventos/?start=YYYY-MM-DD&end=YYYY-MM-DD&carrera=ID&q=texto
    Retorna eventos JSON para FullCalendar.
    Filtra según el rol del usuario.
    """
    user = request.user
    start = request.GET.get('start')
    end = request.GET.get('end')
    carrera_id = request.GET.get('carrera')
    busqueda = request.GET.get('q', '').strip()

    qs = ActoProtocolario.objects.select_related(
        'expediente__alumno__carrera',
        'expediente__modalidad',
        'jurado__presidente',
        'jurado__secretario',
        'jurado__vocal_propietario',
        'jurado__vocal_suplente',
    )

    # Filtrar por rango de fechas (FullCalendar envía start/end)
    if start:
        qs = qs.filter(fecha_acto__gte=start)
    if end:
        qs = qs.filter(fecha_acto__lte=end)

    # Filtrar por rol del usuario
    if user.es_jefe_proyecto:
        if user.departamento:
            qs = qs.filter(expediente__alumno__carrera__departamento=user.departamento)
        elif user.carrera:
            qs = qs.filter(expediente__alumno__carrera=user.carrera)
    elif user.es_alumno:
        qs = qs.filter(expediente__alumno=user)

    # Filtrar por carrera (opcional, para académico/escolares/admin)
    if carrera_id:
        qs = qs.filter(expediente__alumno__carrera_id=carrera_id)

    # Búsqueda por nombre/control
    if busqueda:
        from django.db.models import Q
        qs = qs.filter(
            Q(expediente__alumno__first_name__unaccent__icontains=busqueda) |
            Q(expediente__alumno__last_name__unaccent__icontains=busqueda) |
            Q(expediente__alumno__username__unaccent__icontains=busqueda) |
            Q(expediente__alumno__numero_control__unaccent__icontains=busqueda)
        )

    eventos = []
    for acto in qs.order_by('fecha_acto'):
        exp = acto.expediente
        alumno = exp.alumno

        # Color según resultado
        color_map = {
            'PENDIENTE': '#f59e0b',       # amarillo
            'APROBADO': '#16a34a',        # verde
            'APROBADO_MENCION': '#7c3aed', # morado
            'SUSPENDIDO': '#dc3545',       # rojo
            'NO_PRESENTADO': '#6c757d',    # gris
        }
        color = color_map.get(acto.resultado, '#0d6efd')

        # Info del jurado
        jurado = acto.jurado
        jurado_info = ''
        if jurado:
            jurado_info = (
                f"Presidente: {jurado.presidente.get_full_name()}\n"
                f"Secretario: {jurado.secretario.get_full_name()}\n"
            )
            if jurado.vocal_propietario:
                jurado_info += f"Vocal: {jurado.vocal_propietario.get_full_name()}\n"
            if jurado.vocal_suplente:
                jurado_info += f"Suplente: {jurado.vocal_suplente.get_full_name()}"

        eventos.append({
            'id': acto.pk,
            'title': alumno.get_full_name(),
            'start': acto.fecha_acto.isoformat(),
            'backgroundColor': color,
            'borderColor': color,
            'extendedProps': {
                'alumno': alumno.get_full_name(),
                'control': getattr(alumno, 'numero_control', alumno.username) or alumno.username,
                'carrera': alumno.carrera.nombre if alumno.carrera else '—',
                'modalidad': exp.modalidad.nombre if exp.modalidad else '—',
                'titulo_trabajo': exp.titulo_trabajo or '—',
                'lugar': acto.lugar,
                'resultado': acto.get_resultado_display(),
                'resultado_key': acto.resultado,
                'jurado': jurado_info,
                'expediente_pk': exp.pk,
            },
        })

    return JsonResponse(eventos, safe=False)
