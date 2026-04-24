"""
Modelos del Núcleo del Sistema de Titulación (App Expediente)
Incluye todos los modelos del proceso:
- PlanEstudios, Modalidad, TipoDocumento (catálogos)
- Expediente, Documento, ValidacionDocumento
- EnvioCDMX, RecepcionEmpastado
- AsignacionJurado, ActoProtocolario
- HistorialExpediente, HistorialDocumento
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


# ─────────────────────────────────────────────────────────────
# CATÁLOGOS ADMINISTRABLES
# ─────────────────────────────────────────────────────────────

class PlanEstudios(models.Model):
    nombre = models.CharField(max_length=20, unique=True, verbose_name='Plan de Estudios')
    descripcion = models.CharField(max_length=200, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Plan de Estudios'
        verbose_name_plural = 'Planes de Estudios'
        ordering = ['-nombre']

    def __str__(self):
        return f'Plan {self.nombre}'


class Modalidad(models.Model):
    """Modalidades de titulación por plan de estudios."""
    plan_estudios = models.ForeignKey(
        PlanEstudios, on_delete=models.CASCADE,
        related_name='modalidades',
        verbose_name='Plan de Estudios'
    )
    nombre = models.CharField(max_length=200, verbose_name='Nombre de la modalidad')
    clave = models.CharField(max_length=30, verbose_name='Clave (ej: RESIDENCIA, TESIS)')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Modalidad de Titulación'
        verbose_name_plural = 'Modalidades de Titulación'
        ordering = ['plan_estudios', 'nombre']

    def __str__(self):
        return f'{self.nombre} — {self.plan_estudios}'


class TipoDocumento(models.Model):
    """
    Catálogo de documentos requeridos por modalidad.
    El administrador configura qué documentos pide cada modalidad.
    """
    modalidad = models.ForeignKey(
        Modalidad, on_delete=models.CASCADE,
        related_name='tipos_documento',
        verbose_name='Modalidad'
    )
    nombre = models.CharField(max_length=200, verbose_name='Nombre del documento')
    descripcion_ayuda = models.TextField(
        verbose_name='Instrucciones para el alumno',
        help_text='Describe cómo debe ser el documento (formato, requisitos, etc.)'
    )
    es_obligatorio = models.BooleanField(default=True, verbose_name='¿Es obligatorio?')
    orden = models.PositiveIntegerField(default=0, verbose_name='Orden de presentación')
    # ¿Qué departamentos deben validarlo?
    valida_division = models.BooleanField(default=True, verbose_name='Valida División de Estudios')
    valida_escolares = models.BooleanField(default=True, verbose_name='Valida Servicios Escolares')
    acepta_solo_pdf = models.BooleanField(default=True, verbose_name='Solo acepta PDF')
    es_fotografia = models.BooleanField(default=False, verbose_name='¿Es fotografía?')

    class Meta:
        verbose_name = 'Tipo de Documento Requerido'
        verbose_name_plural = 'Tipos de Documentos Requeridos'
        ordering = ['modalidad', 'orden']

    def __str__(self):
        return f'{self.nombre} ({self.modalidad.nombre})'


# ─────────────────────────────────────────────────────────────
# ESTADOS DEL PROCESO
# ─────────────────────────────────────────────────────────────

class EstadoExpediente(models.TextChoices):
    BORRADOR = 'BORRADOR', 'Borrador'
    EN_REVISION_ACADEMICO = 'EN_REVISION_ACADEMICO', 'En Revisión — División de Estudios'
    RECHAZADO_ACADEMICO = 'RECHAZADO_ACADEMICO', 'Rechazado por División de Estudios'
    EN_CORRECCION = 'EN_CORRECCION', 'En Corrección por el Alumno'
    DOCUMENTOS_PENDIENTES = 'DOCUMENTOS_PENDIENTES', 'Carga de Documentos Pendiente'
    EN_REVISION_DOCUMENTOS = 'EN_REVISION_DOCUMENTOS', 'Documentos en Revisión'
    LISTO_INTEGRACION = 'LISTO_INTEGRACION', 'Listo para Integración (Escolares)'
    INTEGRADO = 'INTEGRADO', 'Expediente Integrado'
    ENVIADO_CDMX = 'ENVIADO_CDMX', 'Enviado a Revisión CDMX'
    RECHAZADO_CDMX = 'RECHAZADO_CDMX', 'Rechazado por CDMX'
    APROBADO_CDMX = 'APROBADO_CDMX', 'Aprobado por CDMX'
    EMPASTADO_PENDIENTE = 'EMPASTADO_PENDIENTE', 'Pendiente de Recepción de Empastado'
    EMPASTADO_RECIBIDO = 'EMPASTADO_RECIBIDO', 'Empastado Recibido'
    JURADO_ASIGNADO = 'JURADO_ASIGNADO', 'Jurado Asignado'
    ACTO_PROGRAMADO = 'ACTO_PROGRAMADO', 'Acto Protocolario Programado'
    CONCLUIDO = 'CONCLUIDO', 'Proceso Concluido'
    CANCELADO = 'CANCELADO', 'Cancelado'


class EstadoDocumento(models.TextChoices):
    PENDIENTE = 'PENDIENTE', 'Pendiente de carga'
    CARGADO = 'CARGADO', 'Cargado — Sin Revisar'
    EN_REVISION = 'EN_REVISION', 'En Revisión'
    APROBADO = 'APROBADO', 'Aprobado'
    RECHAZADO = 'RECHAZADO', 'Rechazado'
    REQUIERE_CORRECCION = 'REQUIERE_CORRECCION', 'Requiere Corrección'


class EstadoValidacion(models.TextChoices):
    PENDIENTE = 'PENDIENTE', 'Pendiente'
    APROBADO = 'APROBADO', 'Aprobado'
    RECHAZADO = 'RECHAZADO', 'Rechazado'
    REQUIERE_CORRECCION = 'REQUIERE_CORRECCION', 'Requiere Corrección'


# ─────────────────────────────────────────────────────────────
# EXPEDIENTE
# ─────────────────────────────────────────────────────────────

class Expediente(models.Model):
    """
    Expediente de titulación del alumno.
    Existe uno por alumno. Centraliza todo el proceso.
    """
    alumno = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='expediente',
        limit_choices_to={'rol': 'ALUMNO'},
        verbose_name='Alumno'
    )
    modalidad = models.ForeignKey(
        Modalidad, on_delete=models.PROTECT,
        verbose_name='Modalidad de Titulación',
        null=True, blank=True
    )
    estado = models.CharField(
        max_length=40,
        choices=EstadoExpediente.choices,
        default=EstadoExpediente.BORRADOR,
        verbose_name='Estado del proceso'
    )
    # Datos del trabajo terminal
    titulo_trabajo = models.CharField(
        max_length=500, blank=True,
        verbose_name='Título del trabajo / proyecto'
    )
    nombre_empresa = models.CharField(
        max_length=300, blank=True,
        verbose_name='Empresa / Organización (para residencia)'
    )
    # Fotografía del alumno (digital)
    fotografia_digital = models.ImageField(
        upload_to='fotografias/%Y/',
        null=True, blank=True,
        verbose_name='Fotografía óvalo (digital)'
    )
    # Fotografía física (entrega independiente por departamento)
    foto_fisica_division = models.BooleanField(
        default=False,
        verbose_name='¿Foto física entregada en División?'
    )
    foto_fisica_escolares = models.BooleanField(
        default=False,
        verbose_name='¿Foto física entregada en Escolares?'
    )
    # Fechas clave
    fecha_apertura = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de apertura')
    fecha_ultima_actualizacion = models.DateTimeField(auto_now=True)
    fecha_conclusion = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de conclusión')
    # Observaciones generales de División de Estudios
    observaciones_division = models.TextField(
        blank=True,
        verbose_name='Observaciones de División de Estudios'
    )

    class Meta:
        verbose_name = 'Expediente de Titulación'
        verbose_name_plural = 'Expedientes de Titulación'
        ordering = ['-fecha_apertura']

    def __str__(self):
        return f'Expediente #{self.pk} — {self.alumno.get_full_name()}'

    def get_estado_display_color(self):
        colores = {
            EstadoExpediente.BORRADOR: 'secondary',
            EstadoExpediente.EN_REVISION_ACADEMICO: 'info',
            EstadoExpediente.RECHAZADO_ACADEMICO: 'danger',
            EstadoExpediente.EN_CORRECCION: 'warning',
            EstadoExpediente.DOCUMENTOS_PENDIENTES: 'warning',
            EstadoExpediente.EN_REVISION_DOCUMENTOS: 'info',
            EstadoExpediente.LISTO_INTEGRACION: 'primary',
            EstadoExpediente.INTEGRADO: 'primary',
            EstadoExpediente.ENVIADO_CDMX: 'info',
            EstadoExpediente.RECHAZADO_CDMX: 'danger',
            EstadoExpediente.APROBADO_CDMX: 'success',
            EstadoExpediente.EMPASTADO_PENDIENTE: 'warning',
            EstadoExpediente.EMPASTADO_RECIBIDO: 'success',
            EstadoExpediente.JURADO_ASIGNADO: 'primary',
            EstadoExpediente.ACTO_PROGRAMADO: 'primary',
            EstadoExpediente.CONCLUIDO: 'success',
            EstadoExpediente.CANCELADO: 'dark',
        }
        return colores.get(self.estado, 'secondary')

    def porcentaje_progreso(self):
        """Calcula el porcentaje de avance del proceso para la barra de progreso."""
        etapas = list(EstadoExpediente.values)
        etapas_lineales = [
            EstadoExpediente.BORRADOR,
            EstadoExpediente.EN_REVISION_ACADEMICO,
            EstadoExpediente.DOCUMENTOS_PENDIENTES,
            EstadoExpediente.EN_REVISION_DOCUMENTOS,
            EstadoExpediente.LISTO_INTEGRACION,
            EstadoExpediente.INTEGRADO,
            EstadoExpediente.ENVIADO_CDMX,
            EstadoExpediente.APROBADO_CDMX,
            EstadoExpediente.EMPASTADO_RECIBIDO,
            EstadoExpediente.JURADO_ASIGNADO,
            EstadoExpediente.ACTO_PROGRAMADO,
            EstadoExpediente.CONCLUIDO,
        ]
        if self.estado in etapas_lineales:
            idx = etapas_lineales.index(self.estado)
            return round((idx / (len(etapas_lineales) - 1)) * 100)
        return 0

    def documentos_aprobados(self):
        return self.documentos.filter(estado=EstadoDocumento.APROBADO).count()

    def documentos_total(self):
        return self.documentos.count()

    def documentos_pendientes(self):
        return self.documentos.exclude(estado=EstadoDocumento.APROBADO).count()

    def todos_documentos_aprobados(self):
        docs = self.documentos.all()
        if not docs.exists():
            return False
        return all(d.estado == EstadoDocumento.APROBADO for d in docs)

    @property
    def get_documento_fotografia(self):
        """Retorna el objeto documento que es de tipo fotografía."""
        return self.documentos.filter(tipo_documento__es_fotografia=True).first()


# ─────────────────────────────────────────────────────────────
# DOCUMENTOS
# ─────────────────────────────────────────────────────────────

def upload_documento_path(instance, filename):
    return (
        f'documentos/{instance.expediente.alumno.pk}/'
        f'{instance.tipo_documento.pk}/{filename}'
    )


class Documento(models.Model):
    """
    Documento individual dentro del expediente.
    Cada documento tiene su propio estado y puede ser validado por
    División de Estudios y Servicios Escolares de forma independiente.
    """
    expediente = models.ForeignKey(
        Expediente, on_delete=models.CASCADE,
        related_name='documentos',
        verbose_name='Expediente'
    )
    tipo_documento = models.ForeignKey(
        TipoDocumento, on_delete=models.PROTECT,
        verbose_name='Tipo de documento'
    )
    archivo = models.FileField(
        upload_to=upload_documento_path,
        null=True, blank=True,
        verbose_name='Archivo'
    )
    estado = models.CharField(
        max_length=25,
        choices=EstadoDocumento.choices,
        default=EstadoDocumento.PENDIENTE,
        verbose_name='Estado'
    )
    version = models.PositiveIntegerField(default=1, verbose_name='Versión')
    fecha_carga = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de carga')
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    notas_alumno = models.TextField(blank=True, verbose_name='Notas del alumno')

    class Meta:
        verbose_name = 'Documento'
        verbose_name_plural = 'Documentos'
        ordering = ['tipo_documento__orden']

    def __str__(self):
        return f'{self.tipo_documento.nombre} — {self.expediente.alumno.get_full_name()}'

    def get_estado_color(self):
        colores = {
            EstadoDocumento.PENDIENTE: 'secondary',
            EstadoDocumento.CARGADO: 'info',
            EstadoDocumento.EN_REVISION: 'warning',
            EstadoDocumento.APROBADO: 'success',
            EstadoDocumento.RECHAZADO: 'danger',
            EstadoDocumento.REQUIERE_CORRECCION: 'warning',
        }
        return colores.get(self.estado, 'secondary')

    def validacion_division(self):
        return self.validaciones.filter(departamento='DIVISION').first()

    def validacion_escolares(self):
        return self.validaciones.filter(departamento='ESCOLARES').first()

    def puede_escolares_validar(self):
        """
        Determina si Servicios Escolares puede validar este documento.
        Debe requerir validación de Escolares y, si requiere División, ésta debe estar APROBADA.
        """
        if not self.tipo_documento.valida_escolares:
            return False
            
        if self.tipo_documento.valida_division:
            val_div = self.validacion_division()
            if not val_div or val_div.estado != 'APROBADO':
                return False
        return True


class ValidacionDocumento(models.Model):
    """
    Registro de validación de un documento por un departamento.
    Se crea una instancia por departamento por documento.
    """
    DEPARTAMENTO_CHOICES = [
        ('DIVISION', 'División de Estudios Profesionales'),
        ('ESCOLARES', 'Servicios Escolares'),
    ]

    documento = models.ForeignKey(
        Documento, on_delete=models.CASCADE,
        related_name='validaciones',
        verbose_name='Documento'
    )
    departamento = models.CharField(
        max_length=15,
        choices=DEPARTAMENTO_CHOICES,
        verbose_name='Departamento validador'
    )
    estado = models.CharField(
        max_length=25,
        choices=EstadoValidacion.choices,
        default=EstadoValidacion.PENDIENTE,
        verbose_name='Estado de validación'
    )
    validado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='validaciones_realizadas',
        verbose_name='Validado por'
    )
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones / Motivo de rechazo'
    )
    fecha = models.DateTimeField(auto_now=True, verbose_name='Fecha de última acción')
    fecha_primera_revision = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Validación de Documento'
        verbose_name_plural = 'Validaciones de Documentos'
        unique_together = [['documento', 'departamento']]

    def __str__(self):
        return f'{self.get_departamento_display()} — {self.documento} — {self.get_estado_display()}'


# ─────────────────────────────────────────────────────────────
# ENVÍO A CDMX
# ─────────────────────────────────────────────────────────────

class EnvioCDMX(models.Model):
    """
    Registro del envío del expediente a CDMX para registro de título
    y expedición de cédula profesional electrónica.
    """
    ESTADO_CHOICES = [
        ('PREPARADO', 'Preparado para envío'),
        ('ENVIADO', 'Enviado a CDMX/TecNM'),
        ('EN_REVISION', 'En revisión en CDMX'),
        ('APROBADO', 'Aprobado por CDMX'),
        ('RECHAZADO', 'Rechazado por CDMX'),
    ]

    expediente = models.ForeignKey(
        Expediente, on_delete=models.CASCADE,
        related_name='envios_cdmx',
        verbose_name='Expediente'
    )
    numero_oficio = models.CharField(
        max_length=100, blank=True,
        verbose_name='Número de oficio de envío'
    )
    fecha_envio = models.DateField(null=True, blank=True, verbose_name='Fecha de envío')
    estado = models.CharField(
        max_length=15, choices=ESTADO_CHOICES,
        default='PREPARADO', verbose_name='Estado'
    )
    observaciones_envio = models.TextField(blank=True, verbose_name='Observaciones del envío')
    # Respuesta de CDMX
    fecha_respuesta = models.DateField(null=True, blank=True, verbose_name='Fecha de respuesta')
    observaciones_cdmx = models.TextField(
        blank=True,
        verbose_name='Observaciones de CDMX (en caso de rechazo)'
    )
    numero_registro_titulo = models.CharField(
        max_length=100, blank=True,
        verbose_name='Número de registro del título (si fue aprobado)'
    )
    # Auditoría
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='envios_cdmx_registrados',
        verbose_name='Registrado por'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Envío a CDMX'
        verbose_name_plural = 'Envíos a CDMX'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f'Envío CDMX — {self.expediente.alumno.get_full_name()} — {self.get_estado_display()}'


# ─────────────────────────────────────────────────────────────
# RECEPCIÓN DE EMPASTADO
# ─────────────────────────────────────────────────────────────

class RecepcionEmpastado(models.Model):
    """
    Registro de la recepción física del trabajo empastado por División de Estudios.
    El alumno entrega físicamente; el sistema registra la recepción.
    """
    expediente = models.OneToOneField(
        Expediente, on_delete=models.CASCADE,
        related_name='empastado',
        verbose_name='Expediente'
    )
    fecha_recepcion = models.DateField(verbose_name='Fecha de recepción')
    recibido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='empastados_recibidos',
        verbose_name='Recibido por'
    )
    estado = models.CharField(
        max_length=20,
        choices=[
            ('REVISADO', 'Revisado y Aceptado'),
            ('OBSERVACIONES', 'Con Observaciones'),
            ('RECHAZADO', 'Rechazado'),
        ],
        default='REVISADO',
        verbose_name='Estado de revisión física'
    )
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')

    class Meta:
        verbose_name = 'Recepción de Empastado'
        verbose_name_plural = 'Recepciones de Empastado'

    def __str__(self):
        return f'Empastado — {self.expediente.alumno.get_full_name()} — {self.fecha_recepcion}'


# ─────────────────────────────────────────────────────────────
# JURADO Y ACTO PROTOCOLARIO
# ─────────────────────────────────────────────────────────────

class AsignacionJurado(models.Model):
    """
    Oficio de asignación del jurado para el acto protocolario.
    Los miembros del jurado son instancias de Profesor (catálogo institucional).
    """
    from administracion.models import Profesor

    expediente = models.OneToOneField(
        Expediente, on_delete=models.CASCADE,
        related_name='jurado',
        verbose_name='Expediente'
    )
    # ── Miembros del jurado ──────────────────────────────────────
    presidente = models.ForeignKey(
        'administracion.Profesor',
        on_delete=models.PROTECT,
        related_name='jurado_presidente',
        verbose_name='Presidente del jurado'
    )
    secretario = models.ForeignKey(
        'administracion.Profesor',
        on_delete=models.PROTECT,
        related_name='jurado_secretario',
        verbose_name='Secretario/a del jurado'
    )
    vocal_propietario = models.ForeignKey(
        'administracion.Profesor',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='jurado_vocal_prop',
        verbose_name='Vocal Propietario/a'
    )
    vocal_suplente = models.ForeignKey(
        'administracion.Profesor',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='jurado_vocal_sup',
        verbose_name='Vocal Suplente'
    )
    # ── Datos del oficio ─────────────────────────────────────────
    numero_oficio = models.CharField(
        max_length=50, blank=True,
        verbose_name='Número de oficio',
        help_text='Ej: S.C./OPV/0099/2026'
    )
    fecha_oficio = models.DateField(
        null=True, blank=True,
        verbose_name='Fecha del oficio'
    )
    # ── Acto protocolario ────────────────────────────────────────
    fecha_acto = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Fecha y hora del acto protocolario'
    )
    lugar_acto = models.CharField(
        max_length=300, blank=True,
        verbose_name='Lugar del acto',
        help_text='Ej: SALA MAGNA (edificio T)'
    )
    # ── Auditoría ────────────────────────────────────────────────
    asignado_por = models.ForeignKey(
        'administracion.Usuario',
        on_delete=models.SET_NULL, null=True,
        related_name='jurados_asignados',
        verbose_name='Asignado por'
    )
    notas = models.TextField(blank=True, verbose_name='Notas adicionales')

    class Meta:
        verbose_name = 'Asignación de Jurado'
        verbose_name_plural = 'Asignaciones de Jurado'

    def __str__(self):
        return f'Jurado — {self.expediente.alumno.get_full_name()}'


class ActoProtocolario(models.Model):
    """
    Fecha y datos del acto protocolario / examen profesional.
    """
    RESULTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('APROBADO', 'Aprobado'),
        ('APROBADO_MENCION', 'Aprobado con Mención Honorífica'),
        ('SUSPENDIDO', 'Suspendido'),
        ('NO_PRESENTADO', 'No se presentó'),
    ]

    expediente = models.OneToOneField(
        Expediente, on_delete=models.CASCADE,
        related_name='acto_protocolario',
        verbose_name='Expediente'
    )
    jurado = models.ForeignKey(
        AsignacionJurado, on_delete=models.PROTECT,
        verbose_name='Jurado asignado'
    )
    fecha_acto = models.DateTimeField(verbose_name='Fecha y hora del acto')
    lugar = models.CharField(max_length=300, verbose_name='Lugar / Sala')
    resultado = models.CharField(
        max_length=20,
        choices=RESULTADO_CHOICES,
        default='PENDIENTE',
        verbose_name='Resultado'
    )
    calificacion = models.DecimalField(
        max_digits=4, decimal_places=2,
        null=True, blank=True,
        verbose_name='Calificación (si aplica)'
    )
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    programado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='actos_programados',
        verbose_name='Programado por'
    )

    class Meta:
        verbose_name = 'Acto Protocolario'
        verbose_name_plural = 'Actos Protocolarios'
        ordering = ['fecha_acto']

    def __str__(self):
        return f'Acto — {self.expediente.alumno.get_full_name()} — {self.fecha_acto}'


# ─────────────────────────────────────────────────────────────
# HISTORIAL (AUDITORÍA)
# ─────────────────────────────────────────────────────────────

class HistorialExpediente(models.Model):
    """
    Registro inmutable de todos los cambios de estado del expediente.
    Proporciona auditoría completa del proceso.
    """
    expediente = models.ForeignKey(
        Expediente, on_delete=models.CASCADE,
        related_name='historial',
        verbose_name='Expediente'
    )
    estado_anterior = models.CharField(max_length=40, blank=True, verbose_name='Estado anterior')
    estado_nuevo = models.CharField(max_length=40, verbose_name='Estado nuevo')
    realizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='cambios_realizados',
        verbose_name='Realizado por'
    )
    descripcion = models.TextField(verbose_name='Descripción del cambio')
    fecha = models.DateTimeField(auto_now_add=True, verbose_name='Fecha y hora')

    class Meta:
        verbose_name = 'Historial del Expediente'
        verbose_name_plural = 'Historial de Expedientes'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.expediente} → {self.estado_nuevo} ({self.fecha})'

    def get_estado_nuevo_display(self):
        return dict(EstadoExpediente.choices).get(self.estado_nuevo, self.estado_nuevo)

    def get_estado_anterior_display(self):
        return dict(EstadoExpediente.choices).get(self.estado_anterior, self.estado_anterior)

    def get_estado_nuevo_color(self):
        """Color for timeline badges."""
        colores = {
            'BORRADOR': 'secondary',
            'EN_REVISION_ACADEMICO': 'info',
            'RECHAZADO_ACADEMICO': 'danger',
            'EN_CORRECCION': 'warning',
            'DOCUMENTOS_PENDIENTES': 'warning',
            'EN_REVISION_DOCUMENTOS': 'info',
            'LISTO_INTEGRACION': 'primary',
            'INTEGRADO': 'primary',
            'ENVIADO_CDMX': 'info',
            'RECHAZADO_CDMX': 'danger',
            'APROBADO_CDMX': 'success',
            'EMPASTADO_PENDIENTE': 'warning',
            'EMPASTADO_RECIBIDO': 'success',
            'JURADO_ASIGNADO': 'primary',
            'ACTO_PROGRAMADO': 'primary',
            'CONCLUIDO': 'success',
            'CANCELADO': 'dark',
        }
        return colores.get(self.estado_nuevo, 'secondary')


class HistorialDocumento(models.Model):
    """Auditoría de cambios en documentos individuales."""
    documento = models.ForeignKey(
        Documento, on_delete=models.CASCADE,
        related_name='historial',
        verbose_name='Documento'
    )
    accion = models.CharField(max_length=100, verbose_name='Acción realizada')
    departamento = models.CharField(max_length=15, blank=True, verbose_name='Departamento')
    realizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='historial_documentos',
        verbose_name='Realizado por'
    )
    observaciones = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Historial de Documento'
        verbose_name_plural = 'Historial de Documentos'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.documento} — {self.accion}'
