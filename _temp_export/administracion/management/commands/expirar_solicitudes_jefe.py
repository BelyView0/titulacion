from django.core.management.base import BaseCommand
from django.utils import timezone
import datetime
from administracion.models import SolicitudCambioJefe
from administracion.utils import procesar_resolucion_solicitud

class Command(BaseCommand):
    help = 'Expira las solicitudes de cambio de Jefe de Departamento que tienen más de 14 días y regenera los PDFs afectados.'

    def handle(self, *args, **options):
        limite_fecha = timezone.now() - datetime.timedelta(days=14)
        vencidas = SolicitudCambioJefe.objects.filter(estado='PENDIENTE', fecha_solicitud__lt=limite_fecha)
        
        total = vencidas.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('No hay solicitudes vencidas.'))
            return
            
        for sol in vencidas:
            sol.estado = 'EXPIRADO'
            sol.fecha_resolucion = timezone.now()
            procesar_resolucion_solicitud(sol, aprobada=False)
            
        self.stdout.write(self.style.SUCCESS(f'Se han expirado {total} solicitudes.'))
