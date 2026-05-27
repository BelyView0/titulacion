from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from expediente.models import Expediente, EstadoExpediente
from expediente.notifications import registrar_cambio_estado, notificar_alumno

class Command(BaseCommand):
    help = 'Establece el estado de TODOS los expedientes a ACTO_PROGRAMADO (excepto los ya en esa etapa)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra cuántos expedientes se actualizarían sin ejecutar los cambios.'
        )
        parser.add_argument(
            '--notify',
            action='store_true',
            help='Envía una notificación al alumno después de cambiar el estado.'
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        notify = options['notify']
        qs = Expediente.objects.exclude(estado=EstadoExpediente.ACTO_PROGRAMADO)
        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('✅ No hay expedientes que necesiten actualización.'))
            return
        if dry:
            self.stdout.write(f'⚙️  Se actualizarían {total} expedientes a ACTO_PROGRAMADO (modo dry-run).')
            return
        self.stdout.write(f'🔄  Actualizando {total} expedientes a ACTO_PROGRAMADO...')
        for expediente in qs:
            old_estado = expediente.estado
            expediente.estado = EstadoExpediente.ACTO_PROGRAMADO
            expediente.save(update_fields=['estado', 'fecha_ultima_actualizacion'])
            # Registrar auditoría
            registrar_cambio_estado(
                expediente=expediente,
                estado_nuevo=EstadoExpediente.ACTO_PROGRAMADO,
                realizado_por=None,
                descripcion='Cambio masivo a ACTO_PROGRAMADO ejecutado por administrador.'
            )
            if notify:
                notificar_alumno(
                    expediente=expediente,
                    tipo='INFO',
                    titulo='Estado actualizado: Acto Programado',
                    mensaje='Tu expediente ha sido devuelto a la etapa "Acto Programado" por el equipo administrativo.'
                )
        self.stdout.write(self.style.SUCCESS(f'✅  Se actualizaron {total} expedientes a ACTO_PROGRAMADO.'));
