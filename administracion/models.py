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
    departamento = models.ForeignKey(
        'Departamento',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='carreras',
        verbose_name='Departamento'
    )

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


class Profesor(models.Model):
    """
    Catedrático / sinodal de la institución.
    Independiente del sistema de usuarios — no necesita login.
    """
    first_name = models.CharField(max_length=150, verbose_name='Nombre(s)')
    last_name = models.CharField(max_length=150, verbose_name='Apellido paterno')
    apellido_materno = models.CharField(max_length=150, blank=True, verbose_name='Apellido materno')
    titulo_academico = models.CharField(
        max_length=250,
        verbose_name='Título académico',
        help_text='Ej: Doctor en Sistemas Computacionales, Maestra en Ingeniería'
    )
    cedula = models.CharField(
        max_length=20,
        verbose_name='Cédula profesional',
        help_text='Número de cédula expedida por SEP'
    )
    email = models.EmailField(blank=True, verbose_name='Correo electrónico')
    departamento = models.ForeignKey(
        'Departamento',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='profesores',
        verbose_name='Departamento'
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Profesor / Sinodal'
        verbose_name_plural = 'Profesores / Sinodales'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return self.get_full_name()

    def get_full_name(self):
        partes = [self.first_name, self.last_name, self.apellido_materno]
        return ' '.join(p.strip().upper() for p in partes if p and p.strip())

    def get_nombre_con_titulo(self):
        """Formato para el oficio: 'Doctor en SC JUAN RAMOS RAMOS No. Cédula 14098703'"""
        return f'{self.titulo_academico} {self.get_full_name()} No. Cédula {self.cedula}'

    def get_nombre_corto(self):
        """Formato para correos: 'Doctor en SC JUAN RAMOS RAMOS' (sin cédula)."""
        return f'{self.titulo_academico} {self.get_full_name()}'


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
    numero_control = models.CharField(
        max_length=20, blank=True, null=True,
        verbose_name='Número de control / empleado',
        help_text='Número de control para alumnos o número de empleado para personal'
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
    # Sobrescribimos los verboses de Django para el contexto mexicano
    first_name = models.CharField(
        max_length=150, blank=True,
        verbose_name='Nombre(s)'
    )
    last_name = models.CharField(
        max_length=150, blank=True,
        verbose_name='Apellido paterno'
    )
    apellido_materno = models.CharField(
        max_length=150, blank=True,
        verbose_name='Apellido materno'
    )
    departamento = models.ForeignKey(
        'Departamento',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='jefes',
        verbose_name='Departamento (solo para Jefes de Proyecto)'
    )

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f'{self.get_full_name()} ({self.get_rol_display()})'

    def get_full_name(self):
        """Nombre completo: Nombre(s) ApellidoPaterno ApellidoMaterno"""
        partes = [self.first_name, self.last_name, self.apellido_materno]
        return ' '.join(p.strip() for p in partes if p and p.strip()) or self.username

    def get_short_name(self):
        return self.first_name or self.username

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


class ConfiguracionInstitucional(models.Model):
    """
    Modelo Singleton para almacenar la configuración de logos institucionales.
    Permite subir la imagen completa del encabezado y del pie de página.
    """
    anio_en_curso = models.IntegerField(
        verbose_name="Año en curso",
        help_text="Ej: 2026",
        default=2026
    )
    imagen_encabezado = models.ImageField(
        upload_to='configuracion/',
        blank=True, null=True,
        verbose_name="Imagen completa del Encabezado",
        help_text="Sube la imagen completa que servirá de membrete superior."
    )
    imagen_pie_pagina = models.ImageField(
        upload_to='configuracion/',
        blank=True, null=True,
        verbose_name="Imagen completa del Pie de Página",
        help_text="Sube la imagen completa que servirá de pie de página."
    )

    class Meta:
        verbose_name = "Configuración Institucional"
        verbose_name_plural = "Configuración Institucional"

    def __str__(self):
        return f"Membretes Oficiales del Año {self.anio_en_curso}"

    def save(self, *args, **kwargs):
        if not self.pk and ConfiguracionInstitucional.objects.exists():
            return ConfiguracionInstitucional.objects.first()
        return super(ConfiguracionInstitucional, self).save(*args, **kwargs)


class JefeDepartamento(models.Model):
    """
    Representa al Jefe o Jefa de un Departamento Académico o Administrativo.
    Se utiliza principalmente para estampar la firma y el cargo en los oficios generados.
    """
    departamento = models.OneToOneField(
        Departamento,
        on_delete=models.CASCADE,
        related_name='jefe_asignado',
        verbose_name="Departamento"
    )
    titulo_academico = models.CharField(
        max_length=50,
        verbose_name="Título Académico",
        help_text="Ej: Ing., M.C., Dra., Dr."
    )
    nombre = models.CharField(max_length=150, verbose_name="Nombre(s)")
    apellido_paterno = models.CharField(max_length=150, verbose_name="Apellido Paterno")
    apellido_materno = models.CharField(max_length=150, blank=True, verbose_name="Apellido Materno")
    genero = models.CharField(
        max_length=1,
        choices=Genero.choices,
        default=Genero.FEMENINO,
        verbose_name="Género",
        help_text="Se usa para determinar si el cargo dice 'JEFE' o 'JEFA'"
    )

    class Meta:
        verbose_name = "Jefe de Departamento"
        verbose_name_plural = "Jefes de Departamento"

    def __str__(self):
        return f"{self.titulo_academico} {self.get_full_name()} - {self.departamento.nombre}"

    def get_full_name(self):
        partes = [self.nombre, self.apellido_paterno, self.apellido_materno]
        return ' '.join(p.strip() for p in partes if p and p.strip())
