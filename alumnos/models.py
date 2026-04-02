"""
Modelos del módulo Alumnos:
- PerfilAlumno: datos adicionales del alumno
- Notificacion: inbox interno del sistema
"""
from django.db import models
from django.conf import settings


class PerfilAlumno(models.Model):
    """Perfil extendido del alumno con datos académicos."""
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil_alumno',
        limit_choices_to={'rol': 'ALUMNO'}
    )
    numero_control = models.CharField(
        max_length=20, unique=True,
        verbose_name='Número de control'
    )
    carrera = models.ForeignKey(
        'administracion.Carrera',
        on_delete=models.PROTECT,
        verbose_name='Carrera'
    )
    plan_estudios = models.ForeignKey(
        'expediente.PlanEstudios',
        on_delete=models.PROTECT,
        verbose_name='Plan de Estudios',
        null=True, blank=True
    )
    semestre_egreso = models.CharField(
        max_length=20, blank=True,
        verbose_name='Semestre de egreso (ej: Ago-Dic 2024)'
    )
    promedio = models.DecimalField(
        max_digits=4, decimal_places=2,
        null=True, blank=True,
        verbose_name='Promedio general'
    )
    correo_institucional = models.EmailField(
        blank=True,
        verbose_name='Correo institucional',
        help_text='Correo @apizaco.tecnm.mx o institucional para notificaciones'
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Perfil de Alumno'
        verbose_name_plural = 'Perfiles de Alumnos'

    def __str__(self):
        return f'{self.numero_control} — {self.usuario.get_full_name()}'


class Notificacion(models.Model):
    """
    Notificaciones internas del sistema para el alumno.
    Se crean automáticamente vía señales Django al cambiar estados.
    """
    TIPO_CHOICES = [
        ('INFO', 'Información'),
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
        ('CORRECCION', 'Se requiere corrección'),
        ('AVANCE', 'Avance del proceso'),
        ('URGENTE', 'Urgente'),
    ]

    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notificaciones',
        verbose_name='Destinatario'
    )
    tipo = models.CharField(
        max_length=15, choices=TIPO_CHOICES,
        default='INFO', verbose_name='Tipo'
    )
    titulo = models.CharField(max_length=200, verbose_name='Título')
    mensaje = models.TextField(verbose_name='Mensaje')
    leida = models.BooleanField(default=False, verbose_name='¿Leída?')
    fecha = models.DateTimeField(auto_now_add=True, verbose_name='Fecha')
    url_relacionada = models.CharField(
        max_length=300, blank=True,
        verbose_name='URL relacionada (para enlace directo)'
    )

    class Meta:
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.titulo} → {self.destinatario.get_full_name()}'

    def get_tipo_color(self):
        colores = {
            'INFO': 'info',
            'APROBADO': 'success',
            'RECHAZADO': 'danger',
            'CORRECCION': 'warning',
            'AVANCE': 'primary',
            'URGENTE': 'danger',
        }
        return colores.get(self.tipo, 'secondary')

    def get_tipo_icono(self):
        iconos = {
            'INFO': 'bi-info-circle',
            'APROBADO': 'bi-check-circle',
            'RECHAZADO': 'bi-x-circle',
            'CORRECCION': 'bi-exclamation-triangle',
            'AVANCE': 'bi-arrow-right-circle',
            'URGENTE': 'bi-bell',
        }
        return iconos.get(self.tipo, 'bi-bell')
