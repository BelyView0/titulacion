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
    JEFE_PROYECTO = 'JEFE_PROYECTO', 'Jefe de Proyectos / Academia'
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
    departamentos = models.ManyToManyField(
        'Departamento',
        blank=True,
        related_name='profesores',
        verbose_name='Departamentos'
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
    debe_cambiar_password = models.BooleanField(
        default=False,
        verbose_name='Debe cambiar contrasena',
        help_text='Si es True, el usuario sera forzado a cambiar su contrasena al iniciar sesion.'
    )
    correo_institucional = models.EmailField(
        blank=True, null=True,
        verbose_name='Correo institucional',
        help_text='Correo @apizaco.tecnm.mx o institucional para notificaciones'
    )
    correo_institucional_verificado = models.BooleanField(
        default=False,
        verbose_name='Correo institucional verificado'
    )
    email_verificado = models.BooleanField(
        default=False,
        verbose_name='Correo alternativo verificado'
    )

    @property
    def username_visual(self):
        if self.numero_control:
            return self.numero_control
        
        if not self.first_name:
            return self.username
            
        nombres = self.first_name.strip().split()
        primer_nombre = nombres[0].capitalize()
        inicial_segundo = nombres[1][0].upper() if len(nombres) > 1 and nombres[1] else ""
        
        inicial_paterno = self.last_name.strip()[0].upper() if self.last_name and self.last_name.strip() else ""
        inicial_materno = self.apellido_materno.strip()[0].upper() if self.apellido_materno and self.apellido_materno.strip() else ""
        
        generado = f"{primer_nombre}{inicial_segundo}{inicial_paterno}{inicial_materno}"
        return generado if len(generado) > 1 else self.username

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
        return self.first_name or self.numero_control or self.username

    def save(self, *args, **kwargs):
        if self.numero_control:
            self.username = self.numero_control
        super().save(*args, **kwargs)

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

    @property
    def tiene_expediente(self):
        """Verifica si el usuario tiene un expediente asociado (OneToOne)."""
        try:
            return self.expediente is not None
        except Exception:
            return False

    @property
    def url_foto_perfil(self):
        """Obtiene la URL de la foto de perfil, ya sea del modelo o del expediente del alumno."""
        if self.foto_perfil:
            return self.foto_perfil.url
        
        if self.es_alumno and self.tiene_expediente:
            try:
                from expediente.models import Documento
                doc_foto = Documento.objects.filter(
                    expediente=self.expediente, 
                    tipo_documento__es_fotografia=True
                ).exclude(archivo='').first()
                if doc_foto and doc_foto.archivo:
                    return doc_foto.archivo.url
            except Exception:
                pass
                
        return None

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
    dominio_institucional = models.CharField(
        max_length=100,
        verbose_name="Dominio Institucional",
        help_text="Dominio requerido para el correo institucional (ej: apizaco.tecnm.mx)",
        default="apizaco.tecnm.mx"
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
    
    # ── Configuración de Correo Electrónico (SMTP) ──
    email_host = models.CharField(
        max_length=255, default='smtp.gmail.com',
        verbose_name='Servidor SMTP (Host)',
        help_text='Ej: smtp.gmail.com, smtp.office365.com'
    )
    email_port = models.IntegerField(
        default=587,
        verbose_name='Puerto SMTP',
        help_text='Ej: 587 (TLS), 465 (SSL)'
    )
    email_use_tls = models.BooleanField(
        default=True,
        verbose_name='Usar TLS',
        help_text='Habilitar seguridad TLS (Recomendado para el puerto 587)'
    )
    email_remitente = models.EmailField(
        blank=True, null=True,
        verbose_name='Correo Remitente',
        help_text='Cuenta de correo desde donde se enviarán las notificaciones'
    )
    email_password = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name='Contraseña de Aplicación',
        help_text='Contraseña de aplicación generada desde el proveedor de correo'
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


class SolicitudCambioJefe(models.Model):
    """
    Ticket para solicitar la actualización de un Jefe de Departamento.
    Permite uso urgente en oficios mientras el Administrador lo aprueba.
    """
    class EstadoSolicitud(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        APROBADO = 'APROBADO', 'Aprobado'
        RECHAZADO = 'RECHAZADO', 'Rechazado'
        EXPIRADO = 'EXPIRADO', 'Expirado'

    departamento = models.ForeignKey(
        Departamento,
        on_delete=models.CASCADE,
        related_name='solicitudes_cambio_jefe'
    )
    solicitante = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        related_name='solicitudes_cambio_jefe'
    )
    titulo_academico_nuevo = models.CharField(max_length=50, verbose_name="Título Académico")
    nombre_nuevo = models.CharField(max_length=150, verbose_name="Nombre(s)")
    apellido_paterno_nuevo = models.CharField(max_length=150, verbose_name="Apellido Paterno")
    apellido_materno_nuevo = models.CharField(max_length=150, blank=True, verbose_name="Apellido Materno")
    genero_nuevo = models.CharField(max_length=1, choices=Genero.choices, default=Genero.FEMENINO)
    
    estado = models.CharField(
        max_length=15,
        choices=EstadoSolicitud.choices,
        default=EstadoSolicitud.PENDIENTE
    )
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Solicitud de Cambio de Jefe"
        verbose_name_plural = "Solicitudes de Cambio de Jefe"

    def __str__(self):
        return f"Solicitud para {self.departamento.nombre} - {self.get_full_name()}"

    @property
    def titulo_academico(self):
        return self.titulo_academico_nuevo

    @property
    def nombre(self):
        return self.nombre_nuevo

    @property
    def apellido_paterno(self):
        return self.apellido_paterno_nuevo

    @property
    def apellido_materno(self):
        return self.apellido_materno_nuevo

    def get_full_name(self):
        partes = [self.nombre_nuevo, self.apellido_paterno_nuevo, self.apellido_materno_nuevo]
        return ' '.join(p.strip() for p in partes if p and p.strip())

    def get_genero_display(self):
        return dict(Genero.choices).get(self.genero_nuevo, self.genero_nuevo)

class PasswordResetOTP(models.Model):
    """
    Almacena los códigos de 6 dígitos (OTP) para verificación de contraseña.
    """
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='otps')
    codigo = models.CharField(max_length=6, verbose_name="Código de 6 dígitos")
    creado_en = models.DateTimeField(auto_now_add=True)
    usado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Código OTP"
        verbose_name_plural = "Códigos OTP"

    def __str__(self):
        return f"OTP para {self.usuario.username} - {self.creado_en}"

class EmailVerificationOTP(models.Model):
    """
    Almacena los códigos de 6 dígitos (OTP) para verificación de correos.
    """
    TIPO_CORREO_CHOICES = [
        ('INSTITUCIONAL', 'Institucional'),
        ('PERSONAL', 'Personal'),
    ]
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='email_otps')
    email_a_verificar = models.EmailField(verbose_name="Correo a verificar")
    tipo_correo = models.CharField(max_length=15, choices=TIPO_CORREO_CHOICES)
    codigo = models.CharField(max_length=6, verbose_name="Código de 6 dígitos")
    creado_en = models.DateTimeField(auto_now_add=True)
    usado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "OTP de Verificación de Correo"
        verbose_name_plural = "OTPs de Verificación de Correos"

    def __str__(self):
        return f"Verificación para {self.email_a_verificar} - {self.codigo}"

    def is_valid(self):
        from django.utils import timezone
        import datetime
        # Válido si no ha sido usado y han pasado menos de 15 minutos
        return not self.usado and (timezone.now() - self.creado_en) < datetime.timedelta(minutes=15)

