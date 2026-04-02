"""
Modelos de Administración del Sistema
- Usuario (Custom AbstractUser con roles)
- Carrera
- Departamento
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class Genero(models.TextChoices):
    MASCULINO = 'M', 'Masculino'
    FEMENINO = 'F', 'Femenino'
    OTRO = 'O', 'Otro / Prefiero no decir'


class Rol(models.TextChoices):
    ADMINISTRADOR = 'ADMIN', 'Administrador del Sistema'
    JEFE_PROYECTO = 'JEFE_PROYECTO', 'Jefe de Proyecto / Administración'
    ESCOLARES = 'ESCOLARES', 'Servicios Escolares'
    ACADEMICO = 'ACADEMICO', 'División de Estudios Profesionales'
    ALUMNO = 'ALUMNO', 'Alumno'


class Carrera(models.Model):
    nombre = models.CharField(max_length=200, verbose_name='Nombre de la carrera')
    clave = models.CharField(max_length=20, unique=True, verbose_name='Clave')
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Carrera'
        verbose_name_plural = 'Carreras'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Departamento(models.Model):
    nombre = models.CharField(max_length=200, verbose_name='Nombre del departamento')
    clave = models.CharField(max_length=20, unique=True)
    rol_responsable = models.CharField(max_length=20, choices=Rol.choices, default=Rol.ACADEMICO)

    class Meta:
        verbose_name = 'Departamento'
        verbose_name_plural = 'Departamentos'

    def __str__(self):
        return self.nombre


class Usuario(AbstractUser):
    """
    Usuario extendido con rol y datos institucionales.
    Reemplaza al User de Django.
    """
    rol = models.CharField(
        max_length=20,
        choices=Rol.choices,
        default=Rol.ALUMNO,
        verbose_name='Rol en el sistema'
    )
    numero_empleado = models.CharField(
        max_length=20, blank=True, null=True,
        verbose_name='Número de empleado'
    )
    carrera = models.ForeignKey(
        Carrera, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Carrera'
    )
    telefono = models.CharField(max_length=15, blank=True, verbose_name='Teléfono')
    genero = models.CharField(
        max_length=1,
        choices=Genero.choices,
        blank=True,
        verbose_name='Género'
    )
    generacion = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Generación (año de ingreso)',
        help_text='Ej: 2022'
    )
    foto_perfil = models.ImageField(
        upload_to='perfiles/', null=True, blank=True,
        verbose_name='Foto de perfil'
    )

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f'{self.get_full_name()} ({self.get_rol_display()})'

    @property
    def es_admin(self):
        return self.rol == Rol.ADMINISTRADOR

    @property
    def es_escolares(self):
        return self.rol == Rol.ESCOLARES

    @property
    def es_academico(self):
        return self.rol == Rol.ACADEMICO

    @property
    def es_alumno(self):
        return self.rol == Rol.ALUMNO

    @property
    def es_jefe_proyecto(self):
        return self.rol == Rol.JEFE_PROYECTO

    def get_dashboard_url(self):
        from django.urls import reverse
        dashboards = {
            Rol.ADMINISTRADOR: 'administracion:dashboard',
            Rol.JEFE_PROYECTO: 'administracion:jefe_dashboard',
            Rol.ESCOLARES: 'escolares:dashboard',
            Rol.ACADEMICO: 'academico:dashboard',
            Rol.ALUMNO: 'alumnos:dashboard',
        }
        return reverse(dashboards.get(self.rol, 'alumnos:dashboard'))
